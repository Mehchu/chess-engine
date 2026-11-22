from enum import Enum

from fen_handling import CASTLING, FenPosition, display_chess_position, parse_fen
from notation_handling import decompose_notation, encode_square

WHITE, BLACK = 6, 7
ORTHOGONAL = ((-1, 0), (1, 0), (0, -1), (0, 1))
DIAGONAL = ((-1, -1), (-1, 1), (1, -1), (1, 1))
KING_STEPS = ORTHOGONAL + DIAGONAL
KNIGHT_STEPS = ((-2, -1), (-2, 1), (2, -1), (2, 1),
                (-1, -2), (-1, 2), (1, -2), (1, 2))
ROOK_RIGHTS = {0: CASTLING["Q"], 7: CASTLING["K"],
               56: CASTLING["q"], 63: CASTLING["k"]}
KING_RIGHTS = {WHITE: CASTLING["K"] | CASTLING["Q"],
               BLACK: CASTLING["k"] | CASTLING["q"]}


class PieceType(Enum):
    P = 0
    N = 1
    B = 2
    R = 3
    Q = 4
    K = 5


PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = (piece.value for piece in PieceType)
PROMOTIONS = "qrbn"


class GameOver(Exception):
    pass


def _offset(square, dx, dy):
    file, rank = square % 8 + dx, square // 8 + dy
    if 0 <= file < 8 and 0 <= rank < 8:
        return rank * 8 + file
    return None


def _steps(square, directions):
    for dx, dy in directions:
        target = _offset(square, dx, dy)
        if target is not None:
            yield target


