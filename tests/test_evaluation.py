import unittest

import chess

from chess_engine.board_representation import ChessBoard
from chess_engine import evaluation_functions as evaluation
from chess_engine.evaluation_functions import EvaluationFunction


class EvaluationTermsTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = EvaluationFunction()

    def pawn_score(self, fen):
        return self.evaluator.evaluate_pawn_structure(ChessBoard(fen))

    def test_cached_evaluation_matches_uncached_terms_after_make_and_undo(self):
        fen = "4k3/P7/2r5/8/3P4/8/4R3/4K3 w - - 0 1"
        board = ChessBoard(fen)

        def expected():
            masks = board.piece_bitboards
            pawns, _, bishops, _, _, _, white, black = masks
            phase = evaluation._material_phase(masks)
            pawn_score = evaluation._passed_pawn_score.__wrapped__(pawns & white, pawns & black, phase)
            pair_score = (evaluation._bishop_pair_score(bishops & white)
                          - evaluation._bishop_pair_score(bishops & black))
            return evaluation._position_score(
                masks, board.white_to_move, evaluation._WHITE_PHASE_TABLES[phase],
                evaluation._BLACK_PHASE_TABLES[phase], pawn_score + pair_score,
            )

        initial = expected()
        for move in ("a7a8q", "a7a8n", "e2e7"):
            with self.subTest(move=move):
                board.make_move(move)
                self.assertEqual(self.evaluator.evaluate(board), expected())
                self.assertEqual(self.evaluator.evaluate(board), expected())
                board.undo_move()
                self.assertEqual(self.evaluator.evaluate(board), initial)

    def test_passed_pawn_bonus_grows_with_advancement(self):
        fourth = "4k3/8/8/8/4P3/8/8/4K3 w - - 0 1"
        sixth = "4k3/8/4P3/8/8/8/8/4K3 w - - 0 1"
        self.assertGreater(self.pawn_score(fourth), 0)
        self.assertGreater(self.pawn_score(sixth), self.pawn_score(fourth))
        self.assertEqual(self.pawn_score(chess.Board(sixth).mirror().fen()), self.pawn_score(sixth))
        self.assertEqual(self.pawn_score(sixth.replace(" w ", " b ")), -self.pawn_score(sixth))

    def test_passed_pawn_bonus_increases_as_material_comes_off(self):
        full = "rnbqkbnr/8/4P3/8/8/8/8/RNBQKBNR w - - 0 1"
        sparse = "4k3/8/4P3/8/8/8/8/4K3 w - - 0 1"
        self.assertGreater(self.pawn_score(full), 0)
        self.assertGreater(self.pawn_score(sparse), self.pawn_score(full))

    def test_enemy_pawns_block_passers_on_same_and_adjacent_files(self):
        clear = self.pawn_score("4k3/8/8/8/4P3/8/8/4K3 w - - 0 1")
        for enemy_row in ("4p3", "3p4", "5p2"):
            with self.subTest(enemy=enemy_row):
                self.assertEqual(self.pawn_score(f"4k3/8/{enemy_row}/8/4P3/8/8/4K3 w - - 0 1"), 0)
        behind = "k7/4P3/8/8/8/4p3/8/4K3 w - - 0 1"
        self.assertGreater(self.pawn_score(behind), 0)
        opposite_files = "4k3/8/p7/7P/8/8/8/4K3 w - - 0 1"
        self.assertGreater(self.pawn_score(opposite_files), 0)
        self.assertGreater(clear, 0)

    def test_rear_doubled_pawn_does_not_get_a_passer_bonus(self):
        front = "4k3/8/4P3/8/8/8/8/4K3 w - - 0 1"
        doubled = "4k3/8/4P3/8/4P3/8/8/4K3 w - - 0 1"
        self.assertGreater(self.pawn_score(front), 0)
        self.assertEqual(self.pawn_score(doubled), self.pawn_score(front))

    def test_bishop_pair_requires_both_square_colours(self):
        opposite = "4k3/8/8/8/8/8/8/2B1KB2 w - - 0 1"
        same = "4k3/8/8/8/8/4B3/8/2B1K3 w - - 0 1"

        def added_bonus(fen):
            board = ChessBoard(fen)
            return self.evaluator.evaluate(board) - self.evaluator.evaluate_material(board)

        self.assertGreater(added_bonus(opposite), 0)
        self.assertEqual(added_bonus(same), 0)
        self.assertEqual(added_bonus(chess.Board(opposite).mirror().fen()), added_bonus(opposite))
