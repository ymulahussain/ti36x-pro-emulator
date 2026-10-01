"""Menu definitions transcribed from the TI-36X Pro guidebook."""

VARIABLES = ("x", "y", "z", "t", "a", "b", "c", "d")
MODE_ROWS = [
    ("Angle", ["DEG", "RAD", "GRAD"]),
    ("Notation", ["NORM", "SCI", "ENG"]),
    ("Decimals", ["FLOAT", *map(str, range(10))]),
    ("Complex", ["REAL", "a+bi", "r∠θ"]),
    ("Base", ["DEC", "HEX", "BIN", "OCT"]),
    ("Entry", ["CLASSIC", "MATHPRINT"]),
]
MULTI_TAP = {
    "sin": ["sin(", "asin(", "sinh(", "asinh("],
    "cos": ["cos(", "acos(", "cosh(", "acosh("],
    "tan": ["tan(", "atan(", "tanh(", "atanh("],
    "lnlog": ["ln(", "log("],
    "exp10": ["exp(", "10^("],
    "pi": ["π", "e", "i"],
    "prb": ["!", " nCr ", " nPr "],
    "var": list(VARIABLES),
}
# Each item is (label, action). Functions with parentheses paste into the entry;
# other actions select a calculation panel or conversion.
MENUS = {
    "math": {
        "MATH": [
            ("n/d ↔ Un/d", "mixed"),
            ("lcm(", "lcm("),
            ("gcd(", "gcd("),
            ("Pfactor", "factor"),
            ("sum(", "summation"),
            ("prod(", "product"),
        ],
        "NUM": [
            (x + "(", x + "(")
            for x in ["abs", "round", "iPart", "fPart", "int", "min", "max", "mod"]
        ],
        "DMS": [
            ("°", "degree"),
            ("′", "minute"),
            ("″", "second"),
            ("r", "radian"),
            ("g", "gradian"),
            ("→DMS", "dms"),
        ],
        "R↔P": [(x + "(", x + "(") for x in ["rx", "ry", "pr", "pt"]],
    },
    "recall": {"RECALL VAR": [(v, "recall:" + v) for v in VARIABLES]},
    "clearvars": {"CLEAR VAR": [("Yes", "clearvars"), ("No", "quit")]},
    "reset": {"RESET": [("No", "quit"), ("Yes", "reset")]},
    "random": {"RAND": [("rand", "rand()"), ("randint(", "randint(")]},
    "complex": {
        "COMPLEX": [
            ("∠", "polar"),
            ("angle(", "angle("),
            ("abs(", "abs("),
            ("→r∠θ", "polarformat"),
            ("→a+bi", "rectformat"),
            ("conj(", "conj("),
            ("real(", "real("),
            ("imag(", "imag("),
        ]
    },
    "matrix": {
        "NAMES": [(x, "matrix:" + x) for x in ["A", "B", "C", "Ans", "I2", "I3"]],
        "MATH": [
            (x, "matrixop:" + x) for x in ["det", "transpose", "inverse", "ref", "rref"]
        ],
        "EDIT": [(x, "matrixedit:" + x) for x in ["A", "B", "C"]],
    },
    "vector": {
        "NAMES": [(x, "vector:" + x) for x in ["u", "v", "w", "Ans"]],
        "MATH": [(x, "vectorop:" + x) for x in ["DotP", "CrossP", "norm"]],
        "EDIT": [(x, "vectoredit:" + x) for x in ["u", "v", "w"]],
    },
    "stats": {
        "STAT-REG": [
            (x, "stats:" + x)
            for x in [
                "StatVars",
                "1-Var Stats",
                "2-Var Stats",
                "LinReg",
                "QuadraticReg",
                "CubicReg",
                "LnReg",
                "PwrReg",
                "ExpReg",
            ]
        ],
        "DISTR": [
            (x, "distribution:" + x)
            for x in [
                "normalpdf",
                "normalcdf",
                "invNorm",
                "binompdf",
                "binomcdf",
                "poissonpdf",
                "poissoncdf",
            ]
        ],
    },
    "table": {"TABLE": [("f(", "f("), ("Edit function", "table")]},
    "bases": {
        "CONVR": [(x, "baseconvert:" + x) for x in ["HEX", "BIN", "DEC", "OCT"]],
        "TYPE": [(x, "basetype:" + x) for x in ["HEX", "BIN", "DEC", "OCT"]],
        "LOGIC": [
            (x, "logic:" + x) for x in ["and", "or", "xor", "xnor", "not", "2s", "nand"]
        ],
    },
    "constants": {"NAMES": [], "UNITS": []},
    "conversions": {
        "CONVERSIONS": [
            (x, "conversiongroup:" + x)
            for x in [
                "English–Metric",
                "Temperature",
                "Speed and Length",
                "Pressure",
                "Power and Energy",
            ]
        ]
    },
}
SHIFT_MENUS = {
    "pi": "complex",
    "math": "matrix",
    "ee": "vector",
    "data": "stats",
    "prb": "random",
    "table": "expression",
    "lnlog": "derivative",
    "exp10": "integral",
    "sin": "solver",
    "cos": "polynomial",
    "tan": "system",
    "lparen": "constants",
    "8": "conversions",
    "9": "bases",
    "sto": "recall",
    "var": "clearvars",
    "0": "reset",
    "rparen": "storedop",
    "mul": "setop",
}
