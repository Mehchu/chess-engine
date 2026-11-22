# Development progress

## 22 November 2026

- Reviewed board representation, FEN and notation handling, search, evaluation, CLI, timing, and repository setup. Recorded defects and verification gates in [ROADMAP.md](ROADMAP.md).
- Added FEN regression tests before changing the codec. The original code reproduced the wrong en passant index, missing castling placeholder, and acceptance of malformed input.
- Added an immutable `FenPosition` at the I/O boundary. It gives the active colour, flags, en passant target, and clocks explicit names while retaining the existing piece-type and colour masks. The legacy NumPy adapter keeps the current board constructor and display connected.
- Ran `.venv/bin/python -m unittest discover -v`. Four tests passed, including six-field round trips compared with python-chess and rejection of malformed FEN.
- Next increment is the live board's fixed coordinate system and complete make/undo snapshots. The legacy `ChessBoard` still rotates after moves and does not retain every FEN field. Legal move generation, search, and cache correctness remain unverified.

### Fixed board state and legal moves

- The original board failed regressions for black-to-move FEN, rejected moves, castling, en passant, and promotion. The live board now uses fixed a1–h8 indices for both colours and keeps rule state in named fields. It retains the piece-type and colour masks, with Python integers for bit operations and a NumPy compatibility accessor for prototype search.
- Undo stores immutable snapshots of masks, turn, castling rights, en passant, and clocks. Occupancy is derived from the colour masks. The public move entry point checks legality before recording the move, and probes restore their snapshots in a finally block. Promotion retains the moving colour.
- Move generation shares ray traversal with attack detection, then verifies king safety after each candidate move. Castling also checks the starting and transit squares. Checkmate and stalemate are recognised from legal moves and check status. Repetition, move-count and dead-position draw adjudication remain future work.
- Compared complete move sets, occupancy, checked status, and full FEN against python-chess on tactical fixtures and three fixed-seed playouts, including complete undo. Root divide matches python-chess for Kiwipete at depth two. Perft matches the starting position through depth four and Kiwipete through depth three.
- Updated the CLI and existing evaluator for fixed coordinates. Removed two inactive evaluation helpers that depended on rotating the board. Kept the prototype search interface and included turn in its cache lookup. The search and table still need independent correctness tests, starting with uncached negamax and alpha–beta.
- Suggested commits: `fix: keep position state consistent across make and undo` and `test: verify legal move generation against perft and python-chess`. Keep the board and its search compatibility changes together when staging.

### Terminal glyphs and uncached search

- Swapped the terminal glyphs so White uses filled symbols and Black uses outlines. Added display assertions for both back ranks and pawns after a move.
- Replaced the duplicate prototype minimax paths with plain negamax and fail-soft alpha–beta. Both score from the side to move, handle checkmate and stalemate at depth zero, and prefer earlier mates using distance from the root. Every recursive move unwinds in a finally block.
- Removed the colour parameter from the search API because the evaluator already returns a side-to-move score. The CLI uses uncached alpha–beta at the existing two-ply setting. The experimental hash and table classes remain available for the next milestone.
- Checked both searches against a small White-relative minimax using python-chess for test positions and moves. Covered both colours, horizon terminal states, optimal-move sets, fail-high and fail-low bounds, evaluator orientation, and restoration after cutoffs and evaluation exceptions.
- Next milestone is deterministic Zobrist keys and a depth-qualified transposition table, with uncached alpha–beta as the comparison baseline.

### Zobrist hashing and transposition bounds

