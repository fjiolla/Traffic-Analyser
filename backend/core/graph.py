"""
LangGraph State Machine — Wires all agents into a multi-agent orchestration graph.
Flow: feed_ingestion → [risk_scorer, anomaly_detector] → (if incident) →
      [signal_agent || routing_agent || alert_agent || density_agent] → supervisor → narrative
"""
from __future__ import annotations

import asyncio
import time
from typing import TypedDict, Annotated, Callable, Awaitable, Optional
from datetime import datetime

from models.schemas import (
    SegmentSpeed, RiskEntry, IncidentDetection, SignalRecommendation,
    DiversionRoute, AlertDrafts, DensityData, AgentOutput,
    ChatMessage, TimelineEntry, Severity,
)
from core.feed_engine import FeedEngine
from core.risk_scorer import compute_risk_map
from core.anomaly_detector import AnomalyDetector
from agents.signal_agent import run_signal_agent
from agents.routing_agent import run_routing_agent
from agents.alert_agent import run_alert_agent
from agents.density_agent import run_density_agent
from agents.supervisor import run_supervisor
from agents.narrative_agent import NarrativeAgent
from rag.retriever import retrieve_sops
from integrations.twitter_poster import post_tweet


class TrafficState(TypedDict):
    """Complete state for the traffic management graph."""
    # Data layer
    snapshot: list[SegmentSpeed]
    risk_map: list[RiskEntry]
    hour: float

    # Detection
    incident: IncidentDetection | None

    # Agent outputs
    signal_recommendations: list[SignalRecommendation]
    diversion: DiversionRoute | None
    alerts: AlertDrafts | None
    density: DensityData | None

    # Supervisor
    agent_output: AgentOutput | None
    rag_context: list[str]

    # Meta
    timeline: list[TimelineEntry]
    processing: bool
    last_update: str


