# Chess Engine

A Python chess-engine prototype exploring bitboard representations, game-tree search and heuristic position evaluation. The aim is to implement the underlying algorithms rather than delegate search to an existing chess engine.

## Features

- 64-square integer bitboards for piece placement and occupancy.
- Move generation for all six piece types, including promotion candidates.
- FEN position parsing and terminal board visualisation.
- Negamax and alpha–beta search with an optional transposition table.
- Material and piece-square evaluation with phase-dependent king and passed-pawn terms and a bishop-pair bonus.
- Deterministic Zobrist position hashing and depth-qualified cache bounds.
- Interactive command-line interface, fixed-depth and clock-managed UCI mode, and reproducible benchmarks.

**Status:** early-stage experimental engine. Legal moves and position restoration are covered by perft and python-chess comparisons. Uncached search is checked against independent minimax. Cached search is checked against the uncached baseline. Search adjudicates stalemate, fivefold repetition, and the 75-move rule. Dead-position detection and draw-claim submission remain in development.

## Getting started

Requires Python 3.10 or later and NumPy.

```bash
git clone https://github.com/Mehchu/chess-engine.git
cd chess-engine
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

For development, run `python -m pip install -r requirements-dev.txt` inside
the same virtual environment. This also installs python-chess as a reference
for tests.

Press Enter to load the standard starting position, or enter a FEN string to experiment with piece placement. Enter moves in coordinate notation, such as `e2e4`, or `exit` to quit. The current prototype searches at a fixed depth of four plies and prints an evaluation and elapsed search time. Both sides use standard board coordinates. For a promotion, append the piece letter, as in `e7e8q`.

## UCI

Register `bin/chess-engine-uci.sh` as the engine executable in a Linux GUI,
or run `python -m uci` from the repository root. The engine accepts
`uci`, `isready`, `ucinewgame`, `position startpos`, `position fen`,
`go`, `stop`, and `quit`. Both position forms accept a suffix such as
`moves e2e4 e7e5`. Use `go depth N` for fixed-depth analysis,
`go movetime N` for a per-move budget in milliseconds, or
`go wtime 60000 btime 60000 winc 1000 binc 1000` for clock-managed play.
Clock-managed searches also accept `movestogo`. A depth or node limit can be
combined with a time limit. Use `go infinite` for analysis until `stop`.
Pondering, restricted root moves, and engine options remain unsupported.
For bot setup, see the [Lichess guide](docs/DEVELOPMENT.md#lichess-bot)
and [example configuration](examples/lichess-bot.yml).
[UCI protocol reference](https://www.wbec-ridderkerk.nl/html/UCIProtocol.html)

The board API detects threefold and 50-move claims, including an intended move.
Search automatically ends only on the supported automatic rules. Claims are
available to callers through the board API. To retain repetition history, pass
the move list when setting a position. FEN alone supplies the current position
and move counters. [FIDE Laws of Chess, Articles 9.2–9.6](https://handbook.fide.com/chapter/E012023)

## Repository layout

| Path | Contents |
| --- | --- |
| [`chess_engine/`](chess_engine/) | Position state, move generation, FEN, evaluation, search, and interfaces |
| [`tools/`](tools/) | Speed benchmarks, paired UCI matches, and evaluation experiments |
| `main.py`, `uci.py`, `benchmark.py`, `tune_evaluation.py` | Root launchers for the existing run commands |
| `bin/`, `examples/` | Linux engine launcher and token-free lichess-bot configuration |
| `tests/` | Regression tests, perft, and python-chess comparisons |
| `docs/` | Development instructions, engineering decisions, and square index reference |

See the [development guide](docs/DEVELOPMENT.md) for test and benchmark commands,
the [roadmap](docs/ROADMAP.md) for priorities, and the [progress log](docs/PROGRESS.md)
for measurements and verification. Run `python -m benchmark --repeat 3`
to measure speed, or follow the [paired match instructions](docs/DEVELOPMENT.md#relative-playing-strength)
to compare playing strength against a reference executable.

## Technical focus

The project combines discrete mathematics, bit-level state representation, recursive search and heuristic evaluation. Future development prioritises correctness and reproducible performance measurements before adding more sophisticated evaluation features.