def _squares(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def _move_text(move):
    start, end, promotion = move
    return encode_square(start) + encode_square(end) + (promotion or "")


class ChessBoard:
    def __init__(self, fen):
        self._restore(parse_fen(fen))
        self.previous_positions = []

    def _restore(self, position):
        self._boards = list(position.piece_boards)
        self.white_to_move = position.white_to_move
        self.castling_rights = position.castling_rights
        self.en_passant = position.en_passant
        self.halfmove_clock = position.halfmove_clock
        self.fullmove_number = position.fullmove_number

    def _snapshot(self):
        return FenPosition(
            tuple(self._boards), self.white_to_move, self.castling_rights,
            self.en_passant, self.halfmove_clock, self.fullmove_number,
        )

    @property
    def occupancy(self):
        return self._boards[WHITE] | self._boards[BLACK]

    @property
    def all_bitboards(self):
        """Provide the prototype search with its legacy array layout."""
        import numpy as np

        return np.array(
            [*self._boards, self.castling_rights, self.en_passant or 0,
             self.occupancy, 0, 0],
            dtype=np.uint64,
        )

    @property
    def legal_moves(self):
        return self.generate_legal_moves()

    def to_fen(self):
        return self._snapshot().to_fen()

    def _piece_type(self, mask):
        return next((index for index in range(6) if self._boards[index] & mask), None)

    def determine_piece_on_square(self, square):
        mask = 1 << square
        piece = self._piece_type(mask)
        if piece is None:
            return None
        name = PieceType(piece).name
        return name if self._boards[WHITE] & mask else name.lower()

    def make_move(self, notation):
        if notation is None:
            raise GameOver()
        move = decompose_notation(notation)
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        if move not in self._candidates(side, enemy) or not self._keeps_king_safe(move, side, enemy):
            raise ValueError(f"Illegal move: {notation}")
        self._push(move)

    def _push(self, move):
        start, end, promotion = move
        start_mask, end_mask = 1 << start, 1 << end
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        piece = self._piece_type(start_mask)
        capture_mask = end_mask
        if piece == PAWN and end == self.en_passant and not self.occupancy & end_mask:
            capture_mask = 1 << (end - 8 if side == WHITE else end + 8)
        captured = self._piece_type(capture_mask)
        self.previous_positions.append(self._snapshot())

        if captured is not None:
            self._boards[captured] &= ~capture_mask
            self._boards[enemy] &= ~capture_mask
            if captured == ROOK:
                self.castling_rights &= ~ROOK_RIGHTS.get(end, 0)

        self._boards[piece] &= ~start_mask
        placed = PieceType[promotion.upper()].value if promotion else piece
        self._boards[placed] |= end_mask
        self._boards[side] = (self._boards[side] & ~start_mask) | end_mask

        if piece == KING:
            self.castling_rights &= ~KING_RIGHTS[side]
            if abs(end - start) == 2:
                rook_start, rook_end = (start + 3, start + 1) if end > start else (
                    start - 4, start - 1
                )
                rook_move = (1 << rook_start) | (1 << rook_end)
                self._boards[ROOK] ^= rook_move
                self._boards[side] ^= rook_move
        elif piece == ROOK:
            self.castling_rights &= ~ROOK_RIGHTS.get(start, 0)

        self.en_passant = (start + end) // 2 if piece == PAWN and abs(end - start) == 16 else None
        self.halfmove_clock = 0 if piece == PAWN or captured is not None else self.halfmove_clock + 1
        self.fullmove_number += side == BLACK
        self.white_to_move = not self.white_to_move

    def undo_move(self):
        self._restore(self.previous_positions.pop())

    def _rays(self, square, directions):
        occupied = self.occupancy
        for dx, dy in directions:
            target = _offset(square, dx, dy)
            while target is not None:
                yield target
                if occupied & (1 << target):
                    break
                target = _offset(target, dx, dy)

    def _attacked(self, square, attacker):
        attackers = self._boards[attacker]
        pawn_sources = ((-1, -1), (1, -1)) if attacker == WHITE else ((-1, 1), (1, 1))
        for piece, directions in ((PAWN, pawn_sources), (KNIGHT, KNIGHT_STEPS), (KING, KING_STEPS)):
            mask = attackers & self._boards[piece]
            if any(mask & (1 << target) for target in _steps(square, directions)):
                return True
        for piece, directions in ((ROOK, ORTHOGONAL), (BISHOP, DIAGONAL)):
            mask = attackers & (self._boards[piece] | self._boards[QUEEN])
            if mask and any(mask & (1 << target) for target in self._rays(square, directions)):
                return True
        return False

    def _in_check(self, side, enemy):
        king = self._boards[KING] & self._boards[side]
        return bool(king and self._attacked(king.bit_length() - 1, enemy))

    def is_check(self):
        return self._in_check(WHITE, BLACK) if self.white_to_move else self._in_check(BLACK, WHITE)

    def _pawn_targets(self, square, side, enemy):
        direction = 1 if side == WHITE else -1
        first_rank = 1 if side == WHITE else 6
        last_rank = 7 if side == WHITE else 0
        targets = []
        advance = _offset(square, 0, direction)
        if advance is not None and not self.occupancy & (1 << advance):
            targets.append(advance)
            double = advance + 8 * direction
            if square // 8 == first_rank and not self.occupancy & (1 << double):
                targets.append(double)
        enemy_pieces = self._boards[enemy] & ~self._boards[KING]
        for target in _steps(square, ((-1, direction), (1, direction))):
            if enemy_pieces & (1 << target):
                targets.append(target)
            elif target == self.en_passant and not self.occupancy & (1 << target):
                captured = 1 << (target - 8 * direction)
                if captured & self._boards[PAWN] & self._boards[enemy]:
                    targets.append(target)
        for target in targets:
            for promotion in PROMOTIONS if target // 8 == last_rank else (None,):
                yield square, target, promotion

    def _castle_moves(self, square, side, enemy):
        home = 4 if side == WHITE else 60
        if square != home or not self.castling_rights & KING_RIGHTS[side]:
            return
        if self._attacked(square, enemy):
            return
        for step, rook, empty in ((1, home + 3, (home + 1, home + 2)),
                                  (-1, home - 4, (home - 1, home - 2, home - 3))):
            if not self.castling_rights & ROOK_RIGHTS[rook]:
                continue
            if not self._boards[ROOK] & self._boards[side] & (1 << rook):
                continue
            if any(self.occupancy & (1 << target) for target in empty):
                continue
            if not self._attacked(home + step, enemy):
                yield home, home + 2 * step, None

    def _candidates(self, side, enemy):
        excluded = self._boards[side] | (self._boards[enemy] & self._boards[KING])
        for square in _squares(self._boards[side]):
            piece = self._piece_type(1 << square)
            if piece == PAWN:
                yield from self._pawn_targets(square, side, enemy)
                continue
            if piece == KNIGHT:
                targets = _steps(square, KNIGHT_STEPS)
            elif piece == KING:
                targets = _steps(square, KING_STEPS)
                yield from self._castle_moves(square, side, enemy)
            elif piece == BISHOP:
                targets = self._rays(square, DIAGONAL)
            elif piece == ROOK:
                targets = self._rays(square, ORTHOGONAL)
            else:
                targets = self._rays(square, KING_STEPS)
            for target in targets:
                if not excluded & (1 << target):
                    yield square, target, None

    def _keeps_king_safe(self, move, side, enemy):
        self._push(move)
        try:
            return not self._in_check(side, enemy)
        finally:
            self.undo_move()

    def _legal_moves(self):
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        for move in self._candidates(side, enemy):
            if self._keeps_king_safe(move, side, enemy):
                yield move

    def generate_legal_moves(self):
        return [_move_text(move) for move in self._legal_moves()]

    def is_game_over(self):
        """Return terminal status and a score from the side to move's perspective."""
        if next(self._legal_moves(), None) is not None:
            return False, 0
        return True, -99999 if self.is_check() else 0

    def perft(self, depth):
        if depth < 0:
            raise ValueError("Perft depth must be non-negative")
        if depth == 0:
            return 1
        if depth == 1:
            return sum(1 for _ in self._legal_moves())
        count = 0
        for move in self._legal_moves():
            self._push(move)
            try:
                count += self.perft(depth - 1)
            finally:
                self.undo_move()
        return count

    def perft_divide(self, depth):
        if depth < 1:
            raise ValueError("Perft divide depth must be positive")
        counts = {}
        for move in self._legal_moves():
            self._push(move)
            try:
                counts[_move_text(move)] = self.perft(depth - 1)
            finally:
                self.undo_move()
        return counts

    def display_board(self):
        print(str(self))

    def __repr__(self):
        return display_chess_position(self.to_fen())

    __str__ = __repr__