class TrafficGraph:
    """Orchestrates the multi-agent traffic management pipeline."""

    def __init__(self, feed_engine: FeedEngine, on_event: Optional[Callable[[dict], Awaitable[None]]] = None):
        self.feed = feed_engine
        self.detector = AnomalyDetector()
        self.narrative = NarrativeAgent(feed_engine=feed_engine)
        self._on_event = on_event
        self._state: TrafficState = {
            "snapshot": [],
            "risk_map": [],
            "hour": 8.5,
            "incident": None,
            "signal_recommendations": [],
            "diversion": None,
            "alerts": None,
            "density": None,
            "agent_output": None,
            "rag_context": [],
            "timeline": [],
            "processing": False,
            "last_update": "",
        }
        self._incident_active = False
        self._auto_post = False

    def get_state(self) -> TrafficState:
        return self._state

    def get_narrative_agent(self) -> NarrativeAgent:
        return self.narrative

    def set_auto_post(self, enabled: bool):
        self._auto_post = enabled

    def get_auto_post(self) -> bool:
        return self._auto_post

    async def _emit(self, data: dict):
        """Emit a WebSocket event if callback is registered."""
        if self._on_event:
            await self._on_event(data)

    async def process_tick(self, snapshot: list[SegmentSpeed], hour: float):
        """Process one tick of data through the pipeline."""
        self._state["snapshot"] = snapshot
        self._state["hour"] = hour
        self._state["last_update"] = datetime.now().isoformat()

        # Step 1: Update baselines and compute risk
        self.detector.update_baselines(snapshot)
        risk_map = compute_risk_map(snapshot, hour)
        self._state["risk_map"] = risk_map

        # Step 2: Detect anomalies (only if no active incident)
        if not self._incident_active:
            detection = self.detector.detect(snapshot, risk_map)
            if detection and detection.detected:
                self._state["incident"] = detection
                self._incident_active = True
                self._state["timeline"].append(TimelineEntry(
                    timestamp=datetime.now().isoformat(),
                    event=f"🚨 Incident detected: {detection.severity.value} on {detection.street_name}",
                    category="detection",
                ))
                await self._emit({"type": "incident_detected", "incident": detection.model_dump()})
                # Trigger agent pipeline
                await self._run_agents(detection, snapshot, risk_map)

    async def trigger_incident(self, segment_id: str | None = None, severity: Severity = Severity.HIGH):
        """Manually trigger an incident (for demo)."""
        snapshot = self._state["snapshot"] or self.feed.get_snapshot()
        if not snapshot:
            return

        if segment_id:
            target = next((s for s in snapshot if s.segment_id == segment_id), snapshot[0])
        else:
            # Pick a dramatic segment (Flatbush Ave or similar major road)
            target = next(
                (s for s in snapshot if "flatbush" in s.street_name.lower()),
                next(
                    (s for s in snapshot if "atlantic" in s.street_name.lower()),
                    snapshot[0]
                )
            )

        # Inject speed drop
        self.feed.inject_incident(target.segment_id, speed_factor=0.05)

        incident = self.detector.force_incident(target, severity)
        self._state["incident"] = incident
        self._incident_active = True

        risk_map = compute_risk_map(snapshot, self._state["hour"])
        self._state["risk_map"] = risk_map

        self._state["timeline"].append(TimelineEntry(
            timestamp=datetime.now().isoformat(),
            event=f"🚨 Incident triggered: {incident.severity.value} on {incident.street_name}",
            category="detection",
        ))

        await self._emit({"type": "incident_detected", "incident": incident.model_dump()})
        await self._run_agents(incident, snapshot, risk_map)
        return incident

    async def _run_agents(
        self,
        incident: IncidentDetection,
        snapshot: list[SegmentSpeed],
        risk_map: list[RiskEntry],
    ):
        """Run all agents in parallel, then supervisor."""
        self._state["processing"] = True
        start = time.time()

        try:
            # RAG retrieval (fast, no LLM)
            rag_query = f"{incident.severity.value} incident {incident.street_name} {incident.description}"
            rag_context = retrieve_sops(rag_query, top_k=2)
            self._state["rag_context"] = rag_context

            # Fan-out: Run signal, routing, alert, density agents in parallel
            signal_task = run_signal_agent(incident, snapshot, risk_map)
            routing_task = run_routing_agent(incident, snapshot, risk_map)
            alert_task = run_alert_agent(incident)
            density_task = run_density_agent(snapshot)

            signals, diversion, alerts, density = await asyncio.gather(
                signal_task, routing_task, alert_task, density_task
            )

            self._state["signal_recommendations"] = signals or []
            self._state["diversion"] = diversion
            self._state["alerts"] = alerts
            self._state["density"] = density

            # Update alerts with diversion info
            if diversion and alerts:
                alerts_with_diversion = await run_alert_agent(incident, diversion)
                self._state["alerts"] = alerts_with_diversion

            # Fan-in: Supervisor
            agent_output = await run_supervisor(
                incident, signals, diversion, alerts, density, rag_context
            )
            self._state["agent_output"] = agent_output
            self._state["timeline"].extend(agent_output.timeline)

            # Update narrative agent context
            self.narrative.set_context(incident, agent_output, snapshot, risk_map)

            # Auto-post tweet if enabled
            if self._auto_post and alerts and alerts.tweet:
                tweet_result = post_tweet(alerts.tweet)
                tweet_status = tweet_result.get("status", "unknown")
                if tweet_status == "posted":
                    self._state["timeline"].append(TimelineEntry(
                        timestamp=datetime.now().isoformat(),
                        event=f"📱 Tweet posted: {tweet_result.get('url', '')}",
                        category="social",
                    ))
                else:
                    reason = tweet_result.get("reason", "unknown")
                    self._state["timeline"].append(TimelineEntry(
                        timestamp=datetime.now().isoformat(),
                        event=f"📱 Tweet {tweet_status}: {reason}",
                        category="social",
                    ))

            elapsed = round(time.time() - start, 2)
            self._state["timeline"].append(TimelineEntry(
                timestamp=datetime.now().isoformat(),
                event=f"✅ All agents complete ({elapsed}s total)",
                category="system",
            ))

            await self._emit({
                "type": "agents_complete",
                "output": agent_output.model_dump() if agent_output else None,
            })

        except Exception as e:
            print(f"Agent pipeline error: {e}")
            self._state["timeline"].append(TimelineEntry(
                timestamp=datetime.now().isoformat(),
                event=f"❌ Agent pipeline error: {str(e)[:100]}",
                category="error",
            ))
        finally:
            self._state["processing"] = False

    async def resolve_incident(self):
        """Clear the active incident."""
        self._incident_active = False
        self.feed.clear_incident()
        self._state["incident"] = None
        self._state["signal_recommendations"] = []
        self._state["diversion"] = None
        self._state["alerts"] = None
        self._state["processing"] = False
        self.narrative.clear()
        self._state["timeline"].append(TimelineEntry(
            timestamp=datetime.now().isoformat(),
            event="✅ Incident resolved, returning to normal operations",
            category="resolution",
        ))
        await self._emit({"type": "incident_resolved"})
