"""Guidebook calculation workflows used by the keypad menus, API and MCP."""

from __future__ import annotations

import ast
import math
import re
import statistics
from statistics import NormalDist

import sympy as sp

from .evaluator import EvalError, evaluate
from .menus import VARIABLES, MENUS

CONSTANTS = {
    "c": ("299792458", "m/s"),
    "g": ("9.80665", "m/s²"),
    "h": ("6.62607015e-34", "J s"),
    "NA": ("6.02214076e23", "mol⁻¹"),
    "R": ("8.314462618", "J/(mol K)"),
    "me": ("9.1093837015e-31", "kg"),
    "mp": ("1.67262192369e-27", "kg"),
    "mn": ("1.67492749804e-27", "kg"),
    "mm": ("1.883531627e-28", "kg"),
    "G": ("6.6743e-11", "m³/(kg s²)"),
    "F": ("96485.33212", "C/mol"),
    "a0": ("5.29177210903e-11", "m"),
    "re": ("2.8179403262e-15", "m"),
    "k": ("1.380649e-23", "J/K"),
    "e": ("1.602176634e-19", "C"),
    "u": ("1.6605390666e-27", "kg"),
    "atm": ("101325", "Pa"),
    "epsilon0": ("8.8541878128e-12", "F/m"),
    "mu0": ("1.25663706212e-6", "N/A²"),
    "Cc": ("8.987551792261e9", "m/F"),
}
MENUS["constants"]["NAMES"] = [(name, "constant:" + name) for name in CONSTANTS]
MENUS["constants"]["UNITS"] = [
    (f"{name} ({unit})", "constant:" + name) for name, (_, unit) in CONSTANTS.items()
]
# Canonical unit scales within compatible dimensions, with exact definitions.
UNITS = {
    "in": ("length", "0.0254"),
    "cm": ("length", "0.01"),
    "ft": ("length", "0.3048"),
    "m": ("length", "1"),
    "yd": ("length", "0.9144"),
    "mile": ("length", "1609.344"),
    "km": ("length", "1000"),
    "lightyear": ("length", "9460730472580800"),
    "parsec": ("length", "30856775814913673"),
    "angstrom": ("length", "1e-10"),
    "acre": ("area", "4046.8564224"),
    "m2": ("area", "1"),
    "galUS": ("volume", "3.785411784"),
    "galUK": ("volume", "4.54609"),
    "L": ("volume", "1"),
    "oz": ("mass", "28.349523125"),
    "g": ("mass", "1"),
    "lb": ("mass", "453.59237"),
    "kg": ("mass", "1000"),
    "km/h": ("speed", "1/3.6"),
    "m/s": ("speed", "1"),
    "atm": ("pressure", "101325"),
    "Pa": ("pressure", "1"),
    "mmHg": ("pressure", "133.322387415"),
    "J": ("energy", "1"),
    "kWh": ("energy", "3600000"),
    "cal": ("energy", "4.184"),
    "hp": ("power", "745.6998715822702"),
    "kW": ("power", "1000"),
}


def serialize(value):
    if isinstance(value, sp.MatrixBase):
        return [[serialize(x) for x in row] for row in value.tolist()]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(x) for x in value]
    if isinstance(value, sp.Basic):
        return sp.sstr(value).replace("I", "i")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EvalError("OVERFLOW")
        return f"{value:.10g}"
    return value


def value(calc, text, variables=None):
    if isinstance(text, bool) or not isinstance(text, (str, int, float)):
        raise EvalError("DATA TYPE")
    return evaluate(
        str(text),
        angle=calc.state.angle,
        ans=calc._ans_value,
        memory=calc.state.memory,
        variables=variables,
        complex_format=calc.state.complex_format,
        classic=calc.state.entry_format == "CLASSIC",
        rng=calc._random,
    )


def real(calc, text):
    result = value(calc, text)
    if result.is_real is not True:
        raise EvalError("Input must be Real")
    return result


