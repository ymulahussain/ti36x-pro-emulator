"""FastAPI HTTP API + static web UI for the TI-36X Pro emulator.

Endpoints:
    GET  /              → web UI
    GET  /state         → current calculator state
    POST /press         → { "key": "sin" } — press one key
    POST /press_seq     → { "keys": ["5", "add", "3", "enter"] }
    POST /expr          → { "expression": "2+2" } — shortcut eval
    POST /reset         → reset state
    GET  /keys          → key metadata + layout grid
    GET  /events        → Server-Sent Events stream of state updates
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .engine import Calculator
from .keys import KEYS, grid_layout, top_keys, menu_keys


CALC = Calculator()
SUBSCRIBERS: set[asyncio.Queue] = set()

app = FastAPI(title="TI-36X Pro Emulator")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _broadcast() -> None:
    payload = CALC.state.to_dict()
    dead = []
    for q in list(SUBSCRIBERS):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        SUBSCRIBERS.discard(q)


class PressBody(BaseModel):
    key: str


class PressSeqBody(BaseModel):
    keys: list[str]


class ExprBody(BaseModel):
    expression: str


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_DIR / "index.html").read_text()


@app.get("/state")
async def state() -> dict[str, Any]:
    return CALC.state.to_dict()


@app.get("/keys")
async def keys() -> dict[str, Any]:
    return {
        "grid": grid_layout(),
        "top": top_keys(),
        "menu": menu_keys(),
        "keys": {
            name: {
                "label": k.label,
                "shift": k.shift,
                "row": k.row,
                "col": k.col,
                "group": k.group,
            }
            for name, k in KEYS.items()
        },
    }


@app.post("/press")
async def press(body: PressBody) -> dict[str, Any]:
    CALC.press(body.key)
    _broadcast()
    return CALC.state.to_dict()


@app.post("/press_seq")
async def press_seq(body: PressSeqBody) -> dict[str, Any]:
    for k in body.keys:
        CALC.press(k)
        _broadcast()
        await asyncio.sleep(0.12)  # small animation delay so UI can show each press
    return CALC.state.to_dict()


@app.post("/expr")
async def expr(body: ExprBody) -> dict[str, Any]:
    CALC.set_expression(body.expression)
    _broadcast()
    return CALC.state.to_dict()


@app.post("/reset")
async def reset() -> dict[str, Any]:
    CALC.reset()
    _broadcast()
    return CALC.state.to_dict()


@app.get("/events")
async def events() -> StreamingResponse:
    async def gen():
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        SUBSCRIBERS.add(q)
        try:
            # push current state immediately
            yield f"data: {json.dumps(CALC.state.to_dict())}\n\n"
            while True:
                payload = await q.get()
                yield f"data: {json.dumps(payload)}\n\n"
        finally:
            SUBSCRIBERS.discard(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
