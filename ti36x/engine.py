"""TI-36X Pro calculator engine.

State machine + expression evaluator. The entry buffer holds a human-readable
form of the expression (using calculator glyphs like ÷, ×, π, √). On `enter`
we translate to sympy, evaluate in the current angle mode, and push to history.

Modes (high-level):
    NORMAL  — free-form expression entry
    STAT    — 1/2-var statistics
    MATRIX  — matrix editor + ops
    VECTOR  — vector editor + ops
    SOLVER  — numeric equation solver
    TABLE   — function table
    BASEN   — base-n integer math
    DISTR   — probability distributions
    POLY    — polynomial root finder
    SYSEQ   — linear system solver

v1 implements NORMAL fully. Other modes capture entry and raise NotImplemented
for ops, leaving hooks for incremental extension.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Literal, Optional, Any

import sympy as sp


Mode = Literal[
    "NORMAL", "STAT", "MATRIX", "VECTOR", "SOLVER",
    "TABLE", "BASEN", "DISTR", "POLY", "SYSEQ",
]
Angle = Literal["DEG", "RAD", "GRAD"]
FloatFormat = Literal["FLOAT", "FIX", "SCI", "ENG"]


@dataclass
class CalcState:
    entry: str = ""
    cursor: int = 0
    result: str = "0"
    ans: str = "0"
    ans_exact: str = "0"
    mode: Mode = "NORMAL"
    angle: Angle = "DEG"
    is_2nd: bool = False
    is_alpha: bool = False
    fraction_display: str = "AUTO"  # AUTO | DEC
    float_format: FloatFormat = "FLOAT"
    float_digits: int = 4
    history: list[tuple[str, str]] = field(default_factory=list)
    memory: dict[str, str] = field(default_factory=lambda: {
        "A": "0", "B": "0", "C": "0", "D": "0", "E": "0",
        "x": "0", "y": "0", "z": "0", "t": "0",
    })
    error: Optional[str] = None
    # mode state
    matrices: dict[str, list[list[float]]] = field(default_factory=dict)
    vectors: dict[str, list[float]] = field(default_factory=dict)
    stat_lists: dict[str, list[float]] = field(
        default_factory=lambda: {"L1": [], "L2": [], "L3": [], "FRQ": []}
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry": self.entry,
            "cursor": self.cursor,
            "result": self.result,
            "ans": self.ans,
            "mode": self.mode,
            "angle": self.angle,
            "is_2nd": self.is_2nd,
            "is_alpha": self.is_alpha,
            "fraction_display": self.fraction_display,
            "float_format": self.float_format,
            "float_digits": self.float_digits,
            "history": self.history[-10:],
            "memory": dict(self.memory),
            "error": self.error,
        }


# --- token mapping ----------------------------------------------------------
# Each primary key inserts a token into the entry buffer at the cursor. 2nd
# shift selects the shifted token where present.

TOKENS_PRIMARY: dict[str, str] = {
    "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
    "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
    "dot": ".",
    "add": "+", "sub": "−", "mul": "×", "div": "÷",
    "lparen": "(", "rparen": ")",
    "pi": "π",
    "sin": "sin(", "cos": "cos(", "tan": "tan(",
    "lnlog": "ln(",
    "exp10": "e^(",
    "power": "^",
    "sq": "²",
    "neg": "⁻",          # unary minus glyph
    "ee": "ᴇ",           # scientific E
    "frac": "⬚/⬚",       # placeholder fraction
    "var": "x",
    "prb": "!",
}

TOKENS_SHIFT: dict[str, str] = {
    "sin": "asin(",
    "cos": "acos(",
    "tan": "atan(",
    "lnlog": "log(",     # d/dx stubbed → fall back to log()
    "exp10": "10^(",
    "sq": "⁻¹",
    "power": "root(",    # nth root
    "pi": "e",
    "neg": "ans",
    "frac": "▸n/d",
    "dot": ",",
    "div": "/100",       # percent
    "prb": "rand()",
    # memory variable letters (2nd + digit)
    "1": "A", "2": "B", "3": "C",
    "4": "D", "5": "E", "6": "F",
}


# symbols recognised as argument separators during eval
ARG_SEP = ","


class EvalError(Exception):
    pass


class Calculator:
    def __init__(self) -> None:
        self.state = CalcState()

    # ----- input ----------------------------------------------------------
    def press(self, name: str) -> CalcState:
        s = self.state
        s.error = None
        shift = s.is_2nd

        # mode/system keys
        if name == "2nd":
            s.is_2nd = not s.is_2nd
            return s
        if name == "clear":
            if s.entry:
                s.entry = ""
                s.cursor = 0
            else:
                s.result = "0"
            s.is_2nd = False
            return s
        if name == "delete":
            self._delete()
            s.is_2nd = False
            return s
        if name == "mode":
            # cycle DEG → RAD → GRAD for now; full mode menu can come later
            s.angle = {"DEG": "RAD", "RAD": "GRAD", "GRAD": "DEG"}[s.angle]
            s.is_2nd = False
            return s
        if name == "left":
            s.cursor = max(0, s.cursor - 1)
            return s
        if name == "right":
            s.cursor = min(len(s.entry), s.cursor + 1)
            return s
        if name in ("up", "down"):
            # scroll history
            if s.history:
                if name == "up":
                    prev = s.history[-1][0]
                    s.entry = prev
                    s.cursor = len(prev)
            s.is_2nd = False
            return s
        if name == "enter":
            self._evaluate()
            s.is_2nd = False
            return s

        # special action keys (not token insertion)
        if name == "on":
            self.reset()
            return self.state
        if name == "0" and shift:
            self.reset()
            return self.state
        if name == "fd":
            # toggle between exact and decimal display of last result
            if s.ans_exact and s.ans_exact != s.ans:
                s.result = s.ans if s.result == s.ans_exact else s.ans_exact
            s.is_2nd = False
            return s
        if name in ("math", "data", "table", "sto") and not shift:
            s.error = f"{name} menu not yet implemented"
            s.is_2nd = False
            return s
        if name == "var" and shift:
            for k in s.memory:
                s.memory[k] = "0"
            s.is_2nd = False
            return s

        # token insertion
        table = TOKENS_SHIFT if shift else TOKENS_PRIMARY
        tok = table.get(name)
        if tok is None and shift:
            tok = TOKENS_PRIMARY.get(name)
        if tok is None:
            s.error = f"key not yet implemented: {name}"
            s.is_2nd = False
            return s

        self._insert(tok)
        s.is_2nd = False
        return s

    # ----- buffer helpers -------------------------------------------------
    def _insert(self, tok: str) -> None:
        s = self.state
        s.entry = s.entry[: s.cursor] + tok + s.entry[s.cursor:]
        s.cursor += len(tok)

    def _delete(self) -> None:
        s = self.state
        if s.cursor == 0:
            return
        s.entry = s.entry[: s.cursor - 1] + s.entry[s.cursor:]
        s.cursor -= 1

    # ----- evaluation -----------------------------------------------------
    def _evaluate(self) -> None:
        s = self.state
        if not s.entry.strip():
            return
        try:
            py = self._to_python(s.entry)
            expr = sp.sympify(py, locals=self._locals(), rational=True,
                              evaluate=False)
            if s.angle == "DEG":
                expr = self._apply_deg(expr)
            expr = expr.doit() if hasattr(expr, "doit") else expr
            exact = sp.simplify(expr)
            numeric = sp.N(exact, 15)
            pretty_exact = self._format_exact(exact)
            pretty_num = self._format_numeric(numeric)
            # display exact if it's meaningfully different and short
            if pretty_exact and pretty_exact != pretty_num and len(pretty_exact) < 40:
                s.result = pretty_exact
                s.ans = pretty_num
                s.ans_exact = pretty_exact
            else:
                s.result = pretty_num
                s.ans = pretty_num
                s.ans_exact = pretty_exact or pretty_num
            s.history.append((s.entry, s.result))
            s.entry = ""
            s.cursor = 0
        except EvalError as e:
            s.error = str(e)
            s.result = "Error"
        except Exception as e:
            s.error = f"syntax error: {e}"
            s.result = "Error"

    def _to_python(self, expr: str) -> str:
        """Translate the display buffer into a sympy-parseable string."""
        s = expr
        s = s.replace("×", "*").replace("÷", "/").replace("−", "-")
        s = s.replace("π", "pi")
        s = s.replace("ᴇ", "*10**")
        s = s.replace("⁻¹", "**(-1)")
        s = s.replace("²", "**2")
        s = s.replace("⁻", "-")
        s = s.replace("√(", "sqrt(")
        s = s.replace("e^(", "exp(")
        s = s.replace("10^(", "10**(")
        s = s.replace("^", "**")
        s = s.replace("ans", f"({self.state.ans_exact})")
        s = s.replace("⬚/⬚", "/")
        # factorial: n! → factorial(n)
        s = re.sub(r"(\d+|\([^()]*\))!", r"factorial(\1)", s)
        # memory vars (A–F, x/y/z/t)
        for var in self.state.memory:
            s = re.sub(rf"(?<![A-Za-z]){var}(?![A-Za-z])",
                       f"({self.state.memory[var]})", s)
        return s

    def _locals(self) -> dict[str, Any]:
        return {
            "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
            "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
            "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
            "log": lambda x, **_: sp.log(x, 10),
            "ln": sp.log,
            "exp": sp.exp,
            "sqrt": sp.sqrt,
            "root": lambda n, x, **_: x ** (sp.Rational(1, n)),
            "factorial": sp.factorial,
            "rand": lambda **_: sp.Rational(__import__("random").random()),
            "pi": sp.pi,
            "e": sp.E,
            "i": sp.I,
            "x": sp.Symbol("x"),
            "y": sp.Symbol("y"),
            "z": sp.Symbol("z"),
            "t": sp.Symbol("t"),
        }

    def _apply_deg(self, expr: sp.Expr) -> sp.Expr:
        """If angle mode is DEG, scale args of sin/cos/tan by π/180 and
        scale results of asin/acos/atan by 180/π."""
        fwd = {sp.sin, sp.cos, sp.tan}
        inv = {sp.asin, sp.acos, sp.atan}
        deg = sp.pi / 180

        def rewrite(e):
            if e.is_Atom:
                return e
            new_args = [rewrite(a) for a in e.args]
            if e.func in fwd:
                return e.func(new_args[0] * deg)
            if e.func in inv:
                return e.func(*new_args) / deg
            return e.func(*new_args)

        return rewrite(expr)

    def _format_exact(self, expr: sp.Expr) -> str:
        try:
            if expr.is_Integer:
                return str(expr)
            if expr.is_Rational:
                return f"{expr.p}/{expr.q}"
            # show small symbolic forms like sqrt(2), pi/4
            s = sp.sstr(expr)
            return s
        except Exception:
            return ""

    def _format_numeric(self, n: sp.Expr) -> str:
        s = self.state
        try:
            f = float(n)
        except (TypeError, ValueError):
            return str(n)
        if math.isnan(f):
            return "nan"
        if math.isinf(f):
            return "∞" if f > 0 else "-∞"
        if s.float_format == "FIX":
            return f"{f:.{s.float_digits}f}"
        if s.float_format == "SCI":
            return f"{f:.{s.float_digits}e}".replace("e", "ᴇ")
        if s.float_format == "ENG":
            if f == 0:
                return "0"
            exp = int(math.floor(math.log10(abs(f)) / 3) * 3)
            mant = f / (10 ** exp)
            return f"{mant:g}ᴇ{exp}"
        # FLOAT: trim trailing zeros, 10 sig figs
        r = f"{f:.10g}"
        return r

    # ----- external API --------------------------------------------------
    def press_sequence(self, names: list[str]) -> CalcState:
        for n in names:
            self.press(n)
        return self.state

    def reset(self) -> CalcState:
        self.state = CalcState()
        return self.state

    def set_expression(self, expr: str) -> CalcState:
        """Shortcut: clear entry and type a raw expression, then evaluate."""
        self.state.entry = expr
        self.state.cursor = len(expr)
        self._evaluate()
        return self.state