- Replaced the prototype whole-mask hash with deterministic piece-square Zobrist keys. Side to move, castling rights, and the raw en passant target contribute to the key. Make/undo round trips restore it for ordinary moves, castling, en passant, and promotion.
- The table qualifies lookups by halfmove clock and exact remaining depth. Scores from different horizons can differ, so even a deeper entry cannot substitute for a shallower fixed-depth result. Bound entries cut off only when they prove the current window fails. Mate scores are converted between root-relative and position-relative distances.
- The CLI creates a fresh table for each engine reply. Calling alpha–beta without a table still provides the uncached baseline.
- Regression tests verify cold and warm reuse, exact-depth isolation, halfmove isolation, fail-high and fail-low handling, and a cached mate score reused at a different ply. Repetition adjudication still needs a history-aware reuse policy.
- Next milestone is reproducible benchmarks and UCI support. Suggested commit `fix: add deterministic Zobrist keys and depth-qualified transposition bounds`.

### Benchmarks and UCI

- Added `python -m benchmark --repeat 2` for a fixed perft and search corpus with timings, node counts, rates, cache settings, and environment metadata.
- Recorded the following baseline over two runs on CPython 3.14.8 and Linux x86-64 from a working tree based on `e955496`. Both runs returned the same counts, scores, and moves.

| Position | Perft depth and nodes | Uncached search nodes at depth 3 | Fresh-table search nodes at depth 3 |
| --- | --- | ---: | ---: |
| Starting position | 4, 197,281 | 1,448 | 1,448 |
| Kiwipete | 3, 97,862 | 10,106 | 10,082 |

- Added a separate depth-limited UCI entry point. The worker searches successive depths and returns the last completed answer on `stop`, with a legal fallback if stopped before depth one. It shares the existing alpha–beta implementation and restores the board when cancellation unwinds.
- Verified subprocess transcripts and a handshake and depth-two search with the asynchronous python-chess UCI client. Clock-managed play, pondering, and draw adjudication beyond stalemate remain open.
- The synchronous python-chess smoke test timed out before it sent a search command. A standalone cross-thread asyncio wakeup also timed out in this environment. Direct subprocess transcripts and the asynchronous UCI client completed successfully.

### Repetition and move-count draws

- Added python-chess comparisons for threefold claims, fivefold repetition, and the 50- and 75-move thresholds. Tests cover intended moves, unusable and pinned en passant targets, undo, and checkmate on the threshold move.
- Search and both interfaces stop automatically on fivefold repetition and the 75-move rule. The board API reports claim availability separately. Submitting a claim through an interface and adjudicating dead positions remain open.
- Transposition reuse now includes the known reversible history. A regression searches identical FENs with different histories using the same table and gets the correct result for each.
- All 36 tests passed. Two benchmark runs reproduced perft counts, search node counts, best moves, and scores. The counts and scores matched the prior baseline.
- Suggested commit `fix: adjudicate repetition and move-count draws`.

### Clock-managed UCI

- Added fixed move time and side-specific UCI clocks, increments, and moves-to-go. The initial allocation spreads the clock over the reported moves-to-go or 30 by default, uses three quarters of the increment, and reserves up to 50 milliseconds of remaining time. An explicit move time overrides the clock estimate.
- The worker uses a monotonic deadline and the existing search cancellation callback. At the deadline it returns the most recent completed depth, with a legal fallback for zero or very short budgets.
- All 41 tests passed. Subprocess tests cover zero and short budgets, active-side clock selection, combined limits, readiness during search, and manual stop. The asynchronous python-chess UCI client returned legal moves with both time-control forms.
- Next step is to bound transposition-table memory. Suggested commit `feat: support clock-managed UCI search`.

### Move generation and search performance

- Profiled the existing corpus with `python -m cProfile -m benchmark`. King-safety checks, move validation, and leaf evaluation dominated the run.
- Precomputed attack masks and sliding paths. Candidate legality uses projected occupancy and captured-piece masks, including the en passant capture square and castling rook movement. Full make/undo snapshots are still used for moves played and nodes searched.
- Search consumes generated move tuples lazily and formats the root move for the caller. This avoids parsing and revalidating moves and stops generating siblings at a cutoff. Evaluation walks occupied bitboards with the original piece-square values oriented ahead of time.
- Compared medians from three runs of `python -m benchmark --repeat 3` before and after on CPython 3.14.8, based on `68ee361`. All perft counts, search node counts, best moves, and scores matched.

