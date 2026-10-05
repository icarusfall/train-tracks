"""Human-style deductive solver, used to grade puzzles.

The exhaustive solver in solver.py proves a puzzle has one solution, but a
puzzle can be unique and still only crackable by trial and error. This solver
only makes deductions a person would make, so if it finishes, the puzzle can
be solved by reasoning alone.

State: every cell is unknown / empty / track, and every edge between two cells
is unknown / joined / not joined.

Level 1 rules (applied repeatedly):
  * a row or column whose total is reached has no more track; one that needs
    all its remaining unknown cells gets track in all of them;
  * a track cell joins exactly two neighbours: two joins rule out the rest, and
    if only two sides are still possible both are joined;
  * a cell that can no longer have two joins is empty; a joined cell is track;
  * joining two ends of the same piece of track would close a loop, so that
    edge is not joined; joining A's piece to B's piece is only allowed if that
    would use up all the track.
Level 2 adds one-step lookahead: suppose a cell is track (or empty), apply the
level 1 rules, and if that leads to a contradiction the opposite must be true.
"""
from __future__ import annotations

from dataclasses import dataclass

from .puzzle import DIRS, OPPOSITE, Puzzle, piece

UNKNOWN, EMPTY, TRACK = 0, 1, 2      # cell states
U, YES, NO = 0, 1, 2                 # edge states
SIDES = ("N", "S", "E", "W")


class Contradiction(Exception):
    pass


class _Grid:
    """Board geometry shared by all states of one puzzle."""

    def __init__(self, puzzle: Puzzle):
        self.p = puzzle
        R, C = self.R, self.C = puzzle.rows, puzzle.cols
        self.N = R * C
        # Edge list: (cell_a, cell_b); cell_b == -1 for a village's outward side.
        self.edges: list[tuple[int, int]] = []
        self.cell_edges: list[dict[str, int]] = [dict() for _ in range(self.N)]
        for r in range(R):
            for c in range(C):
                i = r * C + c
                for d in ("S", "E"):
                    dr, dc = DIRS[d]
                    rr, cc = r + dr, c + dc
                    if rr < R and cc < C:
                        eid = len(self.edges)
                        self.edges.append((i, rr * C + cc))
                        self.cell_edges[i][d] = eid
                        self.cell_edges[rr * C + cc][OPPOSITE[d]] = eid
        self.terminal_edges = []
        for t in (puzzle.start, puzzle.end):
            i = t.row * C + t.col
            eid = len(self.edges)
            self.edges.append((i, -1))
            self.cell_edges[i][t.side] = eid
            self.terminal_edges.append(eid)
        self.lines = ([[r * C + c for c in range(C)] for r in range(R)]
                      + [[r * C + c for r in range(R)] for c in range(C)])
        self.line_totals = list(puzzle.row_totals) + list(puzzle.col_totals)
        self.total = sum(puzzle.row_totals)


