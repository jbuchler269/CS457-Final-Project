#!/usr/bin/env python3
"""
CS 457 - Cipher Clash Game Client
Sprint 3: Socket Coding & Application Implementation
"""

import argparse
import json
import socket
import sys


def render_game_screen(state):
  print("\n" + "=" * 60)
  print(f"             CIPHER CLASH — ROUND {state.get('round', 1)}")
  print("=" * 60)
  print(f"Hint / Cipher Type   : {state.get('hint', '')}")
  print(f"Encrypted Ciphertext : {state.get('ciphertext', '')}")
  print(f"Masked Progress      : {state.get('masked_text', '')}")
  print("-" * 60)
  scores = state.get("scores", {})
  print(
      f"Scores -> Player 1: {scores.get('PLAYER_1', 0)} pts | Player 2:"
      f" {scores.get('PLAYER_2', 0)} pts"
  )
  print("=" * 60)
  print(f"[STATUS] {state.get('message', '')}\n")


def receive_message(sock):
  buffer = ""
  while True:
    try:
      chunk = sock.recv(1024).decode("utf-8")
      if not chunk:
        return None
      buffer += chunk
      if "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        return json.loads(line.strip())
    except Exception:
      return None


def send_message(sock, msg_dict):
  try:
    data = json.dumps(msg_dict) + "\n"
    sock.sendall(data.encode("utf-8"))
  except Exception as e:
    print(f"[ERROR] Failed to send message: {e}")


def validate_port(value):
  try:
    ivalue = int(value)
  except ValueError:
    raise argparse.ArgumentTypeError(f"Invalid port: '{value}'")
  if not (1024 <= ivalue <= 65535):
    raise argparse.ArgumentTypeError(
        f"Port {ivalue} out of range (1024-65535)."
    )
  return ivalue


def main():
  parser = argparse.ArgumentParser(
      description="Cipher Clash Game Client (CS 457)",
      formatter_class=argparse.RawTextHelpFormatter,
  )
  parser.add_argument(
      "-i",
      "--hostname",
      required=True,
      help="Server DNS hostname or IP address (required).",
  )
  parser.add_argument(
      "-p",
      "--port",
      required=True,
      type=validate_port,
      help="Server port (required, 1024-65535).",
  )
  args = parser.parse_args()

  # Mandatory DNS Resolution Exception Handling (SOW Section 2.2)
  print(f"[INFO] Resolving server hostname '{args.hostname}'...")
  try:
    server_ip = socket.gethostbyname(args.hostname)
    print(f"[INFO] Resolved '{args.hostname}' to IP: {server_ip}")
  except socket.gaierror as e:
    print(f"[ERROR] Unable to resolve DNS hostname '{args.hostname}'.")
    print(
        "Please check your Cisco router DNS configuration ('ip dns server' /"
        " 'ip host') or verify domain spelling."
    )
    sys.exit(1)

  client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  print(f"[INFO] Connecting to server at {server_ip}:{args.port}...")
  try:
    client_socket.connect((server_ip, args.port))
  except Exception as e:
    print(f"[ERROR] Failed to connect to server: {e}")
    sys.exit(1)

  # Send CONNECT message
  send_message(client_socket, {"msg_type": "CONNECT", "client_version": "1.0"})

  player_id = None

  try:
    while True:
      msg = receive_message(client_socket)
      if not msg:
        print("[INFO] Connection closed by server.")
        break

      msg_type = msg.get("msg_type")

      if msg_type == "LOBBY_WAIT":
        print(f"\n[LOBBY] {msg.get('message')}")
        continue

      if msg_type == "GAME_START":
        player_id = msg.get("player_id")
        print(f"\n[INFO] {msg.get('message')} Assigned role: {player_id}")
        continue

      if msg_type == "STATE_UPDATE":
        render_game_screen(msg)

        if msg.get("your_turn"):
          print("Your turn! Choose your action:")
          print("  [1] Guess a single letter")
          print("  [2] Attempt full phrase decryption")
          choice = input("Enter choice (1 or 2): ").strip()

          if choice == "1":
            letter = input("Enter a single letter to guess: ").strip().upper()
            send_message(
                client_socket,
                {
                    "msg_type": "MOVE",
                    "player_id": player_id,
                    "payload": {"action": "guess_letter", "value": letter},
                },
            )
          elif choice == "2":
            phrase = (
                input("Enter the full decrypted plaintext phrase: ")
                .strip()
                .upper()
            )
            send_message(
                client_socket,
                {
                    "msg_type": "MOVE",
                    "player_id": player_id,
                    "payload": {"action": "guess_phrase", "value": phrase},
                },
            )
          else:
            print("[ERROR] Invalid selection. Sending null action.")
            send_message(
                client_socket,
                {
                    "msg_type": "MOVE",
                    "player_id": player_id,
                    "payload": {"action": "invalid", "value": ""},
                },
            )
        else:
          print("[WAIT] Waiting for opponent's turn...")

      if msg_type == "GAME_OVER":
        print("\n" + "=" * 60)
        print("                 GAME OVER - MATCH FINISHED                 ")
        print("=" * 60)
        print(f"Winner: {msg.get('winner')}")
        print(f"Final Scores: {msg.get('scores')}")
        print(f"Summary: {msg.get('message')}")
        print("=" * 60)
        break

  except KeyboardInterrupt:
    print("\n[INFO] Client disconnected by user.")
  finally:
    client_socket.close()


if __name__ == "__main__":
  main()