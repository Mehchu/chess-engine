# Chess engine roadmap

The engine will own its position state, move rules, evaluation, and search. Keep python-chess in the development requirements as a test oracle. Each stage should pass before work begins on optimisations that depend on it.

## 1. Position state and coordinates (implemented)

**Findings.** `ChessBoard` rotates piece bitboards and swaps colour masks after every move. Rotation also treats castling flags and the en passant square index as spatial masks. The old FEN parser loses the active colour and clocks, and reverses en passant ranks. `notation_handling.py` and `referenceBoard.txt` already supply the fixed a1 = 0 coordinate convention.

Keep that convention throughout the engine and preserve the piece and colour masks. Use named fields for turn, castling, en passant, and both clocks. Derive occupancy from the colour masks or update it in one place. Wire the complete FEN codec into the live board when both colours can generate moves in fixed coordinates. Keep display as a read-only projection of the board.

**Acceptance.** Both colours and all six FEN fields survive round trips. Colour masks are disjoint, type masks are disjoint, and both unions give the same occupancy. A black-to-move position uses ordinary coordinates through the CLI.

## 2. Make and undo (implemented)

**Findings.** The move routine records history before validating the move. Undo restores only the array and permits consuming the initial snapshot. Promotion derives colour from the promotion character, and castling and en passant lack complete state transitions.

Use snapshots of board masks and rule state as the first undo implementation. They are straightforward to compare in regression tests. Clear any derived move cache or compute moves on demand. Apply normal moves, captures, promotions, castling, and en passant through the same transition path. Update clocks, castling rights on king and rook moves or rook captures, and the en passant target. Provide a checked public entry point and an internal path for generated moves.

**Acceptance.** Every move class has a make/undo regression, including black promotions and rook captures on original squares. Failed moves leave position and history intact. Undo restores the complete position, including after nested moves.

## 3. Legal move generation (verified)

**Findings.** The current generator produces pseudo-legal moves, permits king captures, can wrap king moves across files, and does not enforce castling or king safety. Game-over detection relies on cached moves and missing kings.

Reuse piece dispatch and sliding-ray traversal where appropriate. Add colour-aware attacks independent of legal move generation. Filter candidates by applying and restoring them and checking king safety. Check the king's starting and transit squares for castling. Distinguish checkmate from stalemate and specify draw handling before enabling history-sensitive search features.

**Acceptance.** Compare full UCI move sets and resulting positions with python-chess using curated fixtures and fixed-seed legal playouts. Cover pins, double check, castling through check, en passant exposing the king, and all promotions. Add perft and root divide with canonical counts, including the starting position at depths 1–4 (20, 400, 8,902, 197,281) and Kiwipete at depths 1–3 (48, 2,039, 97,862). Keep fast cases in the default suite and run deeper cases separately.

## 4. Negamax and alpha–beta (verified)

**Implementation.** Plain negamax and alpha–beta now share the side-to-move score convention. The CLI uses uncached alpha–beta. Tests compare both algorithms with independent minimax and cover cutoff bounds and restoration after an exception.

Keep the existing material and piece-square baseline, verify table orientation, and define a single score convention at the search boundary. Implement plain negamax as a correctness reference. Test alpha–beta with caching disabled. Evaluate checkmate and stalemate at the horizon, score mate with ply distance, and restore the board in a finally block after every recursive move. Route CLI play through the verified entry point. Leave the unfinished Monte Carlo prototype outside the active path.

**Acceptance.** Compare both searches with a small independent minimax on forced mates, stalemates, and material positions for either side. Compare scores and membership in the set of equally best legal moves. Verify position and history restoration after normal searches and cutoffs.

## 5. Zobrist keys and transposition table (next)

**Findings.** The prototype XORs products of whole bitboards and random values. It omits explicit side to move and stores all scores as exact, including cutoff bounds.

Start with deterministic recomputation from colour, piece, square, side to move, castling rights, and en passant state. Define the en passant policy for repetition identity explicitly. Account for rule-50 clocks and path-dependent repetition when deciding whether an entry can be reused. Store depth and exact, lower, or upper bounds. Classify against the original search window and normalise mate distance across plies.

**Acceptance.** Changing each relevant field changes the key on targeted fixtures. Undo restores the key. With the table enabled, full-window scores agree with uncached search. Narrow-window tests cover both bound directions, and shallow entries cannot cut off deeper searches. If incremental hashing is added later, compare it with recomputation after every move and undo.

## 6. Benchmarks and UCI

**Findings.** The interactive CLI searches at a fixed depth and `Timer` prints elapsed time. There is no reproducible benchmark or UCI command loop.

Record a fixed perft and search corpus with depths, nodes, elapsed time, and nodes per second. Include interpreter version, hardware, commit, and table settings. Use the existing monotonic timer approach. Implement UCI with scripted subprocess tests for `uci`, `isready`, `ucinewgame`, `position`, `go depth`, `stop`, and `quit`. Keep diagnostic output off protocol stdout.

**Acceptance.** Benchmark runs reproduce node counts and report timings. Protocol transcripts produce legal best moves or `0000` at terminal positions and handle both starting positions and explicit FENs. Evaluate optimisations such as iterative deepening, move ordering, and quiescence only after the move generation and search gates pass.

## Suggested commit boundaries

- `chore: add runtime and development dependency files`
- `fix: round-trip complete FEN position state`
- `fix: keep board coordinates stable across make and undo`
- `feat: verify legal move generation with perft and python-chess`
- `fix: use filled glyphs for white pieces in the CLI`
- `fix: verify negamax and alpha-beta against reference search`
- `fix: store depth-qualified transposition bounds`
- `feat: add reproducible benchmarks and UCI support`
