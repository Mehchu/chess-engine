import queue
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

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

    def test_movetime_returns_legal_move_without_stop(self):
        self.send("isready")
        self.assertEqual(self.receive(), "readyok")
        for milliseconds in (0, 35):
            with self.subTest(milliseconds=milliseconds):
                started = monotonic()
                self.send(f"go movetime {milliseconds}")
                self.assert_best_move(chess.Board())
                self.assertLess(monotonic() - started, 1.5)
                self.send("isready")
                self.assertEqual(self.receive(), "readyok")

    def test_clocked_search_uses_the_active_side_and_can_be_stopped(self):
        self.send("position startpos moves e2e4")
        board = chess.Board()
        board.push_uci("e2e4")

        self.send("go wtime 60000 btime 0 winc 4000 binc 1000 movestogo 8")
        self.assert_best_move(board)

        self.send("go wtime 0 btime 60000 winc 0 binc 2000 movestogo 10")
        self.assertTrue(self.receive().startswith("info depth 1 "))
        self.send("isready")
        line = self.receive()
        while line.startswith("info depth "):
            line = self.receive()
        self.assertEqual(line, "readyok")
        self.send("stop")
        self.assert_best_move(board)

    def test_depth_and_time_limits_can_be_combined(self):
        self.send("go depth 1 movetime 5000")
        self.assertTrue(self.receive().startswith("info depth 1 "))
        self.assertTrue(self.receive().startswith("bestmove "))

    def test_complete_history_is_used_for_repetition(self):
        cycle = "g1f3 g8f6 f3g1 f6g8".split()
        history = cycle * 4
        self.send("position startpos moves " + " ".join(history))
        self.send("go depth 2")
        self.assertEqual(self.receive(), "info depth 0 score cp 0 nodes 0")
        board = chess.Board()
        for move in history:
            board.push_uci(move)
        self.assertTrue(board.is_fivefold_repetition())
        self.assert_best_move(board)

    def test_fen_history_replays_special_move_notation(self):
        cases = (
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1 e8c8"),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6 e8d7"),
            ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8n"),
        )
        for fen, history in cases:
            with self.subTest(history=history):
                self.send(f"position fen {fen} moves {history}")
                self.send("go depth 1")
                board = chess.Board(fen)
                for move in history.split():
                    board.push_uci(move)
                self.assert_best_move(board)

    def test_automatic_draw_with_legal_moves_returns_a_legal_move(self):
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 150 1"
        self.send(f"position fen {fen}")
        self.send("go depth 2")
        self.assert_best_move(chess.Board(fen))

    def test_infinite_analysis_stops_with_one_legal_move(self):
        self.send("go infinite")
        self.assertTrue(self.receive().startswith("info depth 1 "))
        self.send("stop")
        self.assert_best_move(chess.Board())
        self.send("isready")
        self.assertEqual(self.receive(), "readyok")

    def test_node_limit_returns_legal_fallback(self):
        self.send("go nodes 1")
        self.assert_best_move(chess.Board())

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


class TimeBudgetTests(unittest.TestCase):
    def test_invalid_limits_are_rejected(self):
        from chess_engine.uci import _parse_go, _time_budget_ms

        for args in (["wtime"], ["depth", "0"], ["movetime", "-1"],
                     ["movestogo", "0"], ["depth", "1", "depth", "2"],
                     ["nodes", "0"], ["infinite", "depth", "1"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                _parse_go(args)
        with self.assertRaisesRegex(ValueError, "Missing btime"):
            _time_budget_ms({"wtime": 1000}, False)

    def test_clock_allocation_and_cap(self):
        from chess_engine.uci import _time_budget_ms

        clocks = {"wtime": 9000, "btime": 1000, "winc": 400, "binc": 200}
        self.assertEqual(_time_budget_ms(clocks, True), 600)
        self.assertEqual(_time_budget_ms(clocks, False), 183)
        self.assertEqual(_time_budget_ms({**clocks, "movestogo": 1}, False), 950)
        self.assertEqual(_time_budget_ms({**clocks, "movetime": 10}, False), 10)
        self.assertIsNone(_time_budget_ms({"depth": 4}, True))


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux engine launcher")
class LinuxLauncherTests(unittest.TestCase):
    def test_launches_from_another_working_directory(self):
        launcher = Path(__file__).resolve().parents[1] / "bin" / "chess-engine-uci.sh"
        with TemporaryDirectory() as working_dir:
            result = subprocess.run(
                [launcher], cwd=working_dir, input="uci\nisready\nquit\n",
                text=True, capture_output=True, check=True, timeout=5,
            )
        self.assertEqual(result.stdout.splitlines()[-2:], ["uciok", "readyok"])
        self.assertEqual(result.stderr, "")
