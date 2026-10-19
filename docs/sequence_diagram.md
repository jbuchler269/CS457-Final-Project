# State & Score Broadcast Sequence Diagram

## 1. Overview & Narrative Flow
This document provides the official Mermaid sequence diagram illustrating the complete round-trip message flow for **Cipher Clash**. It models client move submissions, server authority validation under thread lock protection, branching logic for invalid or out-of-turn moves, and synchronous state/score broadcasts to all connected clients.

---

## 2. Mermaid Sequence Diagram (`sequenceDiagram`)

```mermaid
sequenceDiagram
    autonumber
    actor clientOne as Client 1 (Player X)
    participant Server as Game Server
    actor clientTwo as Client 2 (Player O)

    clientOne->>Server: MOVE (row: 0, col: 2)
    Note over Server: Acquire server_lock<br/>Validate turn & cell availability
    
    alt Valid Move
        Note over Server: Update Board State<br/>Switch Turn to Player O<br/>Release lock
        Server-->>clientOne: STATE_UPDATE (Board, Turn: Player O)
        Server-->>clientTwo: STATE_UPDATE (Board, Turn: Player O)
    else Invalid Move or Out of Turn
        Note over Server: Release lock
        Server-->>clientOne: ERROR ("OUT_OF_TURN" or "INVALID_CELL")
    end

    Note over Server: Round Completion Check
    alt Round Win / Completion Detected
        Note over Server: Update Scores & Leaderboard
        Server-->>clientOne: GAME_OVER (Winner, Final Scores)
        Server-->>clientTwo: GAME_OVER (Winner, Final Scores)
    end
