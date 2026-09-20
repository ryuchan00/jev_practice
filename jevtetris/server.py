"""FastAPI + WebSocket。2 エージェントを別スレッドで走らせ、盤面をそのまま流す。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agents import AGENT_NAMES, build
from .match import MatchConfig, play

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="jev-tetris")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/agents")
async def agents() -> dict[str, list[str]]:
    return {"agents": list(AGENT_NAMES)}


async def _run_agent(name: str, config: MatchConfig, send) -> None:
    """同期の play() を別スレッドで回し、イベントだけをイベントループに戻す。"""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def worker() -> None:
        try:
            agent = build(name)
        except Exception as exc:
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "agent": name, "message": str(exc)}
            )
            loop.call_soon_threadsafe(queue.put_nowait, None)
            return
        try:
            for event in play(agent, config):
                loop.call_soon_threadsafe(queue.put_nowait, {"agent": name, **event})
        except Exception as exc:  # 片方が落ちても相手の対局は続ける
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "agent": name, "message": str(exc)}
            )
        finally:
            agent.close()
            loop.call_soon_threadsafe(queue.put_nowait, None)

    task = loop.run_in_executor(None, worker)
    while True:
        event = await queue.get()
        if event is None:
            break
        await send(event)
    await task


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        request = json.loads(await websocket.receive_text())
    except (WebSocketDisconnect, json.JSONDecodeError):
        return

    names = request.get("agents") or ["heuristic", "jev"]
    config = MatchConfig(
        seed=int(request.get("seed", 0)),
        target_lines=int(request.get("target_lines", 20)),
        max_pieces=int(request.get("max_pieces", 200)),
    )

    lock = asyncio.Lock()

    async def send(event: dict) -> None:
        async with lock:
            await websocket.send_text(json.dumps(event, ensure_ascii=False))

    try:
        await asyncio.gather(*(_run_agent(n, config, send) for n in names))
        await send({"type": "done"})
        await websocket.close()
    except WebSocketDisconnect:
        return
