"""Command line: python -m traintracks {solve,generate} ..."""
from __future__ import annotations

import argparse
import json
import sys
import time

from .generator import generate
from .logic import difficulty, logic_solve
from .puzzle import Puzzle, solution_to_rows
from .solver import solve


def cmd_solve(args) -> int:
    puzzle = Puzzle.load(args.file)
    print(puzzle.render())
    t = time.perf_counter()
    res = solve(puzzle, limit=args.limit)
    ms = (time.perf_counter() - t) * 1000
    for i, sol in enumerate(res.solutions, 1):
        print(f"\nSolution {i}:")
        print(puzzle.render(sol))
    more = "" if res.complete else f" (stopped at {args.limit})"
    print(f"\n{len(res.solutions)} solution(s){more}, {res.nodes} search nodes, {ms:.1f} ms")
    logic = logic_solve(puzzle)
    if logic.solved:
        print(f"Solvable by deduction: {difficulty(logic.lookaheads)} "
              f"({logic.lookaheads} lookahead step(s))")
    else:
        print("Not solvable by the deduction rules alone (needs trial and error)")
    return 0 if res.unique else 1


def puzzle_record(puzzle: Puzzle, solution, pid: str) -> dict:
    logic = logic_solve(puzzle)
    data = puzzle.to_json()
    data["id"] = pid
    data["difficulty"] = difficulty(logic.lookaheads) if logic.solved else "unrated"
    data["solution"] = solution_to_rows(solution, puzzle.rows, puzzle.cols)
    return data


def cmd_generate(args) -> int:
    out = []
    for path in args.include:
        p = Puzzle.load(path)
        res = solve(p, limit=2)
        if not res.unique:
            print(f"{path}: not uniquely solvable, skipped", file=sys.stderr)
            continue
        pid = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        out.append(puzzle_record(p, res.solutions[0], pid))
    for i in range(args.count):
        seed = args.seed + i
        diff = args.difficulty or ("easy", "medium", "hard")[i % 3]
        g = generate(args.rows, args.cols, min_len=args.min_len, max_len=args.max_len,
                     max_extra_givens=args.max_hints, difficulty=diff, seed=seed)
        p = g.puzzle
        p.name = f"Puzzle {seed}"
        out.append(puzzle_record(p, g.solution, f"g{seed}"))
        if not args.quiet:
            print(f"#{i + 1} seed={seed} {g.difficulty} length={len(g.solution)} "
                  f"hints={len(p.givens) - 2} lookaheads={g.lookaheads}", file=sys.stderr)
            if args.output is None:
                print(p.render(), file=sys.stderr)
    text = json.dumps(out, separators=(",", ":"))
    if args.output and args.output.endswith(".js"):
        # A script the web page can load directly (works from file:// too).
        text = f"window.PUZZLES = {text};\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {len(out)} puzzles to {args.output}", file=sys.stderr)
    else:
        print(text)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="traintracks")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("solve", help="solve a puzzle JSON file")
    s.add_argument("file")
    s.add_argument("--limit", type=int, default=2, help="stop after this many solutions")
    s.set_defaults(func=cmd_solve)

    g = sub.add_parser("generate", help="generate uniquely solvable puzzles as JSON")
    g.add_argument("-n", "--count", type=int, default=1)
    g.add_argument("-o", "--output", help="output file (default: stdout)")
    g.add_argument("--seed", type=int, default=1, help="seed of the first puzzle")
    g.add_argument("--rows", type=int, default=8)
    g.add_argument("--cols", type=int, default=8)
    g.add_argument("--min-len", type=int, default=22)
    g.add_argument("--max-len", type=int, default=36)
    g.add_argument("--max-hints", type=int, default=3, help="max hints beyond the villages")
    g.add_argument("--difficulty", choices=["easy", "medium", "hard"],
                   help="default: cycle through easy, medium, hard")
    g.add_argument("--include", nargs="*", default=[], help="puzzle files to put first")
    g.add_argument("-q", "--quiet", action="store_true")
    g.set_defaults(func=cmd_generate)

    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
