import unittest
from unittest.mock import patch

import chess

from board_representation import ChessBoard
from search_algorithms import (
    SearchControl,
    SearchStopped,
    TranspositionTable,
    negamax,
    negamax_alpha_beta_top,
)

MATE = 100_000
VALUES = {chess.PAWN: 100, chess.KNIGHT: 300, chess.BISHOP: 320,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


def white_material(board):
    return sum(value if piece.color else -value
               for piece in board.piece_map().values()
               for value in (VALUES[piece.piece_type],))


def material(board):
    reference = chess.Board(board.to_fen())
    score = white_material(reference)
    return score if reference.turn else -score


def reference_minimax(board, depth, ply=0):
    """Return a White-relative score and all optimal moves."""
    if not board.legal_moves:
        if not board.is_check():
            return 0, set()
        return (-1 if board.turn else 1) * (MATE - ply), set()
    if depth == 0:
        return white_material(board), set()

    scores = {}
    for move in board.legal_moves:
        board.push(move)
        scores[move.uci()] = reference_minimax(board, depth - 1, ply + 1)[0]
        board.pop()
    best = (max if board.turn else min)(scores.values())
    return best, {move for move, score in scores.items() if score == best}


class SearchTests(unittest.TestCase):
    def test_matches_independent_minimax(self):
        for fen, depth in (
            ("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1", 3),
            ("8/8/8/8/8/6k1/5q2/7K b - - 0 1", 2),
            ("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1", 0),
            ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", 0),
            ("4k3/8/8/3r4/3Q4/8/8/4K3 w - - 0 1", 2),
            ("4k3/8/8/3r4/3Q4/8/8/4K3 b - - 0 1", 2),
            ("4k3/8/8/3r4/3Q4/8/8/4K3 b - - 0 1", 0),
        ):
            reference = chess.Board(fen)
            expected, best_moves = reference_minimax(reference, depth)
            expected *= 1 if reference.turn else -1
            for search in (negamax, negamax_alpha_beta_top):
                with self.subTest(fen=fen, depth=depth, search=search.__name__):
                    board = ChessBoard(fen)
                    with patch("search_algorithms.eval.evaluate", side_effect=material):
                        move, score = search(board, depth)
                    self.assertEqual(score, expected)
                    self.assertIn(move, best_moves or {None})
                    self.assertEqual(board.to_fen(), fen)
                    self.assertFalse(board.previous_positions)

    def test_builtin_evaluation_follows_side_to_move(self):
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
        white_score = negamax(ChessBoard(fen), 0)[1]
        self.assertGreater(white_score, 0)
        self.assertEqual(negamax(ChessBoard(fen.replace(" w ", " b ")), 0)[1], -white_score)
        mirrored = chess.Board(fen).mirror().fen()
        self.assertEqual(negamax(ChessBoard(mirrored), 0)[1], white_score)

    def test_evaluation_preserves_piece_square_scores(self):
        from evaluation_functions import EvaluationFunction, table_array

        evaluator = EvaluationFunction()
        positions = (
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            "1N2k3/5p2/8/3r4/8/4B3/2P5/4K3 b - - 0 1",
        )
        for fen in positions:
            with self.subTest(fen=fen):
                reference = chess.Board(fen)
                white_score = sum(
                    int(table_array[piece.piece_type - 1][square ^ (7 if piece.color else 63)])
                    * (1 if piece.color else -1)
                    for square, piece in reference.piece_map().items()
                )
                expected = white_score if reference.turn else -white_score
                self.assertEqual(evaluator.evaluate(ChessBoard(fen)), expected)

    def test_narrow_windows_restore_existing_history(self):
        board = ChessBoard("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        board.make_move("d4d5")
        fen = board.to_fen()
        history = board.previous_positions.copy()
        with patch("search_algorithms.eval.evaluate", side_effect=material):
            _, exact = negamax(board, 2)
            _, lower_bound = negamax_alpha_beta_top(board, 2, -1000, -950)
            _, upper_bound = negamax_alpha_beta_top(board, 2, -850, -800)
        self.assertLessEqual(-950, lower_bound)
        self.assertLessEqual(lower_bound, exact)
        self.assertLessEqual(exact, upper_bound)
        self.assertLessEqual(upper_bound, -850)
        self.assertEqual(board.to_fen(), fen)
        self.assertEqual(board.previous_positions, history)

    def test_search_unwinds_when_evaluation_raises(self):
        fen = "4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1"
        for search in (negamax, negamax_alpha_beta_top):
            board = ChessBoard(fen)
            with (self.subTest(search=search.__name__),
                  patch("search_algorithms.eval.evaluate", side_effect=RuntimeError),
                  self.assertRaises(RuntimeError)):
                search(board, 2)
            self.assertEqual(board.to_fen(), fen)
            self.assertFalse(board.previous_positions)

    def test_interruption_restores_board_and_table_can_be_reused(self):
        board = ChessBoard("4k3/8/8/8/3Q4/8/8/4K3 w - - 0 1")
        board.make_move("d4d5")
        fen = board.to_fen()
        history = board.previous_positions.copy()
        table = TranspositionTable()
        control = SearchControl(should_stop=lambda: control.nodes >= 5)
        with self.assertRaises(SearchStopped):
            negamax_alpha_beta_top(board, 3, table=table, control=control)
        self.assertEqual(control.nodes, 5)
        self.assertEqual(board.to_fen(), fen)
        self.assertEqual(board.previous_positions, history)
        self.assertIsNone(table.lookup(table.key_for(board), 3))
        self.assertEqual(negamax_alpha_beta_top(board, 3, table=table),
                         negamax_alpha_beta_top(board, 3))