| Position | Workload | Before | After | Speedup |
| --- | --- | ---: | ---: | ---: |
| Starting position | Perft depth 4 | 2.032 s | 0.469 s | 4.3× |
| Kiwipete | Perft depth 3 | 0.924 s | 0.182 s | 5.1× |
| Starting position | Uncached search depth 3 | 0.155 s | 0.017 s | 9.0× |
| Kiwipete | Uncached search depth 3 | 1.276 s | 0.127 s | 10.1× |
| Starting position | Fresh-table search depth 3 | 0.171 s | 0.029 s | 5.9× |
| Kiwipete | Fresh-table search depth 3 | 1.422 s | 0.217 s | 6.5× |

- All 42 tests passed. Starting-position perft at depth five returned 4,865,609. Legal move sets, check status, and FEN agreed with python-chess across 1,200 additional seeded positions.
- The fresh table still costs more time than uncached search on both depth-three cases. These measurements cover the fixed corpus on one machine.
- Suggested commit `perf: speed up king-safety checks and search traversal`.

### Phase-dependent king evaluation

- The previous evaluator scored a sheltered king above a central king in a sparse pawn ending. The new evaluator blends the original king table with a centralisation table as queens, rooks and minor pieces come off the board. It precomputes the 25 blends and preserves the remaining material and piece-square terms.
- All 44 tests passed. Regressions verify the endgame preference, full-material baseline, and side-to-move symmetry.
- Three before/after benchmark runs preserved perft and depth-three moves, scores and node counts on the starting position and Kiwipete. Median uncached search rose from 0.0173 to 0.0179 seconds on the starting position and 0.1272 to 0.1314 seconds on Kiwipete. These fixtures measure throughput. Playing strength has yet to be measured with paired self-play.
- Suggested commit `feat: taper king evaluation by material phase`.

### Passed pawns and bishop pair

