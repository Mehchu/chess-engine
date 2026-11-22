from enum import Enum
from itertools import islice

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
Move = tuple[int, int, str | None]


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


def _ray_squares(square, dx, dy):
    target = _offset(square, dx, dy)
    while target is not None:
        yield target
        target = _offset(target, dx, dy)


def _square_mask(squares):
    return sum(1 << square for square in squares)


KNIGHT_TARGETS = tuple(tuple(_steps(square, KNIGHT_STEPS)) for square in range(64))
KING_TARGETS = tuple(tuple(_steps(square, KING_STEPS)) for square in range(64))
KNIGHT_ATTACKS = tuple(map(_square_mask, KNIGHT_TARGETS))
KING_ATTACKS = tuple(map(_square_mask, KING_TARGETS))
PAWN_SOURCES = {
    side: tuple(_square_mask(_steps(square, ((-1, rank), (1, rank))))
                for square in range(64))
    for side, rank in ((WHITE, -1), (BLACK, 1))
}
RAY_SQUARES = {
    directions: tuple(tuple(tuple(_ray_squares(square, dx, dy)) for dx, dy in directions)
                      for square in range(64))
    for directions in (ORTHOGONAL, DIAGONAL, KING_STEPS)
}
RAY_MASKS = {
    directions: tuple(tuple((_square_mask(ray), dx + 8 * dy > 0)
                            for ray, (dx, dy) in zip(rays, directions))
                      for rays in RAY_SQUARES[directions])
    for directions in (ORTHOGONAL, DIAGONAL)
}


def _castle_rook_mask(start, end):
    rook_start, rook_end = (start + 3, start + 1) if end > start else (start - 4, start - 1)
    return (1 << rook_start) | (1 << rook_end)


