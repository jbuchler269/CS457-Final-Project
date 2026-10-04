Server Game Finite State Machine (FSM) Specification
1. Overview
The server state engine governs player session lifetimes, game setup, turn control, move validation, error handling, and state transitions during orderly and abrupt client departures.
2. Mermaid FSM Diagram (stateDiagram-v2)
stateDiagram-v2
    [*] --> INIT

    INIT --> WAITING_FOR_PLAYERS : Server Start / Listen
    
    state WAITING_FOR_PLAYERS {
        [*] --> P1_WAITING
        P1_WAITING --> P2_CONNECTED : Connect(P1) / Send LOBBY_WAIT
        P2_CONNECTED --> MATCH_READY : Connect(P2)
    }

    WAITING_FOR_PLAYERS --> GAME_START : Both Players Connected
    WAITING_FOR_PLAYERS --> CLEANUP : P1 Disconnect / Reset Lobby

    GAME_START --> PLAYER_1_TURN : Assign Roles & Broadcast GAME_START

    state IN_GAME {
        PLAYER_1_TURN --> EVALUATE_MOVE : Submit MOVE (P1)
        PLAYER_2_TURN --> EVALUATE_MOVE : Submit MOVE (P2)

        EVALUATE_MOVE --> PLAYER_2_TURN : Valid Move / Turn Switch (P2 Next)
        EVALUATE_MOVE --> PLAYER_1_TURN : Valid Move / Turn Switch (P1 Next)

        EVALUATE_MOVE --> PLAYER_1_TURN : Invalid Move or Out-of-Turn / Send ERROR (P1)
        EVALUATE_MOVE --> PLAYER_2_TURN : Invalid Move or Out-of-Turn / Send ERROR (P2)
    }

    IN_GAME --> GAME_OVER : Win / Loss / Draw Condition
    IN_GAME --> GAME_OVER : Disconnect / Opponent Forfeit Win

    GAME_OVER --> CLEANUP : Broadcast GAME_OVER to Active Clients

    CLEANUP --> WAITING_FOR_PLAYERS : Reclaim Resources & Reset State
    CLEANUP --> [*] : Server Shutdown


3. Detailed State & Transition Specification
3.1 INIT
Description: Server initializes networking socket, binds host/port, and enters non-blocking or multi-threaded listen loop.
Transitions: Moves to WAITING_FOR_PLAYERS upon successful socket binding.
3.2 WAITING_FOR_PLAYERS
Description: Server listens for client connections.
P1 Connect: Assigns role PLAYER_1, sends LOBBY_WAIT.
P2 Connect: Assigns role PLAYER_2.
Transitions:
Moves to GAME_START when 2 valid clients connect.
Moves to CLEANUP if PLAYER_1 disconnects while waiting.
3.3 GAME_START
Description: Game engine constructs a fresh board matrix, sets active_turn = PLAYER_1, and broadcasts GAME_START containing assigned symbols (X for P1, O for P2).
Transitions: Automatically transitions into PLAYER_1_TURN.
3.4 IN_GAME (PLAYER_1_TURN / PLAYER_2_TURN / EVALUATE_MOVE)
Description:
Active player submits a MOVE frame.
EVALUATE_MOVE verifies:
Turn Identity: Is msg.player_id == active_turn?
Coordinate Bounds: Are row and col within allowable grid dimensions?
Cell Availability: Is target square unconsumed?
Edge Case Handling:
Out-of-Turn or Invalid Payload: State machine remains in current player turn, emits an ERROR frame back to the offending client, and waits for a corrected move.
Client Disconnect / Socket Failure: Immediately triggers transition to GAME_OVER with reason = FORFEIT_DISCONNECT.
3.5 GAME_OVER
Description: Halts turn state engine. Determines final state payload (Win, Draw, or Forfeit) and emits GAME_OVER to all reachable client sockets.
Transitions: Unconditionally transitions to CLEANUP.
3.6 CLEANUP
Description: Closes disconnected client sockets, releases game session buffers, resets internal state registers, and prepares the room context for new incoming connections.
Transitions: Transitions to WAITING_FOR_PLAYERS.
