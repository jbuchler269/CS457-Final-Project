# Application Protocol Blueprint

## 1. Overview & Objectives
This document specifies the custom application-layer protocol for the networked 2-player turn-based game engine. The protocol operates on top of TCP and provides deterministic framing, structured message parsing, and explicit connection lifecycle management.

---

## 2. Transport Layer & Framing Mechanism

### 2.1 Protocol Choice: Length-Prefixed Framing (Fixed-Width Binary Header)
TCP is a continuous, unstructured byte stream. To guarantee message boundary isolation against TCP coalescing (multiple messages arriving in a single `recv()` call) and fragmentation (a single message split across multiple `recv()` calls), this application uses **Option B: Length-Prefixed Framing**.

* **Header Format**: 4-byte unsigned integer in **Network Byte Order (Big-Endian)** (`!I` in Python struct format).
* **Payload Format**: UTF-8 encoded JSON string.
* **Maximum Payload Size**: $16\,\text{MB}$ ($16,777,216$ bytes).

### 2.2 Wire Stream Binary Representation
Every transmission consists of exactly $[4\text{ Bytes Length}] + [N\text{ Bytes Payload}]$.

#### On-the-Wire Example (Two Coalesced Back-to-Back Messages)
Suppose a client sends a `CONNECT` message followed immediately by a `MOVE` message:

```
[0x00, 0x00, 0x00, 0x45] + {"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}
[0x00, 0x00, 0x00, 0x5C] + {"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}
```

* **Header 1**: `0x00000045` (69 bytes length prefix).
* **Payload 1**: 69-byte JSON string representing `CONNECT`.
* **Header 2**: `0x0000005C` (92 bytes length prefix).
* **Payload 2**: 92-byte JSON string representing `MOVE`.

### 2.3 Receiver Stream Parsing Logic Algorithm
The receiver MUST maintain an accumulation stream buffer and extract messages using a strict two-phase loop:

1. **Header Phase**: Read exactly 4 bytes to determine payload length $N$.
2. **Payload Phase**: Read exactly $N$ bytes from the socket stream before deserializing JSON.

```python
import struct
import json

def recv_exact(sock, n_bytes):
    """
    Reads exactly n_bytes from socket stream.
    Handles TCP fragmentation by looping until buffer is full.
    Returns None on EOF (0-byte read).
    """
    buf = bytearray()
    while len(buf) < n_bytes:
        chunk = sock.recv(n_bytes - len(buf))
        if not chunk:
            return None  # Connection closed cleanly (EOF)
        buf.extend(chunk)
    return bytes(buf)

def receive_message(sock):
    """
    Extracts a single framing-compliant message from the TCP socket.
    """
    header_bytes = recv_exact(sock, 4)
    if not header_bytes:
        return None  # EOF / Disconnect
    
    payload_len = struct.unpack("!I", header_bytes)[0]
    payload_bytes = recv_exact(sock, payload_len)
    if not payload_bytes:
        return None  # EOF during payload read
        
    return json.loads(payload_bytes.decode("utf-8"))
```

---

## 3. Application Message Schemas

All messages follow a base JSON object structure containing `msg_type`, `player_id`, `payload`, and `timestamp`.

### 3.1 `CONNECT` (Client $\rightarrow$ Server)
Client requests entry into the server game lobby.

```json
{
  "msg_type": "CONNECT",
  "player_id": "Alice",
  "payload": {},
  "timestamp": 1727000000
}
```

### 3.2 `LOBBY_WAIT` (Server $\rightarrow$ Client)
Server notifies Client 1 that it is queued in the lobby waiting for an opponent.

```json
{
  "msg_type": "LOBBY_WAIT",
  "player_id": "SERVER",
  "payload": {
    "message": "Waiting for Player 2 to join..."
  },
  "timestamp": 1727000001
}
```

### 3.3 `GAME_START` (Server $\rightarrow$ Clients)
Server notifies both connected clients that a match has started, assigning roles.

