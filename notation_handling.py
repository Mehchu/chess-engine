# Creates an exception via inheritance which can be raised when invalid notation is attempted to be parsed
class InvalidNotation(ValueError):
    def __init__(self, notation: str):
        self.message = f'"{notation}" is invalid move notation'
        super().__init__(self.message)


# Creates an exception via inheritance which can be raised when an invalid square is attempted to be parsed
class InvalidSquare(Exception):
    def __init__(self, square: str):
        self.message = f'"{square}" is an invalid square'
        super().__init__(self.message)


def decompose_notation(notation: str) -> tuple[int, int, str | None]:
    if len(notation) not in (4, 5):
        raise InvalidNotation(notation)
    promotion = notation[4:].lower() or None
    if promotion is not None and promotion not in "qrbn":
        raise InvalidNotation(notation)
    try:
        return decode_square(notation[:2]), decode_square(notation[2:4]), promotion
    except (InvalidSquare, ValueError) as exc:
        raise InvalidNotation(notation) from exc


# Function to convert a numerical square into an algebraic square
def encode_square(numerical_square: int) -> str:
    if isOnBoard(numerical_square):  # First checks if the square is on the board
        return chr(numerical_square % 8 + 97) + str(
            numerical_square // 8 + 1
        )  # Converts the number to algebra e.g. 0 becomes a1, through mod and div and relevant ASCII conversions
    else:  # Raises an exception if the square is not on the board
        raise InvalidSquare(numerical_square)


# Function to convert an algebraic square to a numerical square
def decode_square(algebraic_square: str) -> int:
    square = (ord(algebraic_square[0]) - 97) + 8 * (
        int(algebraic_square[1]) - 1
    )  # Converts algebra to a number, through mod and div and relevant ASCII conversions
    if (
        isOnBoard(square)
        and algebraic_square[0]
        in "abcdefgh"  # Checks that the first character is in the first 8 letters of the alphabet
        and algebraic_square[1]
        in "12345678"  # Checks that the second character is in the first 8 integers of the positive integers
    ):
        return square  # Returns the converted square once validated
    else:
        raise InvalidSquare(
            algebraic_square
        )  # If an invalid square is converted then raise this exception


def isOnBoard(
    square: int,
) -> (
    bool
):  # Boolean expression to check if an inputted numerical square is on a standard chess board
    return 0 <= square < 64
