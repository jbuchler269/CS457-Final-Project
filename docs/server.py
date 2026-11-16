#!/usr/env/python3
"""
CS 457 - Cipher Clash Game Server
Sprint 3: Socket Coding & Application Implementation (Exact SOW Ciphers)
"""

import argparse
import json
import socket
import sys
import threading

# Substitution Cipher Mapping Key (A-Z mapped to scrambled alphabet)
SUB_KEY = "QWERTYUIOPASDFGHJKLZXCVBNM"
NORM_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# SOW-compliant puzzle bank using the 3 required ciphers
PUZZLES = [
    {
        "plaintext": "COMPUTER NETWORKS",
        "cipher_type": "caesar",
        "hint": "Classic Caesar Cipher (Fixed Shift +3)",
    },
    {
        "plaintext": "SOCKET PROGRAMMING",
        "cipher_type": "atbash",
        "hint": "Atbash Cipher (Reverse Alphabet Substitution)",
    },
    {
        "plaintext": "CIPHER CLASH",
        "cipher_type": "substitution",
        "hint": "Monoalphabetic Substitution Cipher (QWERTY Key)",
    },
]


def encrypt_caesar(plaintext, shift=3):
  """Encrypts plaintext using Caesar Cipher with a fixed shift of 3."""
  ciphertext = ""
  for char in plaintext:
    if char.isalpha():
      code = ord(char)
      base = ord("A")
      encrypted_char = chr((code - base + shift) % 26 + base)
      ciphertext += encrypted_char
    else:
      ciphertext += char
  return ciphertext


def encrypt_atbash(plaintext):
  """Encrypts plaintext using Atbash Cipher (reverse alphabet)."""
  ciphertext = ""
  for char in plaintext:
    if char.isalpha():
      code = ord(char)
      base = ord("A")
      encrypted_char = chr(ord("Z") - (code - base))
      ciphertext += encrypted_char
    else:
      ciphertext += char
  return ciphertext


def encrypt_substitution(plaintext):
  """Encrypts plaintext using a Monoalphabetic Substitution cipher."""
  ciphertext = ""
  for char in plaintext:
    if char.isalpha():
      idx = NORM_ALPHABET.index(char)
      ciphertext += SUB_KEY[idx]
    else:
      ciphertext += char
  return ciphertext


def get_puzzle(round_index):
  """Retrieves the puzzle corresponding to the round index (modulo 3 for cycling)."""
  p_info = PUZZLES[round_index % len(PUZZLES)]
  plaintext = p_info["plaintext"]
  ctype = p_info["cipher_type"]

  if ctype == "caesar":
    ciphertext = encrypt_caesar(plaintext, shift=3)
  elif ctype == "atbash":
    ciphertext = encrypt_atbash(plaintext)
  else:
    ciphertext = encrypt_substitution(plaintext)

  return {
      "plaintext": plaintext,
      "ciphertext": ciphertext,
      "hint": p_info["hint"],
  }


