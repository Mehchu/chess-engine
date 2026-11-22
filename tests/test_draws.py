import unittest

import chess

from board_representation import ChessBoard
from search_algorithms import TranspositionTable, negamax, negamax_alpha_beta_top

FEN = "4k1n1/8/8/8/3Q4/8/8/4K1N1 w - - 0 1"
CYCLE = ("g1f3", "g8f6", "f3g1", "f6g8")


class DrawTests(unittest.TestCase):
    def test_threefold_claim_fivefold_and_undo(self):
        board = ChessBoard(FEN)
        oracle = chess.Board(FEN)
        for ply, move in enumerate(CYCLE * 4, 1):
            board.make_move(move)
            oracle.push_uci(move)
            self.assertEqual(board.can_claim_threefold_repetition(), oracle.can_claim_threefold_repetition())
            self.assertEqual(board.is_game_over()[0], oracle.is_fivefold_repetition())
            if ply == 7:
                self.assertTrue(board.can_claim_threefold_repetition())
                self.assertFalse(board.is_game_over()[0])
        self.assertEqual(board.is_game_over(), (True, 0))
        board.undo_move()
        self.assertFalse(board.is_game_over()[0])
        board.make_move(CYCLE[-1])
        self.assertEqual(board.is_game_over(), (True, 0))

    def test_same_fen_different_history_has_different_search_result(self):
        repeated = ChessBoard(FEN)
        for move in CYCLE * 4:
            repeated.make_move(move)
        fresh = ChessBoard(repeated.to_fen())
        table = TranspositionTable()
        self.assertNotEqual(table.key_for(repeated), table.key_for(fresh))
        for depth in (0, 1):
            expected = negamax(fresh, depth)
            self.assertNotEqual(expected[1], 0)
            self.assertEqual(negamax_alpha_beta_top(fresh, depth, table=table), expected)
            self.assertEqual(negamax_alpha_beta_top(repeated, depth, table=table), (None, 0))
            self.assertEqual(negamax_alpha_beta_top(fresh, depth, table=table), expected)

    def test_move_count_claim_and_automatic_draw(self):
        for clock in (98, 99, 100, 149, 150):
            with self.subTest(clock=clock):
                fen = FEN.replace(" 0 1", f" {clock} 1")
                board = ChessBoard(fen)
                oracle = chess.Board(fen)
                self.assertEqual(board.can_claim_fifty_moves(), oracle.can_claim_fifty_moves())
                self.assertEqual(board.is_game_over()[0], oracle.is_seventyfive_moves())

    def test_search_adjudicates_move_count_inside_tree(self):
        board = ChessBoard(FEN.replace(" 0 1", " 149 1"))
        for search in (negamax, negamax_alpha_beta_top):
            move, score = search(board, 1)
            self.assertIn(move, board.legal_moves)
            self.assertEqual(score, 0)
        self.assertEqual(board.halfmove_clock, 149)
        self.assertFalse(board.previous_positions)

    def test_mate_takes_precedence_over_move_count(self):
        board = ChessBoard("7k/5Q2/6K1/8/8/8/8/8 w - - 149 1")
        move, score = negamax_alpha_beta_top(board, 1)
        self.assertGreater(score, 90_000)
        board.make_move(move)
        self.assertEqual(board.halfmove_clock, 150)
        self.assertEqual(board.is_game_over(), (True, -99_999))

    def test_historical_unusable_en_passant_target_does_not_prevent_repetition(self):
        fen = FEN.replace("/8/3Q4/", "/3p4/3Q4/").replace(" w - - ", " w - d6 ")
        board = ChessBoard(fen)
        oracle = chess.Board(fen)
        for move in CYCLE * 4:
            board.make_move(move)
            oracle.push_uci(move)
        self.assertTrue(oracle.is_fivefold_repetition())
        self.assertEqual(board.game_end_reason(), "fivefold repetition")

    def test_repetition_identity_uses_only_legal_en_passant(self):
        for placement, legal in (
            ("4k3/8/8/3pP3/8/8/8/4K3", True),
            ("k3r3/8/8/3pP3/8/8/8/4K3", False),
            ("4k3/8/8/3p4/8/8/8/4K3", False),
        ):
            fen = f"{placement} w - d6 0 1"
            with self.subTest(fen=fen):
                key = ChessBoard(fen).repetition_key()
                other_key = ChessBoard(fen.replace(" d6 ", " - ")).repetition_key()
                self.assertEqual(chess.Board(fen).has_legal_en_passant(), legal)
                self.assertEqual(key != other_key, legal)
