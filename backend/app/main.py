import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import Incident, PlantState
from app.services.baseline import state

app = FastAPI(title="SentinelTwin API", version="0.1.0", description="Academic safety-monitoring integration baseline.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_mode": "SIMULATED_INTEGRATION_BASELINE"}


@app.get("/api/v1/plant/state", response_model=PlantState)
def plant_state() -> PlantState:
    return state()


@app.get("/api/v1/incidents", response_model=list[Incident])
def incidents() -> list[Incident]:
    return []


@app.get("/api/v1/report")
def report() -> dict[str, str]:
    return {"status": "not_available", "reason": "Reporting is planned for Phase 8; no report is fabricated."}


@app.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    tick = 0
    try:
        while True:
            await websocket.send_json(state(tick).model_dump(mode="json"))
            tick += 1
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return

