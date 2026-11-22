# Chess engine roadmap

The engine will own its position state, move rules, evaluation, and search. Keep python-chess in the development requirements as a test oracle. Each stage should pass before work begins on optimisations that depend on it.

## 1. Position state and coordinates (implemented)

**Findings.** `ChessBoard` rotates piece bitboards and swaps colour masks after every move. Rotation also treats castling flags and the en passant square index as spatial masks. The old FEN parser loses the active colour and clocks, and reverses en passant ranks. `notation_handling.py` and the [square index reference](square-index-reference.txt) already supply the fixed a1 = 0 coordinate convention.

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

**Implementation.** Plain negamax and alpha–beta now share the side-to-move score convention. Uncached alpha–beta remains the reference for cached search. Tests compare both algorithms with independent minimax and cover cutoff bounds and restoration after an exception.

Keep the existing material and piece-square baseline, verify table orientation, and define a single score convention at the search boundary. Implement plain negamax as a correctness reference. Test alpha–beta with caching disabled. Evaluate checkmate and stalemate at the horizon, score mate with ply distance, and restore the board in a finally block after every recursive move. Route CLI play through the verified entry point. Leave the unfinished Monte Carlo prototype outside the active path.

**Acceptance.** Compare both searches with a small independent minimax on forced mates, stalemates, and material positions for either side. Compare scores and membership in the set of equally best legal moves. Verify position and history restoration after normal searches and cutoffs.

## 5. Zobrist keys and transposition table (verified)

**Implementation.** Recompute a seeded 64-bit key from colour, piece, square, turn, castling, and the raw FEN en passant target. Key table entries by that hash, halfmove clock, and exact remaining depth. Use exact, lower, and upper bounds classified against the original window. Normalise mate scores relative to the cached position.

**Draw policy.** Table reuse includes the known reversible history. The repetition key includes the en passant target only when a legal capture is available. The table uses raw historical targets conservatively, which can miss some equivalent entries.

**Acceptance.** Changing each relevant field changes the key on targeted fixtures. Undo restores the key. With the table enabled, full-window scores agree with uncached search. Narrow-window tests cover both bound directions, and shallow entries cannot cut off deeper searches. If incremental hashing is added later, compare it with recomputation after every move and undo.

## 6. Benchmarks and UCI (verified)

**Implementation.** The fixed benchmark corpus reports perft, cached and uncached search, timings, and environment metadata as JSON. A separate UCI entry point serves fixed-depth searches. It reports completed depths and uses cooperative cancellation so it can acknowledge `isready` during search and return the latest completed result on `stop`.

**Verification.** Two benchmark runs reproduced node counts, scores, and moves. Subprocess tests cover handshake, positions and move lists, fixed-depth search, cancellation, terminal `0000`, and shutdown.

**Follow-up.** Dead-position adjudication and claim submission through the user interfaces remain open. Measure any move ordering or quiescence changes against the fixed benchmark and keep the current correctness checks.

## 7. Repetition and move-count draws (verified)

