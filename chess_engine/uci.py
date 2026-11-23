"""Universal Chess Interface entry point for depth and clock limits."""

import sys
from itertools import count
from threading import Event, Lock, Thread
from time import monotonic_ns

from .board_representation import ChessBoard
from .fen_handling import InvalidFEN, STARTING_FEN
from .search_algorithms import (
    MATE_SCORE,
    MATE_THRESHOLD,
    SearchControl,
    SearchStopped,
    TranspositionTable,
    negamax_alpha_beta_top,
)


def _parse_position(tokens):
    if tokens[:1] == ["startpos"]:
        board = ChessBoard(STARTING_FEN)
        rest = tokens[1:]
    elif tokens[:1] == ["fen"] and len(tokens) >= 7:
        board = ChessBoard.from_playable_fen(" ".join(tokens[1:7]))
        rest = tokens[7:]
    else:
        raise ValueError("Expected position startpos or position fen <six fields>")

    if rest:
        if rest[0] != "moves":
            raise ValueError("Expected moves after the position")
        for move in rest[1:]:
            board.make_move(move)
    return board


def _parse_go(tokens):
    if not tokens or tokens == ["infinite"]:
        return {}
    supported = {"depth", "nodes", "movetime", "wtime", "btime", "winc", "binc", "movestogo"}
    if len(tokens) % 2:
        raise ValueError("Search limits require a name and an integer")
    limits = {}
    for name, value in zip(tokens[::2], tokens[1::2]):
        if name not in supported or name in limits:
            raise ValueError(f"Unsupported or repeated search limit: {name}")
        minimum = 1 if name in ("depth", "nodes", "movestogo") else 0
        limit = int(value)
        if limit < minimum:
            raise ValueError(f"{name} must be at least {minimum}")
        limits[name] = limit
    if not limits.keys() & {"depth", "nodes", "movetime", "wtime", "btime"}:
        raise ValueError("Expected a depth, node, move-time, or clock limit")
    return limits


def _time_budget_ms(limits, white_to_move):
    if "movetime" in limits:
        return limits["movetime"]
    if "wtime" not in limits and "btime" not in limits:
        return None

    colour = "w" if white_to_move else "b"
    clock = f"{colour}time"
    if clock not in limits:
        raise ValueError(f"Missing {clock} for the side to move")
    remaining = limits[clock]
    increment = limits.get(f"{colour}inc", 0)
    moves = limits.get("movestogo", 30)
    reserve = min(50, remaining // 10)
    return min(remaining - reserve, remaining // moves + 3 * increment // 4)


def _score_text(score):
    if abs(score) < MATE_THRESHOLD:
        return f"cp {round(score)}"
    plies = MATE_SCORE - abs(score)
    moves = (plies + 1) // 2
    return f"mate {moves if score > 0 else -moves}"


def _search_iteration(board, depth, previous_score, preferred_move, table, control):
    alpha, beta = -float("inf"), float("inf")
    margin = 35
    if depth >= 3 and abs(previous_score) < MATE_THRESHOLD:
        alpha, beta = previous_score - margin, previous_score + margin

    while True:
        move, score = negamax_alpha_beta_top(
            board, depth, alpha, beta, table=table, control=control,
            quiescence=True, preferred_move=preferred_move,
        )
        if alpha < score < beta:
            return move, score
        if score <= alpha:
            alpha -= margin
        else:
            beta += margin
        margin *= 2


class UciEngine:
    def __init__(self, output):
        self.board = ChessBoard(STARTING_FEN)
        self._output = output
        self._output_lock = Lock()
        self._stop = Event()
        self._worker = None

    def _send(self, message):
        with self._output_lock:
            print(message, file=self._output, flush=True)

    def _search(self, board, limits, deadline):
        moves = board.generate_legal_moves()
        if not moves:
            self._send("bestmove 0000")
            return

        best_move = moves[0]
        if board.automatic_draw_reason() is not None:
            self._send("info depth 0 score cp 0 nodes 0")
            self._send(f"bestmove {best_move}")
            return

        node_limit = limits.get("nodes")
        max_depth = limits.get("depth")

        def should_stop():
            return (self._stop.is_set()
                    or (deadline is not None and monotonic_ns() >= deadline)
                    or (node_limit is not None and control.nodes >= node_limit))

        # Share quiet cutoff moves across iterations of this search.
        control = SearchControl(should_stop=should_stop, killers={})
        table = TranspositionTable()
        depths = count(1) if max_depth is None else range(1, max_depth + 1)
        score = 0
        try:
            for depth in depths:
                move, score = _search_iteration(
                    board, depth, score, best_move if depth > 1 else None, table, control
                )
                if move not in moves:
                    raise RuntimeError(f"Search returned an illegal root move: {move}")
                best_move = move
                self._send(f"info depth {depth} score {_score_text(score)} "
                           f"nodes {control.nodes} pv {best_move}")
        except SearchStopped:
            pass
        finally:
            self._send(f"bestmove {best_move}")

    def _stop_search(self):
        if self._worker is not None:
            self._stop.set()
            self._worker.join()
            self._worker = None

    def _go(self, tokens):
        limits = _parse_go(tokens)
        self._stop_search()
        # The worker makes temporary moves on the board while it searches.
        # Read the root side only after joining the previous worker.
        budget = _time_budget_ms(limits, self.board.white_to_move)
        deadline = None if budget is None else monotonic_ns() + budget * 1_000_000
        self._stop.clear()
        self._worker = Thread(target=self._search, args=(self.board, limits, deadline))
        self._worker.start()

    def run(self, commands):
        try:
            for line in commands:
                tokens = line.split()
                if not tokens:
                    continue
                command, *args = tokens
                try:
                    if command == "uci":
                        self._send("id name Chess Engine")
                        self._send("id author Mehchu")
                        self._send("uciok")
                    elif command == "isready":
                        self._send("readyok")
                    elif command == "ucinewgame":
                        self._stop_search()
                        self.board = ChessBoard(STARTING_FEN)
                    elif command == "position":
                        board = _parse_position(args)
                        self._stop_search()
                        self.board = board
                    elif command == "go":
                        self._go(args)
                    elif command == "stop":
                        self._stop_search()
                    elif command == "quit":
                        return
                except (InvalidFEN, ValueError) as exc:
                    print(exc, file=sys.stderr, flush=True)
        finally:
            self._stop_search()


def main():
    UciEngine(sys.stdout).run(sys.stdin)


if __name__ == "__main__":
    main()
