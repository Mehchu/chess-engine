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