Threefold and 50-move draw claims are available through the board API, including
when an intended move would qualify. Fivefold repetition and the 75-move rule
end search automatically. Checkmate takes precedence on the move-count
threshold. The same FEN can have different draw outcomes depending on prior
moves, so the transposition table qualifies reuse with the known reversible
history. [FIDE Laws of Chess, Articles 9.2–9.6](https://handbook.fide.com/chapter/E012023)

## 8. Clock-managed UCI (verified)

`go movetime` sets a per-move limit. For clock-managed play, the engine uses
the active side's remaining time and increment, divides the clock by
`movestogo` or 30 as a default, and keeps a small reserve. A depth limit
can be combined with either time control. The worker checks a monotonic
deadline at each search node and retains the last completed result.

The next step is a bounded transposition table so longer searches have a
predictable memory footprint.

## 9. Profile-guided move and search performance (verified)

Precompute attack masks, test king safety using projected occupancy, and
stream generated moves into search. Keep the existing evaluation and move
ordering as regression baselines. The before/after results are recorded in
[PROGRESS.md](PROGRESS.md#move-generation-and-search-performance).

## 10. Phase-dependent king evaluation (implemented)

Blend the original king table with an endgame centralisation table as
non-pawn material disappears. Keep the other piece values and tables as a
baseline. Targeted tests verify the intended position preferences. Measure
playing strength in paired self-play before tuning or adding new evaluation
terms.

## 11. Passed pawns and bishop pair (implemented)

Reward more advanced passed pawns, with a larger bonus in the endgame.
Award a small material bonus for bishops on both square colours. Use the paired self-play runner to screen weights before adding more terms.
The first screen and held-out run kept the current defaults. See the
[progress log](PROGRESS.md#passed-pawns-and-bishop-pair) for research sources
and measurements.

## 12. Quiescence search and engine review

The CLI and UCI search captures and promotions after nominal depth zero.
Checked positions search legal evasions and receive no standing evaluation.
The extension is capped at six additional plies. Terminal rules still apply
at the cap, and a nonterminal position still in check receives a neutral
fallback score. Quiescence and static entries use separate cache keys.
Use `python -m benchmark --quiescence` to measure the active leaf policy.
[Classical Stockfish quiescence reference](https://github.com/official-stockfish/Stockfish/blob/sf_11/src/search.cpp#L1228)

| Priority | Area | Finding and next change |
| --- | --- | --- |
| 1 | Position validation and draws | The FEN codec checks field syntax, so UCI can load a board with missing kings. Add playable-position validation at interactive and UCI boundaries. The engine also keeps playing king-and-bishop versus king. Add conservative insufficient-material detection and test it against the reference. |
| 2 | Search and move ordering | Quiescence-enabled alpha–beta orders captures and promotions but starts each iteration without the previous best move. Try the previous iteration's principal move first, then measure quiet-move ordering. Measure nodes, completed depth, and match outcomes. Keep score reuse at the existing exact-depth policy. |
| 3 | Move generation | Native tactical generation now avoids quiet move tuples, but still walks sliding rays and projects occupancy for each candidate. Profile checker and pin masks to restrict candidates, and use a dedicated capture path that jumps to the first blocker on each ray. Preserve the current generator as a differential reference until both paths agree on perft divide and seeded positions. |
| 4 | Position updates and cache memory | Every searched ply saves a full snapshot. Every table probe recomputes the Zobrist key and packages reversible history. Bound the table first, then measure incremental keys and smaller undo records against the current recomputation and snapshot references. Keep history-aware score isolation. |
| 5 | Evaluation and test data | The evaluator has material, piece-square, passed-pawn, and bishop-pair terms. The existing weight matches left many games unfinished. Expand the opening and tactical corpora before tuning or adding mobility or king-safety terms. |
| 6 | UCI and maintenance | The time allocator uses a fixed moves-to-go estimate and a hard deadline. Measure completed depth and deadline overruns on full clocked games before adding soft limits or position-dependent budgets. Report a full principal variation for GUI analysis. The unused Monte Carlo scaffold contains incomplete methods and should be isolated or retired in a focused cleanup. |

## Suggested commit boundaries

- `chore: add runtime and development dependency files`
- `fix: round-trip complete FEN position state`
- `fix: keep board coordinates stable across make and undo`
- `feat: verify legal move generation with perft and python-chess`
- `fix: use filled glyphs for white pieces in the CLI`
- `fix: verify negamax and alpha-beta against reference search`
- `fix: store depth-qualified transposition bounds`
- `feat: add reproducible perft and search benchmarks`
- `feat: add a depth-limited UCI entry point`
- `fix: adjudicate repetition and move-count draws`
- `feat: support clock-managed UCI search`
- `perf: speed up king-safety checks and search traversal`
- `feat: taper king evaluation by material phase`
- `feat: evaluate passed pawns and opposite-colour bishop pairs`
- `feat: extend tactical leaves with quiescence search`
