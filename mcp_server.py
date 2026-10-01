"""MCP server that drives the TI-36X Pro emulator.

Connects to the running HTTP API (default http://127.0.0.1:8765) so that key
presses animate in the browser while the model drives the calculator.

Tools exposed:
    press_key         — press a single key by canonical name
    press_sequence    — press a list of keys, animated
    type_expression   — shortcut: set the entry buffer and evaluate
    get_state         — return current display, mode, angle, error
    get_keys          — return the full key map so the model knows valid names
    reset             — clear all state
    get_panel         — input fields for the selected guidebook workflow
    calculate_feature — advanced calculations and mode settings

Run:
    python mcp_server.py
"""

from __future__ import annotations

import os
import socket
from typing import Any

import urllib.request
import urllib.error
import json

from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("TI36X_API", "http://127.0.0.1:8765").rstrip("/")

mcp = FastMCP("ti36x")


def _request(
    path: str, method: str = "GET", body: dict | None = None
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        # A complete animated sequence can take over fifteen seconds, plus
        # another sequence may already be ahead of it in the API's queue.
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("detail", e.reason)
        except (ValueError, UnicodeDecodeError):
            detail = e.reason
        return {"error": f"emulator returned HTTP {e.code}: {detail}"}
    except urllib.error.URLError as e:
        return {"error": f"could not reach emulator at {API_BASE}: {e}"}
    except (TimeoutError, socket.timeout):
        return {"error": f"emulator request timed out at {API_BASE}"}
    except (ValueError, UnicodeDecodeError):
        return {"error": f"emulator at {API_BASE} returned invalid JSON"}


@mcp.tool()
def press_key(key: str) -> dict[str, Any]:
    """Press a single calculator key by name.

    Valid names: digits ("0"-"9"), "dot", "add", "sub", "mul", "div",
    "lparen", "rparen", "sin", "cos", "tan", "log", "ln", "power", "square",
    "inv", "sqrt", "pi", "e", "i", "ee", "neg", "ans", "frac",
    "enter", "clear", "delete", "2nd", "mode", "left", "right", "up",
    "down", "sto", "math", "prb", "fd", "on", "lnlog", "exp10", "sq",
    "asin", "acos", "atan", "abs", "ncr", "npr", "factorial", "exp",
    "reciprocal". Use get_keys for metadata and shortcuts.

    Multi-tap sin/cos/tan cycles normal, inverse, hyperbolic, inverse hyperbolic.
    lnlog cycles ln/log; exp10 cycles exp/10^x; pi cycles pi/e/i;
    prb cycles factorial/nCr/nPr; var cycles x/y/z/t/a/b/c/d.
    2nd + sq = sqrt, 2nd + frac = mixed number, 2nd + power = nth root.
    The reciprocal shortcut key is reciprocal (or inv).
    2nd + sin/cos/tan opens numeric/polynomial/system solvers; mode opens settings.
    select_0, select_1, etc. choose a menu item; tab_0, tab_1 choose tabs.
    """
    return _request("/press", "POST", {"key": key})


@mcp.tool()
def press_sequence(keys: list[str]) -> dict[str, Any]:
    """Press a list of keys in order with a small animation delay so the user
    can watch each press in the browser. Prefer this over many single presses.

    Example — compute sin(30°): ["sin", "3", "0", "rparen", "enter"]
    """
    return _request("/press_seq", "POST", {"keys": keys})


@mcp.tool()
def type_expression(expression: str) -> dict[str, Any]:
    """Shortcut: set the entry buffer to a raw expression and evaluate.

    Use calculator glyphs: × ÷ − π √ ² ⁻¹ or ASCII (* / -) — both work.
    Example: "sin(30)" or "2+2" or "√(2)"
    """
    return _request("/expr", "POST", {"expression": expression})


@mcp.tool()
def get_state() -> dict[str, Any]:
    """Return current calculator state: entry buffer, result, mode, angle,
    error (if any), and recent history."""
    return _request("/state")


@mcp.tool()
def get_keys() -> dict[str, Any]:
    """Return the full key layout and metadata so you know what's valid."""
    return _request("/keys")


@mcp.tool()
def reset() -> dict[str, Any]:
    """Reset the calculator to power-on state."""
    return _request("/reset", "POST")


@mcp.tool()
def get_panel() -> dict[str, Any]:
    """Return the input form for the selected advanced calculator workflow.

    Choose a workflow with keypad menus first (for example 2nd + sin for the
    numeric solver). The result gives the operation name and parameter fields
    accepted by calculate_feature. No credentials are required.
    """
    return _request("/panel") or {"message": "Select an advanced workflow first."}


@mcp.tool()
def calculate_feature(operation: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Run a guidebook calculation or change calculator settings.

    Operations include modes, derivative, integral, summation, product, table,
    expression, solver, polynomial, system, matrix, vector, array_expression,
    data, stats:1-Var Stats, stats:2-Var Stats, stats:LinReg, stats:QuadraticReg,
    stats:CubicReg, stats:LnReg, stats:PwrReg, stats:ExpReg,
    distribution:normalpdf/normalcdf/invNorm/binompdf/binomcdf/poissonpdf/poissoncdf,
    constant, convert, factor, mixed, base, logic, dms, storedop.
    Use get_panel after selecting a keypad menu for its parameter names.
    Examples: modes with {"angle":"RAD"}; table with
    {"expression":"x(36-x)","start":15,"step":3,"count":4};
    system with {"coefficients":[[1,1],[1,-2]],"rhs":[1,3]}.
    Results appear in the browser and feature_result in the returned state.
    """
    return _request(
        "/feature", "POST", {"operation": operation, "parameters": parameters}
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
