"""Run the FastAPI server: `python -m live_underwriter.api_server`."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("live_underwriter.api:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
