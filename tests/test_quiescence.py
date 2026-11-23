import unittest
from unittest.mock import patch

import chess

from chess_engine.board_representation import ChessBoard, move_to_uci
from chess_engine.search_algorithms import (
    SearchControl,
    SearchStopped,
    TranspositionTable,
    _quiescence,
    negamax_alpha_beta_top,
)

HORIZON_TRAP = "4k3/8/4p3/3r4/8/8/8/3QK3 w - - 0 1"


class QuiescenceTests(unittest.TestCase):
    def test_legal_move_probe_with_and_without_free_pawn_pushes(self):
        for fen in (
            chess.STARTING_FEN,
            chess.STARTING_FEN.replace(" w ", " b "),
            "8/8/8/8/3b4/8/1Pk5/K1n5 w - - 0 1",
            "7k/P7/8/8/8/8/8/K7 w - - 0 1",
            "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1",
            "4r1k1/8/8/8/8/8/8/4K3 w - - 0 1",
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                expected = bool(chess.Board(fen).legal_moves)
                self.assertEqual(board._has_legal_move(board._move_context()), expected)

    def test_sees_the_recapture_beyond_nominal_depth(self):
        board = ChessBoard(HORIZON_TRAP)
        self.assertEqual(negamax_alpha_beta_top(board, 1)[0], "d1d5")
        quiet_move, quiet_score = negamax_alpha_beta_top(board, 1, quiescence=True)
        self.assertNotEqual(quiet_move, "d1d5")
        self.assertIn(quiet_move, board.generate_legal_moves())
        self.assertLess(quiet_score, negamax_alpha_beta_top(board, 1)[1])
        self.assertEqual(board.to_fen(), HORIZON_TRAP)
        self.assertFalse(board.previous_positions)

    def test_in_check_searches_quiet_evasions_before_evaluating(self):
        fen = "4r1k1/8/8/8/8/8/8/4K3 w - - 0 1"
        board = ChessBoard(fen)
        reference = chess.Board(fen)
        self.assertTrue(reference.is_check())
        self.assertTrue(all(not reference.is_capture(move) for move in reference.legal_moves))
        scores = []

        def evaluate(position):
            self.assertFalse(position.is_check())
            scores.append(position.to_fen())
            return 40

        with patch("chess_engine.search_algorithms.eval.evaluate", side_effect=evaluate):
            self.assertEqual(negamax_alpha_beta_top(board, 0, quiescence=True), (None, -40))
        self.assertTrue(scores)
        self.assertEqual(board.to_fen(), fen)

    def test_tactical_generator_includes_en_passant_and_quiet_promotions(self):
        for fen in (
            "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
            "4k3/P7/8/8/8/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/1p6/R3K3 b - - 0 1",
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                reference = chess.Board(fen)
                expected = {move.uci() for move in reference.legal_moves
                            if move.promotion or reference.is_capture(move)}
                self.assertTrue(expected)
                self.assertEqual({move_to_uci(move) for move in board._legal_moves(tactical_only=True)}, expected)

    def test_terminal_scores_at_quiescence_horizon(self):
        for fen, expected in (
            ("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", -100_000),
            ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", 0),
            ("4k3/8/8/8/4Q3/8/8/4K3 b - - 150 1", 0),
        ):
            with self.subTest(fen=fen):
                self.assertEqual(negamax_alpha_beta_top(ChessBoard(fen), 0, quiescence=True),
                                 (None, expected))

    def test_cache_separates_static_and_quiescent_scores(self):
        board = ChessBoard(HORIZON_TRAP)
        table = TranspositionTable()
        static = negamax_alpha_beta_top(board, 1, table=table)
        quiet = negamax_alpha_beta_top(board, 1, table=table, quiescence=True)
        self.assertNotEqual(quiet, static)
        self.assertEqual(quiet, negamax_alpha_beta_top(board, 1, quiescence=True))
        self.assertEqual(static, negamax_alpha_beta_top(board, 1, table=table))

    def test_stop_unwinds_quiescence(self):
        fen = "4r1k1/8/8/8/8/8/8/4K3 w - - 0 1"
        board = ChessBoard(fen)
        control = SearchControl(should_stop=lambda: control.nodes >= 1)
        with self.assertRaises(SearchStopped):
            negamax_alpha_beta_top(board, 0, quiescence=True, control=control)
        self.assertEqual(board.to_fen(), fen)
        self.assertFalse(board.previous_positions)

    def test_extension_cap_still_adjudicates_mate_and_avoids_static_score_in_check(self):
        checked = ChessBoard("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")
        mated = ChessBoard("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        with patch("chess_engine.search_algorithms.eval.evaluate", side_effect=AssertionError):
            self.assertEqual(_quiescence(checked, -float("inf"), float("inf"), 8, None, remaining=0), 0)
            self.assertEqual(
                _quiescence(mated, -float("inf"), float("inf"), 8, None, remaining=0), -99_992
            )
