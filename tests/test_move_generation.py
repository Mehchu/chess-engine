import random
import unittest

import chess

from chess_engine.board_representation import ChessBoard
from tests.test_position import START

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"


class MoveGenerationTests(unittest.TestCase):
    def assert_matches_reference(self, board, reference):
        moves = board.generate_legal_moves()
        self.assertEqual(len(moves), len(set(moves)))
        self.assertEqual(set(moves), {move.uci() for move in reference.legal_moves})
        self.assertEqual(board.to_fen(), reference.fen(en_passant="fen"))
        self.assertEqual(board.is_check(), reference.is_check())
        pieces = [int(mask) for mask in board.all_bitboards[:8]]
        self.assertFalse(pieces[6] & pieces[7])
        self.assertEqual(sum(pieces[:6]), board.occupancy)
        self.assertEqual(sum(mask.bit_count() for mask in pieces[:6]), board.occupancy.bit_count())
        self.assertEqual(board.occupancy, reference.occupied)

    def test_perft_positions(self):
        for fen, counts in ((START, (20, 400, 8902)), (KIWIPETE, (48, 2039, 97862))):
            board = ChessBoard(fen)
            for depth, expected in enumerate(counts, 1):
                with self.subTest(fen=fen, depth=depth):
                    self.assertEqual(board.perft(depth), expected)
                    self.assertEqual(board.to_fen(), fen)
                    self.assertFalse(board.previous_positions)

    def test_root_divide_matches_reference(self):
        board = ChessBoard(KIWIPETE)
        reference = chess.Board(KIWIPETE)
        expected = {}
        for move in reference.legal_moves:
            reference.push(move)
            expected[move.uci()] = reference.legal_moves.count()
            reference.pop()
        self.assertEqual(board.perft_divide(2), expected)
        self.assertFalse(board.previous_positions)
        self.assertEqual(board.to_fen(), KIWIPETE)

    def test_tactical_move_sets(self):
        for fen in (
            KIWIPETE,
            "4kr2/8/8/8/8/8/8/4K2R w K - 0 1",
            "4k3/8/8/r4pPK/8/8/8/8 w - f6 0 1",
            "4r1k1/8/8/8/1b6/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/p7/1R2K3 b - - 1 15",
            "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1",
            "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1",
        ):
            with self.subTest(fen=fen):
                board = ChessBoard(fen)
                reference = chess.Board(fen)
                self.assert_matches_reference(board, reference)
                ended, score = board.is_game_over()
                self.assertEqual(ended, reference.is_checkmate() or reference.is_stalemate())
                if ended:
                    self.assertEqual(score < 0, reference.is_checkmate())
                for move in reference.legal_moves:
                    reference.push(move)
                    board.make_move(move.uci())
                    self.assertEqual(board.to_fen(), reference.fen(en_passant="fen"))
                    board.undo_move()
                    reference.pop()
                    self.assertEqual(board.to_fen(), fen)

    def test_seeded_playouts_and_undo(self):
        rng = random.Random(42)
        for _ in range(3):
            board = ChessBoard(START)
            reference = chess.Board(START)
            for _ in range(80):
                self.assert_matches_reference(board, reference)
                choices = sorted(move.uci() for move in reference.legal_moves)
                if not choices:
                    break
                move = rng.choice(choices)
                board.make_move(move)
                reference.push_uci(move)
            while reference.move_stack:
                self.assert_matches_reference(board, reference)
                board.undo_move()
                reference.pop()
            self.assert_matches_reference(board, reference)
