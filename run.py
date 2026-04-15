"""Start the TI-36X Pro emulator HTTP + web UI.

    python run.py               # serves on http://127.0.0.1:8765
    python run.py --port 9000
"""
import argparse
import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--reload", action="store_true")
    args = ap.parse_args()
    uvicorn.run("ti36x.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
