# Development progress

## 22 November 2026

- Reviewed board representation, FEN and notation handling, search, evaluation, CLI, timing, and repository setup. Recorded defects and verification gates in [ROADMAP.md](ROADMAP.md).
- Added FEN regression tests before changing the codec. The original code reproduced the wrong en passant index, missing castling placeholder, and acceptance of malformed input.
- Added an immutable `FenPosition` at the I/O boundary. It gives the active colour, flags, en passant target, and clocks explicit names while retaining the existing piece-type and colour masks. The legacy NumPy adapter keeps the current board constructor and display connected.
- Ran `.venv/bin/python -m unittest discover -v`. Four tests passed, including six-field round trips compared with python-chess and rejection of malformed FEN.
- Next increment is the live board's fixed coordinate system and complete make/undo snapshots. The legacy `ChessBoard` still rotates after moves and does not retain every FEN field. Legal move generation, search, and cache correctness remain unverified.