def integer(calc, text, low=None, high=None):
    result = real(calc, text)
    if (
        result.is_Integer is not True
        or (low is not None and result < low)
        or (high is not None and result > high)
    ):
        raise EvalError("DOMAIN: integer outside the allowed range")
    return int(result)


def sequence(calc, items, limit=42):
    if not isinstance(items, list) or not 1 <= len(items) <= limit:
        raise EvalError("DIM MISMATCH")
    return [real(calc, item) for item in items]


def matrix(calc, items):
    if (
        not isinstance(items, list)
        or not 1 <= len(items) <= 3
        or any(not isinstance(row, list) or not 1 <= len(row) <= 3 for row in items)
    ):
        raise EvalError("DIM MISMATCH: matrices have 1–3 rows and columns")
    if len({len(row) for row in items}) != 1:
        raise EvalError("DIM MISMATCH")
    return sp.Matrix([[real(calc, item) for item in row] for row in items])


def evaluate_base(expression, base):
    radix = {"DEC": 10, "HEX": 16, "BIN": 2, "OCT": 8}[base]
    if len(expression) > 512:
        raise EvalError("EQUATION LENGTH ERROR")
    tokens = re.findall(r"[A-Fa-f0-9]+|[()+\-*/^]", expression)
    if "".join(tokens).lower() != re.sub(r"\s", "", expression).lower():
        raise EvalError("SYNTAX")
    try:
        translated = " ".join(
            (
                str(int(token, radix))
                if re.fullmatch(r"[A-Fa-f0-9]+", token)
                else ("**" if token == "^" else token)
            )
            for token in tokens
        )
    except ValueError as exc:
        raise EvalError("DOMAIN: digit is invalid in this base") from exc
    result = evaluate(translated, angle="DEG", ans=sp.S.Zero, memory={})
    if result.is_real is not True:
        raise EvalError("DOMAIN")
    result = int(result)  # Base-n operations truncate fractional parts.
    if not -(1 << 31) <= result < (1 << 32):
        raise EvalError("OVERFLOW")
    return sp.Integer(result)


def format_base(number, base):
    if base == "DEC":
        return str(number)
    if number < 0:
        number &= 0xFFFFFFFF
    return format(number, {"HEX": "X", "BIN": "b", "OCT": "o"}[base])


def substitute_table(expression, function):
    # f takes one scalar argument. AST validates it; no Python eval is used.
    return re.sub(
        r"\bf\(([^()]*)\)",
        lambda m: "(" + function.replace("x", "(" + m[1] + ")") + ")",
        expression,
    )


