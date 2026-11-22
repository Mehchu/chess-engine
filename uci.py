"""Depth-limited Universal Chess Interface entry point."""

import sys
from threading import Event, Lock, Thread

from board_representation import ChessBoard
from fen_handling import InvalidFEN, STARTING_FEN
from search_algorithms import (
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
        board = ChessBoard(" ".join(tokens[1:7]))
        rest = tokens[7:]
    else:
        raise ValueError("Expected position startpos or position fen <six fields>")

    if rest:
        if rest[0] != "moves":
            raise ValueError("Expected moves after the position")
        for move in rest[1:]:
            board.make_move(move)
    return board


def _score_text(score):
    if abs(score) < MATE_THRESHOLD:
        return f"cp {round(score)}"
    plies = MATE_SCORE - abs(score)
    moves = (plies + 1) // 2
    return f"mate {moves if score > 0 else -moves}"


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

    def _search(self, board, max_depth):
        moves = board.generate_legal_moves()
        if not moves or board.automatic_draw_reason() is not None:
            self._send("bestmove 0000")
            return
        best_move = moves[0]
        control = SearchControl(should_stop=self._stop.is_set)
        table = TranspositionTable()
        try:
            for depth in range(1, max_depth + 1):
                best_move, score = negamax_alpha_beta_top(
                    board, depth, table=table, control=control
                )
                self._send(f"info depth {depth} score {_score_text(score)} nodes {control.nodes}")
        except SearchStopped:
            pass
        self._send(f"bestmove {best_move}")

    def _stop_search(self):
        if self._worker is not None:
            self._stop.set()
            self._worker.join()
            self._worker = None

    def _go(self, tokens):
        if len(tokens) != 2 or tokens[0] != "depth":
            raise ValueError("Supported search command is go depth <positive integer>")
        depth = int(tokens[1])
        if depth < 1:
            raise ValueError("Search depth must be positive")
        self._stop_search()
        self._stop.clear()
        self._worker = Thread(target=self._search, args=(self.board, depth))
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


if __name__ == "__main__":
    UciEngine(sys.stdout).run(sys.stdin)
