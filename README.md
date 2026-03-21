# TrafficMind — AI Co-Pilot for Traffic Incident Command (v1.0.0)

A real-time, LLM-powered multi-agent system for traffic incident detection, response coordination, and public alert management — built for Brooklyn, NYC.

![TrafficMind](https://img.shields.io/badge/TrafficMind-v1.0.0-2563eb?style=for-the-badge)
![Next.js](https://img.shields.io/badge/Next.js-16-000?style=flat-square&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-7C3AED?style=flat-square)

## 🔄 Updates

All updates from v1.0.0 onwards are documented in [UPDATES.md](UPDATES.md). 📝

Refer to it for the latest changes! 😉

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                     │
│  Next.js 16 + React 19 + TypeScript + Tailwind + Mapbox │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐                │
│  │ Dashboard │ │Digital Twin│ │ Landing  │                │
│  └──────────┘ └───────────┘ └──────────┘                │
│              ▲ WebSocket (real-time) ▲                    │
├──────────────┼───────────────────────┼───────────────────┤
│              │    AGENT LAYER        │                    │
│  ┌───────────▼───────────────────────▼────────────┐      │
│  │           LangGraph Orchestrator               │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │      │
│  │  │  Signal   │ │ Routing  │ │  Alert   │       │      │
│  │  │  Agent    │ │  Agent   │ │  Agent   │       │      │
│  │  │ (Groq)   │ │ (Groq)   │ │ (Groq)   │       │      │
│  │  └──────────┘ └──────────┘ └──────────┘       │      │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │      │
│  │  │ Density  │ │Supervisor│ │Narrative │       │      │
│  │  │ Agent    │ │ (Gemini) │ │  Agent   │       │      │
│  │  └──────────┘ └──────────┘ └──────────┘       │      │
│  └────────────────────────────────────────────────┘      │
├──────────────────────────────────────────────────────────┤
│                     DATA LAYER                           │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────┐     │
│  │ Feed Engine │ │Risk Scorer │ │ RAG (12 SOPs)    │     │
│  │ 250 segs   │ │  Anomaly   │ │ TF-IDF retrieval │     │
│  │ Brooklyn   │ │  Detector  │ │                  │     │
│  └────────────┘ └────────────┘ └──────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Real-Time Feed** | 250 Brooklyn road segments with simulated speed data (OSMnx road graph) |
| **Multi-Agent Pipeline** | 6 LLM agents run in parallel fan-out → supervisor fan-in pattern |
| **Signal Re-Timing** | Upstream/downstream intersection phase adjustments with sensor citations |
| **Smart Diversion** | Alternative route computation with risk delta and volume redistribution |
| **Triple-Format Alerts** | VMS (≤20 chars/line), 15s radio script, 280-char tweet — format-constrained |
| **Vehicle Density** | Fundamental flow equation + optional Gemini vision analysis |
| **RAG-Grounded SOPs** | 12 Standard Operating Procedures retrieved via TF-IDF for recommendation validation |
| **Digital Twin** | Side-by-side before/after comparison map showing intervention impact |
| **Chat Interface** | Natural language Q&A with full incident context via narrative agent |
| **Sub-2s Response** | Groq Llama 3.3 70B for inference-heavy agents — measured 0.34s E2E |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind v4, Mapbox GL |
| Backend | FastAPI, Python 3.9+, Pydantic v2 |
| LLM (Fast) | Groq — Llama 3.3 70B Versatile |
| LLM (Deep) | Google Gemini 2.0 Flash |
| Maps | Mapbox GL JS via react-map-gl v8 |
| Road Data | OSMnx (Brooklyn road graph, 250 segments) |
| RAG | TF-IDF vectorizer on 12 SOP documents |
| Real-Time | WebSocket (5s tick interval) |
| State | Zustand (client), in-memory (server) |

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- API keys: Groq, Google AI Studio, Mapbox

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_TEAM/trafficmind.git
cd trafficmind

# Create .env in project root
cat > .env << 'EOF'
GROQ_API_KEY=your_groq_key
GOOGLE_AI_API_KEY=your_google_ai_key
GOOGLE_AI_API_KEY_2=your_google_ai_key_2
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will:
- Download the Brooklyn road graph via OSMnx (cached after first run)
- Generate 250 road segments
- Start the real-time feed engine (5s tick interval)
- Index 12 SOP documents for RAG retrieval

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — the landing page. Navigate to `/dashboard` for the operational view.

## Demo Flow

1. **Open Dashboard** → `/dashboard` — see the Brooklyn map with 250 real-time speed segments
2. **Click "Simulate Incident"** → triggers a HIGH severity incident on Flatbush Avenue
3. **Watch the agent pipeline**:
   - Signal Agent: 4 intersection re-timing recommendations
   - Routing Agent: Alternative diversion route with risk reduction
   - Alert Agent: VMS signs, radio script, social media post
   - Density Agent: Vehicle density estimation
   - Supervisor: Cross-agent coherence check, cascade risk assessment
4. **Explore tabs**: Signals, Routing, Alerts, Chat, Timeline, Summary
5. **Chat** → ask "What happened?" or "Should I extend the diversion?"
6. **Digital Twin** → `/twin` — side-by-side before/after impact comparison
7. **Click "Resolve"** → clears incident, returns to normal monitoring

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server status + segment count |
| GET | `/api/state` | Current snapshot, risk map, incident |
| GET | `/api/agents` | Latest agent outputs |
| GET | `/api/signals` | Signal re-timing recommendations |
| GET | `/api/diversion` | Active diversion route |
| GET | `/api/alerts` | Alert drafts (VMS/Radio/Tweet) |
| GET | `/api/density` | Vehicle density data |
| GET | `/api/timeline` | Incident timeline events |
| GET | `/api/hotspots` | Brooklyn black-spot data |
| GET | `/api/metrics` | Evaluation metrics |
| GET | `/api/twin` | Digital twin comparison data |
| GET | `/api/documents` | RAG document index |
| POST | `/api/trigger-incident` | Trigger demo incident |
| POST | `/api/resolve-incident` | Resolve active incident |
| POST | `/api/chat` | Chat with narrative agent |
| WS | `/ws/feed` | Real-time WebSocket feed |

## Multi-Agent Pipeline

```
Feed Tick (5s)
    │
    ├─→ Risk Scorer (rule-based, no LLM)
    │
    ├─→ Anomaly Detector (statistical deviation)
    │       │
    │       ▼ (if incident detected)
    │
    ├─→ RAG Retrieval (TF-IDF, top-2 SOPs)
    │
    ├─→ [PARALLEL FAN-OUT]
    │       ├─→ Signal Agent (Groq Llama 3.3 70B)
    │       ├─→ Routing Agent (Groq Llama 3.3 70B)
    │       ├─→ Alert Agent (Groq Llama 3.3 70B)
    │       └─→ Density Agent (simulated + optional Gemini vision)
    │
    └─→ [FAN-IN] Supervisor (Gemini 2.0 Flash)
            │
            ├─→ Coherence check
            ├─→ Cascade risk assessment
            ├─→ SOP compliance validation
            └─→ Final summary + confidence scores
```

## Project Structure

```
trafficmind/
├── .env                          # API keys
├── backend/
│   ├── main.py                   # FastAPI app + WebSocket
│   ├── requirements.txt
│   ├── models/
│   │   └── schemas.py            # Pydantic models
│   ├── core/
│   │   ├── feed_engine.py        # Real-time data feed (OSMnx)
│   │   ├── risk_scorer.py        # Risk computation
│   │   ├── anomaly_detector.py   # Statistical anomaly detection
│   │   └── graph.py              # LangGraph orchestrator
│   ├── agents/
│   │   ├── signal_agent.py       # Signal re-timing (Groq)
│   │   ├── routing_agent.py      # Diversion routing (Groq)
│   │   ├── alert_agent.py        # Public alerts (Groq)
│   │   ├── density_agent.py      # Vehicle density (Gemini)
│   │   ├── supervisor.py         # Cross-agent supervision (Gemini)
│   │   └── narrative_agent.py    # Chat interface (Gemini)
│   ├── rag/
│   │   └── retriever.py          # TF-IDF RAG retriever
│   └── sops/                     # 12 SOP documents
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Landing page
│   │   │   ├── dashboard/page.tsx # Operational dashboard
│   │   │   ├── twin/page.tsx      # Digital twin view
│   │   │   ├── layout.tsx         # Root layout
│   │   │   └── globals.css        # Tailwind v4 theme
│   │   ├── components/
│   │   │   ├── TrafficMap.tsx     # Mapbox GL map
│   │   │   ├── Sidebar.tsx       # Status sidebar
│   │   │   ├── SignalPanel.tsx   # Signal recommendations
│   │   │   ├── RoutingPanel.tsx  # Diversion route
│   │   │   ├── AlertPanel.tsx    # Alert drafts
│   │   │   ├── ChatInterface.tsx # Chat UI
│   │   │   ├── Timeline.tsx      # Event timeline
│   │   │   └── SummaryPanel.tsx  # Supervisor summary
│   │   └── lib/
│   │       ├── types.ts           # TypeScript interfaces
│   │       ├── api.ts             # REST client
│   │       ├── store.ts           # Zustand state
│   │       ├── utils.ts           # Utilities
│   │       └── useWebSocket.ts    # WebSocket hook
│   └── .env.local                 # Frontend env vars
└── README.md
```

## Differentiators

1. **Sub-second inference** — Groq Llama 3.3 70B delivers <0.5s agent responses
2. **250 real road segments** — Not mock data: actual Brooklyn road network via OSMnx
3. **Format-constrained alerts** — VMS signs enforce ≤20 chars/line, tweets ≤280 chars
4. **RAG-grounded SOPs** — 12 real standard operating procedures validate recommendations
5. **Digital twin** — Before/after impact visualization with quantified time savings
6. **Cascade risk assessment** — Supervisor checks if diversion routes are themselves at risk
7. **Cross-agent coherence** — Supervisor detects conflicts between signal and routing recommendations
8. **WebSocket real-time** — Live 5-second ticks with instant incident event propagation
9. **Production architecture** — Clean separation: data layer → agent layer → presentation layer

## Team

**2AM Coders** — Built in 24 hours.

## License

MIT