def stats(calc, kind, params):
    xs = sequence(calc, params.get("x", calc.state.stat_lists["L1"]))
    frequencies = (
        sequence(calc, params["frequency"])
        if params.get("frequency") is not None
        else [sp.S.One] * len(xs)
    )
    if len(frequencies) != len(xs):
        raise EvalError("DIM MISMATCH")
    if any(f < 0 for f in frequencies):
        raise EvalError("FRQ DOMAIN")
    n = sum(frequencies)
    if n <= 0:
        raise EvalError("STAT")
    total = sum(x * f for x, f in zip(xs, frequencies))
    mean = total / n
    variance = sum(f * (x - mean) ** 2 for x, f in zip(xs, frequencies)) / n
    result = {
        "n": n,
        "mean_x": mean,
        "sum_x": total,
        "sum_x2": sum(f * x * x for x, f in zip(xs, frequencies)),
        "sigma_x": sp.sqrt(variance),
        "Sx": (
            sp.sqrt(variance * n / (n - 1))
            if n > 1 and all(f.is_Integer for f in frequencies)
            else "Error"
        ),
        "min_x": min(xs),
        "max_x": max(xs),
    }
    if kind == "1-Var Stats":
        if all(f.is_Integer for f in frequencies) and n <= 10000:
            ordered = sorted(x for x, f in zip(xs, frequencies) for _ in range(int(f)))
            middle = len(ordered) // 2
            result["median"] = statistics.median(ordered)
            result["Q1"] = statistics.median(ordered[:middle]) if middle else ordered[0]
            result["Q3"] = (
                statistics.median(ordered[-middle:]) if middle else ordered[0]
            )
        return result
    ys = sequence(calc, params.get("y", calc.state.stat_lists["L2"]))
    if len(xs) != len(ys):
        raise EvalError("DIM MISMATCH")
    ytotal = sum(y * f for y, f in zip(ys, frequencies))
    ymean = ytotal / n
    yvar = sum(f * (y - ymean) ** 2 for y, f in zip(ys, frequencies)) / n
    result.update(
        mean_y=ymean,
        sum_y=ytotal,
        sum_y2=sum(f * y * y for y, f in zip(ys, frequencies)),
        sum_xy=sum(f * x * y for x, y, f in zip(xs, ys, frequencies)),
        sigma_y=sp.sqrt(yvar),
        Sy=(
            sp.sqrt(yvar * n / (n - 1))
            if n > 1 and all(f.is_Integer for f in frequencies)
            else "Error"
        ),
    )
    if kind in ("2-Var Stats", "LinReg", "LnReg", "PwrReg", "ExpReg"):
        tx = xs
        ty = ys
        if kind in ("LnReg", "PwrReg"):
            if min(xs) <= 0:
                raise EvalError("DOMAIN")
            tx = [sp.log(x) for x in xs]
        if kind in ("PwrReg", "ExpReg"):
            if min(ys) <= 0:
                raise EvalError("DOMAIN")
            ty = [sp.log(y) for y in ys]
        mx = sum(f * x for f, x in zip(frequencies, tx)) / n
        my = sum(f * y for f, y in zip(frequencies, ty)) / n
        ssx = sum(f * (x - mx) ** 2 for f, x in zip(frequencies, tx))
        ssy = sum(f * (y - my) ** 2 for f, y in zip(frequencies, ty))
        cov = sum(f * (x - mx) * (y - my) for f, x, y in zip(frequencies, tx, ty))
        if ssx == 0:
            raise EvalError("SINGULAR MAT")
        slope = cov / ssx
        intercept = my - slope * mx
        a, b = slope, intercept
        if kind == "LnReg":
            a, b = intercept, slope
        if kind == "PwrReg":
            a, b = sp.exp(intercept), slope
        if kind == "ExpReg":
            a, b = sp.exp(intercept), sp.exp(slope)
        result.update(
            a=sp.N(a, 13),
            b=sp.N(b, 13),
            r=sp.N(cov / sp.sqrt(ssx * ssy), 13) if ssy else "Error",
            r2=sp.N(cov**2 / (ssx * ssy), 13) if ssy else "Error",
        )
        if "predict_x" in params:
            result["predicted_y"] = sp.N(
                slope * real(calc, params["predict_x"]) + intercept, 13
            )
    else:
        degree = {"QuadraticReg": 2, "CubicReg": 3}[kind]
        if len(xs) < degree + 1:
            raise EvalError("STAT")
        design = sp.Matrix([[x**power for power in range(degree, -1, -1)] for x in xs])
        weights = sp.diag(*frequencies)
        try:
            coefficients = (
                (design.T * weights * design).inv() * design.T * weights * sp.Matrix(ys)
            )
        except Exception as exc:
            raise EvalError("SINGULAR MAT") from exc
        residual = sum(
            f * (y - est) ** 2
            for f, y, est in zip(frequencies, ys, design * coefficients)
        )
        result.update(
            {
                name: sp.N(coefficient, 13)
                for name, coefficient in zip("abcd", coefficients)
            }
        )
        result["R2"] = sp.N(1 - residual / (yvar * n), 13) if yvar else "Error"
    return result


