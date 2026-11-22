from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from itertools import chain
from random import Random

from .board_representation import Move, move_to_uci
from .evaluation_functions import EvaluationFunction
from .notation_handling import decompose_notation

MATE_SCORE = 100_000
MATE_THRESHOLD = 90_000
MAX_QUIESCENCE_PLIES = 6
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
    move: Move | None
    score: float
    bound: Bound


class TranspositionTable:
    """Bound the number of exact-depth cache entries with FIFO eviction."""

    def __init__(self, max_entries=32_768):
        if not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("The table requires at least one entry")
        self._max_entries = max_entries
        self._hasher = ZobristHash()
        self._entries = OrderedDict()

    def __len__(self):
        return len(self._entries)

    def key_for(self, board, *, quiescence=False):
        # Raw history is conservative: equivalent en passant targets may miss
        # a hit, but positions with different repetition histories cannot share it.
        history = tuple(
            (position.piece_boards, position.white_to_move, position.en_passant)
            for position in board.reversible_history()
        )
        return self._hasher.generate_key(board), board.halfmove_clock, history, quiescence

    def lookup(self, key, depth):
        # Different horizons can yield different fixed-depth scores.
        return self._entries.get((key, depth))

    def store(self, key, depth, entry):
        slot = key, depth
        if slot not in self._entries and len(self._entries) >= self._max_entries:
            self._entries.popitem(last=False)
        self._entries[slot] = entry


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

    moves = board._legal_moves()
    first = next(moves, None)
    if first is None:
        return (), -MATE_SCORE + ply if board.is_check() else 0
    if board.automatic_draw_reason() is not None:
        return (), 0
    return chain((first,), moves), None


def negamax(board, depth):
    """Return a best move and exact score from the root side's perspective."""
    if depth < 0:
        raise ValueError("Search depth must be non-negative")
    move, score = _negamax(board, depth, 0)
    return (move_to_uci(move) if move is not None else None), score


def _negamax(board, depth, ply):
    moves, score = _moves_or_score(board, depth, ply)
    if score is not None:
        return None, score

    best_move, best_score = None, -float("inf")
    for move in moves:
        board._push(move)
        try:
            _, child_score = _negamax(board, depth - 1, ply + 1)
        finally:
            board.undo_move()

        score = -child_score
        if score > best_score:
            best_move, best_score = move, score
    return best_move, best_score


def negamax_alpha_beta_top(
    board, depth, alpha=-float("inf"), beta=float("inf"), *, table=None, control=None,
    quiescence=False, preferred_move=None
):
    """Return a move and side-to-move score, or a bound outside the window.

    Enable quiescence to extend leaves with captures, promotions and check evasions.
    """
    if depth < 0:
        raise ValueError("Search depth must be non-negative")
    if not alpha < beta:
        raise ValueError("Alpha must be less than beta")
    preferred = decompose_notation(preferred_move) if preferred_move is not None else None
    move, score = _alpha_beta(board, depth, alpha, beta, 0, table, control, quiescence, preferred)
    return (move_to_uci(move) if move is not None else None), score


def negamax_alpha_beta(
    board, depth, alpha=-float("inf"), beta=float("inf"), *, table=None, quiescence=False
):
    """Return just the root score or bound."""
    return negamax_alpha_beta_top(
        board, depth, alpha, beta, table=table, quiescence=quiescence
    )[1]


def _alpha_beta(board, depth, alpha, beta, ply, table, control, quiescence, preferred=None):
    if control is not None:
        control.visit()
    if table is None:
        return _search_node(board, depth, alpha, beta, ply, table, control, quiescence, preferred)

    key = table.key_for(board, quiescence=quiescence)
    entry = table.lookup(key, depth)
    if entry is not None:
        score = _adjust_mate_score(entry.score, -ply)
        if (entry.bound is Bound.EXACT
                or (entry.bound is Bound.LOWER and score >= beta)
                or (entry.bound is Bound.UPPER and score <= alpha)):
            return entry.move, score

    move, score = _search_node(board, depth, alpha, beta, ply, table, control, quiescence, preferred)
    if score <= alpha:
        bound = Bound.UPPER
    elif score >= beta:
        bound = Bound.LOWER
    else:
        bound = Bound.EXACT
    table.store(key, depth, TranspositionEntry(move, _adjust_mate_score(score, ply), bound))
    return move, score


def _search_node(board, depth, alpha, beta, ply, table, control, quiescence, preferred):
    if depth == 0 and quiescence:
        return None, _quiescence(board, alpha, beta, ply, control)

    moves, score = _moves_or_score(board, depth, ply)
    if score is not None:
        return None, score

    if preferred is not None:
        def priority(move):
            return move == preferred, board._tactical_priority(move) if quiescence else 0

        moves = sorted(moves, key=priority, reverse=True)
    elif quiescence:
        moves = sorted(moves, key=board._tactical_priority, reverse=True)

    best_move, best_score = None, -float("inf")
    for move in moves:
        board._push(move)
        try:
            _, child_score = _alpha_beta(
                board, depth - 1, -beta, -alpha, ply + 1, table, control, quiescence
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


def _quiescence(board, alpha, beta, ply, control, remaining=MAX_QUIESCENCE_PLIES):
    # Check terminal rules before accepting static evaluation. A checked side
    # must move, so it cannot use its current score as a lower bound.
    evasions, terminal_score = _moves_or_score(board, 1, ply)
    if terminal_score is not None:
        return terminal_score
    in_check = board.is_check()
    if remaining == 0:
        # Avoid treating a missing evasion search as a reliable static score.
        return 0 if in_check else eval.evaluate(board)
    if in_check:
        best_score = -float("inf")
        moves = evasions
    else:
        best_score = eval.evaluate(board)
        if best_score >= beta:
            return best_score
        alpha = max(alpha, best_score)
        moves = board._legal_moves(tactical_only=True)

    for move in sorted(moves, key=board._tactical_priority, reverse=True):
        board._push(move)
        try:
            if control is not None:
                control.visit()
            score = -_quiescence(board, -beta, -alpha, ply + 1, control, remaining - 1)
        finally:
            board.undo_move()
        best_score = max(best_score, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best_score


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
