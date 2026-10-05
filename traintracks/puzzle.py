"""Puzzle model for Train Tracks.

Coordinates are (row, col), zero-based, row 0 at the top.
A track piece is the pair of sides it connects, written as two letters in the
canonical order N, S, E, W:  NS, EW (straights) and NE, NW, SE, SW (curves).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

DIRS = {"N": (-1, 0), "S": (1, 0), "E": (0, 1), "W": (0, -1)}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
PIECES = ("NS", "EW", "NE", "NW", "SE", "SW")

# Box-drawing glyphs used for text rendering.
GLYPHS = {"NS": "│", "EW": "─", "NE": "└", "NW": "┘", "SE": "┌", "SW": "┐"}


def piece(a: str, b: str) -> str:
    """Canonical piece name for a track joining sides a and b."""
    if a == b:
        raise ValueError(f"a piece needs two different sides, got {a}{b}")
    order = "NSEW"
    return "".join(sorted((a, b), key=order.index))


@dataclass(frozen=True)
class Terminal:
    """A village: the edge cell where the line enters/leaves, and through which side."""
    row: int
    col: int
    side: str

    def to_json(self) -> dict:
        return {"row": self.row, "col": self.col, "side": self.side}


@dataclass
class Puzzle:
    row_totals: list[int]
    col_totals: list[int]
    start: Terminal                      # village A
    end: Terminal                        # village B
    givens: dict[tuple[int, int], str] = field(default_factory=dict)
    name: str = ""

    @property
    def rows(self) -> int:
        return len(self.row_totals)

    @property
    def cols(self) -> int:
        return len(self.col_totals)

    def validate(self) -> None:
        if sum(self.row_totals) != sum(self.col_totals):
            raise ValueError("row totals and column totals have different sums")
        for t in (self.start, self.end):
            dr, dc = DIRS[t.side]
            r, c = t.row + dr, t.col + dc
            if 0 <= r < self.rows and 0 <= c < self.cols:
                raise ValueError(f"terminal {t} does not face the edge of the grid")
        for (r, c), p in self.givens.items():
            if p not in PIECES:
                raise ValueError(f"unknown piece {p!r} at {(r, c)}")
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                raise ValueError(f"given {(r, c)} is outside the grid")

    # ---- serialisation -------------------------------------------------
    def to_json(self) -> dict:
        return {
            "name": self.name,
            "rows": self.rows,
            "cols": self.cols,
            "row_totals": self.row_totals,
            "col_totals": self.col_totals,
            "start": self.start.to_json(),
            "end": self.end.to_json(),
            "givens": [{"row": r, "col": c, "piece": p}
                       for (r, c), p in sorted(self.givens.items())],
        }

    @classmethod
    def from_json(cls, data: dict) -> "Puzzle":
        p = cls(
            row_totals=list(data["row_totals"]),
            col_totals=list(data["col_totals"]),
            start=Terminal(**data["start"]),
            end=Terminal(**data["end"]),
            givens={(g["row"], g["col"]): g["piece"] for g in data.get("givens", [])},
            name=data.get("name", ""),
        )
        p.validate()
        return p

    @classmethod
    def load(cls, path: str) -> "Puzzle":
        with open(path, encoding="utf-8") as f:
            return cls.from_json(json.load(f))

    # ---- display --------------------------------------------------------
    def render(self, solution: dict[tuple[int, int], str] | None = None) -> str:
        """Text picture of the puzzle, or of a solution if one is supplied."""
        cells = solution if solution is not None else self.givens
        lines = ["   " + " ".join(str(t) for t in self.col_totals)]
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                row.append(GLYPHS[cells[(r, c)]] if (r, c) in cells else "·")
            label = ""
            for t, name in ((self.start, "A"), (self.end, "B")):
                if t.row == r and t.side in "EW":
                    label += f" {name}({t.side})"
            lines.append(f"   {' '.join(row)}  {self.row_totals[r]}{label}")
        for t, name in ((self.start, "A"), (self.end, "B")):
            if t.side in "NS":
                lines.append(f"   {name}: col {t.col + 1}, {'top' if t.side == 'N' else 'bottom'}")
        return "\n".join(lines)


def solution_to_rows(solution: dict[tuple[int, int], str], rows: int, cols: int) -> list[list[str]]:
    """Solution as a grid of piece names, '' for empty cells (used in JSON output)."""
    return [[solution.get((r, c), "") for c in range(cols)] for r in range(rows)]
