import unittest
from unittest.mock import patch

from chess_engine.board_representation import ChessBoard, move_to_uci
from chess_engine.fen_handling import STARTING_FEN
from chess_engine.search_algorithms import (
    SearchControl,
    SearchStopped,
    TranspositionTable,
    ZobristHash,
    _ordered_moves,
    negamax_alpha_beta_top,
)


class StagedMoveTests(unittest.TestCase):
    def test_partitions_special_moves_without_gaps_or_duplicates(self):
        for fen in (
            "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
            "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1",
            "1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1",
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                moves = list(board._legal_moves())
                for hint in (moves[0], (0, 63, None)):
                    staged = list(_ordered_moves(board, hint, board._move_context()))
                    self.assertCountEqual(staged, moves)
                    if hint in moves:
                        self.assertEqual(staged[0], hint)

    def test_preferred_cutoff_does_not_generate_other_root_moves(self):
        board = ChessBoard(STARTING_FEN)
        original = board._legal_moves

        def legal_moves(**kwargs):
            self.assertTrue(board.previous_positions, "Root generated extra moves before cutoff")
            return original(**kwargs)

        with patch.object(board, "_legal_moves", side_effect=legal_moves):
            move, _ = negamax_alpha_beta_top(
                board, 1, beta=-1000, quiescence=True, preferred_move="g1f3"
            )
        self.assertEqual(move, "g1f3")

    def test_iterative_deepening_uses_cached_hints_below_root(self):
        board = ChessBoard(STARTING_FEN)
        table = TranspositionTable()
        preferred, _ = negamax_alpha_beta_top(board, 2, table=table, quiescence=True)
        internal_hints = []

        def record(position, hint, context):
            if position.previous_positions and hint is not None:
                internal_hints.append(hint)
            return _ordered_moves(position, hint, context)

        with patch("chess_engine.search_algorithms._ordered_moves", side_effect=record):
            result = negamax_alpha_beta_top(
                board, 3, table=table, quiescence=True, preferred_move=preferred
            )
        self.assertTrue(internal_hints)
        self.assertEqual(result[1], negamax_alpha_beta_top(board, 3, quiescence=True)[1])


class IncrementalHashTests(unittest.TestCase):
    def test_make_and_undo_match_full_recomputation(self):
        for fen, moves in (
            (STARTING_FEN, ("e2e4", "d7d5", "e4d5", "g8f6")),
            ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", ("e1g1", "e8c8")),
            ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", ("e5d6",)),
            ("1r2k3/P7/8/8/8/8/8/4K3 w - - 0 1", ("a7b8n",)),
            ("r3k3/8/8/8/8/8/8/R3K3 b Qq - 7 9", ("a8a1",)),
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                hasher = ZobristHash()
                board._zobrist_key = initial = hasher.generate_key(board)
                for move in moves:
                    board.make_move(move)
                    self.assertEqual(board._zobrist_key, hasher.generate_key(board))
                for _ in moves:
                    board.undo_move()
                    self.assertEqual(board._zobrist_key, hasher.generate_key(board))
                self.assertEqual(board._zobrist_key, initial)

    def test_cached_search_matches_recomputed_keys(self):
        board = ChessBoard(STARTING_FEN)
        recomputed = TranspositionTable(incremental_hash=False)
        incremental = TranspositionTable()
        for depth in (1, 2, 3):
            result = negamax_alpha_beta_top(board, depth, table=incremental, quiescence=True)
            self.assertEqual(result, negamax_alpha_beta_top(board, depth, table=recomputed, quiescence=True))
            self.assertIsNone(board._zobrist_key)
            self.assertEqual(board.to_fen(), STARTING_FEN)

    def test_cancelled_search_restores_hash_lifecycle(self):
        board = ChessBoard(STARTING_FEN)
        board.make_move("e2e4")
        fen = board.to_fen()
        history = board.previous_positions.copy()
        control = SearchControl(should_stop=lambda: control.nodes >= 3)
        with self.assertRaises(SearchStopped):
            negamax_alpha_beta_top(board, 3, table=TranspositionTable(), control=control,
                                   quiescence=True)
        self.assertIsNone(board._zobrist_key)
        self.assertEqual(board.to_fen(), fen)
        self.assertEqual(board.previous_positions, history)
