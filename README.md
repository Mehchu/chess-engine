# Chess Engine

A Python chess-engine prototype exploring bitboard representations, game-tree search and heuristic position evaluation. The aim is to implement the underlying algorithms rather than delegate search to an existing chess engine.

## Features

- 64-square integer bitboards for piece placement and occupancy.
- Move generation for all six piece types, including promotion candidates.
- FEN position parsing and terminal board visualisation.
- Experimental minimax and negamax search, including alpha–beta pruning.
- Material and piece-square-table evaluation.
- Prototype position hashing and transposition-table caching.
- Interactive command-line interface with search timing.

**Status:** early-stage experimental engine. Legal moves and position restoration are covered by perft and python-chess comparisons. Draw adjudication beyond stalemate, search correctness, and UCI support remain in development.

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

## Implementation

| Module | Responsibility |
| --- | --- |
| `board_representation.py` | Bitboards, move generation, move application and undo |
| `fen_handling.py` | FEN parsing, serialisation and board display |
| `notation_handling.py` | Coordinate notation and square indexing |
| `search_algorithms.py` | Game-tree search and prototype transposition table |
| `evaluation_functions.py` | Material and positional evaluation |
| `timer.py` | Search timing |
| `main.py` | Interactive entry point |

## Development roadmap

See [the detailed roadmap](docs/ROADMAP.md) and [development progress](docs/PROGRESS.md). Run the regression suite with `python -m unittest discover -v`.

- [x] Correct position state, make/undo and FEN round trips.
- [x] Verify legal move generation, including checks, castling and en passant, with perft and python-chess.
- [ ] Verify negamax and alpha–beta against an independent reference search.
- [ ] Correct transposition table keys and bound handling.
- [ ] Introduce iterative deepening, move ordering and quiescence search.
- [ ] Benchmark search throughput and document measured improvements.
- [ ] Add UCI support for use with external chess interfaces.

## Technical focus

The project combines discrete mathematics, bit-level state representation, recursive search and heuristic evaluation. Future development prioritises correctness and reproducible performance measurements before adding more sophisticated evaluation features.