def distribution(calc, name, params):
    def number(key, default):
        return float(real(calc, params.get(key, default)))

    if name in ("normalpdf", "normalcdf", "invNorm"):
        mu = number("mu", 0)
        sigma = number("sigma", 1)
        if sigma <= 0:
            raise EvalError("sigma>0 sigma Real")
        normal = NormalDist(mu, sigma)
        if name == "normalpdf":
            return normal.pdf(number("x", 0))
        if name == "normalcdf":
            lower = number("lower", -1e99)
            upper = number("upper", 1e99)
            if lower > upper:
                raise EvalError("ARGUMENT")
            # erfc avoids subtracting nearly equal CDFs in the tails.
            a = (lower - mu) / (sigma * math.sqrt(2))
            b = (upper - mu) / (sigma * math.sqrt(2))
            if a >= 0:
                return (math.erfc(a) - math.erfc(b)) / 2
            if b <= 0:
                return (math.erfc(-b) - math.erfc(-a)) / 2
            return (math.erf(b) - math.erf(a)) / 2
        area = number("area", 0.5)
        if not 0 < area < 1:
            raise EvalError("0<area<1")
        return normal.inv_cdf(area)
    trials = (
        integer(calc, params.get("n", 20), 1, 40) if name.startswith("binom") else None
    )
    probability = number("p", 0.5)
    mu = number("mu", 1)
    if trials is not None and not 0 <= probability <= 1:
        raise EvalError("Probability 0<p<1")
    if trials is None and mu <= 0:
        raise EvalError("Mean mu>0")

    def single(item):
        x = integer(calc, item, 0, 10000)
        if trials is not None:

            def pdf(k):
                return (
                    math.comb(trials, k)
                    * probability**k
                    * (1 - probability) ** (trials - k)
                    if k <= trials
                    else 0
                )

            return (
                sum(pdf(k) for k in range(min(x, trials) + 1))
                if name.endswith("cdf")
                else pdf(x)
            )

        def pdf(k):
            return math.exp(-mu + k * math.log(mu) - math.lgamma(k + 1))

        return (
            math.fsum(pdf(k) for k in range(x + 1)) if name.endswith("cdf") else pdf(x)
        )

    x = params.get("x", 0)
    if x == "ALL":
        if trials is None:
            raise EvalError("ARGUMENT")
        return [single(k) for k in range(trials + 1)]
    if isinstance(x, list):
        if len(x) > 42:
            raise EvalError("DIM MISMATCH")
        return [single(k) for k in x]
    return single(x)


