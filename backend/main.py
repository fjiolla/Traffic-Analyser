"""
TrafficMind Backend — FastAPI application.
REST + WebSocket server for real-time traffic incident management.
"""
from __future__ import annotations

import os
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from core.feed_engine import FeedEngine
from core.risk_scorer import compute_risk_map, get_hotspots
from core.graph import TrafficGraph
from pydantic import BaseModel
from models.schemas import (
    ChatRequest, ChatResponse, Severity, IncidentDetection,
    FeedTick, TimelineEntry,
)
from rag.retriever import get_all_documents
from typing import Optional


class IncidentTriggerRequest(BaseModel):
    severity: str = "HIGH"
    segment_id: Optional[str] = None

# Global instances
feed_engine = FeedEngine()
traffic_graph: Optional[TrafficGraph] = None
connected_clients: list[WebSocket] = []


async def broadcast_ws(data: dict):
    """Send a JSON message to all connected WebSocket clients."""
    msg = json.dumps(data)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


async def broadcast_tick(tick: FeedTick):
    """Broadcast feed tick to all connected WebSocket clients."""
    state = traffic_graph.get_state() if traffic_graph else {}
    await broadcast_ws({
        "type": "tick",
        "tick": tick.tick,
        "timestamp": tick.timestamp,
        "hour": feed_engine.get_simulated_hour(),
        "segments": [s.model_dump() for s in tick.segments],
        "risk_map": [r.model_dump() for r in (state.get("risk_map") or [])],
        "incident": state.get("incident").model_dump() if state.get("incident") else None,
        "processing": state.get("processing", False),
    })


@asynccontextmanager
async def lifespan(app: FastAPI):
    global traffic_graph
    
    # Initialize
    feed_engine.initialize()
    traffic_graph = TrafficGraph(feed_engine, on_event=broadcast_ws)
    feed_engine.add_listener(broadcast_tick)

    async def on_tick(tick: FeedTick):
        await traffic_graph.process_tick(tick.segments, feed_engine.get_simulated_hour())

    feed_engine.add_listener(on_tick)

    # Start feed in background
    feed_task = asyncio.create_task(feed_engine.run(interval=5.0))

    yield

    # Cleanup
    feed_engine.stop()
    feed_task.cancel()


app = FastAPI(
    title="TrafficMind API",
    description="LLM Co-Pilot for Traffic Incident Command",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── REST Endpoints ────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "segments": len(feed_engine.get_segments()), "timestamp": datetime.now().isoformat()}


@app.get("/api/state")
async def get_state():
    """Get current system state."""
    state = traffic_graph.get_state()
    return {
        "snapshot": [s.model_dump() for s in state.get("snapshot", [])],
        "risk_map": [r.model_dump() for r in state.get("risk_map", [])],
        "incident": state["incident"].model_dump() if state.get("incident") else None,
        "hour": state.get("hour", 0),
        "processing": state.get("processing", False),
        "last_update": state.get("last_update", ""),
    }


@app.get("/api/agents")
async def get_agent_output():
    """Get latest agent outputs."""
    state = traffic_graph.get_state()
    output = state.get("agent_output")
    if not output:
        return {"status": "no_incident", "agent_output": None}

    return {
        "status": "active",
        "agent_output": output.model_dump(),
        "incident": state["incident"].model_dump() if state.get("incident") else None,
    }


@app.get("/api/signals")
async def get_signals():
    """Get signal recommendations."""
    state = traffic_graph.get_state()
    return {
        "recommendations": [s.model_dump() for s in state.get("signal_recommendations", [])],
        "incident": state["incident"].model_dump() if state.get("incident") else None,
    }


@app.get("/api/diversion")
async def get_diversion():
    """Get diversion route."""
    state = traffic_graph.get_state()
    diversion = state.get("diversion")
    return {
        "diversion": diversion.model_dump() if diversion else None,
        "incident": state["incident"].model_dump() if state.get("incident") else None,
    }


@app.get("/api/alerts")
async def get_alerts():
    """Get alert drafts."""
    state = traffic_graph.get_state()
    alerts = state.get("alerts")
    return {
        "alerts": alerts.model_dump() if alerts else None,
        "incident": state["incident"].model_dump() if state.get("incident") else None,
    }


@app.get("/api/density")
async def get_density():
    """Get vehicle density data."""
    state = traffic_graph.get_state()
    density = state.get("density")
    return {
        "density": density.model_dump() if density else None,
    }


@app.get("/api/timeline")
async def get_timeline():
    """Get incident timeline."""
    state = traffic_graph.get_state()
    return {
        "timeline": [t.model_dump() for t in state.get("timeline", [])],
    }


@app.get("/api/hotspots")
async def get_hotspots_endpoint():
    """Get Brooklyn black-spot hotspot data."""
    return {"hotspots": get_hotspots()}


@app.get("/api/documents")
async def get_documents():
    """Get RAG document index."""
    return {"documents": get_all_documents()}


