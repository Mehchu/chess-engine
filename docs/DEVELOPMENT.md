# Development guide

Run commands from the repository root with the virtual environment active.
Install the development requirements once with
`python -m pip install -r requirements-dev.txt`. The engine implements its
own search and chess rules. The development tools use python-chess as a test
reference and self-play referee.

## Python modules

Use package imports when calling the engine from Python, for example
`from chess_engine.board_representation import ChessBoard` and
`from chess_engine.search_algorithms import negamax_alpha_beta_top`.
The scripts at the repository root launch the implementations in
`chess_engine/` and `tools/`.

## Regression suite

```sh
python -m unittest discover -v
```

For a focused protocol check, run `python -m unittest tests.test_uci -v`.
These tests launch the UCI process and exercise its handshake, position
commands, time controls, and shutdown locally.

## Benchmarks

```sh
python -m benchmark --repeat 2
```

The report includes perft and depth-three search for the starting position
and Kiwipete, with the cache disabled and freshly initialised. It records
the Git revision, dirty-tree status, interpreter, and hardware details.
Perft counts leaf positions. Search counts visited nodes, including
transposition-table hits. Compare repeated runs on the same machine and
check node counts and scores alongside elapsed time.

## Evaluation experiments

```sh
python -m tune_evaluation
```

The experiment compares candidate weights in colour-swapped self-play.
The JSON lines include starting FENs and distinguish completed games from
games that reached the ply cap. Use `--help` to select a candidate,
a validation suite, or a custom FEN list.

## UCI clients

Launch the engine with the virtual environment's interpreter and run
`python -m uci` from the repository root. A client should send `uci` and
`isready` before setting a position and searching it.

A Lichess deployment requires a separate bridge, such as lichess-bot, plus
its own account and configuration. Local UCI tests verify the engine side
of that connection. See the [lichess-bot configuration guide](https://github.com/lichess-bot-devs/lichess-bot/wiki/Configure-lichess-bot).

## Board indexing

The [square index reference](square-index-reference.txt) shows the bit indices
used by the engine. The first row represents rank one, starting with a1 at
index zero.
