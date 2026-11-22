from .board_representation import ChessBoard
from .fen_handling import InvalidFEN, STARTING_FEN
from .notation_handling import InvalidNotation
from .search_algorithms import TranspositionTable, negamax_alpha_beta_top
from .timer import Timer

TEST_FEN = "k5q1/8/8/8/8/8/8/K4Q2 w - - 0 1"


def main():
    """
    Main function to start the game.
    """
    while True:
        customFEN = input(
            "Enter in a valid FEN for the position you wish the computer to play, leave blank for default: "
        )
        if len(customFEN) == 0:
            customFEN = STARTING_FEN
        try:
            board = ChessBoard(
                customFEN
            )  # Creating a ChessBoard object with the specified FEN
            break
        except InvalidFEN as e:
            print(f"{e.message}, try again")

    playGame(board)


def _finished(board):
    reason = board.game_end_reason()
    if reason == "checkmate":
        winner = "Black" if board.white_to_move else "White"
        print(f"Checkmate. {winner} wins.")
    elif reason == "stalemate":
        print("Stalemate.")
    elif reason:
        print(f"Draw by {reason}.")
    return reason is not None


def playGame(board: ChessBoard):
    timer = Timer()
    depth = 4
    board.display_board()

    while not _finished(board):
        player_move = input("Enter your move: ")
        if player_move == "exit":
            return

        try:
            board.make_move(player_move)
        except InvalidNotation:
            print("Enter a move such as e2e4 or e7e8q.")
            continue
        except ValueError:
            print("Illegal move, try again.")
            continue

        if _finished(board):
            board.display_board()
            return

        timer.start()
        move, score = negamax_alpha_beta_top(board, depth, table=TranspositionTable())
        timer.stop()
        print(f"The evaluation is {-score / 100}")
        board.make_move(move)
        board.display_board()


if __name__ == "__main__":
    main()
