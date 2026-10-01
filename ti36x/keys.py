"""TI-36X Pro key layout — matches the physical calculator.

Three sections:
  • TOP    — [2nd] [mode] [delete] + circular nav pad (row 1 of spec)
  • MENU   — [ln/log] [math] [data] wider shortcut row (row 2 of spec)
  • GRID   — 5-col × 7-row main keypad (rows 3–9 of spec)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Key:
    name: str
    label: str
    shift: Optional[str] = None
    group: str = "std"  # std | num | op | fn | nav | mode | clear | enter | menu
    row: int = 0
    col: int = 0


KEYS: dict[str, Key] = {}


def _k(*args, **kwargs) -> Key:
    k = Key(*args, **kwargs)
    KEYS[k.name] = k
    return k


# --- TOP strip (row 1) ----------------------------------------------------
_k("2nd", "2nd", None, group="2nd")
_k("mode", "mode", "quit", group="mode")
_k("delete", "delete", "insert", group="mode")
_k("up", "▲", None, group="nav")
_k("left", "◀", None, group="nav")
_k("right", "▶", None, group="nav")
_k("down", "▼", None, group="nav")


# --- MENU row (row 2, 3 wider keys) ---------------------------------------
_k("lnlog", "ln log", "d/dx", group="menu", row=2, col=0)
_k("math", "math", "matrix", group="menu", row=2, col=1)
_k("data", "data", "stat-reg/distr", group="menu", row=2, col=2)


# --- MAIN grid: rows 3–9, 5 columns ---------------------------------------
# Row 3
_k("exp10", "eˣ 10ˣ", "∫", group="fn", row=3, col=0)
_k("ee", "EE", "vector", group="fn", row=3, col=1)
_k("prb", "! nCr nPr", "random", group="fn", row=3, col=2)
_k("table", "table", "expr-eval", group="fn", row=3, col=3)
_k("clear", "clear", None, group="clear", row=3, col=4)

# Row 4
_k("pi", "π e i", "complex", group="fn", row=4, col=0)
_k("sin", "sin sin⁻¹", "num-solv", group="fn", row=4, col=1)
_k("cos", "cos cos⁻¹", "poly-solv", group="fn", row=4, col=2)
_k("tan", "tan tan⁻¹", "sys-solv", group="fn", row=4, col=3)
_k("div", "÷", "%", group="op", row=4, col=4)

# Row 5
_k("power", "x□", "ⁿ√", group="fn", row=5, col=0)
_k("frac", "n/d", "1/x", group="fn", row=5, col=1)
_k("lparen", "(", "constants", group="fn", row=5, col=2)
_k("rparen", ")", "op", group="fn", row=5, col=3)
_k("mul", "×", "set op", group="op", row=5, col=4)

# Row 6
_k("sq", "x²", "√", group="fn", row=6, col=0)
_k("7", "7", "mixed fraction", group="num", row=6, col=1)
_k("8", "8", "convert", group="num", row=6, col=2)
_k("9", "9", "base n", group="num", row=6, col=3)
_k("sub", "−", "decrease contrast", group="op", row=6, col=4)

# Row 7
_k("var", "x y z t a b c d", "clear var", group="fn", row=7, col=0)
_k("4", "4", "D", group="num", row=7, col=1)
_k("5", "5", "E", group="num", row=7, col=2)
_k("6", "6", "F", group="num", row=7, col=3)
_k("add", "+", "increase contrast", group="op", row=7, col=4)

# Row 8
_k("sto", "sto→", "recall", group="fn", row=8, col=0)
_k("1", "1", "A", group="num", row=8, col=1)
_k("2", "2", "B", group="num", row=8, col=2)
_k("3", "3", "C", group="num", row=8, col=3)
_k("fd", "◀▶≈", "f↔d", group="fn", row=8, col=4)

# Row 9
_k("on", "on", "off", group="fn", row=9, col=0)
_k("0", "0", "reset", group="num", row=9, col=1)
_k("dot", ".", ",", group="num", row=9, col=2)
_k("neg", "(−)", "answer", group="fn", row=9, col=3)
_k("enter", "enter", None, group="enter", row=9, col=4)


GRID_FIRST_ROW = 3
GRID_LAST_ROW = 9
GRID_COLS = 5

TOP_NAMES = ("2nd", "mode", "delete", "up", "left", "right", "down")
MENU_NAMES = ("lnlog", "math", "data")


def top_keys() -> list[str]:
    return list(TOP_NAMES)


def menu_keys() -> list[str]:
    return list(MENU_NAMES)


def grid_layout() -> list[list[Optional[str]]]:
    n_rows = GRID_LAST_ROW - GRID_FIRST_ROW + 1
    grid: list[list[Optional[str]]] = [[None] * GRID_COLS for _ in range(n_rows)]
    for k in KEYS.values():
        if k.name in TOP_NAMES or k.name in MENU_NAMES:
            continue
        rr = k.row - GRID_FIRST_ROW
        grid[rr][k.col] = k.name
    return grid


def key_names() -> list[str]:
    return list(KEYS.keys())
