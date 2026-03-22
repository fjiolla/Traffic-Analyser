"""
Narrative Agent — Conversational TAO loop for officer Q&A.
TAO = Thought → Action (tool call) → Observation → Answer.
Uses Gemini 2.0 Flash with multi-turn memory.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from models.schemas import (
    SegmentSpeed, RiskEntry, IncidentDetection, AgentOutput,
    ChatMessage, ChatResponse,
)

from core.key_manager import get_gemini_key
from rag.retriever import retrieve_sops

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


SYSTEM_PROMPT = """You are TrafficMind, an AI co-pilot assisting traffic control officers in Brooklyn, New York.
You have access to real-time traffic sensor data and incident management tools.

PERSONA: Professional, concise, data-driven. You are a decision-support tool, not a replacement for the officer.
The officer stays in command — you handle the cognitive load.

AVAILABLE TOOLS (use by including [TOOL_CALL: tool_name(args)] in your thinking):
- get_speed(street_name) → current speed in mph and % of normal
- get_risk_score(street_name) → risk score 0-1 with breakdown
- check_diversion_status() → current diversion route status and compliance
- get_density(street_name) → vehicle density and congestion level

RESPONSE FORMAT:
1. Think through the question (brief internal reasoning)
2. Call any tools needed
3. Answer with sensor-backed data and confidence level

Always cite specific data: "Flatbush Ave is currently at 12 mph (40% of normal), risk score 0.78."
End with confidence level: [Confidence: HIGH/MEDIUM/LOW]

