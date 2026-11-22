from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from random import Random

from evaluation_functions import EvaluationFunction

MATE_SCORE = 100_000
MATE_THRESHOLD = 90_000
eval = EvaluationFunction()


class SearchStopped(Exception):
    """A caller requested that the search unwind."""


@dataclass
class SearchControl:
    """Count alpha–beta node visits and optionally check for cancellation."""

    should_stop: Callable[[], bool] | None = None
    nodes: int = 0

    def visit(self):
        if self.should_stop is not None and self.should_stop():
            raise SearchStopped()
        self.nodes += 1


class ZobristHash:
    """Recompute a 64-bit key from piece placement and rule state."""

    def __init__(self):
        rng = Random(0x5A4F4252495354)
        self._pieces = tuple(
            tuple(tuple(rng.getrandbits(64) for _ in range(64)) for _ in range(6))
            for _ in range(2)
        )
        self._black_to_move = rng.getrandbits(64)
        self._castling = tuple(rng.getrandbits(64) for _ in range(16))
        self._en_passant = tuple(rng.getrandbits(64) for _ in range(64))

    def generate_key(self, board):
        boards = board.piece_bitboards
        key = self._castling[board.castling_rights]
        if not board.white_to_move:
            key ^= self._black_to_move
        # Keep the raw FEN target, even when no legal capture is available.
        if board.en_passant is not None:
            key ^= self._en_passant[board.en_passant]
        for colour, occupancy in enumerate(boards[6:]):
            for piece, piece_mask in enumerate(boards[:6]):
                mask = occupancy & piece_mask
                while mask:
                    bit = mask & -mask
                    key ^= self._pieces[colour][piece][bit.bit_length() - 1]
                    mask ^= bit
        return key


class Bound(Enum):
    EXACT = auto()
    LOWER = auto()
    UPPER = auto()


@dataclass(frozen=True)
class TranspositionEntry:
    move: str | None
    score: float
    bound: Bound


class TranspositionTable:
    """Cache entries for one evaluation and draw policy at fixed search depths."""

    def __init__(self):
        self._hasher = ZobristHash()
        self._entries = {}

    def key_for(self, board):
        # Raw history is conservative: equivalent en passant targets may miss
        # a hit, but positions with different repetition histories cannot share it.
        history = tuple(
            (position.piece_boards, position.white_to_move, position.en_passant)
            for position in board.reversible_history()
        )
        return self._hasher.generate_key(board), board.halfmove_clock, history

    def lookup(self, key, depth):
        # Different horizons can yield different fixed-depth scores.
        return self._entries.get((key, depth))

    def store(self, key, depth, entry):
        self._entries[key, depth] = entry


def _adjust_mate_score(score, ply_offset):
    if score >= MATE_THRESHOLD:
        return score + ply_offset
    if score <= -MATE_THRESHOLD:
        return score - ply_offset
    return score


def _moves_or_score(board, depth, ply):
    if depth == 0:
        ended, terminal = board.is_game_over()
        if not ended:
            return (), eval.evaluate(board)
        return (), -MATE_SCORE + ply if terminal else 0

    moves = board.generate_legal_moves()
    if not moves:
        return (), -MATE_SCORE + ply if board.is_check() else 0
    if board.automatic_draw_reason() is not None:
        return (), 0
    return moves, None


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


def negamax_alpha_beta_top(
    board, depth, alpha=-float("inf"), beta=float("inf"), *, table=None, control=None
):
    """Return a move and side-to-move score, or a bound outside the window."""
    if depth < 0:
        raise ValueError("Search depth must be non-negative")
    if not alpha < beta:
        raise ValueError("Alpha must be less than beta")
    return _alpha_beta(board, depth, alpha, beta, 0, table, control)


def negamax_alpha_beta(board, depth, alpha=-float("inf"), beta=float("inf"), *, table=None):
    """Return just the root score or bound."""
    return negamax_alpha_beta_top(board, depth, alpha, beta, table=table)[1]


def _alpha_beta(board, depth, alpha, beta, ply, table, control):
    if control is not None:
        control.visit()
    if table is None:
        return _search_node(board, depth, alpha, beta, ply, table, control)

    key = table.key_for(board)
    entry = table.lookup(key, depth)
    if entry is not None:
        score = _adjust_mate_score(entry.score, -ply)
        if (entry.bound is Bound.EXACT
                or (entry.bound is Bound.LOWER and score >= beta)
                or (entry.bound is Bound.UPPER and score <= alpha)):
            return entry.move, score

    move, score = _search_node(board, depth, alpha, beta, ply, table, control)
    if score <= alpha:
        bound = Bound.UPPER
    elif score >= beta:
        bound = Bound.LOWER
    else:
        bound = Bound.EXACT
    table.store(key, depth, TranspositionEntry(move, _adjust_mate_score(score, ply), bound))
    return move, score


def _search_node(board, depth, alpha, beta, ply, table, control):
    moves, score = _moves_or_score(board, depth, ply)
    if score is not None:
        return None, score

    best_move, best_score = None, -float("inf")
    for move in moves:
        board.make_move(move)
        try:
            _, child_score = _alpha_beta(
                board, depth - 1, -beta, -alpha, ply + 1, table, control
            )
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