def calculate(calc, operation, params):
    s = calc.state
    if s.base != "DEC" and operation not in {"base", "logic", "modes"}:
        raise EvalError("CHANGE MODE to DEC")
    if operation == "modes":
        calc.set_modes(**params)
        return {name: getattr(calc.state, name) for name in params}
    if operation == "constant":
        name = params.get("name", "c")
        if name not in CONSTANTS:
            raise EvalError("ARGUMENT")
        return value(calc, CONSTANTS[name][0])
    if operation == "convert":
        x = real(calc, params.get("value", 0))
        source = params.get("from", "C")
        target = params.get("to", "F")
        if source in ["C", "F", "K"] and target in ["C", "F", "K"]:
            c = (
                x
                if source == "C"
                else ((x - 32) * 5 / 9 if source == "F" else x - sp.Rational("273.15"))
            )
            return (
                c
                if target == "C"
                else (c * 9 / 5 + 32 if target == "F" else c + sp.Rational("273.15"))
            )
        if (
            source not in UNITS
            or target not in UNITS
            or UNITS[source][0] != UNITS[target][0]
        ):
            raise EvalError("ARGUMENT: incompatible units")
        return x * value(calc, UNITS[source][1]) / value(calc, UNITS[target][1])
    if operation == "factor":
        return {
            "factors": {
                str(p): int(n)
                for p, n in sp.factorint(
                    integer(calc, params.get("value", 253), 2, 10**10)
                ).items()
            }
        }
    if operation == "mixed":
        x = real(calc, params.get("value", calc._ans_value))
        if x.is_Rational is not True:
            raise EvalError("DATA TYPE")
        whole = int(x)
        fraction = abs(x - whole)
        return {
            "whole": whole,
            "numerator": int(fraction.p),
            "denominator": int(fraction.q),
        }
    if operation in (
        "derivative",
        "integral",
        "summation",
        "product",
        "table",
        "solver",
        "expression",
    ):
        expression = params.get("expression", "x^2")
        variable = params.get("variable", "x")
        if variable not in VARIABLES:
            raise EvalError("ARGUMENT")
        symbol = sp.Symbol(variable, real=True)
        if operation == "expression":
            inputs = params.get("values", {})
            if not isinstance(inputs, dict) or any(k not in VARIABLES for k in inputs):
                raise EvalError("ARGUMENT")
            return value(
                calc, expression, {k: value(calc, v) for k, v in inputs.items()}
            )
        if operation == "solver":
            if len(expression) > 40 or expression.count("=") > 1:
                raise EvalError("INVALID EQUATION")
            expression = (
                "(" + expression.split("=")[0] + ")-(" + expression.split("=")[1] + ")"
                if "=" in expression
                else expression
            )
        function = value(calc, expression, {variable: symbol})
        if operation == "derivative":
            point = real(calc, params.get("point", -1))
            epsilon = real(calc, params.get("epsilon", "0.001"))
            if epsilon <= 0:
                raise EvalError("DOMAIN")
            return sp.N(
                (
                    function.subs(symbol, point + epsilon)
                    - function.subs(symbol, point - epsilon)
                )
                / (2 * epsilon),
                13,
            )
        if operation == "integral":
            lower = real(calc, params.get("lower", 0))
            upper = real(calc, params.get("upper", 1))
            if lower > upper:
                raise EvalError("ARGUMENT")
            import mpmath

            numeric = sp.lambdify(symbol, function, modules="mpmath")
            with mpmath.workdps(20):
                result = mpmath.quad(numeric, [float(lower), float(upper)])
            if not mpmath.isfinite(result) or abs(mpmath.im(result)) > 1e-12:
                raise EvalError("DOMAIN")
            return sp.Float(str(result), 13)
        if operation in ("summation", "product"):
            start = integer(calc, params.get("start", 1))
            end = integer(calc, params.get("end", 4))
            if start > end or end - start > 1000:
                raise EvalError("ARGUMENT")
            values = [function.subs(symbol, k) for k in range(start, end + 1)]
            result = sum(values) if operation == "summation" else sp.prod(values)
            if result.has(sp.zoo, sp.oo, sp.nan):
                raise EvalError("DOMAIN")
            return result
        if operation == "table":
            calc.table_function = expression
            if "x_values" in params:
                inputs = sequence(calc, params["x_values"])
            else:
                start = real(calc, params.get("start", 0))
                step = real(calc, params.get("step", 1))
                count = integer(calc, params.get("count", 10), 1, 42)
                inputs = [start + k * step for k in range(count)]
            return [{"x": x, "f(x)": function.subs(symbol, x)} for x in inputs]
        if operation == "solver":
            guess = real(calc, params.get("guess", 0))
            try:
                solution = sp.nsolve(function, symbol, guess, prec=20, maxsteps=100)
            except Exception as exc:
                raise EvalError("No Solution Found — change guess") from exc
            if solution.is_real is not True:
                raise EvalError("Input must be Real")
            s.memory[variable] = sp.sstr(solution)
            return {
                "variable": variable,
                "solution": solution,
                "left_minus_right": sp.N(function.subs(symbol, solution), 13),
            }
    if operation == "polynomial":
        coefficients = sequence(calc, params.get("coefficients", [1, -2, 2]), 4)
        if len(coefficients) not in (3, 4):
            raise EvalError("ARGUMENT")
        if coefficients[0] == 0:
            raise EvalError("Highest Degree coefficient cannot be zero")
        x = sp.Symbol("x")
        poly = sum(
            coefficient * x ** (len(coefficients) - i - 1)
            for i, coefficient in enumerate(coefficients)
        )
        roots = sp.Poly(poly, x).all_roots()
        result = {"roots": roots, "polynomial": sp.sstr(poly)}
        if len(coefficients) == 3:
            a, b, c = coefficients
            vx = -b / (2 * a)
            result["vertex"] = [vx, poly.subs(x, vx)]
        calc.table_function = sp.sstr(poly)
        return result
    if operation == "system":
        a = matrix(calc, params.get("coefficients", [[1, 1], [1, -2]]))
        b = sp.Matrix(sequence(calc, params.get("rhs", [1, 3]), 3))
        if a.rows != a.cols or a.rows not in (2, 3) or b.rows != a.rows:
            raise EvalError("DIM MISMATCH")
        if a.rank() < a.row_join(b).rank():
            raise EvalError("No Solution Found")
        if a.rank() < a.cols:
            raise EvalError("Infinite Solutions")
        solution = a.inv() * b
        for v, item in zip(VARIABLES, solution):
            s.memory[v] = sp.sstr(item)
        return dict(zip(VARIABLES, solution))
    if operation in ("matrix", "vector"):
        name = params.get("name", "A" if operation == "matrix" else "u")
        valid = ["A", "B", "C"] if operation == "matrix" else ["u", "v", "w"]
        if name not in valid:
            raise EvalError("ARGUMENT")
        data = params.get(
            "values", [[1, 2], [3, 4]] if operation == "matrix" else [2, 3]
        )
        parsed = (
            matrix(calc, data)
            if operation == "matrix"
            else sp.Matrix(sequence(calc, data, 3))
        )
        if operation == "vector" and parsed.rows not in (2, 3):
            raise EvalError("DIM MISMATCH")
        container = s.matrices if operation == "matrix" else s.vectors
        container[name] = (
            [[sp.sstr(x) for x in row] for row in parsed.tolist()]
            if operation == "matrix"
            else [sp.sstr(x) for x in parsed]
        )
        return {"name": name, "values": parsed}
    if operation == "array_expression":
        expression = params.get("expression", "det([A])")
        calc.set_expression(expression)
        if s.error:
            raise EvalError(s.error)
        return {"result": s.result}
    if operation == "data":
        lists = params.get("lists", {"L1": [45, 55, 55, 55]})
        if not isinstance(lists, dict) or any(
            name not in ["L1", "L2", "L3"] for name in lists
        ):
            raise EvalError("ARGUMENT")
        updated = {name: list(s.stat_lists[name]) for name in ["L1", "L2", "L3"]}
        for name, items in lists.items():
            updated[name] = [sp.sstr(x) for x in sequence(calc, items)] if items else []
        formulas = params.get("formulas", calc.list_formulas)
        if not isinstance(formulas, dict) or any(
            k not in updated or not isinstance(v, str) for k, v in formulas.items()
        ):
            raise EvalError("FORMULA")
        remaining = dict(formulas)
        for _ in range(3):
            for name, formula in list(remaining.items()):
                dependencies = set(re.findall(r"\bL[123]\b", formula))
                if not dependencies or name in dependencies:
                    raise EvalError("FORMULA")
                if any(dep in remaining for dep in dependencies):
                    continue
                lengths = {len(updated[dep]) for dep in dependencies}
                if len(lengths) != 1:
                    raise EvalError("DIM MISMATCH")
                updated[name] = [
                    sp.sstr(
                        value(
                            calc,
                            formula,
                            {dep: value(calc, updated[dep][i]) for dep in dependencies},
                        )
                    )
                    for i in range(next(iter(lengths)))
                ]
                del remaining[name]
        if remaining:
            raise EvalError("FORMULA")
        calc.list_formulas = dict(formulas)
        s.stat_lists.update(updated)
        return {name: s.stat_lists[name] for name in ["L1", "L2", "L3"]}
    if operation.startswith("stats:"):
        kind = operation.split(":")[1]
        if kind == "StatVars":
            return calc.stat_results or {"message": "Calculate statistics first"}
        calc.stat_results = stats(calc, kind, params)
        return calc.stat_results
    if operation.startswith("distribution:"):
        return distribution(calc, operation.split(":")[1], params)
    if operation == "base":
        source = params.get("from", s.base)
        target = params.get("to", "HEX")
        if source not in ["DEC", "HEX", "BIN", "OCT"] or target not in [
            "DEC",
            "HEX",
            "BIN",
            "OCT",
        ]:
            raise EvalError("ARGUMENT")
        number = evaluate_base(str(params.get("value", 127)), source)
        return {
            "value": format_base(int(number), target),
            "base": target,
            "decimal": int(number),
        }
    if operation == "logic":
        left = int(evaluate_base(str(params.get("left", 0)), s.base))
        right = int(evaluate_base(str(params.get("right", 0)), s.base))
        op = params.get("operator", "and")
        functions = {
            "and": lambda: left & right,
            "or": lambda: left | right,
            "xor": lambda: left ^ right,
            "xnor": lambda: ~(left ^ right),
            "not": lambda: ~left,
            "2s": lambda: -left,
            "nand": lambda: ~(left & right),
        }
        if op not in functions:
            raise EvalError("ARGUMENT")
        result = functions[op]() & 0xFFFFFFFF
        if s.base == "DEC" and result >= 2**31:
            result -= 2**32
        return {"value": format_base(result, s.base), "decimal": result}
    if operation == "dms":
        angle = real(calc, params.get("value", "1.5"))
        sign = -1 if angle < 0 else 1
        angle = abs(angle)
        degrees = int(angle)
        minutes = int((angle - degrees) * 60)
        seconds = sp.N(((angle - degrees) * 60 - minutes) * 60, 13)
        return {"degrees": sign * degrees, "minutes": minutes, "seconds": seconds}
    if operation == "storedop":
        calc.stored_operation = str(params.get("operation", "*2+3"))
        if len(calc.stored_operation) > 44:
            raise EvalError("EQUATION LENGTH ERROR")
        return {"stored_operation": calc.stored_operation}
    raise EvalError("ARGUMENT: unknown operation")