```json
{
  "msg_type": "GAME_START",
  "player_id": "SERVER",
  "payload": {
    "assigned_role": "PLAYER_1",
    "symbol": "X",
    "opponent_id": "Bob",
    "active_turn": "PLAYER_1"
  },
  "timestamp": 1727000002
}
```

### 3.4 `MOVE` (Client $\rightarrow$ Server)
Active player submits board coordinates or game action.

```json
{
  "msg_type": "MOVE",
  "player_id": "Alice",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000005
}
```

### 3.5 `STATE_UPDATE` (Server $\rightarrow$ Clients)
Broadcast from server containing current board state, turn status, and updated metrics.

```json
{
  "msg_type": "STATE_UPDATE",
  "player_id": "SERVER",
  "payload": {
    "board": ["X", "-", "-", "-", "O", "-", "-", "-", "-"],
    "next_turn": "Bob",
    "last_move": {"player": "Alice", "row": 0, "col": 0}
  },
  "timestamp": 1727000006
}
```

### 3.6 `ERROR` (Server $\rightarrow$ Client)
Server sends an error notification for invalid/out-of-turn moves or schema violations without closing the connection.

```json
{
  "msg_type": "ERROR",
  "player_id": "SERVER",
  "payload": {
    "error_code": "OUT_OF_TURN",
    "message": "It is not your turn to move."
  },
  "timestamp": 1727000007
}
```

### 3.7 `DISCONNECT` (Client $\rightarrow$ Server)
Graceful client exit notification.

```json
{
  "msg_type": "DISCONNECT",
  "player_id": "Alice",
  "payload": {
    "reason": "USER_QUIT"
  },
  "timestamp": 1727000010
}
```

### 3.8 `GAME_OVER` (Server $\rightarrow$ Clients)
Server broadcasts final match outcome (Win, Draw, Forfeit).

```json
{
  "msg_type": "GAME_OVER",
  "player_id": "SERVER",
  "payload": {
    "winner": "Bob",
    "reason": "FORFEIT_DISCONNECT",
    "final_board": ["X", "-", "-", "-", "O", "-", "-", "-", "-"]
  },
  "timestamp": 1727000011
}
```

---

## 4. Connection Termination & Socket Lifecycle Management

### 4.1 Graceful Disconnection (Application-Layer)
1. Client sends a `DISCONNECT` message to the server.
2. Server logs the intent, triggers an internal forfeit/cleanup event, sends a `GAME_OVER` to the remaining opponent, and closes the TCP socket via `sock.close()`.

### 4.2 Transport-Layer Teardown & 0-Byte EOF Handling
When a peer closes its socket cleanly (calls `close()`), POSIX TCP implementation sends a `FIN` packet. 
* **The 0-Byte EOF Rule**: Calling `recv()` on a closed socket does not raise an exception; it immediately returns `b""` (0 bytes).
* **Infinite Loop Mitigation**: Receive loops must explicitly test for empty returns (`if not data: break`). Failure to check causes 100% CPU usage in an unblocked infinite loop.

### 4.3 Abrupt Disconnection & Socket Exception Handling
In network drops, process crashes (`kill -9`), or physical link disconnects:
* **TCP Reset (RST)**: Subsequent reads/writes raise `ConnectionResetError`.
* **Broken Pipe**: Writing to a peer that closed its socket raises `BrokenPipeError`.

#### Robust Receiver Exception Handler Pattern
```python
try:
    message = receive_message(client_socket)
    if message is None:
        # Detected clean TCP FIN closure (EOF)
        handle_disconnect(player_id, reason="CLEAN_EOF")
    else:
        process_message(message)
except (ConnectionResetError, ConnectionAbruptlyClosedError):
    handle_disconnect(player_id, reason="ABRUPT_RESET")
except BrokenPipeError:
    handle_disconnect(player_id, reason="BROKEN_PIPE")
except Exception as e:
    logger.error(f"Unexpected socket error on player {player_id}: {e}")
    handle_disconnect(player_id, reason="UNKNOWN_ERROR")
```