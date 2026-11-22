import unittest
from unittest.mock import patch

from chess_engine.board_representation import ChessBoard
from chess_engine.search_algorithms import TranspositionTable, ZobristHash, negamax_alpha_beta_top
from tests.test_position import START


class ZobristTests(unittest.TestCase):
    def test_position_fields_change_the_key(self):
        fen = "r3k2r/8/8/8/4P3/8/8/R3K2R b KQkq e3 0 1"
        hasher = ZobristHash()
        original = hasher.generate_key(ChessBoard(fen))
        self.assertEqual(original, ZobristHash().generate_key(ChessBoard(fen)))
        for changed in (
            fen.replace(" b KQkq e3 ", " w KQkq - "),
            fen.replace(" e3 ", " - "),
            fen.replace(" e3 ", " d3 "),
            fen.replace("KQkq", "KQk"),
            fen.replace("4P3", "4p3"),
            fen.replace("4P3", "4N3"),
            fen.replace("4P3", "3P4"),
        ):
            with self.subTest(fen=changed):
                self.assertNotEqual(original, hasher.generate_key(ChessBoard(changed)))

        without_ep = fen.replace(" e3 ", " - ")
        white = without_ep.replace(" b ", " w ")
        self.assertNotEqual(hasher.generate_key(ChessBoard(without_ep)),
                            hasher.generate_key(ChessBoard(white)))

    def test_make_and_undo_restore_key(self):
        hasher = ZobristHash()
        for fen, move in (
            (START, "e2e4"),
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "e1g1"),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "e5d6"),
            ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7b8n"),
        ):
            with self.subTest(move=move):
                board = ChessBoard(fen)
                key = hasher.generate_key(board)
                board.make_move(move)
                self.assertNotEqual(hasher.generate_key(board), key)
                board.undo_move()
                self.assertEqual(hasher.generate_key(board), key)


class TranspositionTests(unittest.TestCase):
    def test_cached_search_agrees_with_uncached(self):
        for fen, depth in (
            (START, 3),
            ("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1", 3),
            ("4k3/8/8/3r4/3Q4/8/8/4K3 b - - 0 1", 2),
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                expected = negamax_alpha_beta_top(board, depth)
                table = TranspositionTable()
                self.assertEqual(negamax_alpha_beta_top(board, depth, table=table), expected)
                with patch.object(board, "_legal_moves", side_effect=AssertionError):
                    self.assertEqual(negamax_alpha_beta_top(board, depth, table=table), expected)
                self.assertEqual(board.to_fen(), fen)
                self.assertFalse(board.previous_positions)

    def test_window_bounds_never_replace_full_window_scores(self):
        board = ChessBoard("4k3/8/8/3r4/3Q4/8/8/4K3 w - - 0 1")
        expected = negamax_alpha_beta_top(board, 2)
        for offset, bound_name in ((-1, "LOWER"), (1, "UPPER")):
            with self.subTest(bound=bound_name):
                table = TranspositionTable()
                edge = expected[1] + offset
                alpha, beta = (edge - 1, edge) if offset < 0 else (edge, edge + 1)
                result = negamax_alpha_beta_top(board, 2, alpha, beta, table=table)
                self.assertEqual(table.lookup(table.key_for(board), 2).bound.name, bound_name)
                with patch.object(board, "_legal_moves", side_effect=AssertionError):
                    self.assertEqual(negamax_alpha_beta_top(board, 2, alpha, beta, table=table), result)
                self.assertEqual(negamax_alpha_beta_top(board, 2, table=table), expected)

    def test_depth_and_halfmove_clock_qualify_reuse(self):
        board = ChessBoard("4k3/8/8/3r4/3Q4/8/8/4K3 b - - 0 1")
        other_clock = ChessBoard(board.to_fen().replace(" 0 1", " 99 1"))
        table = TranspositionTable()
        shallow = negamax_alpha_beta_top(board, 0)
        deep = negamax_alpha_beta_top(board, 2)
        self.assertNotEqual(shallow[1], deep[1])
        self.assertEqual(negamax_alpha_beta_top(board, 0, table=table), shallow)
        self.assertEqual(negamax_alpha_beta_top(board, 2, table=table), deep)
        self.assertEqual(negamax_alpha_beta_top(board, 0, table=table), shallow)
        self.assertNotEqual(table.key_for(board), table.key_for(other_clock))
        self.assertIsNone(table.lookup(table.key_for(other_clock), 2))

    def test_cached_mate_scores_are_relative_to_the_current_root(self):
        board = ChessBoard("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
        table = TranspositionTable()
        move, score = negamax_alpha_beta_top(board, 1, table=table)
        self.assertEqual(score, 99_999)
        board.make_move(move)
        self.assertIsNotNone(table.lookup(table.key_for(board), 0))
        with patch.object(board, "is_game_over", side_effect=AssertionError):
            self.assertEqual(negamax_alpha_beta_top(board, 0, table=table), (None, -100_000))