class _State:
    def __init__(self, g: _Grid, cells=None, edges=None):
        self.g = g
        self.cells = cells if cells is not None else [UNKNOWN] * g.N
        self.edges = edges if edges is not None else [U] * len(g.edges)

    def copy(self) -> "_State":
        return _State(self.g, self.cells[:], self.edges[:])

    def set_cell(self, i: int, v: int) -> bool:
        if self.cells[i] == v:
            return False
        if self.cells[i] != UNKNOWN:
            raise Contradiction
        self.cells[i] = v
        return True

    def set_edge(self, e: int, v: int) -> bool:
        if self.edges[e] == v:
            return False
        if self.edges[e] != U:
            raise Contradiction
        self.edges[e] = v
        return True

    def solved(self) -> bool:
        return UNKNOWN not in self.cells and U not in self.edges

    # ---- level 1 ---------------------------------------------------------
    def propagate(self) -> None:
        changed = True
        while changed:
            changed = self._cells() | self._lines()
            if not changed:
                changed = self._loops()

    def _cells(self) -> bool:
        changed = False
        g = self.g
        for i in range(g.N):
            ce = g.cell_edges[i]
            yes = [e for e in ce.values() if self.edges[e] == YES]
            open_ = [e for e in ce.values() if self.edges[e] == U]
            st = self.cells[i]
            if yes and st != TRACK:
                changed |= self.set_cell(i, TRACK)
                st = TRACK
            if st == EMPTY:
                for e in open_:
                    changed |= self.set_edge(e, NO)
            elif st == TRACK:
                if len(yes) > 2 or len(yes) + len(open_) < 2:
                    raise Contradiction
                if len(yes) == 2:
                    for e in open_:
                        changed |= self.set_edge(e, NO)
                elif len(yes) + len(open_) == 2:
                    for e in open_:
                        changed |= self.set_edge(e, YES)
            elif len(yes) + len(open_) < 2:
                changed |= self.set_cell(i, EMPTY)
        return changed

    def _lines(self) -> bool:
        changed = False
        for cells, total in zip(self.g.lines, self.g.line_totals):
            t = sum(1 for i in cells if self.cells[i] == TRACK)
            u = [i for i in cells if self.cells[i] == UNKNOWN]
            if t > total or t + len(u) < total:
                raise Contradiction
            if u and t == total:
                for i in u:
                    changed |= self.set_cell(i, EMPTY)
            elif u and t + len(u) == total:
                for i in u:
                    changed |= self.set_cell(i, TRACK)
        return changed

    def _loops(self) -> bool:
        """Rule out edges that would close a loop or finish the line too early."""
        g = self.g
        parent = list(range(g.N))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for e, (a, b) in enumerate(g.edges):
            if b >= 0 and self.edges[e] == YES:
                ra, rb = find(a), find(b)
                if ra == rb:
                    raise Contradiction       # a closed loop
                parent[ra] = rb
        size: dict[int, int] = {}
        for i in range(g.N):
            if self.cells[i] == TRACK:
                r = find(i)
                size[r] = size.get(r, 0) + 1
        ra = find(g.edges[g.terminal_edges[0]][0])
        rb = find(g.edges[g.terminal_edges[1]][0])
        if ra == rb:
            # A and B are already connected: that must be the whole line.
            if size.get(ra, 0) != g.total or len(size) != 1:
                raise Contradiction
        changed = False
        for e, (a, b) in enumerate(g.edges):
            if b < 0 or self.edges[e] != U:
                continue
            x, y = find(a), find(b)
            if x == y:
                changed |= self.set_edge(e, NO)
            elif {x, y} == {ra, rb}:
                if size.get(x, 1) + size.get(y, 1) < g.total or len(size) > 2:
                    changed |= self.set_edge(e, NO)
        return changed


@dataclass
class LogicResult:
    solved: bool
    level: int                         # highest rule level needed (0 if unsolved)
    lookaheads: int                    # number of level-2 deductions made
    cells: list[int]                   # final cell states (row-major)


def logic_solve(puzzle: Puzzle, max_level: int = 2) -> LogicResult:
    g = _Grid(puzzle)
    st = _State(g)
    try:
        for e in g.terminal_edges:
            st.set_edge(e, YES)
        for (r, c), p in puzzle.givens.items():
            i = r * g.C + c
            st.set_cell(i, TRACK)
            for d in SIDES:
                e = g.cell_edges[i].get(d)
                if e is None:
                    if d in p:
                        raise Contradiction
                    continue
                st.set_edge(e, YES if d in p else NO)
        st.propagate()
    except Contradiction:
        return LogicResult(False, 0, 0, st.cells)

    level, lookaheads = 1, 0
    while not st.solved() and max_level >= 2:
        progress = False
        for i in range(g.N):
            if st.cells[i] != UNKNOWN:
                continue
            for guess, other in ((TRACK, EMPTY), (EMPTY, TRACK)):
                trial = st.copy()
                try:
                    trial.set_cell(i, guess)
                    trial.propagate()
                except Contradiction:
                    try:
                        st.set_cell(i, other)
                        st.propagate()
                    except Contradiction:
                        return LogicResult(False, 0, lookaheads, st.cells)
                    progress = True
                    lookaheads += 1
                    level = 2
                    break
        if not progress:
            for e in range(len(g.edges)):
                if st.edges[e] != U:
                    continue
                for guess, other in ((YES, NO), (NO, YES)):
                    trial = st.copy()
                    try:
                        trial.set_edge(e, guess)
                        trial.propagate()
                    except Contradiction:
                        try:
                            st.set_edge(e, other)
                            st.propagate()
                        except Contradiction:
                            return LogicResult(False, 0, lookaheads, st.cells)
                        progress = True
                        lookaheads += 1
                        level = 2
                        break
        if not progress:
            break
    return LogicResult(st.solved(), level if st.solved() else 0, lookaheads, st.cells)


DIFFICULTIES = {"easy": (0, 0), "medium": (1, 4), "hard": (5, 10**9)}


def difficulty(lookaheads: int) -> str:
    return next(name for name, (lo, hi) in DIFFICULTIES.items() if lo <= lookaheads <= hi)


def grade(puzzle: Puzzle) -> str:
    """'easy' (level 1 rules only), 'medium' (a few lookaheads), 'hard' (many),
    or 'unsolvable' (needs deeper trial and error, or has no unique solution)."""
    res = logic_solve(puzzle)
    return difficulty(res.lookaheads) if res.solved else "unsolvable"
