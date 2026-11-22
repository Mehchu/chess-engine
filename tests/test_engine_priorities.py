import unittest
from unittest.mock import patch

import chess

from chess_engine.board_representation import BLACK, WHITE, ChessBoard, move_to_uci
from chess_engine.fen_handling import InvalidFEN, STARTING_FEN
from chess_engine.search_algorithms import Bound, TranspositionEntry, TranspositionTable, negamax_alpha_beta_top
from chess_engine.uci import _parse_position


class PlayablePositionTests(unittest.TestCase):
    def test_rejects_inconsistent_positions_at_uci_boundary(self):
        fens = (
            "8/8/8/8/8/8/8/4K3 w - - 0 1",
            "P3k3/8/8/8/8/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/4R3/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/8/4K3 w K - 0 1",
            "4k3/8/8/8/8/8/8/4K3 w - d6 0 1",
        )
        for fen in fens:
            with self.subTest(fen=fen), self.assertRaises(InvalidFEN):
                _parse_position(["fen", *fen.split()])

    def test_accepts_uncapturable_en_passant_target(self):
        fen = "4k3/8/8/3p4/8/8/8/4K3 w - d6 0 1"
        self.assertEqual(_parse_position(["fen", *fen.split()]).to_fen(), fen)

    def test_insufficient_material_matches_reference_and_search(self):
        for fen in (
            "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/8/2B1K3 w - - 0 1",
            "2b1k3/8/8/8/8/8/8/5BK1 w - - 0 1",
            "2b1k3/8/8/8/8/8/8/2B1K3 w - - 0 1",
            "4k3/8/8/8/8/8/8/1NN1K3 w - - 0 1",
        ):
            with self.subTest(fen=fen):
                expected = chess.Board(fen).is_insufficient_material()
                board = ChessBoard(fen)
                self.assertEqual(board.game_end_reason() == "insufficient material", expected)
                if expected:
                    self.assertEqual(negamax_alpha_beta_top(board, 2, quiescence=True), (None, 0))


class MoveConstraintTests(unittest.TestCase):
    def test_pin_check_and_tactical_filters_match_safety_reference(self):
        for fen in (
            "4r1k1/8/8/8/8/8/4R3/4K3 w - - 0 1",
            "4r1k1/8/8/8/1b6/8/8/4K3 w - - 0 1",
            "4k3/8/8/3pP3/4K3/8/8/8 w - d6 0 1",
            "4k3/8/8/r4pPK/8/8/8/8 w - f6 0 1",
            "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                reference = chess.Board(fen)
                side, enemy = (WHITE, BLACK) if board.white_to_move else (BLACK, WHITE)
                exhaustive = [move for move in board._candidates(side, enemy)
                              if board._keeps_king_safe(move, side, enemy)]
                self.assertEqual(list(board._legal_moves()), exhaustive)
                self.assertEqual({move_to_uci(move) for move in exhaustive},
                                 {move.uci() for move in reference.legal_moves})
                expected = {move.uci() for move in reference.legal_moves
                            if move.promotion or reference.is_capture(move)}
                self.assertEqual({move_to_uci(move) for move in board._legal_moves(tactical_only=True)},
                                 expected)


class SearchPriorityTests(unittest.TestCase):
    def test_preferred_root_move_is_searched_first_without_changing_score(self):
        board = ChessBoard(STARTING_FEN)
        expected_score = negamax_alpha_beta_top(board, 2, quiescence=True)[1]
        original_push = board._push
        root_moves = []

        def track(move):
            if not board.previous_positions:
                root_moves.append(move_to_uci(move))
            return original_push(move)

        with patch.object(board, "_push", side_effect=track):
            _, score = negamax_alpha_beta_top(board, 2, quiescence=True, preferred_move="g1f3")
        self.assertEqual(root_moves[0], "g1f3")
        self.assertEqual(score, expected_score)
        self.assertEqual(board.to_fen(), STARTING_FEN)

    def test_table_evicts_oldest_entry_and_preserves_scores(self):
        table = TranspositionTable(max_entries=2)
        entry = TranspositionEntry(None, 0, Bound.EXACT)
        table.store("one", 0, entry)
        table.store("two", 0, entry)
        table.store("three", 0, entry)
        self.assertIsNone(table.lookup("one", 0))
        self.assertEqual(table.lookup("two", 0), entry)
        self.assertEqual(table.lookup("three", 0), entry)
        board = ChessBoard(STARTING_FEN)
        expected = negamax_alpha_beta_top(board, 2, quiescence=True)
        self.assertEqual(negamax_alpha_beta_top(board, 2, table=table, quiescence=True), expected)
        self.assertLessEqual(len(table), 2)
