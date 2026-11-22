import unittest

from chess_engine.board_representation import ChessBoard
from chess_engine.fen_handling import InvalidFEN

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class PositionTests(unittest.TestCase):
    def test_black_fen_round_trip(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        board = ChessBoard(fen)
        self.assertFalse(board.white_to_move)
        self.assertEqual(board.to_fen(), fen)

    def test_make_and_undo_use_fixed_coordinates(self):
        board = ChessBoard(START)
        board.make_move("e2e4")
        after_white = board.to_fen()
        self.assertIn("e7e5", board.generate_legal_moves())
        board.make_move("e7e5")
        self.assertEqual(board.determine_piece_on_square(36), "p")
        self.assertEqual(board.to_fen().split()[1:], ["w", "KQkq", "e6", "0", "2"])
        board.undo_move()
        self.assertEqual(board.to_fen(), after_white)
        board.undo_move()
        self.assertEqual(board.to_fen(), START)

    def test_rejected_move_leaves_position_and_history_unchanged(self):
        board = ChessBoard(START)
        for move in ("e3e4", "e7e5", "e2e5", "e2e4q", "z2e4", "e2e4extra"):
            with self.subTest(move=move), self.assertRaises(ValueError):
                board.make_move(move)
        with self.assertRaises(IndexError):
            board.undo_move()
        self.assertEqual(board.to_fen(), START)

    def test_display_uses_fixed_orientation_and_piece_colours(self):
        board = ChessBoard(START)
        board.make_move("e2e4")
        rows = str(board).splitlines()
        self.assertEqual(rows[0].split(), list("♖♘♗♕♔♗♘♖"))
        self.assertEqual(rows[1].split(), ["♙"] * 8)
        self.assertEqual(rows[4].split()[4], "♟")
        self.assertEqual(rows[7].split(), list("♜♞♝♛♚♝♞♜"))

    def test_malformed_fen(self):
        for fen in (
            "8/8/8/8/8/8/8/9 w - - 0 1",
            "8/8/8/8/8/8/8/8 x - - 0 1",
            "8/8/8/8/8/8/8/8 w - a4 0 1",
        ):
            with self.subTest(fen=fen), self.assertRaises(InvalidFEN):
                ChessBoard(fen)

    def test_special_moves_restore_every_field(self):
        cases = (
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 7 9", "e1g1",
             "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 8 9"),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 9", "e5d6",
             "4k3/8/3P4/8/8/8/8/4K3 b - - 0 9"),
            ("1r2k3/P7/8/8/8/8/8/4K3 w - - 7 9", "a7b8n",
             "1N2k3/8/8/8/8/8/8/4K3 b - - 0 9"),
            ("r3k3/8/8/8/8/8/8/R3K3 b Qq - 7 9", "a8a1",
             "4k3/8/8/8/8/8/8/r3K3 w - - 0 10"),
        )
        for before, move, after in cases:
            with self.subTest(move=move):
                board = ChessBoard(before)
                self.assertIn(move, board.generate_legal_moves())
                board.make_move(move)
                self.assertEqual(board.to_fen(), after)
                board.undo_move()
                self.assertEqual(board.to_fen(), before)
