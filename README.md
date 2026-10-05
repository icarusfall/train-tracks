# Train Tracks

A solver, generator and phone-friendly player for the *Train Tracks* puzzle
printed in The Times on Saturdays.

Lay track from village **A** to village **B**. The numbers give how many cells
in each row and column contain track. The track is a single unbroken line of
straight and curved pieces and never crosses itself. A few pieces are given.

## Layout

| Path | What it is |
| --- | --- |
| `traintracks/solver.py` | Exhaustive solver: finds every solution (or stops at 2 to prove uniqueness). |
| `traintracks/logic.py` | Human-style deductive solver, used to check a puzzle can be solved by reasoning and to grade difficulty. |
| `traintracks/generator.py` | Random puzzle generator: unique solution, solvable by deduction, Times-style hints. |
| `puzzles/` | Hand-entered puzzles (e.g. `times-2987.json`). |
| `web/` | The static web player (`index.html`, `app.js`, `style.css`, `puzzles.js`). |
| `tests/` | Unit tests. |

Requires Python 3.10+, no third-party packages.

## Solving a puzzle

```bash
python -m traintracks solve puzzles/times-2987.json
```

Puzzle files are JSON. Rows and columns count from 0, top-left. A piece names
the two sides it joins: `NS`, `EW`, `NE`, `NW`, `SE`, `SW`. Each village is a
cell on the edge plus the side the line leaves the grid through:

```json
{
  "row_totals": [7, 7, 3, 3, 2, 2, 3, 2],
  "col_totals": [5, 6, 2, 2, 7, 3, 2, 2],
  "start": {"row": 7, "col": 0, "side": "W"},
  "end":   {"row": 7, "col": 4, "side": "S"},
  "givens": [{"row": 0, "col": 6, "piece": "EW"}, ...]
}
```

## Difficulty

`logic.py` solves with the rules a person uses (full rows/columns, each track
cell joins exactly two neighbours, no closed loops, don't finish the line
early). When those stall it uses *lookahead*: "if this cell were track, would
that lead to a contradiction?". Difficulty is the number of lookahead steps
needed: **easy** 0, **medium** 1–4, **hard** 5+. Times No 2987 is medium
(2 lookaheads).

## Generating puzzles

```bash
python -m traintracks generate -n 300 --include puzzles/times-2987.json -o web/puzzles.js
```

Each puzzle is checked to have exactly one solution, and to be solvable by
deduction alone. `--difficulty easy|medium|hard` picks a level (by default the
levels take turns); `--seed` makes runs repeatable. Output ending in `.js` is
written as a script the web page loads; anything else is plain JSON.

## Web player

Open `web/index.html` in a browser, or serve the folder:

```bash
python -m http.server 8000 --directory web
```

- **Mouse:** left-click ✕ (no track), right-click ○ (track), double-click to clear, drag to mark several.
- **Touch:** tap once ✕, twice ○, three times to clear; drag to mark several the same way.
- **Keyboard:** arrow keys, X, O, Delete.
- **Check** colours each *completed* row and column total green (matches) or red (doesn't). Nothing is checked until you ask.
- When the last square is filled in and the board is right, the circles turn into track, laid piece by piece from A to B, and a train runs along it. A finished but wrong board isn't flagged until you press **Check**.
- **Undo**, **Reset** (undoable), **New puzzle** by difficulty, and **Show solution**.
- Progress is saved in the browser; the URL (`#g42`) links to a specific puzzle.

## Deploying to Vercel

`vercel.json` serves the `web/` folder as a static site with no build step.
In Vercel: *Add New → Project → Import* this GitHub repo and deploy with the
defaults. Every push to `main` redeploys.

## Tests

```bash
python -m unittest -v
```
