import asyncio
import json
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.schemas import DatasetFrame, Incident, PlantState, ReplaySeries
from app.services.baseline import state as baseline_state
from app.services import ai4i_dataset, tep_dataset, tep_models, tep_replay

app = FastAPI(title="SentinelTwin API", version="0.4.0", description="Dataset-driven Tennessee Eastman Process and AI4I research dashboard. Not connected to a physical plant.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    models = tep_models.availability()
    ready = tep_dataset.available() and ai4i_dataset.available() and all(value == "ready" for value in models.values())
    return {"status": "ok" if ready else "degraded", "data_mode": "TEP_DATASET", "tep_dataset": "available" if tep_dataset.available() else "unavailable", "ai4i_dataset": "available" if ai4i_dataset.available() else "unavailable", "tep_replay": "available" if tep_replay.available() else "unavailable", "tep_detector": models["detector"], "tep_pressure_forecast": models["pressure"]}


@app.get("/api/v1/tep/dataset/frame", response_model=DatasetFrame)
def tep_dataset_frame(sample: int = 170, points: int = 90, partition: str = "testing", fault: int = 6, run: int = 401) -> DatasetFrame:
    try:
        return tep_dataset.frame(sample, points, partition, fault, run)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/ai4i/frame")
def ai4i_frame(udi: int = 1) -> dict:
    try:
        return ai4i_dataset.frame(udi)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/ai4i/summary")
def ai4i_summary() -> dict:
    try:
        return ai4i_dataset.summary()
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/ai4i/record")
def ai4i_record(udi: int = 1) -> dict:
    try:
        return ai4i_dataset.record(udi)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/ai4i/records")
def ai4i_records(start: int = 1, limit: int = 50) -> dict:
    try:
        return ai4i_dataset.records(start, limit)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/tep/dataset/options")
def tep_dataset_options() -> dict:
    if not tep_dataset.available():
        raise HTTPException(status_code=503, detail="Local TEP Parquet dataset is not available")
    return {"source_kind": "TEP_DATASET", "partitions": ["training", "testing"], "fault_numbers": list(range(21)),
            "run_min": 1, "run_max": 500, "samples_by_partition": {"training": 500, "testing": 960},
            "sample_period_minutes": 3, "notice": tep_dataset.NOTICE}


@app.get("/api/v1/tep/dataset/state", response_model=PlantState)
def tep_dataset_state(sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401) -> PlantState:
    try:
        return tep_dataset.state(sample, partition, fault, run)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/tep/dataset/series", response_model=ReplaySeries)
def tep_dataset_series(end_sample: int = 170, points: int = 90, partition: str = "testing", fault: int = 6, run: int = 401) -> ReplaySeries:
    try:
        return tep_dataset.series(end_sample, points, partition, fault, run)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/plant/state", response_model=PlantState)
def plant_state(sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401) -> PlantState:
    return tep_dataset_state(sample, partition, fault, run)


@app.get("/api/v1/testing/baseline", response_model=PlantState)
def testing_baseline(tick: int = 0) -> PlantState:
    return baseline_state(tick)


@app.get("/api/v1/tep/replay", response_model=PlantState)
def tep_replay_state(sample: int = 1) -> PlantState:
    try:
        return tep_replay.state(sample)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/tep/replay/series", response_model=ReplaySeries)
def tep_replay_series(end_sample: int = 170, points: int = 90) -> ReplaySeries:
    try:
        return tep_replay.series(end_sample, points)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/models/tep-detector")
def tep_detector_card() -> dict:
    card = Path(__file__).resolve().parents[2] / "docs/models/TEP_fault_detector.json"
    if not card.exists():
        raise HTTPException(status_code=503, detail="TEP detector model card is not available")
    try:
        return json.loads(card.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Detector evaluation card could not be read") from exc


@app.get("/api/v1/models/tep-pressure-20m")
def tep_pressure_card() -> dict:
    card = Path(__file__).resolve().parents[2] / "docs/models/TEP_pressure_20m.json"
    if not card.exists():
        raise HTTPException(status_code=503, detail="TEP pressure model card is not available")
    try:
        return json.loads(card.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Pressure evaluation card could not be read") from exc


@app.get("/api/v1/incidents", response_model=list[Incident])
def incidents() -> list[Incident]:
    return []


@app.get("/api/v1/report")
def report(source: Literal["tep", "ai4i"] = "tep", sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401, udi: int = 1) -> dict:
    if source == "ai4i":
        frame = ai4i_frame(udi)
        return {"status": "ready", "report_kind": "dataset_snapshot", **frame}
    frame = tep_dataset_frame(sample, 90, partition, fault, run)
    cards = {}
    for kind, reader in (("detector", tep_detector_card), ("pressure", tep_pressure_card)):
        try:
            cards[kind] = reader()
        except HTTPException:
            cards[kind] = {"status": "unavailable"}
    return {"status": "ready", "report_kind": "dataset_snapshot", "source_kind": "TEP_DATASET",
            **frame.model_dump(mode="json"), "model_cards": cards}


@app.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket, sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401) -> None:
    await websocket.accept()
    try:
        while True:
            snapshot = await asyncio.to_thread(tep_dataset.state, sample, partition, fault, run)
            await websocket.send_json(snapshot.model_dump(mode="json"))
            if sample >= snapshot.total_samples:
                await websocket.close(code=1000, reason="Selected dataset run complete")
                return
            sample += 1
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    except (FileNotFoundError, OSError):
        await websocket.close(code=1011, reason="Dataset unavailable")
    except ValueError:
        await websocket.close(code=1008, reason="Invalid dataset selection")


@app.websocket("/ws/testing/baseline")
async def testing_baseline_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    tick = 0
    try:
        while True:
            await websocket.send_json(baseline_state(tick).model_dump(mode="json"))
            tick += 1
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


@app.websocket("/ws/tep/replay")
async def tep_replay_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    sample = 1
    try:
        while True:
            snapshot = await asyncio.to_thread(tep_replay.state, sample)
            await websocket.send_json(snapshot.model_dump(mode="json"))
            sample = 1 if sample == 960 else sample + 1
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return
    except (OSError, ValueError):
        await websocket.close(code=1011, reason="Replay data unavailable")


# The built dashboard can also run on the API's origin without a Vite server.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend/dist"
if (frontend_dist / "index.html").is_file():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="dashboard")