# Browser forms keep typed expressions available where MathPrint would provide
# structured input boxes. Every menu workflow has a matching API operation.
def schema(panel, calc):
    fields = []
    operation = panel

    def add(name, default, kind="text", label=None):
        fields.append(
            {"name": name, "default": default, "type": kind, "label": label or name}
        )

    if panel.startswith("constant:"):
        operation = "constant"
        add("name", panel.split(":")[1])
    elif panel.startswith("conversiongroup:"):
        operation = "convert"
        add("value", "-22")
        add("from", "C")
        add("to", "F")
    elif panel in ("mixed", "factor", "dms"):
        add("value", calc.state.entry or sp.sstr(calc._ans_value))
    elif panel in ("degree", "minute", "second", "radian", "gradian"):
        operation = "expression"
        factors = {
            "degree": "deg",
            "radian": "rad",
            "gradian": "grad",
            "minute": "deg",
            "second": "deg",
        }
        add(
            "expression",
            factors[panel]
            + "("
            + (calc.state.entry or "30")
            + ("/60" if panel == "minute" else "/3600" if panel == "second" else "")
            + ")",
        )
        add("values", {}, "json")
    elif panel in ("rectformat", "polarformat"):
        operation = "modes"
        add("complex_format", "a+bi" if panel == "rectformat" else "r∠θ")
    elif panel == "polar":
        operation = "expression"
        add("expression", "polar(5,90)")
        add("values", {}, "json")
    elif panel in (
        "derivative",
        "integral",
        "summation",
        "product",
        "table",
        "solver",
        "expression",
    ):
        add(
            "expression",
            {
                "derivative": "x^2+5x",
                "integral": "-x^2+4",
                "summation": "2x",
                "product": "1/x",
                "table": "x(36-x)",
                "solver": "x^2=2",
                "expression": "2x+z",
            }[panel],
        )
        if panel == "expression":
            add("values", {"x": 2, "z": 5}, "json")
        else:
            add("variable", "x")
        defaults = {
            "derivative": {"point": "-1", "epsilon": "0.001"},
            "integral": {"lower": "-2", "upper": "0"},
            "summation": {"start": 1, "end": 4},
            "product": {"start": 1, "end": 5},
            "table": {"start": 15, "step": 3, "count": 4},
            "solver": {"guess": 1},
        }
        for name, default in defaults.get(panel, {}).items():
            add(name, default)
    elif panel == "polynomial":
        add("coefficients", [1, -2, 2], "json")
    elif panel == "system":
        add("coefficients", [[1, 1], [1, -2]], "json")
        add("rhs", [1, 3], "json")
    elif panel.startswith(("matrixedit:", "vectoredit:")):
        operation = "matrix" if panel.startswith("matrix") else "vector"
        name = panel.split(":")[1]
        add("name", name)
        current = (
            calc.state.matrices if operation == "matrix" else calc.state.vectors
        ).get(name)
        add(
            "values",
            current or ([[1, 2], [3, 4]] if operation == "matrix" else [2, 3]),
            "json",
        )
    elif panel.startswith(("matrix:", "vector:", "matrixop:", "vectorop:")):
        operation = "array_expression"
        name = panel.split(":")[1]
        expression = (
            "[" + name + "]"
            if panel.startswith(("matrix:", "vector:"))
            else (
                {
                    "inverse": "[A]⁻¹",
                    "DotP": "DotP([u],[v])",
                    "CrossP": "CrossP([u],[v])",
                    "norm": "norm([v])",
                }.get(name, name + "([A])")
            )
        )
        add("expression", expression)
    elif panel == "data":
        add(
            "lists",
            {name: calc.state.stat_lists[name] for name in ["L1", "L2", "L3"]},
            "json",
        )
        add("formulas", calc.list_formulas, "json")
    elif panel.startswith("stats:"):
        add("x", calc.state.stat_lists["L1"] or [45, 55, 55, 55], "json")
        if panel != "stats:1-Var Stats":
            add("y", calc.state.stat_lists["L2"] or [30, 25], "json")
    elif panel.startswith("distribution:"):
        name = panel.split(":")[1]
        options = {
            "normalpdf": {"x": 0, "mu": 0, "sigma": 1},
            "normalcdf": {"lower": -1, "upper": 1, "mu": 0, "sigma": 1},
            "invNorm": {"area": 0.95, "mu": 0, "sigma": 1},
            "binompdf": {"n": 20, "p": 0.6, "x": [3, 6, 9]},
            "binomcdf": {"n": 20, "p": 0.6, "x": 9},
            "poissonpdf": {"mu": 3, "x": 2},
            "poissoncdf": {"mu": 3, "x": 2},
        }
        for name, default in options[name].items():
            add(name, default, "json" if isinstance(default, list) else "text")
    elif panel.startswith(("baseconvert:", "basetype:")):
        operation = "base"
        add("value", calc.state.entry or "127")
        add("from", calc.state.base)
        add("to", panel.split(":")[1])
    elif panel.startswith("logic:"):
        operation = "logic"
        add("operator", panel.split(":")[1])
        add("left", format_base(15, calc.state.base))
        add("right", format_base(10, calc.state.base))
    elif panel == "setop":
        operation = "storedop"
        add("operation", "*2+3")
    else:
        return None
    return {
        "operation": operation,
        "fields": fields,
        "title": panel.replace(":", " · "),
    }
