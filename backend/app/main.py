import asyncio
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.schemas import DatasetFrame, Incident, LabFrame, PlantState, ReplaySeries, RtfFrame
from app.services.baseline import state as baseline_state
from app.services import ai4i_dataset, equipment_prognosis, tep_dataset, tep_models, tep_replay, tep_rtf

app = FastAPI(title="SentinelTwin API", version="0.4.0", description="Dataset-driven Tennessee Eastman Process and AI4I research dashboard. Not connected to a physical plant.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    models = tep_models.availability()
    datasets = {"tep": tep_dataset.available(), "ai4i": ai4i_dataset.available(), "rtf": tep_rtf.available(),
                "prognosis_lab": equipment_prognosis.available()}
    rtf_model = tep_rtf.model_availability()
    lab_model = equipment_prognosis.model_availability()
    ready = all(datasets.values()) and all(value == "ready" for value in models.values()) and rtf_model == "ready" and lab_model == "ready"
    return {"status": "ok" if ready else "degraded", "data_mode": "TEP_DATASET",
            "tep_dataset": "available" if datasets["tep"] else "unavailable",
            "ai4i_dataset": "available" if datasets["ai4i"] else "unavailable",
            "tep_replay": "available" if tep_replay.available() else "unavailable",
            "tep_detector": models["detector"], "tep_pressure_forecast": models["pressure"],
            "tep_rtf_dataset": "available" if datasets["rtf"] else "unavailable",
            "tep_rtf_prognosis": rtf_model,
            "equipment_prognosis_dataset": "available" if datasets["prognosis_lab"] else "unavailable",
            "equipment_prognosis_model": lab_model}


@app.get("/api/v1/prognosis-lab/options")
def prognosis_lab_options() -> dict:
    try:
        return equipment_prognosis.options()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"Equipment prognosis dataset unavailable: {exc}") from exc


@app.get("/api/v1/prognosis-lab/frame", response_model=LabFrame)
def prognosis_lab_frame(run: int = 1, sample: int = 1, points: int = 90) -> LabFrame:
    try:
        return equipment_prognosis.frame(run, sample, points)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/models/equipment-prognosis")
def equipment_prognosis_card() -> dict:
    if equipment_prognosis.model_availability() != "ready":
        raise HTTPException(status_code=503, detail="Equipment prognosis model is not ready")
    return equipment_prognosis.model()[1]


@app.get("/api/v1/tep/rtf/options")
def tep_rtf_options() -> dict:
    try:
        return tep_rtf.options()
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=f"RTF dataset unavailable: {exc}") from exc


@app.get("/api/v1/tep/rtf/frame", response_model=RtfFrame)
def tep_rtf_frame(case: str = "case1", run: int = 1, sample: int = 1, points: int = 90) -> RtfFrame:
    try:
        return tep_rtf.frame(case, run, sample, points)
    except (FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/v1/models/tep-rtf-prognosis")
def tep_rtf_card() -> dict:
    if tep_rtf.model_availability() != "ready":
        raise HTTPException(status_code=503, detail="RTF prognosis model is not ready")
    return tep_rtf.model()[1]


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
    try:
        return tep_models.evaluation_card("detector")
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Detector evaluation card could not be read") from exc


@app.get("/api/v1/models/tep-pressure-20m")
def tep_pressure_card() -> dict:
    try:
        return tep_models.evaluation_card("pressure")
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Pressure evaluation card could not be read") from exc


@app.get("/api/v1/incidents", response_model=list[Incident])
def incidents() -> list[Incident]:
    return []


@app.get("/api/v1/report")
def report(source: Literal["tep", "ai4i", "rtf", "prognosis_lab"] = "tep", sample: int = 170, partition: str = "testing", fault: int = 6, run: int = 401, udi: int = 1, case: str = "case1") -> dict:
    if source == "ai4i":
        frame = ai4i_frame(udi)
        return {"status": "ready", "report_kind": "dataset_snapshot", **frame}
    if source == "rtf":
        frame = tep_rtf_frame(case, run, sample, 90)
        return {"status": "ready", "report_kind": "rtf_snapshot", "source_kind": "TEP_RTF",
                **frame.model_dump(mode="json"), "model_card": tep_rtf_card() if tep_rtf.model_availability() == "ready" else {"status": "unavailable"}}
    if source == "prognosis_lab":
        frame = prognosis_lab_frame(run, sample, 90)
        return {"status": "ready", "report_kind": "equipment_prognosis_snapshot",
                **frame.model_dump(mode="json"),
                "model_card": equipment_prognosis_card() if equipment_prognosis.model_availability() == "ready" else {"status": "unavailable"}}
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