- Reviewed the classical Stockfish evaluator for established uses of passed-pawn rank bonuses and the bishop pair. This engine uses its own bitboard spans, phase weights, and square-colour test. [Passed-pawn evaluation](https://github.com/official-stockfish/Stockfish/blob/sf_11/src/evaluate.cpp#L112) · [Pawn spans](https://github.com/official-stockfish/Stockfish/blob/sf_11/src/pawns.cpp#L86) · [Bishop-pair material term](https://github.com/official-stockfish/Stockfish/blob/sf_11/src/material.cpp#L184)
- Passed-pawn bonuses grow with relative rank and increase as material comes off. Enemy pawns ahead on the same or adjacent files block the bonus. A doubled pawn behind a friendly pawn does not receive it. Owning bishops on both square colours adds 25 centipawns.
- The passed-pawn score matched a square-by-square reference on 5,000 seeded layouts. Regressions cover phase, both colours, file edges, doubled pawns, and the square-colour requirement.
- Three benchmark runs preserved both best moves and perft counts. Median uncached search time rose from 0.0177 to 0.0208 seconds on the starting position and from 0.1305 to 0.1475 seconds on Kiwipete. Kiwipete searched 449 fewer nodes and scored 25 centipawns higher.
- An exploratory fixed-depth self-play run used four endgame positions, swapped evaluators between colours, and capped games at 80 plies. At depth two, one game drew and seven reached the cap. The sample gave no useful playing-strength estimate.
- Suggested commit `feat: evaluate passed pawns and opposite-colour bishop pairs`.

### Evaluation weight experiments

- Added a repeatable colour-swapped self-play runner using the current evaluator as the control. Each candidate changes one term. Search runs at a fixed depth without a table, and python-chess adjudicates completed games. Games that hit the ply cap are reported separately. The pairing follows the same general test design as Stockfish's Fishtest. [Fishtest worker](https://github.com/official-stockfish/fishtest/blob/master/worker/games.py)
- The depth-two screen used eight positions, swapped colours for each candidate, and capped games at 120 plies. The material scale changes the nominal non-king values relative to the piece-square terms.

| Candidate change | Wins | Draws | Losses | Unfinished |
| --- | ---: | ---: | ---: | ---: |
| Material ×0.85 | 4 | 4 | 4 | 4 |
| Material ×1.15 | 4 | 3 | 5 | 4 |
| Endgame king centralisation ×0.5 | 2 | 3 | 2 | 9 |
| Endgame king centralisation ×1.5 | 4 | 3 | 4 | 5 |
| Passed pawns ×0.5 | 3 | 3 | 3 | 7 |
| Passed pawns ×1.5 | 3 | 5 | 4 | 4 |
| Bishop pair at 12 centipawns | 4 | 4 | 4 | 4 |
| Bishop pair at 40 centipawns | 4 | 4 | 4 | 4 |

Run the screen with `python -m tune_evaluation`. The validation command is
`python -m tune_evaluation --suite validation --depth 3 --max-plies 100 --candidate material-low --candidate king-high --candidate passers-low --candidate bishop-pair-high`.

| Depth-three candidate | Wins | Draws | Losses | Unfinished |
| --- | ---: | ---: | ---: | ---: |
| Material ×0.85 | 1 | 0 | 1 | 6 |
| Endgame king centralisation ×1.5 | 1 | 0 | 2 | 5 |
| Passed pawns ×0.5 | 1 | 0 | 1 | 6 |
| Bishop pair at 40 centipawns | 1 | 0 | 1 | 6 |

Across both runs, 96 of 160 games finished. None of the candidates recorded
more wins than losses. The small, hand-picked position sets and unfinished
games limit the comparison, so the current weights remain the reference.
All 51 tests passed, including candidate-score and runner checks.

Suggested commit `test: add paired self-play for evaluation weights`.

### Repository layout

- Moved the square index reference into `docs/`, added a development guide, and made README navigation reflect the repository layout. Updated Git ignore rules for local Python, coverage, and profiling artifacts.
- All 51 tests passed. The benchmark returned 197,281 and 97,862 perft nodes for the starting position and Kiwipete. The interactive CLI, evaluation runner, and fixed-depth and timed UCI client checks completed locally.
- The current checkout contains the UCI engine. Live Lichess verification requires the separate bot bridge and its configuration.
- Grouped engine modules under `chess_engine/` and development programs under `tools/`. Updated project imports and kept the root launch commands as thin wrappers. Python callers now import engine modules through `chess_engine`.

### UCI launcher and lichess-bot setup

- Added an executable Linux launcher and a token-free lichess-bot configuration. The launcher resolves the repository from its own path and keeps the bridge's token out of the engine subprocess.
- Added infinite analysis and node limits. Search reports its completed root move and only emits `0000` when there are no legal moves. An automatic draw with legal moves reports a zero score and returns a legal move.
- Extended subprocess tests to cover full repetition histories, special moves replayed from FEN, infinite search, node limits, and launching from another directory. A local UCI client also exercised clocked play and infinite analysis through the launcher.
- The example follows the bridge's configuration schema. A live authenticated Lichess game remains unverified.

### Speed and relative strength benchmarks

- Added median elapsed time and nodes per second to the existing perft and search report. Added a paired UCI match runner with fixed-depth and equal-move-time options, legal-move validation, per-engine latency, and separate reporting for unfinished games.
- Three speed runs gave median perft rates of about 418,000 nodes/s from the starting position and 547,000 nodes/s on Kiwipete. Median uncached depth-three search took 21 ms and 149 ms, respectively.
- A depth-two versus depth-one check with the same engine recorded 10 wins, three draws, zero losses, and three unfinished games from eight starting positions. The candidate scored 90% over the five completed pairs. This checks that the harness distinguishes search limits. It does not measure an engine revision or estimate Elo. The equal-time smoke test also completed.
- All 58 tests passed, including a subprocess match that verifies colour swapping and result reporting.
