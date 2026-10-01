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

Menu actions follow the TI-36X Pro guidebook. Advanced workflows are implemented
in features.py and presented as structured browser input panels.
"""

from __future__ import annotations

import math
import re
import random
import time
from dataclasses import dataclass, field
from typing import Literal, Optional, Any

import sympy as sp

from .evaluator import EvalError, MAX_EXPRESSION_LENGTH, evaluate
from .menus import VARIABLES, MODE_ROWS, MULTI_TAP, MENUS, SHIFT_MENUS

Mode = Literal[
    "NORMAL",
    "STAT",
    "MATRIX",
    "VECTOR",
    "SOLVER",
    "TABLE",
    "BASEN",
    "DISTR",
    "POLY",
    "SYSEQ",
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
    memory: dict[str, str] = field(default_factory=lambda: {v: "0" for v in VARIABLES})
    error: Optional[str] = None
    menu: Optional[str] = None
    memory_action: Optional[str] = None
    menu_view: dict = field(default_factory=dict)
    panel: Optional[str] = None
    feature_result: Any = None
    powered_on: bool = True
    notation: str = "NORM"
    decimal_places: Optional[int] = None
    complex_format: str = "REAL"
    base: str = "DEC"
    entry_format: str = "MATHPRINT"
    contrast: int = 5
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
            "menu": self.menu,
            "memory_action": self.memory_action,
            "menu_view": self.menu_view,
            "panel": self.panel,
            "feature_result": self.feature_result,
            "powered_on": self.powered_on,
            "notation": self.notation,
            "decimal_places": self.decimal_places,
            "complex_format": self.complex_format,
            "base": self.base,
            "entry_format": self.entry_format,
            "contrast": self.contrast,
        }


# --- token mapping ----------------------------------------------------------
# Each primary key inserts a token into the entry buffer at the cursor. 2nd
# shift selects the shifted token where present.

TOKENS_PRIMARY: dict[str, str] = {
    "0": "0",
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "dot": ".",
    "add": "+",
    "sub": "−",
    "mul": "×",
    "div": "÷",
    "lparen": "(",
    "rparen": ")",
    "pi": "π",
    "sin": "sin(",
    "cos": "cos(",
    "tan": "tan(",
    "lnlog": "ln(",
    "exp10": "e^(",
    "power": "^",
    "sq": "²",
    "neg": "⁻",  # unary minus glyph
    "ee": "ᴇ",  # scientific E
    "frac": "/",
    "var": "x",
    "prb": "!",
    "sqrt": "√(",
    "ln": "ln(",
    "log": "log(",
    "exp": "exp(",
    "e": "e",
    "i": "i",
    "ans": "ans",
    "asin": "asin(",
    "acos": "acos(",
    "atan": "atan(",
    "abs": "abs(",
    "ncr": "ncr(",
    "npr": "npr(",
    "reciprocal": "⁻¹",
    "factorial": "!",
    "comma": ",",
    "sinh": "sinh(",
    "cosh": "cosh(",
    "tanh": "tanh(",
    "asinh": "asinh(",
    "acosh": "acosh(",
    "atanh": "atanh(",
}

TOKENS_SHIFT = {
    "frac": "⁻¹",
    "sq": "√(",
    "power": "root(",
    "neg": "ans",
    "dot": ",",
    "div": "%",
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "E",
    "6": "F",
}


KEY_ALIASES = {"square": "sq", "inv": "reciprocal"}
VALID_KEYS = (
    set(TOKENS_PRIMARY)
    | set(KEY_ALIASES)
    | {
        "2nd",
        "clear",
        "delete",
        "mode",
        "left",
        "right",
        "up",
        "down",
        "enter",
        "on",
        "fd",
        "math",
        "data",
        "table",
        "sto",
        "backspace",
    }
)

VALID_KEYS.update(f"select_{i}" for i in range(32))
VALID_KEYS.update(f"tab_{i}" for i in range(6))


class Calculator:
    def __init__(self) -> None:
        self.state = CalcState()
        self._ans_value = sp.S.Zero
        self._history_position = None
        self._tap = None
        self._menu_tab = 0
        self._menu_item = 0
        self._fractions = []
        self._store_variable = "x"
        self._insert_mode = False
        self.stored_operation = ""
        self.table_function = ""
        self.stat_results = {}
        self._prefer_exact = True
        self._random = random.Random()
        self._seed_pending = False
        self._last_activity = time.monotonic()
        self.list_formulas = {}

    def expire_if_idle(self):
        if self.state.powered_on and time.monotonic() - self._last_activity >= 300:
            self.state.powered_on = False
            return True
        return False

    def open_menu(self, name):
        self.state.menu = name
        self.state.panel = None
        self._menu_tab = self._menu_item = 0
        self._refresh_menu()

    def _refresh_menu(self):
        s = self.state
        if s.menu == "mode":
            current = [
                s.angle,
                s.notation,
                "FLOAT" if s.decimal_places is None else str(s.decimal_places),
                s.complex_format,
                s.base,
                s.entry_format,
            ]
            s.menu_view = {
                "tabs": [row[0] for row in MODE_ROWS],
                "tab": self._menu_tab,
                "items": MODE_ROWS[self._menu_tab][1],
                "selected": self._menu_item,
                "current": current[self._menu_tab],
            }
        elif s.menu in MENUS:
            tabs = list(MENUS[s.menu])
            items = MENUS[s.menu][tabs[self._menu_tab]]
            labels = [label for label, _ in items]
            if s.menu == "recall":
                labels = [f"{v} = {s.memory[v]}" for v in VARIABLES]
            s.menu_view = {
                "tabs": tabs,
                "tab": self._menu_tab,
                "items": labels,
                "selected": self._menu_item,
            }
        else:
            s.menu_view = {}

    def _close_menu(self):
        self.state.menu = None
        self.state.menu_view = {}
        self.state.panel = None

    def set_modes(self, **modes):
        s = self.state
        allowed = {
            "angle": ["DEG", "RAD", "GRAD"],
            "notation": ["NORM", "SCI", "ENG"],
            "complex_format": ["REAL", "a+bi", "r∠θ"],
            "base": ["DEC", "HEX", "BIN", "OCT"],
            "entry_format": ["CLASSIC", "MATHPRINT"],
            "decimal_places": [None, *range(10)],
        }
        for name, value in modes.items():
            if name not in allowed or value not in allowed[name]:
                raise EvalError("DOMAIN: invalid mode setting")
        for name, value in modes.items():
            setattr(s, name, value)
        s.float_format = (
            s.notation
            if s.notation != "NORM"
            else ("FLOAT" if s.decimal_places is None else "FIX")
        )
        s.float_digits = 4 if s.decimal_places is None else s.decimal_places
        if s.history:
            self._display_result(self._ans_value)
        if s.menu == "mode":
            self._refresh_menu()

    def _select_menu(self, index):
        s = self.state
        if s.menu == "mode":
            options = MODE_ROWS[self._menu_tab][1]
            if index >= len(options):
                return
            key = [
                "angle",
                "notation",
                "decimal_places",
                "complex_format",
                "base",
                "entry_format",
            ][self._menu_tab]
            value = options[index]
            if key == "decimal_places":
                value = None if value == "FLOAT" else int(value)
            self.set_modes(**{key: value})
            self._menu_item = index
            self._refresh_menu()
            return
        tabs = MENUS.get(s.menu, {})
        if not tabs:
            return
        items = tabs[list(tabs)[self._menu_tab]]
        if index >= len(items):
            return
        _, action = items[index]
        self._close_menu()
        if action == "rand()" and s.memory_action == "store":
            self._seed_pending = True
        elif action.endswith("(") or action == "rand()":
            self._insert(action)
        elif action.startswith("recall:"):
            self._insert("(" + s.memory[action.split(":")[1]] + ")")
        elif action == "clearvars":
            s.memory = dict.fromkeys(VARIABLES, "0")
        elif action == "reset":
            self.reset()
        elif action == "quit":
            pass
        else:
            s.panel = action

    def _menu_press(self, name):
        s = self.state
        if name == "clear" or (name == "mode" and s.is_2nd):
            self._close_menu()
            s.is_2nd = False
            return True
        if name.startswith("tab_"):
            self._menu_tab = min(int(name[4:]), len(s.menu_view["tabs"]) - 1)
            self._menu_item = 0
        elif name.startswith("select_"):
            self._select_menu(int(name[7:]))
            return True
        elif name == "enter":
            self._select_menu(self._menu_item)
            return True
        elif name in ("up", "down", "left", "right"):
            if s.menu == "mode":
                if name in ("up", "down"):
                    self._menu_tab = (
                        self._menu_tab + (1 if name == "down" else -1)
                    ) % len(MODE_ROWS)
                    self._menu_item = 0
                else:
                    self._menu_item = (
                        self._menu_item + (1 if name == "right" else -1)
                    ) % len(MODE_ROWS[self._menu_tab][1])
            elif name in ("left", "right"):
                self._menu_tab = (
                    self._menu_tab + (1 if name == "right" else -1)
                ) % len(s.menu_view["tabs"])
                self._menu_item = 0
            else:
                self._menu_item = (
                    self._menu_item + (1 if name == "down" else -1)
                ) % max(1, len(s.menu_view["items"]))
        elif name.isdigit() and 1 <= int(name) <= len(s.menu_view["items"]):
            self._select_menu(int(name) - 1)
            return True
        else:
            return False
        self._refresh_menu()
        return True

    def press(self, name: str) -> CalcState:
        self.expire_if_idle()
        self._last_activity = time.monotonic()
        name = KEY_ALIASES.get(name, name)
        s = self.state
        previous_error = s.error
        s.error = None
        shift = s.is_2nd
        if name == "on":
            if shift:
                s.powered_on = False
                s.entry = ""
                s.cursor = 0
                s.result = ""
                self._close_menu()
            else:
                s.powered_on = True
                s.result = s.result or "0"
            s.is_2nd = False
            self._tap = None
            return s
        if not s.powered_on:
            return s
        if name == "2nd":
            s.is_2nd = not shift
            return s
        if name not in MULTI_TAP or shift:
            self._tap = None
        if s.menu and s.menu_view and self._menu_press(name):
            return self.state
        if name == "mode":
            if shift:
                self._close_menu()
                s.memory_action = None
            else:
                self.open_menu("mode")
            s.is_2nd = False
            return s
        if name == "clear":
            if previous_error:
                # The first Clear dismisses the error and lets the user correct it.
                s.result = s.ans
            elif s.menu or s.panel:
                self._close_menu()
            else:
                s.entry = ""
                s.cursor = 0
                self._fractions.clear()
            s.memory_action = None
            self._history_position = None
            self._tap = None
            s.is_2nd = False
            return s
        if name == "delete" and shift:
            self._insert_mode = True
            s.is_2nd = False
            return s
        if name in ("delete", "backspace"):
            pos = s.cursor - (name == "backspace")
            if 0 <= pos < len(s.entry):
                s.entry = s.entry[:pos] + s.entry[pos + 1 :]
                s.cursor = pos
            self._history_position = None
            return s
        if name in ("left", "right"):
            if shift:
                s.cursor = 0 if name == "left" else len(s.entry)
            elif (
                name == "right"
                and s.cursor == len(s.entry)
                and s.entry.count("(") > s.entry.count(")")
            ):
                self._insert(")")
                if self._fractions and self._fractions[-1] == "denominator":
                    self._fractions.pop()
            else:
                s.cursor = max(
                    0, min(len(s.entry), s.cursor + (-1 if name == "left" else 1))
                )
            s.is_2nd = False
            return s
        if name == "down" and self._fractions and self._fractions[-1] == "numerator":
            self._insert(")/(")
            self._fractions[-1] = "denominator"
            return s
        if name in ("up", "down"):
            if s.history:
                if name == "up":
                    self._history_position = max(
                        0,
                        (
                            len(s.history)
                            if self._history_position is None
                            else self._history_position
                        )
                        - 1,
                    )
                elif self._history_position is not None:
                    self._history_position += 1
                    if self._history_position >= len(s.history):
                        self._history_position = None
                s.entry = (
                    ""
                    if self._history_position is None
                    else s.history[self._history_position][0]
                )
                s.cursor = len(s.entry)
            s.is_2nd = False
            return s
        if name == "enter":
            if self._seed_pending:
                self._evaluate()
                if self._ans_value.is_Integer is not True or self._ans_value < 0:
                    s.error = "DOMAIN"
                elif not s.error:
                    self._random.seed(int(self._ans_value))
                self._seed_pending = False
                s.memory_action = None
                return s
            if self._history_position is not None:
                self._history_position = None
                return s
            if s.memory_action == "store":
                self._evaluate()
                if not s.error:
                    s.memory[self._store_variable] = sp.sstr(self._ans_value)
                    s.memory_action = None
                return s
            if s.panel == "setop":
                if len(s.entry) > 44:
                    s.error = "EQUATION LENGTH ERROR"
                else:
                    self.stored_operation = s.entry
                    s.entry = ""
                    s.cursor = 0
                    s.panel = None
                return s
            self._evaluate()
            s.is_2nd = False
            return s
        if name == "fd":
            s.result = s.ans if s.result == s.ans_exact else s.ans_exact
            s.is_2nd = False
            return s
        if shift and name in SHIFT_MENUS:
            menu = SHIFT_MENUS[name]
            if menu == "storedop":
                if not self.stored_operation:
                    s.error = "OP NOT DEFINED"
                else:
                    prefix = "(" + s.entry + ")" if s.entry else "ans"
                    self.set_expression(prefix + self.stored_operation)
            elif menu in MENUS:
                self.open_menu(menu)
            else:
                self._close_menu()
                s.panel = menu
            s.is_2nd = False
            return s
        if name == "math":
            self.open_menu("math")
            return s
        if name == "data":
            self._close_menu()
            s.panel = "data"
            return s
        if name == "table":
            self.open_menu("table")
            return s
        if name == "sto":
            s.memory_action = "store"
            self._store_variable = "x"
            self._tap = None
            return s
        if s.memory_action == "store" and name == "var":
            if self._tap and self._tap[0] == "var":
                self._store_variable = VARIABLES[
                    (VARIABLES.index(self._store_variable) + 1) % len(VARIABLES)
                ]
            self._tap = ("var", 0, 0, 0)
            s.feature_result = {"store_in": self._store_variable}
            return s
        if shift and name == "add":
            s.contrast = min(9, s.contrast + 1)
            s.is_2nd = False
            return s
        if shift and name == "sub":
            s.contrast = max(0, s.contrast - 1)
            s.is_2nd = False
            return s
        if shift and name == "power":
            degree = s.entry or "2"
            s.entry = ""
            s.cursor = 0
            self._insert("root(" + degree + ",")
            s.is_2nd = False
            return s
        if name == "frac" and not shift and s.entry_format == "MATHPRINT":
            if not s.entry:
                self._insert("(")
                self._fractions.append("numerator")
            else:
                self._insert("/(")
                self._fractions.append("denominator")
            self._tap = None
            return s
        if name == "7" and shift:
            match = re.search(r"\d+(?:\.\d+)?$", s.entry)
            whole = match[0] if match else "0"
            prefix = s.entry[: match.start()] if match else s.entry
            s.entry = prefix + "(" + whole + "+("
            s.cursor = len(s.entry)
            self._fractions.append("numerator")
            self._tap = None
            s.is_2nd = False
            return s
        token = TOKENS_SHIFT.get(name) if shift else TOKENS_PRIMARY.get(name)
        if not shift and name in MULTI_TAP:
            choices = MULTI_TAP[name]
            if self._tap and self._tap[0] == name and s.cursor == self._tap[3]:
                _, index, start, end = self._tap
                index = (index + 1) % len(choices)
                token = choices[index]
                s.entry = s.entry[:start] + token + s.entry[end:]
                s.cursor = start + len(token)
                self._tap = (name, index, start, s.cursor)
                return s
            token = choices[0]
        if token is None:
            token = TOKENS_PRIMARY.get(name)
        if token is None:
            s.error = "SYNTAX: unknown key"
            return s
        if not s.entry and token in {"+", "−", "×", "÷", "^", "²", "⁻¹", "/", "!", "%"}:
            self._insert("ans")
        start = s.cursor
        self._insert(token)
        if not shift and name in MULTI_TAP:
            self._tap = (name, 0, start, s.cursor)
        s.is_2nd = False
        return s

    def _insert(self, token):
        s = self.state
        if len(s.entry) + len(token) > MAX_EXPRESSION_LENGTH:
            s.error = "EQUATION LENGTH ERROR"
            return
        overwrite = (
            len(token) if s.cursor < len(s.entry) and not self._insert_mode else 0
        )
        s.entry = s.entry[: s.cursor] + token + s.entry[s.cursor + overwrite :]
        s.cursor += len(token)
        self._insert_mode = False
        self._history_position = None

    def _evaluate(self):
        s = self.state
        if not s.entry.strip():
            return
        s.error = None
        self._tap = None
        try:
            # Enter closes pending parentheses, as specified by EOS.
            expression = s.entry + ")" * max(0, s.entry.count("(") - s.entry.count(")"))
            if self.table_function and "f(" in expression:
                from .features import substitute_table

                expression = substitute_table(expression, self.table_function)
            if s.base != "DEC":
                from .features import evaluate_base, format_base

                expression = re.sub(
                    r"\bans\b", format_base(int(self._ans_value), s.base), expression
                )
                exact = evaluate_base(expression, s.base)
            else:
                arrays = {
                    f"array_{name}": sp.Matrix(value)
                    for name, value in s.matrices.items()
                }
                arrays.update(
                    {
                        f"array_{name}": sp.Matrix(value)
                        for name, value in s.vectors.items()
                    }
                )
                arrays.update({"array_I2": sp.eye(2), "array_I3": sp.eye(3)})
                if isinstance(self._ans_value, sp.MatrixBase):
                    arrays["array_Ans"] = self._ans_value
                exact = evaluate(
                    expression,
                    angle=s.angle,
                    ans=self._ans_value,
                    memory=s.memory,
                    classic=s.entry_format == "CLASSIC",
                    complex_format=s.complex_format,
                    variables=arrays,
                    rng=self._random,
                )
            self._prefer_exact = not (
                "%" in expression
                or (re.search(r"\d*\.\d", expression) and "/" not in expression)
            )
            self._display_result(exact)
            s.history.append((expression, s.result))
            s.history = s.history[-100:]
            self._history_position = None
            self._fractions.clear()
            s.entry = ""
            s.cursor = 0
        except EvalError as error:
            s.error = str(error)
            s.result = "Error"
        except Exception:
            s.error = "SYNTAX"
            s.result = "Error"

    def _display_result(self, exact):
        s = self.state
        self._ans_value = exact
        if isinstance(exact, sp.MatrixBase):
            values = [[sp.sstr(value) for value in row] for row in exact.tolist()]
            s.feature_result = {
                "array": values,
                "rows": exact.rows,
                "columns": exact.cols,
            }
            s.result = str(values).replace("'", "")
            s.ans_exact = s.ans = s.result
            return
        exact_text = self._format_exact(exact)
        numeric_text = self._format_numeric(sp.N(exact, 13))
        if s.base != "DEC":
            from .features import format_base

            exact_text = numeric_text = format_base(int(exact), s.base)
        if exact.is_real is False:
            if s.complex_format == "r∠θ":
                scale = {"DEG": sp.pi / 180, "RAD": 1, "GRAD": sp.pi / 200}[s.angle]
                exact_text = f"{self._format_numeric(sp.N(abs(exact),13))}∠{self._format_numeric(sp.N(sp.arg(exact)/scale,13))}"
            else:
                exact_text = str(exact).replace("I", "i").replace("*i", "i")
        s.ans_exact = exact_text
        notation, places = s.notation, s.decimal_places
        s.notation, s.decimal_places = "NORM", None
        s.ans = self._format_numeric(sp.N(exact, 13))
        s.notation, s.decimal_places = notation, places
        use_exact = (
            self._prefer_exact
            and not exact.is_Float
            and (not exact.is_Integer or abs(exact) < 10**10)
        )
        use_exact = use_exact and not exact.has(
            sp.log,
            sp.exp,
            sp.sin,
            sp.cos,
            sp.tan,
            sp.sinh,
            sp.cosh,
            sp.tanh,
            sp.asinh,
            sp.acosh,
            sp.atanh,
            sp.E,
        )
        s.result = (
            exact_text
            if use_exact
            and s.notation == "NORM"
            and s.decimal_places is None
            and len(exact_text) < 40
            else numeric_text
        )

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
            return str(n).replace("I", "i")
        if not math.isfinite(f):
            return "Error"
        places = s.decimal_places
        if s.notation == "SCI":
            text = f"{f:.{9 if places is None else places}e}"
            mantissa, exponent = text.split("e")
            if places is None:
                mantissa = mantissa.rstrip("0").rstrip(".")
            return mantissa + "ᴇ" + str(int(exponent))
        if s.notation == "ENG":
            exponent = int(math.floor(math.log10(abs(f)) / 3) * 3) if f else 0
            mantissa = f / 10**exponent
            digits = (
                places
                if places is not None
                else max(
                    0,
                    9 - (int(math.floor(math.log10(abs(mantissa)))) if mantissa else 0),
                )
            )
            text = f"{mantissa:.{digits}f}"
            if abs(float(text)) >= 1000:
                exponent += 3
                text = f"{mantissa/1000:.{places if places is not None else 9}f}"
            if places is None:
                text = text.rstrip("0").rstrip(".")
            return text + "ᴇ" + str(exponent)
        if places is not None:
            return f"{f:.{places}f}"
        return f"{f:.10g}".replace("e+", "ᴇ").replace("e-", "ᴇ-")

    # ----- external API --------------------------------------------------
    def press_sequence(self, names: list[str]) -> CalcState:
        for n in names:
            self.press(n)
        return self.state

    def reset(self) -> CalcState:
        self.__init__()
        return self.state

    def set_expression(self, expr: str) -> CalcState:
        self.state.entry = expr
        self.state.cursor = len(expr)
        self.state.error = None
        self.state.memory_action = None
        self._tap = None
        self._fractions.clear()
        self._evaluate()
        return self.state
