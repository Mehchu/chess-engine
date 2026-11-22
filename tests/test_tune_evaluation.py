import unittest

import chess

from chess_engine.board_representation import ChessBoard
from tools.tune_evaluation import BASELINE, CANDIDATES, _make_evaluator, _play


class WeightScreenTests(unittest.TestCase):
    def test_candidates_change_only_the_selected_feature(self):
        baseline = _make_evaluator(BASELINE)
        cases = (
            ("material-high", "4k3/8/8/8/4P3/8/8/4K3 w - - 0 1", 15),
            ("king-high", "4k3/8/8/8/3K4/8/8/8 w - - 0 1", 12),
            ("passers-high", "4k3/8/4P3/8/8/8/8/4K3 w - - 0 1", 36),
            ("bishop-pair-high", "4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1", 15),
        )
        for name, fen, expected in cases:
            with self.subTest(candidate=name):
                board = ChessBoard(fen)
                candidate = _make_evaluator(CANDIDATES[name])
                self.assertEqual(candidate(board) - baseline(board), expected)

    def test_game_results_are_candidate_relative_and_keep_unfinished_separate(self):
        baseline = _make_evaluator(BASELINE)
        mate_in_one = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"
        self.assertEqual(_play(mate_in_one, chess.WHITE, baseline, baseline, 1, 1), "win")
        self.assertEqual(_play(mate_in_one, chess.BLACK, baseline, baseline, 1, 1), "loss")
        self.assertEqual(_play(chess.STARTING_FEN, chess.WHITE, baseline, baseline, 1, 1), "unfinished")
