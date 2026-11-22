import numpy as np

piece_to_index = {"P": 0, "N": 1, "B": 2, "R": 3, "Q": 4, "K": 5}

# Defines the relative piece value for each piece type for each square on the chess board
# These values have been derived through heuristic testing of the engine and my understanding Steinitz's elements
pawn_table = (
    np.array(
        [
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            98,
            134,
            61,
            95,
            68,
            126,
            34,
            -11,
            -6,
            7,
            26,
            31,
            65,
            56,
            25,
            -20,
            -14,
            13,
            6,
            21,
            23,
            12,
            17,
            -23,
            -27,
            -2,
            -5,
            12,
            17,
            6,
            10,
            -25,
            -26,
            -4,
            -4,
            -10,
            3,
            3,
            33,
            -12,
            -35,
            -1,
            -20,
            -23,
            -15,
            24,
            38,
            -22,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        ][::-1]
    )
    + 100
)

knight_table = (
    np.array(
        [
            -167,
            -89,
            -34,
            -49,
            61,
            -97,
            -15,
            -107,
            -73,
            -41,
            72,
            36,
            23,
            62,
            7,
            -17,
            -47,
            60,
            37,
            65,
            84,
            129,
            73,
            44,
            -9,
            17,
            19,
            53,
            37,
            69,
            18,
            22,
            -13,
            4,
            16,
            13,
            28,
            19,
            21,
            -8,
            -23,
            -9,
            12,
            10,
            19,
            17,
            25,
            -16,
            -29,
            -53,
            -12,
            -3,
            -1,
            18,
            -14,
            -19,
            -105,
            -21,
            -58,
            -33,
            -17,
            -28,
            -19,
            -23,
        ][::-1]
    )
    + 350
)

bishop_table = (
    np.array(
        [
            -29,
            4,
            -82,
            -37,
            -25,
            -42,
            7,
            -8,
            -26,
            16,
            -18,
            -13,
            30,
            59,
            18,
            -47,
            -16,
            37,
            43,
            40,
            35,
            50,
            37,
            -2,
            -4,
            5,
            19,
            50,
            37,
            37,
            7,
            -2,
            -6,
            13,
            13,
            26,
            34,
            12,
            10,
            4,
            0,
            15,
            15,
            15,
            14,
            27,
            18,
            10,
            4,
            15,
            16,
            0,
            7,
            21,
            33,
            1,
            -33,
            -3,
            -14,
            -21,
            -13,
            -12,
            -39,
            -21,
        ][::-1]
    )
    + 350
)

rook_table = (
    np.array(
        [
            32,
            42,
            32,
            51,
            63,
            9,
            31,
            43,
            27,
            32,
            58,
            62,
            80,
            67,
            26,
            44,
            -5,
            19,
            26,
            36,
            17,
            45,
            61,
            16,
            -24,
            -11,
            7,
            26,
            24,
            35,
            -8,
            -20,
            -36,
            -26,
            -12,
            -1,
            9,
            -7,
            6,
            -23,
            -45,
            -25,
            -16,
            -17,
            3,
            0,
            -5,
            -33,
            -44,
            -16,
            -20,
            -9,
            -1,
            11,
            -6,
            -71,
            -19,
            -13,
            1,
            17,
            16,
            7,
            -37,
            -26,
        ][::-1]
    )
    + 550
)

queen_table = (
    np.array(
        [
            13,
            10,
            18,
            15,
            12,
            12,
            8,
            5,
            11,
            13,
            13,
            11,
            -3,
            3,
            8,
            3,
            7,
            7,
            7,
            5,
            4,
            -3,
            -5,
            -3,
            4,
            3,
            13,
            1,
            2,
            1,
            -1,
            2,
            3,
            5,
            8,
            4,
            -5,
            -6,
            -8,
            -11,
            -4,
            0,
            -5,
            -1,
            -7,
            -12,
            -8,
            -16,
            -6,
            -6,
            0,
            2,
            -9,
            -9,
            -11,
            -3,
            -9,
            2,
            3,
            -1,
            -5,
            -13,
            4,
            -20,
        ][::-1]
    )
    + 900
)

king_table = (
    np.array(
        [
            -65,
            23,
            16,
            -15,
            -56,
            -34,
            2,
            13,
            29,
            -1,
            -20,
            -7,
            -8,
            -4,
            -38,
            -29,
            -9,
            24,
            2,
            -16,
            -20,
            6,
            22,
            -22,
            -17,
            -20,
            -12,
            -27,
            -30,
            -25,
            -14,
            -36,
            -49,
            -1,
            -27,
            -39,
            -46,
            -44,
            -33,
            -51,
            -14,
            -14,
            -22,
            -46,
            -44,
            -30,
            -15,
            -27,
            1,
            7,
            -8,
            -64,
            -43,
            -16,
            9,
            8,
            -15,
            36,
            12,
            -54,
            8,
            -28,
            24,
            14,
        ][::-1]
    )
    + 99999
)

table_array = [
    pawn_table,
    knight_table,
    bishop_table,
    rook_table,
    queen_table,
    king_table,
]


# Tables were stored in reverse a8-first order. Orient them once for each colour.
_WHITE_TABLES = tuple(tuple(int(table[square ^ 7]) for square in range(64)) for table in table_array)
_BLACK_TABLES = tuple(tuple(int(table[square ^ 63]) for square in range(64)) for table in table_array)


def _colour_score(occupancy, piece_masks, tables):
    score = 0
    for pieces, table in zip(piece_masks, tables):
        mask = occupancy & pieces
        while mask:
            bit = mask & -mask
            score += table[bit.bit_length() - 1]
            mask ^= bit
    return score


class EvaluationFunction:
    def __init__(self) -> None:
        # Piece values
        self.piece_values = {
            "P": 100,
            "N": 350,
            "B": 350,
            "R": 550,
            "Q": 900,
            "K": 99999,
        }

    def evaluate(self, board) -> float:
        return self.evaluate_material(board)

    def evaluate_material(self, board) -> float:
        *pieces, white, black = board.piece_bitboards
        white_score = _colour_score(white, pieces, _WHITE_TABLES)
        black_score = _colour_score(black, pieces, _BLACK_TABLES)
        score = white_score - black_score
        return float(score if board.white_to_move else -score)

    def evaluate_pawn_structure(self, board) -> float:
        # Evaluate pawn structure (e.g., isolated pawns, doubled pawns, passed pawns)
        eval = 0

        return eval

    def evaluate_piece_development(self, board) -> float:
        # Evaluate piece development (e.g., pieces developed vs. undeveloped)
        eval = 0

        return eval

    def evaluate_center_control(self, board) -> float:
        # Evaluate control of the center (e.g., central pawn structure, piece placement)
        eval = 0

        return eval
