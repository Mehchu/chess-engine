"""Measure relative playing strength in colour-swapped matches between UCI engines."""

import argparse
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
import json
from pathlib import Path
from statistics import median
from time import perf_counter

import chess
import chess.engine

from .benchmark import _environment
from .tune_evaluation import POSITIONS


DEFAULT_ENGINE = Path(__file__).resolve().parents[1] / "bin" / "chess-engine-uci.sh"
POINTS = {"win": 1, "draw": 0.5, "loss": 0}


@asynccontextmanager
async def _engine(executable, timeout):
    transport, protocol = await asyncio.wait_for(
        chess.engine.UciProtocol.popen([str(executable.resolve())]), timeout
    )
    try:
        await asyncio.wait_for(protocol.initialize(), timeout)
        yield protocol
        await asyncio.wait_for(protocol.quit(), timeout)
    finally:
        transport.close()


async def _play_game(fen, candidate_colour, engines, limits, timings, max_plies, timeout):
    board = chess.Board(fen)
    game = object()

    for _ in range(max_plies):
        if board.is_game_over():
            break

        index = 0 if board.turn == candidate_colour else 1
        started = perf_counter()
        result = await asyncio.wait_for(
            engines[index].play(board, limits[index], game=game, info=chess.engine.INFO_BASIC), timeout
        )
        timings[index].append((perf_counter() - started, result.info.get("depth")))

        if result.move is None or result.move not in board.legal_moves:
            raise RuntimeError(f"Engine returned an illegal move in {board.fen()}: {result.move}")
        board.push(result.move)

    outcome = board.outcome()
    if outcome is None:
        result = "unfinished"
    elif outcome.winner is None:
        result = "draw"
    else:
        result = "win" if outcome.winner == candidate_colour else "loss"
    return {
        "result": result,
        "plies": len(board.move_stack),
        "termination": outcome.termination.name.lower() if outcome else "ply_limit",
    }


def _summarise(pairs):
    counts = Counter(game["result"] for pair in pairs for game in pair["games"])
    paired_points = [
        sum(POINTS[game["result"]] for game in pair["games"])
        for pair in pairs
        if all(game["result"] in POINTS for game in pair["games"])
    ]
    complete = len(paired_points)
    return {
        "wins": counts["win"], "draws": counts["draw"], "losses": counts["loss"],
        "unfinished": counts["unfinished"], "complete_pairs": complete,
        "points_fraction_in_complete_pairs": sum(paired_points) / (2 * complete) if complete else None,
    }


def _timing_summary(samples):
    latencies = [seconds for seconds, _ in samples]
    depths = [depth for _, depth in samples if depth is not None]
    return {
        "moves": len(samples),
        "median_move_seconds": median(latencies) if latencies else None,
        "max_move_seconds": max(latencies) if latencies else None,
        "median_reported_depth": median(depths) if depths else None,
        "moves_by_reported_depth": dict(sorted(Counter(depths).items())),
    }


async def _run_match(paths, positions, limits, max_plies, timeout, opponent_elo=None):
    started = perf_counter()
    timings = ([], [])
    pairs = []
    async with _engine(paths[0], timeout) as candidate, _engine(paths[1], timeout) as opponent:
        opponent_options = {}
        if opponent_elo is not None:
            opponent_options = {"UCI_LimitStrength": True, "UCI_Elo": opponent_elo}
            await asyncio.wait_for(opponent.configure(opponent_options), timeout)
        engines = (candidate, opponent)
        identities = [engine.id for engine in engines]
        for fen in positions:
            games = []
            for colour in (chess.WHITE, chess.BLACK):
                game = await _play_game(fen, colour, engines, limits, timings, max_plies, timeout)
                games.append({"candidate_colour": chess.COLOR_NAMES[colour], **game})
            pairs.append({"fen": fen, "games": games})

    return {
        "environment": _environment(),
        "engines": [
            {
                "role": role, "executable": str(path.resolve()), "id": identity,
                "limit": {"depth": limit.depth, "time_seconds": limit.time},
                "uci_options": options,
                **_timing_summary(samples),
            }
            for role, path, identity, limit, samples, options in zip(
                ("candidate", "opponent"), paths, identities, limits, timings,
                ({}, opponent_options)
            )
        ],
        "max_plies": max_plies,
        "elapsed_seconds": perf_counter() - started,
        "results": _summarise(pairs),
        "pairs": pairs,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_ENGINE)
    parser.add_argument("--opponent", type=Path, required=True)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--depth", type=int, default=2, help="Candidate depth (also used for the opponent by default)")
    group.add_argument("--movetime-ms", type=int, help="Candidate per-move time budget, shared by default")
    parser.add_argument("--opponent-depth", type=int, help="Use fixed depth for the opponent instead of the shared limit")
    parser.add_argument("--opponent-elo", type=int,
                        help="Configure UCI_LimitStrength and UCI_Elo on the opponent")
    parser.add_argument("--max-plies", type=int, default=120)
    parser.add_argument("--timeout", type=float, default=10, help="Maximum wait per UCI operation in seconds")
    parser.add_argument("--positions", type=Path, help="Optional file with one FEN per line")
    args = parser.parse_args()

    if args.depth < 1 or args.max_plies < 1 or not 0 < args.timeout < float("inf"):
        parser.error("depth, max plies, and timeout must be positive and finite")
    if args.opponent_elo is not None and args.opponent_elo < 1:
        parser.error("opponent Elo must be positive")
    if args.opponent_depth is not None and args.opponent_depth < 1:
        parser.error("opponent depth must be positive")
    if args.movetime_ms is not None:
        if args.movetime_ms < 1:
            parser.error("movetime must be positive")
        seconds = args.movetime_ms / 1000
        if seconds >= args.timeout:
            parser.error("timeout must exceed the move-time budget")
        candidate_limit = chess.engine.Limit(time=seconds)
    else:
        candidate_limit = chess.engine.Limit(depth=args.depth)
    opponent_limit = (candidate_limit if args.opponent_depth is None
                      else chess.engine.Limit(depth=args.opponent_depth))
    limits = candidate_limit, opponent_limit

    try:
        positions = POSITIONS if args.positions is None else tuple(
            line.strip() for line in args.positions.read_text().splitlines() if line.strip()
        )
        if not positions or any(
            not board.is_valid() or board.is_game_over() for board in map(chess.Board, positions)
        ):
            parser.error("positions must contain at least one valid, playable FEN")
        report = asyncio.run(_run_match(
            (args.candidate, args.opponent), positions, limits, args.max_plies, args.timeout,
            opponent_elo=args.opponent_elo,
        ))
    except (OSError, ValueError, RuntimeError, chess.engine.EngineError, asyncio.TimeoutError) as exc:
        parser.exit(1, f"Match benchmark failed: {str(exc) or type(exc).__name__}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
