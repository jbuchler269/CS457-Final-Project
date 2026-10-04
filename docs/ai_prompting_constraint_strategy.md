# AI Prompting & Constraint Strategy

## 1. Strategy Overview
To prevent AI coding tools from generating unconstrained socket boilerplate or neglecting custom framing and state rules, all AI interactions are governed by System Prompts that enforce our exact protocol blueprint and FSM contract.

---

## 2. System Prompt Template (AI Constraint System)

```text
SYSTEM PROMPT: CUSTOM TCP PROTOCOL AND FSM CODE GENERATOR

You are an expert Python network programming assistant strictly constrained by our application protocol specification.

RULES & CONSTRAINTS:
1. TRANSPORT & FRAMING:
   - You MUST use length-prefixed framing with a 4-byte big-endian header (`!I` format via Python `struct`).
   - EVERY send operation MUST prepend this 4-byte header.
   - EVERY receive operation MUST use a two-phase `recv_exact(sock, n_bytes)` loop to read exactly 4 header bytes first, followed by payload bytes. Never use bare `sock.recv(1024)` calls directly for message deserialization.

2. EXCEPTION & DISCONNECT HANDLING:
   - Handle 0-byte `recv()` returns explicitly as clean EOF (`if not chunk: return None`).
   - Catch `ConnectionResetError`, `BrokenPipeError`, and `ConnectionAbruptlyClosedError` in receive loops and invoke the state machine disconnect trigger.

3. MESSAGE PARSING:
   - Payloads MUST be UTF-8 JSON matching our schema (`msg_type`, `player_id`, `payload`, `timestamp`).
   - Validate required keys; emit an `ERROR` message on invalid schemas without terminating the server.

4. FSM STATE RULES:
   - Only process `MOVE` commands when the current FSM state matches the turn of the sending `player_id`.
   - Reject out-of-turn moves with an `ERROR` payload.

Do not write generic TCP socket examples. Adhere strictly to these rules.
```

---

## 3. Sample Prompt Runs & Constrained Outputs

### Prompt 1: Framing Receiver Implementation
**Prompt Sent to AI:**
> "Generate a Python function `read_framed_message(sock)` that implements our 4-byte length-prefixed framing protocol. Strictly enforce handling TCP fragmentation and clean 0-byte EOF disconnects."

**Generated AI Code Verification:**
```python
import struct
import json

def recv_exact(sock, n_bytes):
    buf = bytearray()
    while len(buf) < n_bytes:
        chunk = sock.recv(n_bytes - len(buf))
        if not chunk:
            return None  # Handle 0-byte TCP EOF
        buf.extend(chunk)
    return bytes(buf)

def read_framed_message(sock):
    header_bytes = recv_exact(sock, 4)
    if not header_bytes:
        return None  # Client disconnected
    
    payload_len = struct.unpack("!I", header_bytes)[0]
    payload_bytes = recv_exact(sock, payload_len)
    if not payload_bytes:
        return None
        
    return json.loads(payload_bytes.decode("utf-8"))
```

### Prompt 2: FSM Invalid Move Guard
**Prompt Sent to AI:**
> "Write the server-side message dispatcher for `MOVE` events. Ensure that out-of-turn moves generate an `ERROR` message without crashing or transitioning states."

**Generated AI Code Verification:**
```python
def handle_move(server_fsm, player_id, payload, client_sock):
    if server_fsm.current_state != f"{player_id.upper()}_TURN":
        error_msg = {
            "msg_type": "ERROR",
            "player_id": "SERVER",
            "payload": {
                "error_code": "OUT_OF_TURN",
                "message": "Move received out of turn."
            },
            "timestamp": get_timestamp()
        }
        send_framed_message(client_sock, error_msg)
        return  # Maintain current state without crashing loop
    
    server_fsm.process_valid_move(player_id, payload)
```