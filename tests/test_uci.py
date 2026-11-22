import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path

import chess


class UciTests(unittest.TestCase):
    def setUp(self):
        self.engine = subprocess.Popen(
            [sys.executable, "-m", "uci"],
            cwd=Path(__file__).resolve().parents[1],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self.addCleanup(self.close_engine)
        self.lines = queue.Queue()

        def read_output():
            for line in self.engine.stdout:
                self.lines.put(line.rstrip())
            self.lines.put(None)

        self.reader = threading.Thread(target=read_output, daemon=True)
        self.reader.start()

    def close_engine(self):
        if self.engine.poll() is None:
            try:
                self.send("quit")
                self.engine.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.engine.kill()
                self.engine.wait()
        self.reader.join(timeout=5)
        for stream in (self.engine.stdin, self.engine.stdout, self.engine.stderr):
            stream.close()

    def send(self, command):
        self.engine.stdin.write(command + "\n")
        self.engine.stdin.flush()

    def receive(self):
        try:
            line = self.lines.get(timeout=5)
        except queue.Empty:
            self.fail("Timed out waiting for a UCI response")
        if line is None:
            self.fail(self.engine.stderr.read())
        return line

    def receive_best_move(self):
        line = self.receive()
        while line.startswith("info depth "):
            line = self.receive()
        return line

    def assert_best_move(self, board):
        line = self.receive_best_move()
        command, move = line.split()
        self.assertEqual(command, "bestmove")
        if board.legal_moves:
            self.assertIn(chess.Move.from_uci(move), board.legal_moves)
        else:
            self.assertEqual(move, "0000")

    def test_handshake_depth_and_terminal_position(self):
        self.send("uci")
        self.assertTrue(self.receive().startswith("id name "))
        self.assertTrue(self.receive().startswith("id author "))
        self.assertEqual(self.receive(), "uciok")
        self.send("ucinewgame")
        self.send("isready")
        self.assertEqual(self.receive(), "readyok")

        self.send("position startpos moves e2e4 e7e5")
        self.send("go depth 2")
        board = chess.Board()
        board.push_uci("e2e4")
        board.push_uci("e7e5")
        self.assert_best_move(board)

        fen = "8/8/8/8/8/6k1/5q2/7K b - - 0 1"
        self.send(f"position fen {fen}")
        self.send("go depth 1")
        board = chess.Board(fen)
        line = self.receive_best_move()
        command, move = line.split()
        self.assertEqual(command, "bestmove")
        board.push_uci(move)
        self.assertTrue(board.is_checkmate())

        mate_fen = board.fen()
        self.send(f"position fen {mate_fen}")
        self.send("go depth 2")
        self.assert_best_move(board)
        self.send("quit")
        self.assertEqual(self.engine.wait(timeout=5), 0)

    def test_stop_during_search_and_search_again(self):
        self.send("position startpos")
        self.send("go depth 20")
        self.assertTrue(self.receive().startswith("info depth 1 "))
        self.send("isready")
        line = self.receive()
        while line.startswith("info depth "):
            line = self.receive()
        self.assertEqual(line, "readyok")
        self.send("stop")
        self.assert_best_move(chess.Board())
        self.send("stop")
        self.send("go depth 1")
        self.assert_best_move(chess.Board())
        self.send("isready")
        self.assertEqual(self.receive(), "readyok")

    def test_automatic_draw_with_legal_moves_returns_null_move(self):
        self.send("position fen 4k3/8/8/8/3Q4/8/8/4K3 w - - 150 1")
        self.send("go depth 2")
        self.assertEqual(self.receive_best_move(), "bestmove 0000")

    def test_bad_position_is_atomic_and_diagnostics_stay_off_stdout(self):
        fen = "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"
        self.send(f"position fen {fen} moves e2e4")
        self.send("position startpos moves e2e4 e7e8")
        self.send("go depth 1")
        board = chess.Board(fen)
        board.push_uci("e2e4")
        self.assert_best_move(board)
        self.send("quit")
        self.assertEqual(self.engine.wait(timeout=5), 0)
        self.assertIn("Illegal move", self.engine.stderr.read())
