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

## UCI and benchmarks

Run `python -m uci` from the repository root. The engine accepts
`uci`, `isready`, `ucinewgame`, `position startpos`, `position fen`,
`go`, `stop`, and `quit`. Both position forms accept a suffix such as
`moves e2e4 e7e5`. Use `go depth N` for fixed-depth analysis,
`go movetime N` for a per-move budget in milliseconds, or
`go wtime 60000 btime 60000 winc 1000 binc 1000` for clock-managed play.
Clock-managed searches also accept `movestogo`. A depth limit can be combined
with a time limit. Pondering and engine options remain unsupported.
[UCI protocol reference](https://www.wbec-ridderkerk.nl/html/UCIProtocol.html)

Run `python -m benchmark --repeat 2` to emit a JSON report for the starting
position and Kiwipete. It records the Git revision and dirty status, Python
and hardware details, perft counts, and depth-three search with the table
disabled and freshly initialised. Perft counts leaf positions. Search
counts every visited node, including transposition-table hits.

With the development requirements installed, run `python -m tune_evaluation`
to compare candidate evaluation weights in colour-swapped games. The JSON
report includes each starting FEN and separates outright results from games
that reached the ply cap.

The board API detects threefold and 50-move claims, including an intended move.
Search automatically ends only on the supported automatic rules. Claims are
available to callers through the board API. To retain repetition history, pass
the move list when setting a position. FEN alone supplies the current position
and move counters. [FIDE Laws of Chess, Articles 9.2–9.6](https://handbook.fide.com/chapter/E012023)

## Implementation

| Module | Responsibility |
| --- | --- |
| `board_representation.py` | Bitboards, move generation, move application and undo |
| `fen_handling.py` | FEN parsing, serialisation and board display |
| `notation_handling.py` | Coordinate notation and square indexing |
| `search_algorithms.py` | Game-tree search and transposition table |
| `evaluation_functions.py` | Material and positional evaluation |
| `timer.py` | Search timing |
| `main.py` | Interactive entry point |
| `uci.py` | Fixed-depth and clock-managed UCI entry point |
| `benchmark.py` | Fixed perft and search corpus with JSON reporting |
| `tune_evaluation.py` | Paired self-play for evaluation weight experiments |

## Development roadmap

See [the detailed roadmap](docs/ROADMAP.md) and [development progress](docs/PROGRESS.md). Run the regression suite with `python -m unittest discover -v`.

- [x] Correct position state, make/undo and FEN round trips.
- [x] Verify legal move generation, including checks, castling and en passant, with perft and python-chess.
- [x] Verify negamax and alpha–beta against an independent reference search.
- [x] Verify transposition-table keys and bound handling.
- [x] Record a reproducible perft and search benchmark.
- [x] Add fixed-depth and clock-managed UCI support for external chess interfaces.
- [ ] Measure changes to move ordering and quiescence search against the baseline.

## Technical focus

The project combines discrete mathematics, bit-level state representation, recursive search and heuristic evaluation. Future development prioritises correctness and reproducible performance measurements before adding more sophisticated evaluation features.
