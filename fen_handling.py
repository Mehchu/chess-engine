from dataclasses import dataclass

import numpy as np

from notation_handling import decode_square, encode_square

PIECES = "pnbrqk"
CASTLING = {"K": 8, "Q": 4, "k": 2, "q": 1}


class InvalidFEN(Exception):
    def __init__(self, fen):
        self.message = f'"{fen}" is an invalid FEN'
        super().__init__(self.message)


@dataclass(frozen=True)
class FenPosition:
    piece_boards: tuple[int, ...]
    white_to_move: bool
    castling_rights: int
    en_passant: int | None
    halfmove_clock: int
    fullmove_number: int

    def to_fen(self) -> str:
        placement = _format_placement(self.piece_boards)
        turn = "w" if self.white_to_move else "b"
        rights = _format_castling(self.castling_rights)
        target = "-" if self.en_passant is None else encode_square(self.en_passant)
        return (
            f"{placement} {turn} {rights} {target} "
            f"{self.halfmove_clock} {self.fullmove_number}"
        )


def parse_fen(fen: str) -> FenPosition:
    """Parse standard six-field FEN syntax without judging position legality."""
    fields = fen.split()
    if len(fields) != 6:
        raise InvalidFEN(fen)
    placement, turn, rights, target, halfmove, fullmove = fields
    ranks = placement.split("/")
    if len(ranks) != 8 or turn not in ("w", "b"):
        raise InvalidFEN(fen)

    boards = [0] * 8
    for rank, row in enumerate(reversed(ranks)):
        file = 0
        previous_was_digit = False
        for char in row:
            if char in "12345678" and not previous_was_digit:
                file += int(char)
                previous_was_digit = True
            elif char in PIECES + PIECES.upper() and file < 8:
                mask = 1 << (rank * 8 + file)
                boards[PIECES.index(char.lower())] |= mask
                boards[6 if char.isupper() else 7] |= mask
                file += 1
                previous_was_digit = False
            else:
                raise InvalidFEN(fen)
        if file != 8:
            raise InvalidFEN(fen)

    castling = 0
    if rights != "-":
        for char in rights:
            mask = CASTLING.get(char, 0)
            if not mask or castling & mask:
                raise InvalidFEN(fen)
            castling |= mask

    en_passant = None
    if target != "-":
        expected_rank = "6" if turn == "w" else "3"
        if len(target) != 2 or target[0] not in "abcdefgh" or target[1] != expected_rank:
            raise InvalidFEN(fen)
        en_passant = decode_square(target)

    if any(not clock.isascii() or not clock.isdecimal() for clock in (halfmove, fullmove)):
        raise InvalidFEN(fen)
    try:
        halfmove_clock, fullmove_number = int(halfmove), int(fullmove)
    except ValueError as exc:
        raise InvalidFEN(fen) from exc
    if fullmove_number < 1:
        raise InvalidFEN(fen)

    return FenPosition(
        tuple(boards), turn == "w", castling, en_passant, halfmove_clock, fullmove_number
    )


def fen_to_bitboards(fen):
    """Adapt complete FEN state to the prototype board's NumPy layout."""
    position = parse_fen(fen)
    return [
        np.uint64(value)
        for value in (*position.piece_boards, position.castling_rights, position.en_passant or 0)
    ]


def _format_placement(boards):
    ranks = []
    for rank in range(7, -1, -1):
        row = []
        empty = 0
        for file in range(8):
            mask = 1 << (rank * 8 + file)
            if not (boards[6] | boards[7]) & mask:
                empty += 1
                continue
            if empty:
                row.append(str(empty))
                empty = 0
            piece = next(PIECES[index] for index in range(6) if boards[index] & mask)
            row.append(piece.upper() if boards[6] & mask else piece)
        if empty:
            row.append(str(empty))
        ranks.append("".join(row))
    return "/".join(ranks)


def _format_castling(rights):
    return "".join(char for char, mask in CASTLING.items() if rights & mask) or "-"


def bitboards_to_fen(bitboards):
    """Format the prototype layout for display with default turn and clocks."""
    *boards, rights, target = map(int, bitboards)
    # The prototype rotates every slot, including the en passant index.
    en_passant = target if 0 < target < 64 else None
    position = FenPosition(tuple(boards), True, rights, en_passant, 0, 1)
    return position.to_fen()


def display_chess_position(fen):

    # Create a mapping for piece characters
    piece_mapping = {
        "R": "♖",
        "N": "♘",
        "B": "♗",
        "Q": "♕",
        "K": "♔",
        "P": "♙",
        "r": "♜",
        "n": "♞",
        "b": "♝",
        "q": "♛",
        "k": "♚",
        "p": "♟",
        ".": "·",
    }

    # Parse FEN string
    rows = fen.split()[0].split("/")

    if len(rows) != 8:  # Detects if a board with an invalid number of rows is entered
        raise InvalidFEN(fen)

    display_str = ""
    for row in rows:  # Converts each row into a printable string
        display_row = []  # Starts with an empty row
        for char in row:  # Loops through each different piece in the row
            if char.isdigit():  # Detects how many empty squares appear in a row
                display_row.extend(
                    ["·"] * int(char)
                )  # Adds on the required amount of empty squares
            else:  # If it is not an empty square
                try:
                    display_row.append(
                        piece_mapping[char]
                    )  # Add on the corresponding piece
                except (
                    KeyError
                ):  # If the current character is not in the dictionary for symbols, then the FEN is invalid so raise that exception
                    raise InvalidFEN(fen)
        display_str += (
            " ".join(display_row) + "\n"
        )  # Join the converted row to the output string

    return display_str
