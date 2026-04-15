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

Run:
    python mcp_server.py
"""
from __future__ import annotations

import os
import sys
from typing import Any

import urllib.request
import urllib.error
import json

from mcp.server.fastmcp import FastMCP


API_BASE = os.environ.get("TI36X_API", "http://127.0.0.1:8765")

mcp = FastMCP("ti36x")


def _request(path: str, method: str = "GET", body: dict | None = None) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.URLError as e:
        return {"error": f"could not reach emulator at {API_BASE}: {e}"}


@mcp.tool()
def press_key(key: str) -> dict[str, Any]:
    """Press a single calculator key by name.

    Valid names: digits ("0"-"9"), "dot", "add", "sub", "mul", "div",
    "lparen", "rparen", "sin", "cos", "tan", "log", "ln", "power", "square",
    "inv", "pi", "e", "ee", "neg", "frac", "enter", "clear", "delete",
    "2nd", "mode", "left", "right", "up", "down", "sto", "math", "apps",
    "prb".

    2nd-shift functions (asin, exp, sqrt, etc.) are accessed by first pressing
    "2nd", then the base key.
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


if __name__ == "__main__":
    mcp.run()