IMPORTANT: Maintain context across the conversation. Reference previous questions/answers when relevant.
If the officer asks about safety (e.g., "Is it safe to open the southbound lane?"), 
check speed, risk, and density data before answering."""


class NarrativeAgent:
    """Conversational agent with TAO loop and tool access."""

    def __init__(self):
        self._messages: list[ChatMessage] = []
        self._incident: IncidentDetection | None = None
        self._agent_output: AgentOutput | None = None
        self._snapshot: list[SegmentSpeed] = []
        self._risk_map: list[RiskEntry] = []

    def set_context(
        self,
        incident: IncidentDetection,
        agent_output: AgentOutput,
        snapshot: list[SegmentSpeed],
        risk_map: list[RiskEntry],
    ):
        """Update the agent's context with latest data."""
        self._incident = incident
        self._agent_output = agent_output
        self._snapshot = snapshot
        self._risk_map = risk_map

    def _execute_tool(self, tool_name: str, args: str) -> str:
        """Execute a TAO tool call and return observation."""
        speed_by_name = {s.street_name.lower(): s for s in self._snapshot}
        risk_by_name = {r.street_name.lower(): r for r in self._risk_map}

        if tool_name == "get_speed":
            street = args.strip().strip('"').strip("'").lower()
            # Fuzzy match
            matched = None
            for name, seg in speed_by_name.items():
                if street in name or name in street:
                    matched = seg
                    break
            if matched:
                pct = round(matched.speed / matched.free_flow_speed * 100, 1) if matched.free_flow_speed > 0 else 0
                return f"{matched.street_name}: {matched.speed} mph ({pct}% of normal {matched.free_flow_speed} mph), density: {matched.density} veh/km"
            return f"No speed data found for '{args}'"

        elif tool_name == "get_risk_score":
            street = args.strip().strip('"').strip("'").lower()
            matched = None
            for name, risk in risk_by_name.items():
                if street in name or name in street:
                    matched = risk
                    break
            if matched:
                return (f"{matched.street_name}: risk score {matched.score:.2f} "
                       f"(speed_dev: {matched.speed_deviation:.2f}, "
                       f"historical: {matched.historical_rate:.2f}, "
                       f"tod: {matched.tod_weight:.2f})")
            return f"No risk data found for '{args}'"

        elif tool_name == "check_diversion_status":
            if self._agent_output and self._agent_output.diversion:
                d = self._agent_output.diversion
                return (f"Diversion ACTIVE via {' → '.join(d.route_street_names[:4])}. "
                       f"Risk delta: {d.risk_delta_pct}% safer. "
                       f"Volume redistribution: {d.diversion_volume_pct}%. "
                       f"Confidence: {d.confidence:.0%}")
            return "No active diversion route."

        elif tool_name == "get_density":
            street = args.strip().strip('"').strip("'")
            if self._agent_output and self._agent_output.density:
                density = self._agent_output.density.segment_densities.get(street)
                if density:
                    return f"{street}: density {density} veh/km, overall congestion: {self._agent_output.density.congestion_level}"
            # Fallback to snapshot density
            for seg in self._snapshot:
                if street.lower() in seg.street_name.lower():
                    return f"{seg.street_name}: density {seg.density} veh/km"
            return f"No density data for '{args}'"

        return f"Unknown tool: {tool_name}"

    async def chat(self, user_message: str) -> ChatResponse:
        """Process officer's question through TAO loop."""
        self._messages.append(ChatMessage(
            role="user",
            content=user_message,
            timestamp=datetime.now().isoformat(),
        ))

        # RAG: retrieve relevant SOP documents
        rag_docs = retrieve_sops(user_message, top_k=2)
        rag_sources: list[str] = []
        if rag_docs:
            for doc in rag_docs:
                # Extract doc name from "[Doc Name]\ncontent" format
                if doc.startswith("[") and "]" in doc:
                    name = doc[1:doc.index("]")]
                    rag_sources.append(name)

        # Build context
        context_parts = []

        if rag_docs:
            context_parts.append("RELEVANT STANDARD OPERATING PROCEDURES:\n" + "\n---\n".join(rag_docs))

        if self._incident:
            context_parts.append(
                f"ACTIVE INCIDENT: {self._incident.severity.value} on {self._incident.street_name} "
                f"(detected {self._incident.timestamp}). "
                f"Duration estimate: {self._incident.duration_estimate_min} min. "
                f"Description: {self._incident.description}"
            )

        if self._agent_output:
            if self._agent_output.signal_recommendations:
                sigs = [f"  - {s.intersection_name}: {s.recommended_phase} ({s.confidence:.0%})"
                       for s in self._agent_output.signal_recommendations[:3]]
                context_parts.append("SIGNAL RECOMMENDATIONS:\n" + "\n".join(sigs))
            if self._agent_output.diversion:
                d = self._agent_output.diversion
                context_parts.append(f"DIVERSION: via {' → '.join(d.route_street_names[:4])}, {d.risk_delta_pct}% safer")
            if self._agent_output.final_summary:
                context_parts.append(f"SUMMARY: {self._agent_output.final_summary}")

        context = "\n\n".join(context_parts)

        # Build conversation history for Gemini
        history_text = ""
        for msg in self._messages[-10:]:  # Last 10 messages
            role_label = "OFFICER" if msg.role == "user" else "TRAFFICMIND"
            history_text += f"\n{role_label}: {msg.content}"

        if not GEMINI_AVAILABLE:
            # Fallback: direct tool-based response
            return self._fallback_response(user_message)

        try:
            genai.configure(api_key=get_gemini_key())
            model = genai.GenerativeModel("gemini-2.0-flash")

            prompt = f"""{SYSTEM_PROMPT}

CURRENT SITUATION:
{context}

CONVERSATION HISTORY:
{history_text}

Respond to the officer's latest question. Use tools if needed by including [TOOL: tool_name("arg")] in your thinking.
Then provide the final answer."""

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=600,
                ),
            )

            response_text = response.text
            thinking = ""
            tool_calls = []

            # Check if response contains tool calls
            if "[TOOL:" in response_text or "[TOOL_CALL:" in response_text:
                import re
                tool_pattern = r'\[TOOL(?:_CALL)?:\s*(\w+)\(([^)]*)\)\]'
                matches = re.findall(tool_pattern, response_text)

                for tool_name, tool_args in matches:
                    observation = self._execute_tool(tool_name, tool_args)
                    tool_calls.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": observation,
                    })

                # If we found tool calls, re-query with observations
                if tool_calls:
                    observations = "\n".join([f"[{tc['tool']}] → {tc['result']}" for tc in tool_calls])
                    follow_up = f"""Based on these tool observations:
{observations}

Provide a clear, data-backed answer to the officer. No further tool calls needed."""

                    response2 = model.generate_content(
                        f"{prompt}\n\nTOOL OBSERVATIONS:\n{observations}\n\n{follow_up}",
                        generation_config=genai.GenerationConfig(
                            temperature=0.3,
                            max_output_tokens=400,
                        ),
                    )
                    thinking = response_text
                    response_text = response2.text

            # Determine confidence from response
            confidence = 0.8
            if "[Confidence: HIGH]" in response_text or "high confidence" in response_text.lower():
                confidence = 0.9
            elif "[Confidence: LOW]" in response_text or "low confidence" in response_text.lower():
                confidence = 0.5

            # Clean response
            response_text = response_text.replace("[Confidence: HIGH]", "").replace("[Confidence: MEDIUM]", "").replace("[Confidence: LOW]", "").strip()

            self._messages.append(ChatMessage(
                role="assistant",
                content=response_text,
                timestamp=datetime.now().isoformat(),
                tool_calls=tool_calls,
                thinking=thinking,
            ))

            return ChatResponse(
                response=response_text,
                thinking=thinking,
                tool_calls=tool_calls,
                confidence=confidence,
                rag_sources=rag_sources,
            )

        except Exception as e:
            print(f"Narrative agent error: {e}")
            return self._fallback_response(user_message)

    def _fallback_response(self, question: str) -> ChatResponse:
        """Generate response using available data without LLM."""
        q = question.lower()
        tool_calls = []

        # RAG: retrieve relevant SOP documents for fallback too
        rag_docs = retrieve_sops(question, top_k=2)
        rag_sources: list[str] = []
        if rag_docs:
            for doc in rag_docs:
                if doc.startswith("[") and "]" in doc:
                    rag_sources.append(doc[1:doc.index("]")])

        if "safe" in q or "open" in q or "lane" in q:
            if self._incident:
                seg = next((s for s in self._snapshot if s.street_name == self._incident.street_name), None)
                if seg:
                    obs = self._execute_tool("get_speed", self._incident.street_name)
                    tool_calls.append({"tool": "get_speed", "args": self._incident.street_name, "result": obs})

                    risk_obs = self._execute_tool("get_risk_score", self._incident.street_name)
                    tool_calls.append({"tool": "get_risk_score", "args": self._incident.street_name, "result": risk_obs})

                    pct = seg.speed / seg.free_flow_speed * 100 if seg.free_flow_speed > 0 else 0
                    safe = pct > 60
                    response = (
                        f"Based on current sensor data: {obs}. {risk_obs}. "
                        f"{'Conditions appear safe for reopening.' if safe else 'Not recommended yet — speed still well below baseline.'} "
                        f"[Confidence: {'HIGH' if safe and pct > 80 else 'MEDIUM'}]"
                    )
                    confidence = 0.85 if safe else 0.7
                else:
                    response = "Unable to assess — no sensor data available for the incident location."
                    confidence = 0.3
            else:
                response = "No active incident to assess."
                confidence = 0.5
        elif "speed" in q:
            # Extract street name and return speed
            for seg in self._snapshot[:5]:
                obs = self._execute_tool("get_speed", seg.street_name)
                tool_calls.append({"tool": "get_speed", "args": seg.street_name, "result": obs})
            response = "Current speeds:\n" + "\n".join(tc["result"] for tc in tool_calls)
            confidence = 0.9
        elif "diversion" in q or "route" in q:
            obs = self._execute_tool("check_diversion_status", "")
            tool_calls.append({"tool": "check_diversion_status", "args": "", "result": obs})
            response = obs
            confidence = 0.85
        else:
            response = "I can help with speed data, risk scores, diversion status, and safety assessments. What would you like to know?"
            confidence = 0.5

        self._messages.append(ChatMessage(
            role="assistant",
            content=response,
            timestamp=datetime.now().isoformat(),
            tool_calls=tool_calls,
        ))

        return ChatResponse(
            response=response,
            tool_calls=tool_calls,
            confidence=confidence,
            rag_sources=rag_sources,
        )

    def get_messages(self) -> list[ChatMessage]:
        return self._messages

    def clear(self):
        self._messages.clear()
