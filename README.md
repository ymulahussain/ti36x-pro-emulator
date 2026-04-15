# 36X Pro Emulator

A browser-based emulator of a scientific calculator inspired by the 36X Pro
form factor, with an HTTP API and an MCP server so AI assistants can drive it
live while you watch each keypress animate in the browser.

This is an independent, unaffiliated educational project. No vendor branding
or trademarks are used.

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

## HTTP API

| Method | Path          | Body                               | Purpose                          |
|--------|---------------|------------------------------------|----------------------------------|
| GET    | `/state`      |                                    | current state                    |
| GET    | `/keys`       |                                    | key layout + metadata            |
| POST   | `/press`      | `{"key":"sin"}`                    | press one key                    |
| POST   | `/press_seq`  | `{"keys":["5","add","3","enter"]}` | press a list, animated           |
| POST   | `/expr`       | `{"expression":"2+2"}`             | evaluate an expression directly  |
| POST   | `/reset`      |                                    | reset state                      |
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
      "command": "python",
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
      "command": "python3",
      "args": ["/path/to/ti36x-pro-emulator/mcp_server.py"]
    }
  }
}
```

## What's implemented

**v1 (core):** digits, `+ − × ÷`, parentheses, `^`, `x²`, `x⁻¹`, `√`, `π`, `e`,
`sin cos tan` (with DEG/RAD/GRAD), `asin acos atan`, `log ln`, `10^x`, `eˣ`,
scientific entry (`EE`), `(-)` unary minus, `ans`, history, fraction entry,
`2nd` shift, `clear`, `delete`, cursor `← →`, mode cycling.

Evaluation uses SymPy, so exact results like `π/4`, `√2`, `3/4` come out exact
unless the float format is FIX/SCI/ENG.

**Coming next (mode hooks already in place):** matrix, vector, stats (1-var /
2-var), numeric equation solver, polynomial solver, linear-system solver,
table mode, base-n, complex, distributions. These modes exist in the state
machine but their key handlers need to be filled in — happy to extend.

## Driving it from AI

Once the MCP is wired in, ask Claude to:

> "Show me how to compute sin(30°) on the calculator."

Claude will call `press_sequence(["sin","3","0","rparen","enter"])` and you'll
see each key flash in the browser, then the result `1/2` in the result line.
