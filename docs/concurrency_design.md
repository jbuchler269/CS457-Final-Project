# Concurrency Architecture & Thread Safety Design

## 1. Server Concurrency Model & Connection Lifecycle
For the **Cipher Clash** networked game server, we select **Option A: Multi-Threading (`threading.Thread`)** as the server concurrency architecture. 

### 1.1 Connection Lifecycle Mechanics
* **Listening & Acceptance**: The main server thread binds to the host and port, entering a non-blocking or blocking `accept()` loop to listen for incoming client socket connections[cite: 5].
* **Worker Thread Allocation**: Upon accepting a connection from a client, the server spawns an independent worker thread (`threading.Thread`) dedicated exclusively to servicing that client's connection socket. This ensures that processing delays or blocking I/O from one player do not freeze or starve the opposing player's connection.
* **Active Servicing Loop**: Once both players are connected, the worker threads execute a continuous receive loop using the 4-byte length-prefixed framing protocol (`recv_exact`) to parse incoming `MOVE` or `DISCONNECT` frames[cite: 3].
* **Socket Teardown & Cleanup**: Upon encountering a clean EOF (`0-byte` read), socket exceptions (`ConnectionResetError`), or an explicit `DISCONNECT` message, the server triggers session cleanup, notifies the remaining opponent via `GAME_OVER`, and closes the socket safely[cite: 3, 4].

---

## 2. Thread Safety, Lock Acquisition & State Isolation Strategy

Because multiple client worker threads operate concurrently, shared server-side resources are vulnerable to race conditions, data corruption, and out-of-order state mutations. 

### 2.1 Identified Shared Resources
* **Game Board Matrix / Cipher State**: The active puzzle grid or encrypted string being decrypted.
* **Active Turn State**: The string identifier indicating whose turn it is (`PLAYER_1` or `PLAYER_2`)[cite: 3, 4].
* **Connected Client Socket Registry**: Active socket references mapped to player IDs for message broadcasting.
* **Round Scores & Leaderboard Metrics**: Cumulative scores tracking match victory conditions[cite: 5].

### 2.2 Critical Section & Lock Acquisition Pattern
To prevent race conditions during turn evaluation and state mutation, all critical sections involving shared state modifications are protected using a master `threading.Lock` context manager (`with server_lock:`).

```python
import threading

class GameServerSession:
    def __init__(self):
        self.lock = threading.Lock()
        self.board = ["-"] * 9
        self.active_turn = "PLAYER_1"
        self.scores = {"PLAYER_1": 0, "PLAYER_2": 0}
        self.clients = {}

    def process_player_move(self, player_id, move_payload):
        with self.lock:  
            # Critical Section Start
            # 1. Enforce turn safety
            if self.active_turn != player_id:
                return {"status": "ERROR", "code": "OUT_OF_TURN"}
            
            # 2. Validate move legality and update board state
            row, col = move_payload["row"], move_payload["col"]
            idx = row * 3 + col
            if self.board[idx] != "-":
                return {"status": "ERROR", "code": "INVALID_CELL"}
            
            symbol = "X" if player_id == "PLAYER_1" else "O"
            self.board[idx] = symbol
            
            # 3. Switch active turn
            self.active_turn = "PLAYER_2" if self.active_turn == "PLAYER_1" else "PLAYER_1"
            
            return {
                "status": "SUCCESS",
                "board": list(self.board),
                "next_turn": self.active_turn
            }
        # Critical Section End (Lock automatically released)