"""Launch the interactive engine."""

from chess_engine.cli import main, playGame as playGame
from chess_engine.fen_handling import STARTING_FEN as STARTING_FEN


if __name__ == "__main__":
    main()