class CipherGameSession:
  """Manages a 2-player Cipher Clash game session with thread safety and exact SOW ciphers."""

  def __init__(self, p1_conn, p1_addr, p2_conn, p2_addr):
    self.p1_conn = p1_conn
    self.p1_addr = p1_addr
    self.p2_conn = p2_conn
    self.p2_addr = p2_addr

    self.lock = threading.Lock()
    self.scores = {"PLAYER_1": 0, "PLAYER_2": 0}
    self.decrypted_count = {"PLAYER_1": 0, "PLAYER_2": 0}

    self.current_round = 0
    self.max_rounds = 3  # Matches the 3 SOW ciphers
    self.load_next_puzzle()

    self.active_turn = "PLAYER_1"
    self.game_active = True

  def load_next_puzzle(self):
    puzzle = get_puzzle(self.current_round)
    self.current_plaintext = puzzle["plaintext"]
    self.current_ciphertext = puzzle["ciphertext"]
    self.current_hint = puzzle["hint"]
    self.revealed_letters = set([" "])

  def get_masked_display(self):
    return "".join(
        c if c in self.revealed_letters else "_"
        for c in self.current_plaintext
    )

  def send_msg(self, conn, msg_dict):
    try:
      data = json.dumps(msg_dict) + "\n"
      conn.sendall(data.encode("utf-8"))
    except Exception as e:
      print(f"[ERROR] Failed to send message: {e}")

  def broadcast_state(self, message=""):
    masked = self.get_masked_display()
    state_payload = {
        "msg_type": "STATE_UPDATE",
        "ciphertext": self.current_ciphertext,
        "hint": self.current_hint,
        "masked_text": masked,
        "scores": self.scores,
        "active_turn": self.active_turn,
        "round": self.current_round + 1,
        "message": message,
    }

    p1_payload = dict(state_payload)
    p1_payload["your_turn"] = self.active_turn == "PLAYER_1"

    p2_payload = dict(state_payload)
    p2_payload["your_turn"] = self.active_turn == "PLAYER_2"

    self.send_msg(self.p1_conn, p1_payload)
    self.send_msg(self.p2_conn, p2_payload)

  def run_session(self):
    print(
        f"[INFO] Cipher Clash session started between {self.p1_addr} and"
        f" {self.p2_addr}"
    )

    self.send_msg(
        self.p1_conn,
        {
            "msg_type": "GAME_START",
            "player_id": "PLAYER_1",
            "message": "Connected as Player 1. Game starting!",
        },
    )
    self.send_msg(
        self.p2_conn,
        {
            "msg_type": "GAME_START",
            "player_id": "PLAYER_2",
            "message": "Connected as Player 2. Game starting!",
        },
    )

    self.broadcast_state(
        "Match started! Round 1: Caesar Cipher (Shift +3) begins."
    )

    while self.game_active:
      active_conn = (
          self.p1_conn if self.active_turn == "PLAYER_1" else self.p2_conn
      )

      buffer = ""
      msg = None
      while True:
        try:
          chunk = active_conn.recv(1024).decode("utf-8")
          if not chunk:
            break
          buffer += chunk
          if "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            msg = json.loads(line.strip())
            break
        except Exception:
          break

      if not msg:
        print(f"[INFO] {self.active_turn} disconnected.")
        break

      with self.lock:
        player_id = msg.get("player_id", self.active_turn)
        if player_id != self.active_turn:
          self.send_msg(
              active_conn,
              {"msg_type": "ERROR", "message": "Out of turn action."},
          )
          continue

        payload = msg.get("payload", {})
        action = payload.get("action")

        round_won = False
        action_msg = ""

        if action == "guess_letter":
          letter = payload.get("value", "").upper()
          if len(letter) != 1 or not letter.isalpha():
            action_msg = "Invalid letter guess. Must be a single alphabetic character."
          elif letter in self.revealed_letters:
            action_msg = f"Letter '{letter}' was already revealed."
          elif letter in self.current_plaintext:
            self.revealed_letters.add(letter)
            self.scores[player_id] += 2
            action_msg = f"Correct! Letter '{letter}' found (+2 pts)."

            if all(
                c in self.revealed_letters for c in self.current_plaintext
            ):
              round_won = True
              self.scores[player_id] += 5
              action_msg += f" Full phrase solved by letters! +5 bonus pts."
          else:
            action_msg = f"Incorrect guess. Letter '{letter}' not in message."
            self.active_turn = (
                "PLAYER_2" if self.active_turn == "PLAYER_1" else "PLAYER_1"
            )

        elif action == "guess_phrase":
          phrase = payload.get("value", "").strip().upper()
          if phrase == self.current_plaintext:
            self.scores[player_id] += 10
            round_won = True
            action_msg = f"Correct full decryption by {player_id}! +10 points."
          else:
            action_msg = (
                f"Incorrect full phrase decryption: '{phrase}'. Turn switches."
            )
            self.active_turn = (
                "PLAYER_2" if self.active_turn == "PLAYER_1" else "PLAYER_1"
            )
        else:
          action_msg = "Unknown action type."

        # Win condition evaluation
        match_won = False
        winner = None
        for pid in ["PLAYER_1", "PLAYER_2"]:
          if (
              self.scores[pid] >= 15
              or self.decrypted_count.get(pid, 0) >= 3
              or (round_won and self.current_round >= self.max_rounds - 1)
          ):
            match_won = True
            winner = pid
            break

        if round_won and not match_won:
          self.decrypted_count[player_id] += 1
          self.current_round += 1
          if self.current_round < self.max_rounds:
            self.load_next_puzzle()
            action_msg += f" Advancing to Round {self.current_round + 1}!"
          else:
            match_won = True
            winner = (
                "PLAYER_1"
                if self.scores["PLAYER_1"] >= self.scores["PLAYER_2"]
                else "PLAYER_2"
            )

        if match_won:
          game_over_payload = {
              "msg_type": "GAME_OVER",
              "winner": winner,
              "scores": self.scores,
              "message": f"Game Over! Winner is {winner} with final scores: {self.scores}",
          }
          self.send_msg(self.p1_conn, game_over_payload)
          self.send_msg(self.p2_conn, game_over_payload)
          self.game_active = False
          break
        else:
          self.broadcast_state(action_msg)

    try:
      self.p1_conn.close()
      self.p2_conn.close()
    except Exception:
      pass
    print("[INFO] Game session ended.")


