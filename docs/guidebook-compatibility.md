# Guidebook compatibility

Behavior reference: the supplied **TI-36XPro_Guidebook_EN.pdf**, copyright
2010–2026, 83 PDF pages. Page numbers below refer to printed page numbers.
The PDF is reference material and is not bundled with the project.

This is an independent behavioral implementation using SymPy and numerical
routines, not TI firmware. The regression tests encode numerical examples and
key sequences from the reference. Passing these examples establishes the tested
behaviors; it does not establish identical behavior for every possible input.

| Guidebook pages | Implemented and checked behavior |
| --- | --- |
| 4–13 | On/off preserves settings, memory, history and ans; automatic power down; menu-based modes; multi-tap functions; history paste; answer toggle; Classic versus MathPrint power order; automatic closing parentheses; delete/insert |
| 14–28 | Fraction and mixed-number entry; percentages; scientific entry; square/root/reciprocal; pi; LCM/GCD/factors/sum/product; numeric functions; angles/DMS; polar coordinates; trig/hyperbolics; logs/exponentials |
| 29–36 | Symmetric numerical derivative, numerical integral, stored operations, eight variables, three data lists, linked list formulas |
| 37–50 | Weighted one/two-variable statistics, polynomial/log/power/exponential regressions, normal/binomial/Poisson distributions, factorial/combinations/permutations, seeded randomness |
| 51–66 | Function tables and f(x); matrices up to 3×3; vectors of dimension 2 or 3; numeric, quadratic/cubic and system solvers; number bases and Boolean logic; parameterized expressions |
| 67–78 | Physical constants, compatible unit conversions, real/rectangular/polar complex results, domain/division/overflow and workflow input errors |

## Controls

- Repeated presses on sin/cos/tan select normal, inverse, hyperbolic and inverse
  hyperbolic functions. ln/log, exponential, pi/e/i, probability and variable
  keys also cycle. An intervening key ends the cycle.
- Mode opens settings. Arrow keys navigate; Enter selects. Clear or 2nd + mode
  exits. Mouse menu buttons perform the same selections.
- 2nd + square inserts a square root. 2nd + power inserts an nth root after
  the degree. 2nd + 7 starts mixed-number entry; 2nd + fraction selects the
  reciprocal. The supplemental 1/x,
  square-root and ans buttons provide direct function shortcuts.
- A fraction entered before its numerator uses Down to enter the denominator;
  Right leaves the denominator. Enter closes remaining parentheses.
- Store, followed by repeated variable-key presses and Enter, saves a value to
  x, y, z, t, a, b, c or d. 2nd + store opens the recall menu.
- 2nd + sin/cos/tan opens numeric/polynomial/system solver inputs; 2nd + math
  opens matrices; 2nd + EE opens vectors; 2nd + data opens statistics and
  distributions. Input panels expose each calculation's parameters.
- 2nd + on turns off; on resumes. 2nd + 0 opens reset confirmation; 2 confirms.

## Deliberate differences and remaining fidelity limits

- The browser face follows the supplied front photo, with a fixed four-line
  display and an original dot-matrix font. History, supplemental shortcuts and
  input forms are in a separate, collapsible tools section. The display does
  not enforce the hardware's sixteen-character scrolling or emulate every
  nested MathPrint template and cursor transition. Advanced matrix/statistics/
  solver/table data entry uses forms instead of the hardware's cell-by-cell
  key sequence. Fractions currently display in linear form.
- The casing, materials and manufacturer mark are browser drawings based on
  the supplied photo, rather than a pixel-exact photographic reproduction.
- Classic fraction entry uses the same numeric parser as division and accepts
  expressions beyond the hardware's restricted integer fraction fields.
  Most expressions have a 512-character limit; not every hardware limit on
  pending operations, eight pending values or nested templates is reproduced.
- Exact arithmetic is retained where possible. Approximate results are
  displayed to ten significant digits, with selectable decimal/SCI/ENG modes.
  Numerical algorithms, intermediate precision and boundary rounding are not
  bit-for-bit copies of TI firmware.
- Memory, history, data and settings belong to a running server and are shared
  by its clients. On/off preserves them within that process; restarting the
  Python server resets them. Run one server worker.
- Numerical integration uses adaptive quadrature rather than the undocumented
  hardware algorithm. Solvers depend on the initial guess and do not implement
  every hardware-specific convergence diagnostic.
- Polar angles and DMS use explicit functions or input panels. Suffix notation
  such as degrees/minutes/seconds or a complex polar angle within the raw input
  buffer is not a full MathPrint implementation.
- Stored operations are replayed, but the hardware's iteration counter is not
  displayed. Regression results are available as StatVars; optional hardware
  flows for saving every regression to f(x) are not reproduced.
- Conversions use named compatible units and published physical definitions.
  Platform battery behavior and hardware-specific contrast response cannot be
  reproduced in a browser.

## Verification

Run `python -m unittest discover -s tests -v` after installing `.[test]`.
`tests/test_guidebook.py` identifies the source page for each expected example.
The optional `tests/browser.cjs` checks real Chromium interactions, connection
recovery, ordered requests, input panels and responsive layouts. Live HTTP/SSE
and all MCP tools are also exercised during cloud-environment setup.
