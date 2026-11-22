import unittest

import chess

from chess_engine import fen_handling
from chess_engine.notation_handling import decode_square


class FenTests(unittest.TestCase):
    def test_en_passant_uses_same_coordinates_as_pieces(self):
        boards = fen_handling.fen_to_bitboards(
            "4k3/8/8/8/4P3/8/8/4K3 b - e3 0 1"
        )
        self.assertEqual(boards[9], decode_square("e3"))

    def test_black_to_move_and_clocks_round_trip(self):
        for fen in (
            "r3k2r/8/8/8/4P3/8/8/R3K2R b KQkq e3 12 34",
            "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 14",
            "4k3/8/8/8/8/8/8/4K3 b - - 99 42",
        ):
            with self.subTest(fen=fen):
                expected = chess.Board(fen)
                position = fen_handling.parse_fen(fen)
                self.assertEqual(position.white_to_move, expected.turn)
                self.assertEqual(position.en_passant, expected.ep_square)
                self.assertEqual(position.halfmove_clock, expected.halfmove_clock)
                self.assertEqual(position.fullmove_number, expected.fullmove_number)
                self.assertEqual(position.to_fen(), expected.fen(en_passant="fen"))

    def test_empty_castling_field_is_serialised_as_dash(self):
        boards = fen_handling.fen_to_bitboards("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
        self.assertEqual(fen_handling.bitboards_to_fen(boards).split()[2], "-")

    def test_malformed_fen_is_rejected(self):
        placement = "4k3/8/8/8/8/8/8/4K3"
        for fen in (
            "4k3/8/8/8/8/8/4K3 w - - 0 1",
            "4k3/8/8/8/8/8/8/4K4 w - - 0 1",
            f"{placement} x - - 0 1",
            f"{placement} w KX - 0 1",
            f"{placement} w KK - 0 1",
            f"{placement} w - e3 0 1",
            f"{placement} w - e6x 0 1",
            f"{placement} w - - -1 1",
            f"{placement} w - - 0 0",
            f"{placement} w - - 0 1 extra",
        ):
            with self.subTest(fen=fen), self.assertRaises(fen_handling.InvalidFEN):
                fen_handling.fen_to_bitboards(fen)