@app.get("/api/metrics")
async def get_metrics():
    """Get evaluation metrics."""
    state = traffic_graph.get_state()
    output = state.get("agent_output")
    incident = state.get("incident")

    base_metrics = {
        "active_segments": len(state.get("snapshot", [])),
        "risk_map_size": len(state.get("risk_map", [])),
        "incident_active": incident is not None,
        "simulated_hour": state.get("hour", 0),
    }

    if output:
        base_metrics.update(output.evaluation_metrics)
        base_metrics["cascade_risk"] = output.cascade_risk
        base_metrics["confidence_scores"] = output.confidence_scores

    if incident:
        # Response time estimate
        base_metrics["incident_severity"] = incident.severity.value
        base_metrics["duration_estimate_min"] = incident.duration_estimate_min
        base_metrics["manual_avg_min"] = 11.0
        base_metrics["time_saved_min"] = round(11.0 - (output.evaluation_metrics.get("response_latency_s", 5) / 60), 1) if output else 0

    return base_metrics


@app.get("/api/twin")
async def get_twin_data():
    """Get digital twin comparison data."""
    state = traffic_graph.get_state()
    snapshot = state.get("snapshot", [])
    incident = state.get("incident")
    diversion = state.get("diversion")

    if not incident or not snapshot:
        return {"no_action": [], "with_action": [], "time_saved_min": 0}

    no_action = []
    with_action = []

    diversion_streets = set(diversion.route_street_names) if diversion else set()

    for seg in snapshot:
        base = {
            "street_name": seg.street_name,
            "lat": seg.lat,
            "lon": seg.lon,
            "segment_id": seg.segment_id,
        }

        # No-action: congestion spreads (distance-decay worsening)
        if seg.segment_id == incident.segment_id:
            no_action_speed = 2.0
        else:
            from core.feed_engine import _haversine
            dist = _haversine(seg.lat, seg.lon, incident.lat, incident.lon)
            if dist < 1.0:
                decay = max(0.2, dist / 1.0)
                no_action_speed = seg.speed * decay
            else:
                no_action_speed = seg.speed

        no_action.append({**base, "speed": round(no_action_speed, 1), "free_flow_speed": seg.free_flow_speed})

        # With-action: diversion working
        if seg.street_name in diversion_streets:
            # Slightly more traffic on diversion route
            with_speed = seg.speed * 0.85
        elif seg.segment_id == incident.segment_id:
            with_speed = seg.speed  # Still blocked but being managed
        else:
            with_speed = min(seg.free_flow_speed, seg.speed * 1.15)  # Recovery

        with_action.append({**base, "speed": round(with_speed, 1), "free_flow_speed": seg.free_flow_speed})

    time_saved = round(incident.duration_estimate_min * 0.3, 1) if incident else 0

    return {
        "no_action": no_action,
        "with_action": with_action,
        "time_saved_min": time_saved,
        "incident": incident.model_dump() if incident else None,
    }


# ─── Actions ───────────────────────────────────────────────


@app.post("/api/trigger-incident")
async def trigger_incident(body: IncidentTriggerRequest):
    """Trigger a demo incident."""
    sev = Severity(body.severity)
    incident = await traffic_graph.trigger_incident(segment_id=body.segment_id, severity=sev)
    if not incident:
        raise HTTPException(status_code=400, detail="No segments available")

    # Wait for agents to complete
    for _ in range(30):
        if not traffic_graph.get_state()["processing"]:
            break
        await asyncio.sleep(1)

    state = traffic_graph.get_state()
    return {
        "incident": incident.model_dump(),
        "agent_output": state["agent_output"].model_dump() if state.get("agent_output") else None,
    }


@app.post("/api/resolve-incident")
async def resolve_incident():
    """Resolve the active incident."""
    await traffic_graph.resolve_incident()
    return {"status": "resolved"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Send a message to the narrative agent."""
    narrative = traffic_graph.get_narrative_agent()
    response = await narrative.chat(request.message)
    return response.model_dump()


@app.get("/api/chat/history")
async def chat_history():
    """Get chat conversation history."""
    narrative = traffic_graph.get_narrative_agent()
    return {"messages": [m.model_dump() for m in narrative.get_messages()]}


# ─── WebSocket ─────────────────────────────────────────────


@app.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    """Real-time feed WebSocket."""
    await websocket.accept()
    connected_clients.append(websocket)

    try:
        while True:
            # Keep connection alive; handle incoming messages
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "trigger_incident":
                severity = msg.get("severity", "HIGH")
                await traffic_graph.trigger_incident(severity=Severity(severity))
            elif msg.get("type") == "resolve_incident":
                await traffic_graph.resolve_incident()
            elif msg.get("type") == "chat":
                narrative = traffic_graph.get_narrative_agent()
                response = await narrative.chat(msg.get("message", ""))
                await websocket.send_text(json.dumps({
                    "type": "chat_response",
                    **response.model_dump(),
                }))

    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
