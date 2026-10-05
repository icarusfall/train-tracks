"""Random puzzle generator.

1. Lay a random self-avoiding line from one edge of the grid to another.
2. Read the row/column totals off it.
3. Show the pieces in the two village cells (as The Times does), then keep
   solving: while a second solution exists, reveal a cell where it differs
   from the intended line.
4. Try removing each extra hint again, keeping the puzzle unique, so only
   the hints that are needed remain.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .logic import DIFFICULTIES, UNKNOWN, logic_solve
from .logic import difficulty as difficulty_name
from .puzzle import DIRS, OPPOSITE, Puzzle, Terminal, piece
from .solver import solve


def _edge_sides(r: int, c: int, rows: int, cols: int) -> list[str]:
    sides = []
    if r == 0:
        sides.append("N")
    if r == rows - 1:
        sides.append("S")
    if c == 0:
        sides.append("W")
    if c == cols - 1:
        sides.append("E")
    return sides


def random_line(rows: int, cols: int, min_len: int, max_len: int,
                rng: random.Random, max_steps: int = 20000):
    """A random self-avoiding walk between two edge cells.

    Returns (cells, start_side, end_side) or None if no line was found."""
    edge_cells = [(r, c) for r in range(rows) for c in range(cols)
                  if _edge_sides(r, c, rows, cols)]
    start = rng.choice(edge_cells)
    start_side = rng.choice(_edge_sides(*start, rows, cols))
    target = rng.randint(min_len, max_len)

    path = [start]
    on_path = {start}
    # Each stack frame holds the untried moves out of the corresponding cell.
    stack = [_shuffled_moves(start, rows, cols, rng)]
    steps = 0
    while stack and steps < max_steps:
        steps += 1
        cur = path[-1]
        if len(path) >= target and len(path) >= 2:
            sides = [s for s in _edge_sides(*cur, rows, cols)
                     if not (cur == start and s == start_side)]
            if sides:
                return path, start_side, rng.choice(sides)
        moves = stack[-1]
        while moves:
            nxt = moves.pop()
            if nxt not in on_path:
                break
        else:
            on_path.discard(path.pop())
            stack.pop()
            continue
        path.append(nxt)
        on_path.add(nxt)
        stack.append(_shuffled_moves(nxt, rows, cols, rng))
    return None


def _shuffled_moves(cell, rows, cols, rng):
    r, c = cell
    moves = [(r + dr, c + dc) for dr, dc in DIRS.values()
             if 0 <= r + dr < rows and 0 <= c + dc < cols]
    rng.shuffle(moves)
    return moves


def line_pieces(cells, start_side, end_side) -> dict[tuple[int, int], str]:
    """Piece in each cell of a line given as a list of cells."""
    def side_towards(a, b):
        d = (b[0] - a[0], b[1] - a[1])
        return next(k for k, v in DIRS.items() if v == d)

    pieces = {}
    for i, cell in enumerate(cells):
        a = start_side if i == 0 else side_towards(cell, cells[i - 1])
        b = end_side if i == len(cells) - 1 else side_towards(cell, cells[i + 1])
        pieces[cell] = piece(a, b)
    return pieces


@dataclass
class Generated:
    puzzle: Puzzle
    solution: dict[tuple[int, int], str]
    nodes: int            # exhaustive-solver effort
    lookaheads: int       # deductions needing one-step lookahead (logic.py)
    difficulty: str


def generate(rows: int = 8, cols: int = 8, *, min_len: int = 22, max_len: int = 36,
             min_extra_givens: int = 1, max_extra_givens: int = 3,
             difficulty: str | None = None, allow_empty_lines: bool = False,
             seed: int | None = None, max_attempts: int = 2000) -> Generated:
    """Generate a puzzle with exactly one solution that can be solved by
    deduction (see logic.py). `difficulty` is None for any, or one of
    'easy', 'medium', 'hard'. Unless `allow_empty_lines`, every row and
    column has at least one piece of track (no totals of 0)."""
    rng = random.Random(seed)
    lo, hi = DIFFICULTIES[difficulty] if difficulty else (0, 10**9)
    for _ in range(max_attempts):
        line = random_line(rows, cols, min_len, max_len, rng)
        if line is None:
            continue
        cells, s_side, e_side = line
        if len(cells) > max_len:
            continue
        truth = line_pieces(cells, s_side, e_side)
        row_totals = [sum(1 for r, _ in cells if r == i) for i in range(rows)]
        col_totals = [sum(1 for _, c in cells if c == i) for i in range(cols)]
        if not allow_empty_lines and (0 in row_totals or 0 in col_totals):
            continue
        start = Terminal(cells[0][0], cells[0][1], s_side)
        end = Terminal(cells[-1][0], cells[-1][1], e_side)
        fixed = {cells[0]: truth[cells[0]], cells[-1]: truth[cells[-1]]}
        puzzle = Puzzle(row_totals, col_totals, start, end, dict(fixed))

        # Add hints until the intended line is the only solution.
        while True:
            res = solve(puzzle, limit=2)
            if res.unique:
                break
            other = next(s for s in res.solutions if s != truth)
            diffs = [c for c in truth if other.get(c) != truth[c] and c not in puzzle.givens]
            cell = rng.choice(diffs)
            puzzle.givens[cell] = truth[cell]
            if len(puzzle.givens) - len(fixed) > max_extra_givens + 3:
                break
        if not solve(puzzle, limit=2).unique:
            continue

        # Drop any hint that is no longer needed.
        extras = [c for c in puzzle.givens if c not in fixed]
        rng.shuffle(extras)
        for cell in extras:
            p = puzzle.givens.pop(cell)
            if not solve(puzzle, limit=2).unique:
                puzzle.givens[cell] = p

        # Like The Times, add friendly hints: always at least min_extra_givens,
        # and more if the puzzle is harder than asked for. Hints go where the
        # basic rules can't yet see, so each one actually helps.
        logic = logic_solve(puzzle)
        while logic.solved and len(puzzle.givens) - len(fixed) <= max_extra_givens and (
                len(puzzle.givens) - len(fixed) < min_extra_givens or logic.lookaheads > hi):
            basic = logic_solve(puzzle, max_level=1)
            open_cells = [c for c in truth if c not in puzzle.givens
                          and basic.cells[c[0] * cols + c[1]] == UNKNOWN]
            if not open_cells:
                break
            cell = rng.choice(open_cells)
            puzzle.givens[cell] = truth[cell]
            logic = logic_solve(puzzle)

        n_extra = len(puzzle.givens) - len(fixed)
        if not logic.solved or not (min_extra_givens <= n_extra <= max_extra_givens):
            continue
        if not lo <= logic.lookaheads <= hi:
            continue
        return Generated(puzzle, truth, solve(puzzle, limit=2).nodes,
                         logic.lookaheads, difficulty_name(logic.lookaheads))
    raise RuntimeError("could not generate a puzzle; try relaxing the constraints")