class Server:

  def __init__(self, port):
    self.port = port
    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self.waiting_player = None

  def start(self):
    try:
      self.server_socket.bind(("0.0.0.0", self.port))
      self.server_socket.listen(5)
      print(
          f"[INFO] Cipher Clash Server listening on 0.0.0.0:{self.port}..."
      )
    except Exception as e:
      print(f"[ERROR] Failed to bind server to port {self.port}: {e}")
      sys.exit(1)

    try:
      while True:
        conn, addr = self.server_socket.accept()
        print(f"[INFO] Connection accepted from {addr}")

        buffer = ""
        connect_msg = None
        try:
          while True:
            chunk = conn.recv(1024).decode("utf-8")
            if not chunk:
              break
            buffer += chunk
            if "\n" in buffer:
              line, buffer = buffer.split("\n", 1)
              connect_msg = json.loads(line.strip())
              break
        except Exception:
          pass

        if not connect_msg or connect_msg.get("msg_type") != "CONNECT":
          conn.sendall(
              json.dumps(
                  {"msg_type": "ERROR", "message": "Expected CONNECT message"}
              ).encode("utf-8")
              + b"\n"
          )
          conn.close()
          continue

        if self.waiting_player is None:
          self.waiting_player = (conn, addr)
          print("[INFO] Player 1 connected. Waiting for Player 2...")
          conn.sendall(
              json.dumps({
                  "msg_type": "LOBBY_WAIT",
                  "message": "Waiting for opponent to connect...",
              }).encode("utf-8")
              + b"\n"
          )
        else:
          p1_conn, p1_addr = self.waiting_player
          p2_conn, p2_addr = conn, addr
          self.waiting_player = None

          session = CipherGameSession(p1_conn, p1_addr, p2_conn, p2_addr)
          t = threading.Thread(target=session.run_session)
          t.daemon = True
          t.start()
    except KeyboardInterrupt:
      print("\n[INFO] Server shutting down gracefully.")
    finally:
      self.server_socket.close()


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
      description="Cipher Clash Game Server (CS 457)",
      formatter_class=argparse.RawTextHelpFormatter,
  )
  parser.add_argument(
      "-p",
      "--port",
      required=True,
      type=validate_port,
      help="Listening port (required, 1024-65535). Binds to 0.0.0.0.",
  )
  args = parser.parse_args()
  server = Server(args.port)
  server.start()


if __name__ == "__main__":
  main()