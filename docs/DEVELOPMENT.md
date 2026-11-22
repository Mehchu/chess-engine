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
check node counts and scores alongside elapsed time. The summary reports
median elapsed time and median nodes per second, and the report keeps every
individual run. Run `python -m benchmark --quiescence` to measure the
capture, promotion, and check-evasion search used by the CLI and UCI.
The default report retains static leaves for comparison with older runs.

### Relative playing strength

Build or check out a reference engine separately, then pass its UCI executable
as the opponent. For a fair comparison, give both engines the same limit.

```sh
python -m tools.match_benchmark --opponent /path/to/reference-engine --depth 3
python -m tools.match_benchmark --opponent /path/to/reference-engine --movetime-ms 100
```

The candidate defaults to this repository's Linux launcher. Override it with
`--candidate` to compare other executables. Each starting FEN is played twice,
with the engine colours reversed. The report shows wins, draws, losses, games
that hit the ply cap, and the candidate's points fraction over completed pairs.
It also reports median and maximum move latency, including UCI communication,
and a histogram of the depths reported by each engine.
Use `--positions` with one playable FEN per line to expand the default corpus.
Use larger position sets for strength comparisons. The small default corpus is
a screening benchmark and does not provide an Elo estimate.

For a quick check using the same build on both sides, compare depth two
against depth one.

```sh
python -m tools.match_benchmark --opponent bin/chess-engine-uci.sh \
  --depth 2 --opponent-depth 1 --max-plies 100
```


To compare search limits against a fixed depth-two anchor, keep the position
suite and ply cap identical across runs. For example, compare a depth limit
and a per-move budget using the same build.

```sh
python -m tools.match_benchmark --opponent bin/chess-engine-uci.sh \
  --depth 3 --opponent-depth 2 --max-plies 100
python -m tools.match_benchmark --opponent bin/chess-engine-uci.sh \
  --movetime-ms 35 --opponent-depth 2 --max-plies 100
```

To use a strength-limited Stockfish as the opponent, pass the nominal
UCI rating explicitly. The report records both UCI options sent to the
opponent.

```sh
python -m tools.match_benchmark --opponent /path/to/stockfish \
  --opponent-elo 1320 --movetime-ms 100 --max-plies 120
```

Stockfish's UCI Elo is calibrated at a different time control. Treat these
matches as comparisons against the stated build and setting. For details
on the limiter, see the [Stockfish FAQ](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html).

## Evaluation experiments

```sh
python -m tune_evaluation
```

The experiment compares candidate weights in colour-swapped self-play.
The JSON lines include starting FENs and distinguish completed games from
games that reached the ply cap. Use `--help` to select a candidate,
a validation suite, or a custom FEN list.

## UCI clients

Select the absolute path to `bin/chess-engine-uci.sh` as the engine executable in
your Linux GUI. The launcher works from any working directory. It uses the
repository's `.venv` when present, then falls back to `python3`. Set
`CHESS_ENGINE_PYTHON` to use a different interpreter with NumPy installed.
You can also run `python -m uci` from the repository root.

A client can send `uci`, `isready`, and then a position such as
`position startpos moves e2e4 e7e5`. Use `go depth 3` for fixed-depth search
or `go infinite` and `stop` for analysis. The engine returns one `bestmove`
per search. It uses `0000` when no legal move exists.

## Lichess bot

Install the [lichess-bot bridge](https://github.com/lichess-bot-devs/lichess-bot)
separately. Copy the [example configuration](../examples/lichess-bot.yml)
to a location outside this repository. Set `engine.dir` to the absolute path
to this repository's `bin` directory and leave `engine.name` set to
`chess-engine-uci.sh`. The example uses standard chess and disables pondering
and matchmaking.

Supply your bot account's token to the bridge using `LICHESS_BOT_TOKEN`.
Leave the YAML token field empty. For example, from the lichess-bot checkout
with its environment active, use Bash to enter the token without showing it
or putting it in the command history.

```bash
read -rsp 'Lichess bot token: ' LICHESS_BOT_TOKEN
printf '\n'
export LICHESS_BOT_TOKEN
python lichess-bot.py --config /path/outside/the/repository/lichess-bot.yml
unset LICHESS_BOT_TOKEN
```

See the [bridge configuration guide](https://github.com/lichess-bot-devs/lichess-bot/wiki/Configure-lichess-bot)
and [environment override](https://github.com/lichess-bot-devs/lichess-bot/blob/master/lib/config.py#L401-L422).

## Board indexing

The [square index reference](square-index-reference.txt) shows the bit indices
used by the engine. The first row represents rank one, starting with a1 at
index zero.
