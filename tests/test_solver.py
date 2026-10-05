import os
import unittest

from traintracks.generator import generate
from traintracks.logic import grade, logic_solve
from traintracks.puzzle import DIRS, OPPOSITE, Puzzle, Terminal
from traintracks.solver import solve

HERE = os.path.dirname(__file__)
TIMES = os.path.join(HERE, "..", "puzzles", "times-2987.json")


def check_solution(test, puzzle, sol):
    """Independently verify a solution obeys every rule."""
    R, C = puzzle.rows, puzzle.cols
    for r in range(R):
        test.assertEqual(sum(1 for (rr, _) in sol if rr == r), puzzle.row_totals[r])
    for c in range(C):
        test.assertEqual(sum(1 for (_, cc) in sol if cc == c), puzzle.col_totals[c])
    for cell, p in puzzle.givens.items():
        test.assertEqual(sol.get(cell), p)
    # Every side either leads to a neighbour that leads back, or is a village exit.
    exits = {(puzzle.start.row, puzzle.start.col, puzzle.start.side),
             (puzzle.end.row, puzzle.end.col, puzzle.end.side)}
    for (r, c), p in sol.items():
        for d in p:
            dr, dc = DIRS[d]
            n = (r + dr, c + dc)
            if (r, c, d) in exits:
                continue
            test.assertIn(n, sol, f"{(r, c)} points {d} at an empty cell")
            test.assertIn(OPPOSITE[d], sol[n])
    # Walk from A: must visit every track cell (so no separate loops) and finish at B.
    cur, came = (puzzle.start.row, puzzle.start.col), puzzle.start.side
    seen = set()
    while True:
        seen.add(cur)
        out = sol[cur].replace(came, "", 1)
        if cur == (puzzle.end.row, puzzle.end.col) and out == puzzle.end.side:
            break
        dr, dc = DIRS[out]
        cur, came = (cur[0] + dr, cur[1] + dc), OPPOSITE[out]
        test.assertNotIn(cur, seen)
    test.assertEqual(seen, set(sol))


class TestSolver(unittest.TestCase):
    def test_times_2987_unique(self):
        p = Puzzle.load(TIMES)
        res = solve(p, limit=10)
        self.assertTrue(res.unique)
        check_solution(self, p, res.solutions[0])
        self.assertEqual(res.solutions[0][(0, 4)], "EW")

    def test_ambiguous(self):
        p = Puzzle([3, 4, 4, 0], [2, 3, 3, 3], Terminal(0, 1, "N"), Terminal(2, 3, "E"))
        res = solve(p, limit=10)
        self.assertTrue(res.complete)
        self.assertEqual(len(res.solutions), 2)
        for sol in res.solutions:
            check_solution(self, p, sol)

    def test_no_solution(self):
        p = Puzzle.load(TIMES)
        p.row_totals[0] = 6
        p.row_totals[1] = 8
        self.assertEqual(solve(p).solutions, [])

    def test_tiny_straight(self):
        p = Puzzle([1, 1], [0, 2], Terminal(0, 1, "N"), Terminal(1, 1, "S"))
        res = solve(p)
        self.assertTrue(res.unique)
        self.assertEqual(res.solutions[0], {(0, 1): "NS", (1, 1): "NS"})


class TestLogic(unittest.TestCase):
    def test_times_2987_by_deduction(self):
        p = Puzzle.load(TIMES)
        self.assertFalse(logic_solve(p, max_level=1).solved)
        res = logic_solve(p)
        self.assertTrue(res.solved)
        self.assertEqual(grade(p), "medium")

    def test_ambiguous_not_deducible(self):
        p = Puzzle([3, 4, 4, 0], [2, 3, 3, 3], Terminal(0, 1, "N"), Terminal(2, 3, "E"))
        self.assertFalse(logic_solve(p).solved)


class TestGenerator(unittest.TestCase):
    def test_generated_puzzles_are_unique(self):
        for seed, diff in enumerate(["easy", "medium", "hard", None, None]):
            g = generate(seed=seed, difficulty=diff)
            p, truth = g.puzzle, g.solution
            if diff:
                self.assertEqual(grade(p), diff)
            res = solve(p, limit=2)
            self.assertTrue(res.unique, f"seed {seed}")
            self.assertEqual(res.solutions[0], truth)
            check_solution(self, p, truth)
            self.assertNotIn(0, p.row_totals + p.col_totals)


if __name__ == "__main__":
    unittest.main()