def _squares(mask):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def move_to_uci(move: Move) -> str:
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
    def piece_bitboards(self):
        """Return the six piece-type masks followed by White and Black masks."""
        return tuple(self._boards)

    @property
    def all_bitboards(self):
        """Provide the original NumPy array layout for compatibility."""
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
        for index in range(6):
            if self._boards[index] & mask:
                return index
        return None

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

    def _capture_mask(self, end, end_mask, is_pawn, side):
        if is_pawn and end == self.en_passant and not self.occupancy & end_mask:
            return 1 << (end - 8 if side == WHITE else end + 8)
        return end_mask

    def _push(self, move):
        """Apply a generated legal move without validating it again."""
        start, end, promotion = move
        start_mask, end_mask = 1 << start, 1 << end
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        piece = self._piece_type(start_mask)
        capture_mask = self._capture_mask(end, end_mask, piece == PAWN, side)
        captured = self._piece_type(capture_mask) if self._boards[enemy] & capture_mask else None
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
                rook_move = _castle_rook_mask(start, end)
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
        for ray in RAY_SQUARES[directions][square]:
            for target in ray:
                yield target
                if occupied & (1 << target):
                    break

    def _attacked(self, square, attacker, occupied, removed=0):
        boards = self._boards
        attackers = boards[attacker] & ~removed
        nearby = ((boards[PAWN] & PAWN_SOURCES[attacker][square])
                  | (boards[KNIGHT] & KNIGHT_ATTACKS[square])
                  | (boards[KING] & KING_ATTACKS[square]))
        if attackers & nearby:
            return True

        for piece, directions in ((ROOK, ORTHOGONAL), (BISHOP, DIAGONAL)):
            sliders = attackers & (boards[piece] | boards[QUEEN])
            if not sliders:
                continue
            for ray, ascending in RAY_MASKS[directions][square]:
                if not ray & sliders:
                    continue
                blockers = ray & occupied
                # A slider on the ray guarantees at least one occupied square.
                first = blockers & -blockers if ascending else 1 << (blockers.bit_length() - 1)
                if first & sliders:
                    return True
        return False

    def is_check(self):
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        king = self._boards[KING] & self._boards[side]
        return bool(king and self._attacked(king.bit_length() - 1, enemy, self.occupancy))

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
        if self._attacked(square, enemy, self.occupancy):
            return
        for step, rook, empty in ((1, home + 3, (home + 1, home + 2)),
                                  (-1, home - 4, (home - 1, home - 2, home - 3))):
            if not self.castling_rights & ROOK_RIGHTS[rook]:
                continue
            if not self._boards[ROOK] & self._boards[side] & (1 << rook):
                continue
            if any(self.occupancy & (1 << target) for target in empty):
                continue
            if not self._attacked(home + step, enemy, self.occupancy):
                yield home, home + 2 * step, None

    def _candidates(self, side, enemy):
        excluded = self._boards[side] | (self._boards[enemy] & self._boards[KING])
        for square in _squares(self._boards[side]):
            piece = self._piece_type(1 << square)
            if piece == PAWN:
                yield from self._pawn_targets(square, side, enemy)
                continue
            if piece == KNIGHT:
                targets = KNIGHT_TARGETS[square]
            elif piece == KING:
                targets = KING_TARGETS[square]
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
        # Project occupancy only. Attacks can change through captures, king
        # moves, and castling without updating clocks or saving a snapshot.
        start, end, _ = move
        start_mask, end_mask = 1 << start, 1 << end
        king = self._boards[KING] & self._boards[side]
        if not king:
            return True

        captured = self._capture_mask(end, end_mask, self._boards[PAWN] & start_mask, side)
        occupied = (self.occupancy & ~(start_mask | captured)) | end_mask
        if king & start_mask:
            king = (king & ~start_mask) | end_mask
            if abs(end - start) == 2:
                occupied ^= _castle_rook_mask(start, end)
        return not self._attacked(king.bit_length() - 1, enemy, occupied, captured)

    def _legal_moves(self):
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        for move in self._candidates(side, enemy):
            if self._keeps_king_safe(move, side, enemy):
                yield move

    def generate_legal_moves(self):
        return [move_to_uci(move) for move in self._legal_moves()]

    def reversible_history(self):
        """Yield prior snapshots that can still matter for repetition."""
        limit = min(self.halfmove_clock, len(self.previous_positions))
        for position in islice(reversed(self.previous_positions), limit):
            if position.castling_rights != self.castling_rights:
                break
            yield position

    def _legal_en_passant_target(self):
        target = self.en_passant
        if target is None or self.occupancy & (1 << target):
            return None
        side, enemy = (WHITE, BLACK) if self.white_to_move else (BLACK, WHITE)
        direction = 1 if self.white_to_move else -1
        captured = 1 << (target - 8 * direction)
        if not captured & self._boards[PAWN] & self._boards[enemy]:
            return None
        pawns = self._boards[PAWN] & self._boards[side]
        for start in _steps(target, ((-1, -direction), (1, -direction))):
            if pawns & (1 << start) and self._keeps_king_safe((start, target, None), side, enemy):
                return target
        return None

    def repetition_key(self):
        """Return position identity under the repetition rule."""
        return (self.piece_bitboards, self.white_to_move, self.castling_rights,
                self._legal_en_passant_target())

    def _is_repetition(self, occurrences):
        if min(self.halfmove_clock, len(self.previous_positions)) < occurrences - 1:
            return False

        pieces, turn, _, target = self.repetition_key()
        matches = 1
        for position in self.reversible_history():
            if position.white_to_move != turn or position.piece_boards != pieces:
                continue
            historical_target = None
            if position.en_passant is not None:
                historical_target = ChessBoard(position.to_fen())._legal_en_passant_target()
            if historical_target == target:
                matches += 1
                if matches == occurrences:
                    return True
        return False

    def can_claim_threefold_repetition(self):
        if self._is_repetition(3):
            return True
        if min(self.halfmove_clock, len(self.previous_positions)) < 1:
            return False
        for move in self._legal_moves():
            self._push(move)
            try:
                if self._is_repetition(3):
                    return True
            finally:
                self.undo_move()
        return False

    def can_claim_fifty_moves(self):
        if self.halfmove_clock >= 100:
            return next(self._legal_moves(), None) is not None
        if self.halfmove_clock == 99:
            for move in self._legal_moves():
                self._push(move)
                try:
                    if self.halfmove_clock >= 100 and next(self._legal_moves(), None) is not None:
                        return True
                finally:
                    self.undo_move()
        return False

    def automatic_draw_reason(self):
        """Return a repetition or move-count draw for a position with legal moves."""
        if self.halfmove_clock >= 150:
            return "seventy-five-move rule"
        if self._is_repetition(5):
            return "fivefold repetition"
        return None

    def game_end_reason(self):
        if next(self._legal_moves(), None) is None:
            return "checkmate" if self.is_check() else "stalemate"
        return self.automatic_draw_reason()

    def is_game_over(self):
        """Return terminal status and a score from the side to move's perspective."""
        reason = self.game_end_reason()
        return reason is not None, -99999 if reason == "checkmate" else 0

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
                counts[move_to_uci(move)] = self.perft(depth - 1)
            finally:
                self.undo_move()
        return counts

    def display_board(self):
        print(str(self))

    def __repr__(self):
        return display_chess_position(self.to_fen())

    __str__ = __repr__
