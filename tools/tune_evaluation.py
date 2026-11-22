"""Screen evaluation weights against the current evaluator in colour-swapped games."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from unittest.mock import patch

import chess

from chess_engine import evaluation_functions as evaluation
from chess_engine.board_representation import ChessBoard
from chess_engine.search_algorithms import negamax_alpha_beta_top


# Include pawn races, minor-piece imbalances, and positions with heavier material.
POSITIONS = (
    "8/5pk1/3p2p1/4p3/3PP3/2P3P1/5PK1/8 w - - 0 1",
    "8/4bk2/3p2p1/4p3/3PP3/2P3P1/4BPK1/8 w - - 0 1",
    "8/4nk2/1p1p2p1/4p3/3PP3/2P3P1/4BPK1/8 w - - 0 1",
    "6k1/2p2pp1/3b3p/1P1p4/3P4/2B2P2/5KPP/8 b - - 0 1",
    "4k3/5pp1/2p5/p2pp3/3PP2P/2P2PP1/P7/4K3 w - - 0 1",
    "4k3/1p3pp1/2n1b2p/p2p4/P2P4/1P2BB1P/5PP1/4K3 w - - 0 1",
    "2r3k1/5pp1/2p4p/1p1p4/3P4/1P3PPP/1BP5/2R3K1 b - - 0 1",
    "r1bq1rk1/pp2bppp/2p2n2/3p4/3P4/2NBPN2/PPQ2PPP/R1B2RK1 w - - 0 1",
)

VALIDATION_POSITIONS = (
    "8/5pk1/6p1/1p1p4/3P1P2/1P4P1/6KP/8 w - - 0 1",
    "8/4k3/1pp2p2/P2p2p1/3P2P1/2P1K3/5P2/8 b - - 0 1",
    "8/4bk2/2p2pp1/1p1p4/1P1P2P1/2P2B2/5P2/6K1 w - - 0 1",
    "8/4kp2/1p2p1p1/7p/1P1P4/4KBPP/1b2B3/8 b - - 0 1",
)



@dataclass(frozen=True)
class Weights:
    material: float = 1.0
    endgame_king: float = 1.0
    passed_pawns: float = 1.0
    bishop_pair: int = 25


BASELINE = Weights()
CANDIDATES = {
    "material-low": replace(BASELINE, material=0.85),
    "material-high": replace(BASELINE, material=1.15),
    "king-low": replace(BASELINE, endgame_king=0.5),
    "king-high": replace(BASELINE, endgame_king=1.5),
    "passers-low": replace(BASELINE, passed_pawns=0.5),
    "passers-high": replace(BASELINE, passed_pawns=1.5),
    "bishop-pair-low": replace(BASELINE, bishop_pair=12),
    "bishop-pair-high": replace(BASELINE, bishop_pair=40),
}


def _weighted_tables(tables_by_phase, weights, material_values):
    result = []
    for phase, tables in enumerate(tables_by_phase):
        material = tuple(
            tuple(value + round(base * (weights.material - 1)) for value in table)
            for table, base in zip(tables[:-1], material_values)
        )
        endgame_fraction = 1 - phase / evaluation._MAX_PHASE
        king = tuple(
            value + round((endgame - evaluation.KING_VALUE) * (weights.endgame_king - 1)
                          * endgame_fraction)
            for value, endgame in zip(tables[-1], evaluation._ENDGAME_KING)
        )
        result.append((*material, king))
    return tuple(result)


def _make_evaluator(weights):
    baseline = evaluation.EvaluationFunction()
    if weights == BASELINE:
        return baseline.evaluate
    values = [baseline.piece_values[piece] for piece in "PNBRQ"]
    white_tables = _weighted_tables(evaluation._WHITE_PHASE_TABLES, weights, values)
    black_tables = _weighted_tables(evaluation._BLACK_PHASE_TABLES, weights, values)

    def evaluate(board):
        boards = board.piece_bitboards
        pawns, _, bishops, _, _, _, white, black = boards
        phase = evaluation._material_phase(boards)
        passers = evaluation._passed_pawn_score(pawns & white, pawns & black, phase)
        pair_difference = (bool(evaluation._bishop_pair_score(bishops & white))
                           - bool(evaluation._bishop_pair_score(bishops & black)))
        bonus = round(passers * weights.passed_pawns) + pair_difference * weights.bishop_pair
        return evaluation._position_score(
            boards, board.white_to_move, white_tables[phase], black_tables[phase], bonus
        )

    return evaluate


def _play(fen, candidate_colour, candidate, baseline, depth, max_plies):
    referee = chess.Board(fen)
    board = ChessBoard(fen)
    for ply in range(max_plies + 1):
        outcome = referee.outcome()
        if outcome is not None:
            if outcome.winner is None:
                return "draw"
            return "win" if outcome.winner == candidate_colour else "loss"
        if ply == max_plies:
            return "unfinished"

        evaluator = candidate if referee.turn == candidate_colour else baseline
        with patch("chess_engine.search_algorithms.eval.evaluate", new=evaluator):
            move, _ = negamax_alpha_beta_top(board, depth)
        referee.push_uci(move)
        board.make_move(move)


def _compare(name, positions, depth, max_plies):
    weights = CANDIDATES[name]
    candidate, baseline = _make_evaluator(weights), _make_evaluator(BASELINE)
    results = Counter(wins=0, draws=0, losses=0, unfinished=0)
    labels = {"win": "wins", "loss": "losses", "draw": "draws", "unfinished": "unfinished"}
    pairs = []
    for fen in positions:
        outcomes = [_play(fen, colour, candidate, baseline, depth, max_plies)
                    for colour in (chess.WHITE, chess.BLACK)]
        results.update(labels[outcome] for outcome in outcomes)
        pairs.append({"fen": fen, "as_white": outcomes[0], "as_black": outcomes[1]})
    return {"candidate": name, "weights": asdict(weights), **results, "pairs": pairs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--suite", choices=("screen", "validation"), default="screen")
    parser.add_argument("--positions", type=Path, help="Optional file with one FEN per line")
    parser.add_argument("--candidate", action="append", choices=CANDIDATES)
    args = parser.parse_args()
    if args.depth < 1 or args.max_plies < 1:
        parser.error("depth and max plies must be positive")
    positions = POSITIONS if args.suite == "screen" else VALIDATION_POSITIONS
    if args.positions:
        positions = tuple(line.strip() for line in args.positions.read_text().splitlines() if line.strip())
    if not positions or any(not chess.Board(fen).is_valid() for fen in positions):
        parser.error("positions must contain valid FENs")

    for name in args.candidate or CANDIDATES:
        report = _compare(name, positions, args.depth, args.max_plies)
        print(json.dumps({"suite": args.suite, "depth": args.depth, "max_plies": args.max_plies, **report}), flush=True)


if __name__ == "__main__":
    main()
