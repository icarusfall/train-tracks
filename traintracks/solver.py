"""Exhaustive solver for Train Tracks.

The search lays track one cell at a time, starting at village A and following the
line until it reaches village B. Building the line as a single walk means it can
never cross itself, branch, or form a separate loop, so the only things left to
check are the row/column totals and the given pieces.

Each step is pruned with:
  * row/column totals: a full row or column cannot take more track;
  * given pieces: a given cell can only be entered through one of its two sides,
    and a cell next to a given that points at it must exit into that given;
  * reachability: a flood fill from the head of the line over the cells it could
    still use must reach B and every unvisited given, and must contain enough
    cells to make up every row's and column's shortfall.

The grid is held as an integer bitmask (bit r*cols + c) so the flood fill is a
handful of shifts per step.
"""
from __future__ import annotations

from dataclasses import dataclass

from .puzzle import DIRS, OPPOSITE, Puzzle, piece


@dataclass
class SolveResult:
    solutions: list[dict[tuple[int, int], str]]
    nodes: int            # search nodes visited: a rough measure of difficulty
    complete: bool        # False if the search stopped early at the solution limit

    @property
    def unique(self) -> bool:
        return self.complete and len(self.solutions) == 1


def solve(puzzle: Puzzle, limit: int = 2) -> SolveResult:
    """Find up to `limit` solutions. limit=2 is enough to test uniqueness."""
    R, C = puzzle.rows, puzzle.cols
    N = R * C
    ALL = (1 << N) - 1
    row_t, col_t = puzzle.row_totals, puzzle.col_totals

    row_mask = [sum(1 << (r * C + c) for c in range(C)) for r in range(R)]
    col_mask = [sum(1 << (r * C + c) for r in range(R)) for c in range(C)]
    not_first_col = ALL & ~col_mask[0]
    not_last_col = ALL & ~col_mask[C - 1]

    def spread(m: int) -> int:
        """Cells orthogonally adjacent to any cell in m."""
        return ((m << C) | (m >> C) | ((m & not_last_col) << 1)
                | ((m & not_first_col) >> 1)) & ALL

    # Neighbour table: nbr[i][d] = index of neighbour in direction d, or -1.
    nbr = []
    for i in range(N):
        r, c = divmod(i, C)
        entry = {}
        for d, (dr, dc) in DIRS.items():
            rr, cc = r + dr, c + dc
            entry[d] = rr * C + cc if 0 <= rr < R and 0 <= cc < C else -1
        nbr.append(entry)

    given = {r * C + c: set(p) for (r, c), p in puzzle.givens.items()}
    given_mask = sum(1 << i for i in given)
    s = puzzle.start.row * C + puzzle.start.col
    e = puzzle.end.row * C + puzzle.end.col
    s_side, e_side = puzzle.start.side, puzzle.end.side

    result = SolveResult(solutions=[], nodes=0, complete=True)
    if sum(row_t) != sum(col_t):
        return result
    # The terminal cells' outward sides must agree with any given piece there.
    if s in given and s_side not in given[s]:
        return result
    if e in given and e_side not in given[e]:
        return result

    rc = [0] * R
    cc = [0] * C
    path: list[tuple[int, str, str]] = []   # (cell, entry side, exit side)

    def feasible(head: int, visited: int) -> bool:
        open_cells = 0
        for r in range(R):
            if rc[r] < row_t[r]:
                open_cells |= row_mask[r]
        col_open = 0
        for c in range(C):
            if cc[c] < col_t[c]:
                col_open |= col_mask[c]
        allowed = open_cells & col_open & ~visited
        if not (allowed >> e) & 1:
            return False
        reach = spread(1 << head) & allowed
        while True:
            grown = reach | (spread(reach) & allowed)
            if grown == reach:
                break
            reach = grown
        if not (reach >> e) & 1:
            return False
        if given_mask & ~visited & ~reach:
            return False
        for r in range(R):
            if rc[r] + (reach & row_mask[r]).bit_count() < row_t[r]:
                return False
        for c in range(C):
            if cc[c] + (reach & col_mask[c]).bit_count() < col_t[c]:
                return False
        return True

    def record() -> None:
        sol = {}
        for cell, a, b in path:
            sol[divmod(cell, C)] = piece(a, b)
        result.solutions.append(sol)

    def dfs(head: int, entry: str, visited: int) -> bool:
        """Extend the line from `head` (entered through side `entry`).
        Returns False to abort the whole search once the limit is reached."""
        result.nodes += 1
        if head == e:
            if (rc == row_t and cc == col_t and given_mask & ~visited == 0
                    and e_side != entry):
                path.append((head, entry, e_side))
                record()
                path.pop()
                if len(result.solutions) >= limit:
                    result.complete = False
                    return False
            return True

        if head in given:
            exits = given[head] - {entry}
        else:
            exits = {"N", "S", "E", "W"} - {entry}

        # An unvisited given that points at this cell must be our next cell.
        forced = None
        for d in ("N", "S", "E", "W"):
            n = nbr[head][d]
            if n >= 0 and n in given and not (visited >> n) & 1 and OPPOSITE[d] in given[n]:
                if forced is not None:
                    return True
                forced = d
        if forced is not None:
            if forced not in exits:
                return True
            exits = {forced}

        for d in exits:
            n = nbr[head][d]
            if n < 0 or (visited >> n) & 1:
                continue
            nr, nc = divmod(n, C)
            if rc[nr] >= row_t[nr] or cc[nc] >= col_t[nc]:
                continue
            back = OPPOSITE[d]
            if n in given and back not in given[n]:
                continue
            rc[nr] += 1
            cc[nc] += 1
            nv = visited | (1 << n)
            path.append((head, entry, d))
            ok = True
            if n == e or feasible(n, nv):
                ok = dfs(n, back, nv)
            path.pop()
            rc[nr] -= 1
            cc[nc] -= 1
            if not ok:
                return False
        return True

    sr, sc = divmod(s, C)
    if row_t[sr] < 1 or col_t[sc] < 1:
        return result
    rc[sr] += 1
    cc[sc] += 1
    dfs(s, s_side, 1 << s)
    return result
