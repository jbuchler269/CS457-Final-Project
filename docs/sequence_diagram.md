# State & Score Broadcast Sequence Diagram

## 1. Overview & Narrative Flow
This document provides the official Mermaid sequence diagram illustrating the complete round-trip message flow for **Cipher Clash**. It models client move submissions, server authority validation under thread lock protection, branching logic for invalid or out-of-turn moves, and synchronous state/score broadcasts to all connected clients.

---

## 2. Mermaid Sequence Diagram (`sequenceDiagram`)

```mermaid
sequenceDiagram
    autonumber
    actor Client1 as Client 1 (Player 1 / X)
    participant Server as Game Server (Thread-Safe FSM)
    actor Client2 as Client 2 (Player 2 / O)

    Client1->>Server: MOVE (row: 0, col: 2)
    Note over Server: Acquire server_lock<br>Validate: Is it Client 1's turn?<br>Is cell (0,2) empty?
    
    alt Valid Move
        Note over Server: Update Game Board State<br>Switch Active Turn to Player 2<br>Release server_lock
        Server-->>Client1: STATE_UPDATE (Board, Turn: Player 2)
        Server-->>Client2: STATE_UPDATE (Board, Turn: Player 2)
    else Invalid Move or Out of Turn
        Note over Server: Release server_lock
        Server-->>Client1: ERROR ("OUT_OF_TURN" or "INVALID_CELL")
    end

    Note over Server, Client2: Round Completion & Score Synchronization
    alt Round Win / Completion Detected
        Note over Server: Update Round Scores & Leaderboard
        Server-->>Client1: GAME_OVER (Winner, Final Scores)
        Server-->>Client2: GAME_OVER (Winner, Final Scores)
    end
