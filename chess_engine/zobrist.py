"""Deterministic position keys with a full recomputation reference."""

from random import Random

_ROOK_INDEX = 3


class ZobristHash:
    """Recompute a 64-bit key from piece placement and rule state."""

    def __init__(self):
        rng = Random(0x5A4F4252495354)
        self._pieces = tuple(
            tuple(tuple(rng.getrandbits(64) for _ in range(64)) for _ in range(6))
            for _ in range(2)
        )
        self._black_to_move = rng.getrandbits(64)
        self._castling = tuple(rng.getrandbits(64) for _ in range(16))
        self._en_passant = tuple(rng.getrandbits(64) for _ in range(64))

    def generate_key(self, board):
        boards = board.piece_bitboards
        key = self._castling[board.castling_rights]
        if not board.white_to_move:
            key ^= self._black_to_move
        # Keep the raw FEN target, even when no legal capture is available.
        if board.en_passant is not None:
            key ^= self._en_passant[board.en_passant]
        for colour, occupancy in enumerate(boards[6:]):
            for piece, piece_mask in enumerate(boards[:6]):
                mask = occupancy & piece_mask
                while mask:
                    bit = mask & -mask
                    key ^= self._pieces[colour][piece][bit.bit_length() - 1]
                    mask ^= bit
        return key

    def after_move(self, previous, board, colour, piece, placed, start, end,
                   captured, capture_mask, rook_move):
        our_keys = self._pieces[colour]
        key = previous.zobrist_key ^ self._black_to_move
        key ^= our_keys[piece][start] ^ our_keys[placed][end]
        if captured is not None:
            key ^= self._pieces[colour ^ 1][captured][capture_mask.bit_length() - 1]
        if rook_move:
            first = rook_move & -rook_move
            rook_keys = our_keys[_ROOK_INDEX]
            key ^= rook_keys[first.bit_length() - 1] ^ rook_keys[rook_move.bit_length() - 1]
        if previous.castling_rights != board.castling_rights:
            key ^= self._castling[previous.castling_rights] ^ self._castling[board.castling_rights]
        if previous.en_passant is not None:
            key ^= self._en_passant[previous.en_passant]
        if board.en_passant is not None:
            key ^= self._en_passant[board.en_passant]
        return key


ZOBRIST = ZobristHash()
