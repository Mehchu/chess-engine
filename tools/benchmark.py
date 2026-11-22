"""Run a fixed perft and alpha–beta corpus and emit JSON results."""

import argparse
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter

from chess_engine.board_representation import ChessBoard
from chess_engine.fen_handling import STARTING_FEN
from chess_engine.search_algorithms import SearchControl, TranspositionTable, negamax_alpha_beta_top

KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
CORPUS = (
    ("startpos", STARTING_FEN, 4, 197281, 3),
    ("kiwipete", KIWIPETE, 3, 97862, 3),
)


def _git(*args):
    try:
        return subprocess.check_output(
            ["git", *args], cwd=Path(__file__).resolve().parents[1],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _environment():
    revision = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain") if revision else None
    return {
        "revision": revision,
        "working_tree_dirty": bool(status) if status is not None else None,
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "logical_cpus": os.cpu_count(),
    }


def _rates(nodes, seconds):
    return {"nodes": nodes, "seconds": seconds, "nodes_per_second": nodes / seconds}


def _run_case(name, fen, perft_depth, expected_perft, search_depth):
    board = ChessBoard(fen)
    start = perf_counter()
    nodes = board.perft(perft_depth)
    perft = _rates(nodes, perf_counter() - start)
    if nodes != expected_perft:
        raise RuntimeError(f"{name} perft({perft_depth}) produced {nodes}; expected {expected_perft}")

    search = {}
    for mode in ("uncached", "fresh_table"):
        table = TranspositionTable() if mode == "fresh_table" else None
        control = SearchControl()
        start = perf_counter()
        move, score = negamax_alpha_beta_top(board, search_depth, table=table, control=control)
        search[mode] = {
            **_rates(control.nodes, perf_counter() - start),
            "move": move, "score": float(score),
        }
    if search["uncached"]["score"] != search["fresh_table"]["score"]:
        raise RuntimeError(f"{name} cached and uncached search scores differ")
    return {
        "position": name,
        "fen": fen,
        "perft": {"depth": perft_depth, **perft},
        "search": {"depth": search_depth, **search},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")

    environment = _environment()
    runs = [[_run_case(*case) for case in CORPUS] for _ in range(args.repeat)]
    print(json.dumps({"environment": environment, "runs": runs}, indent=2))


if __name__ == "__main__":
    main()
