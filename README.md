# 36X Pro Emulator

A browser-based TI-36X Pro emulator with a face modeled on the supplied hardware
photo, an HTTP API and an MCP server so AI assistants can drive it
live while you watch each keypress animate in the browser.

This is an independent, unaffiliated educational project. TI-36X Pro and Texas
Instruments are trademarks of Texas Instruments; their appearance identifies
the calculator being emulated and does not imply endorsement.

## Install

```bash
git clone https://github.com/ymulahussain/ti36x-pro-emulator
cd ti36x-pro-emulator
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run the calculator

```bash
python run.py
# → http://127.0.0.1:8765
```

Click keys, or type on your keyboard (digits, + − × ÷ ^ ( ) = Enter Esc ←).

The face follows the supplied calculator photo: contoured black housing,
six solar cells, gray LCD, oval function keys, gray number keys and blue
secondary legends. Menus stay inside the LCD. Open **History & tools** below
the calculator for history, reset, extra shortcuts and advanced input forms.
The face scales as a unit on smaller screens.

## HTTP API

| Method | Path          | Body                               | Purpose                          |
|--------|---------------|------------------------------------|----------------------------------|
| GET    | `/state`      |                                    | current state                    |
| GET    | `/keys`       |                                    | key layout + metadata            |
| POST   | `/press`      | `{"key":"sin"}`                    | press one key                    |
| POST   | `/press_seq`  | `{"keys":["5","add","3","enter"]}` | press a list, animated           |
| POST   | `/expr`       | `{"expression":"2+2"}`             | evaluate an expression directly  |
| POST   | `/reset`      |                                    | reset state                      |
| GET    | `/panel`      |                                    | fields for the selected workflow |
| POST   | `/feature`    | `{"operation":"table","parameters":{"expression":"x(36-x)","start":15,"step":3,"count":4}}` | advanced calculation |
| GET    | `/events`     |                                    | SSE stream of state updates      |

## MCP server

`mcp_server.py` exposes the same operations as MCP tools. Start the emulator
first, then register the MCP server with your client.

### Claude Code

Add to `~/.claude/settings.json` (or run `claude mcp add`):

```jsonc
{
  "mcpServers": {
    "ti36x": {
      "command": "/path/to/ti36x-pro-emulator/.venv/bin/python",
      "args": ["/path/to/ti36x-pro-emulator/mcp_server.py"],
      "env": { "TI36X_API": "http://127.0.0.1:8765" }
    }
  }
}
```

### Claude Desktop

In `~/Library/Application Support/Claude/claude_desktop_config.json`:

```jsonc
{
  "mcpServers": {
    "ti36x": {
      "command": "/path/to/ti36x-pro-emulator/.venv/bin/python",
      "args": ["/path/to/ti36x-pro-emulator/mcp_server.py"]
    }
  }
}
```

## Guidebook behavior

The supplied TI-36X Pro guidebook is the behavioral reference. See
[compatibility and remaining differences](docs/guidebook-compatibility.md).
This is an independent implementation, not a firmware or pixel-exact emulator.

Repeated presses cycle multi-tap keys: sin → asin → sinh → asinh; ln → log;
exp → 10^x; π → e → i; factorial → nCr → nPr; x → y → z → t → a → b → c → d.
`mode` opens a settings menu for angle units, numeric notation, decimal places,
complex format, number base and Classic/MathPrint entry. Arrows navigate;
Enter selects; Clear or 2nd + mode exits.

Normal calculations support exact fractions, roots, π, arithmetic, chained
answers, scientific entry, trig/hyperbolics, logarithms, number functions,
probability, memory and history. Enter closes open parentheses. `2nd + sq`
enters a square root; `2nd + 7` starts mixed-number entry and `2nd + frac`
selects the reciprocal. The supplemental `1/x` button gives a reciprocal.
Store selects one of eight variables using
the variable key, and commits on Enter. On/off preserves state until the server
restarts; reset requires confirmation.

The blue shortcuts open advanced input panels: calculus, statistics and
regressions, distributions, tables, matrices, vectors, solvers, expressions,
constants, conversions, complex numbers and number bases. Panels use ordinary
expressions and JSON arrays for data; they show the parameter names accepted
by the HTTP `/feature` endpoint and MCP `calculate_feature` tool. For example:

```json
{"operation":"system","parameters":{"coefficients":[[1,1],[1,-2]],"rhs":[1,3]}}
```

This returns x = 5/3 and y = -2/3 and stores them in the calculator's variables.
Use `/keys` for keypad/shortcut metadata and `/panel` for the selected input form.
Invalid request bodies return HTTP 422 before mutating calculator state.
Calculation errors remain visible in the returned state. Animated sequences are
serialized with other mutations so concurrent clients cannot mix their keys.
Run one server worker: this is one shared calculator, not a per-user service.

## Development checks

```bash
python -m pip install -e '.[test]'
python -m unittest discover -s tests -v
python -m pip check
```

The MCP SDK dependency is constrained to v1 because this project uses FastMCP.
Built wheels include the browser assets.

The original LCD font is bundled and requires no external font service. To
regenerate it, install `fonttools[woff]` in a development environment and run
`python tools/build_lcd_font.py`. This is optional and not needed to run the app.

For optional browser tests, start the calculator, install Playwright outside
this repository, and point it at an installed Chromium binary:

```bash
npm install --prefix /tmp/ti36x-browser-tools playwright
NODE_PATH=/tmp/ti36x-browser-tools/node_modules \
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium \
node tests/browser.cjs
```

`CALCULATOR_URL` overrides the browser test's local API address. The browser
test resets calculator state; run it before an interactive session.

## Driving it from AI

Once the MCP is wired in, ask Claude to:

> "Show me how to compute sin(30°) on the calculator."

Claude will call `press_sequence(["sin","3","0","rparen","enter"])` and you'll
see each key flash in the browser, then the result `1/2` in the result line.
