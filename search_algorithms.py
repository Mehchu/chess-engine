from evaluation_functions import EvaluationFunction
import numpy as np


class TranspositionTable:  # Class for storing previously evaluated positions to save on computations at higher depths
    def __init__(self):
        self.table = (
            {}
        )  # Initialises a dictionary to store the hashed key and depth and evaluation

    def lookup(
        self, key
    ):  # Method to fetch the data related to the unique hash of the position
        return self.table.get(key)

    def store(
        self, key, score, depth
    ):  # Stores an evaluated position in the dictionary with relevant information
        self.table[key] = {"score": score, "depth": depth}


class ZobristHash:  # Hashing algorithm to uniquely hash a ChessBoard objects's array of 13 bitboards
    def __init__(self, shape=(13,)):
        self.keys = np.random.randint(
            2**64, size=shape, dtype=np.uint64
        )  # Assigns each bitboard a random integer

    def generate_key(self, position):  # Hashes the array of bitboards to a unique key
        return np.bitwise_xor.reduce(position * self.keys)


MATE_SCORE = 100_000
eval = EvaluationFunction()


def _moves_or_score(board, depth, ply):
    if depth == 0:
        ended, _ = board.is_game_over()
        if not ended:
            return (), eval.evaluate(board)
        moves = ()
    else:
        moves = board.generate_legal_moves()
        if moves:
            return moves, None

    return moves, -MATE_SCORE + ply if board.is_check() else 0


def negamax(board, depth):
    """Return a best move and exact score from the root side's perspective."""
    if depth < 0:
        raise ValueError("Search depth must be non-negative")
    return _negamax(board, depth, 0)


def _negamax(board, depth, ply):
    moves, score = _moves_or_score(board, depth, ply)
    if score is not None:
        return None, score

    best_move, best_score = None, -float("inf")
    for move in moves:
        board.make_move(move)
        try:
            _, child_score = _negamax(board, depth - 1, ply + 1)
        finally:
            board.undo_move()

        score = -child_score
        if score > best_score:
            best_move, best_score = move, score
    return best_move, best_score


def negamax_alpha_beta_top(board, depth, alpha=-float("inf"), beta=float("inf")):
    """Return a move and side-to-move score, or a bound outside the window."""
    if depth < 0:
        raise ValueError("Search depth must be non-negative")
    if not alpha < beta:
        raise ValueError("Alpha must be less than beta")
    return _alpha_beta(board, depth, alpha, beta, 0)


def negamax_alpha_beta(board, depth, alpha=-float("inf"), beta=float("inf")):
    """Return just the root score or bound."""
    return negamax_alpha_beta_top(board, depth, alpha, beta)[1]


def _alpha_beta(board, depth, alpha, beta, ply):
    moves, score = _moves_or_score(board, depth, ply)
    if score is not None:
        return None, score

    best_move, best_score = None, -float("inf")
    for move in moves:
        board.make_move(move)
        try:
            _, child_score = _alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
        finally:
            board.undo_move()

        score = -child_score
        if score > best_score:
            best_move, best_score = move, score
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best_move, best_score


class Node:
    def __init__(self, state):
        self.state = state
        self.children = {}  # Dictionary to store child nodes indexed by actions
        self.visits = 0
        self.reward = 0


def select(node):
    # Implement UCB to select a child node based on the current node's children
    # Recursively call select on the selected child node until a leaf node is reached
    pass


def expand(node):
    # Generate legal moves for the current board state
    legal_moves = node.state.generate_legal_moves()

    # Add child nodes for unexplored moves
    for move in legal_moves:
        if move not in node.children:
            new_state = node.state.make_move(
                move
            )  # Apply the move to create a new state
            node.children[move] = Node(new_state)
    return node.children[move]


def simulate(node):
    # Simulate a game from the current board state until a terminal state is reached
    # Use a simulation policy (e.g., random moves) to determine actions in non-terminal states
    pass


def backpropagate(node, reward):
    # Update the visit count and reward of all nodes traversed from the selected node to the root node
    while node is not None:
        node.visits += 1
        node.reward += reward
        node = node.parent  # Move to the parent node


def monte_carlo(root):
    # Select the action with the highest expected reward based on the visit counts of child nodes of the root node
    best_action = max(
        root.children,
        key=lambda action: root.children[action].reward / root.children[action].visits,
    )
    return best_action
