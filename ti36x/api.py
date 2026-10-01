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
from contextlib import asynccontextmanager
from contextlib import suppress

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .engine import Calculator, VALID_KEYS, TOKENS_PRIMARY, KEY_ALIASES
from .evaluator import MAX_EXPRESSION_LENGTH, MAX_KEYS
from . import features
from .keys import KEYS, grid_layout, top_keys, menu_keys

CALC = Calculator()
SUBSCRIBERS: set[asyncio.Queue] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mutation_lock = asyncio.Lock()

    async def auto_power_down():
        while True:
            await asyncio.sleep(1)
            async with app.state.mutation_lock:
                if CALC.expire_if_idle():
                    _broadcast()

    task = asyncio.create_task(auto_power_down())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="TI-36X Pro Emulator", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _broadcast(key: str | None = None) -> None:
    payload = CALC.state.to_dict()
    payload["last_key"] = key
    for q in list(SUBSCRIBERS):
        # A slow subscriber still needs the latest state; do not strand it.
        if q.full():
            q.get_nowait()
        q.put_nowait(payload)


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


def validate_key(key: str) -> str:
    if key not in VALID_KEYS:
        raise ValueError(f"Unknown key: {key}. Use /keys for valid names.")
    return key


class PressBody(RequestBody):
    key: str = Field(min_length=1, max_length=32)

    _key = field_validator("key")(validate_key)


class PressSeqBody(RequestBody):
    keys: list[str] = Field(min_length=1, max_length=MAX_KEYS)

    @field_validator("keys")
    @classmethod
    def valid_keys(cls, keys: list[str]) -> list[str]:
        return [validate_key(key) for key in keys]


class ExprBody(RequestBody):
    expression: str = Field(min_length=1, max_length=MAX_EXPRESSION_LENGTH)

    @field_validator("expression")
    @classmethod
    def not_blank(cls, expression: str) -> str:
        if not expression.strip():
            raise ValueError("Expression cannot be blank")
        return expression


class FeatureBody(RequestBody):
    operation: str = Field(min_length=1, max_length=64)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def bounded_parameters(cls, parameters):
        if len(json.dumps(parameters)) > 8192:
            raise ValueError("Calculation parameters are too large")
        return parameters


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
                "enabled": True,
            }
            for name, k in KEYS.items()
        },
        "shortcuts": {
            name: TOKENS_PRIMARY[KEY_ALIASES.get(name, name)]
            for name in sorted(VALID_KEYS - KEYS.keys())
            if name in TOKENS_PRIMARY or name in KEY_ALIASES
        },
        "functions": ["sqrt", "abs", "ln", "log", "exp", "ncr", "npr"],
    }


@app.get("/panel")
async def panel():
    return features.schema(CALC.state.panel, CALC) if CALC.state.panel else None


@app.post("/feature")
async def feature(body: FeatureBody):
    async with app.state.mutation_lock:
        CALC.state.error = None
        try:
            result = features.calculate(CALC, body.operation, body.parameters)
            if isinstance(result, float):
                CALC._display_result(features.sp.Float(str(result), 13))
            elif isinstance(result, (features.sp.Expr, features.sp.MatrixBase)):
                CALC._display_result(result)
            CALC.state.feature_result = features.serialize(result)
        except features.EvalError as error:
            CALC.state.error = str(error)
            CALC.state.result = "Error"
        except Exception:
            CALC.state.error = "ARGUMENT: check the calculation inputs"
            CALC.state.result = "Error"
        _broadcast()
        return CALC.state.to_dict()


@app.post("/press")
async def press(body: PressBody) -> dict[str, Any]:
    async with app.state.mutation_lock:
        CALC.press(body.key)
        _broadcast(KEY_ALIASES.get(body.key, body.key))
        return CALC.state.to_dict()


@app.post("/press_seq")
async def press_seq(body: PressSeqBody) -> dict[str, Any]:
    async with app.state.mutation_lock:
        for k in body.keys:
            CALC.press(k)
            _broadcast(KEY_ALIASES.get(k, k))
            await asyncio.sleep(0.12)
        return CALC.state.to_dict()


@app.post("/expr")
async def expr(body: ExprBody) -> dict[str, Any]:
    async with app.state.mutation_lock:
        CALC.set_expression(body.expression)
        _broadcast()
        return CALC.state.to_dict()


@app.post("/reset")
async def reset() -> dict[str, Any]:
    async with app.state.mutation_lock:
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
                try:
                    payload = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(payload)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            SUBSCRIBERS.discard(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
