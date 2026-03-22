# Plan: TrafficMind v2.0 — Complete Hackathon-Winning Upgrade

## TL;DR
Upgrade TrafficMind from partially-hardcoded v1.0 to a fully dynamic, feature-rich traffic intelligence platform across 9 phases. New features: dual-mode toggle (Overview vs Route), Google Maps-style geocoding search, priority routing for emergency vehicles (ambulance/police/fire), weather-aware routing, DBSCAN hotspot prediction, green/yellow/red route coloring, RAG-powered chat, social media auto-posting, voice chat, API key rotation, and custom branding. All routes follow actual Brooklyn roads via OSMnx graph.

---

## Prerequisites — DO BEFORE IMPLEMENTATION

### API Keys to add to `backend/.env`
```
# Primary keys (already exist)
GROQ_API_KEY=<primary_groq_key>
GOOGLE_AI_API_KEY=<primary_gemini_key>
GOOGLE_AI_API_KEY_2=<secondary_gemini_key>

# Backup Groq keys (comma-separated for rotation)
GROQ_API_KEYS=<key1>,<key2>,<key3>,<key4>,<key5>,<key6>,<key7>

# Backup Gemini keys (comma-separated for rotation)
GOOGLE_AI_API_KEYS=<gemini1>,<gemini2>,<gemini3>,<gemini4>

# Mapbox (already exists)
NEXT_PUBLIC_MAPBOX_TOKEN=<mapbox_token>
MAPBOX_TOKEN=<same_mapbox_token_for_backend_geocoding>

# Twitter/X (optional — gracefully skipped if not set)
TWITTER_API_KEY=<optional>
TWITTER_API_SECRET=<optional>
TWITTER_ACCESS_TOKEN=<optional>
TWITTER_ACCESS_SECRET=<optional>

# NYC Open Data (optional — for real accident/speed data for hotspot analysis)
NYC_OPEN_DATA_TOKEN=<optional>
```

### Python packages to install
```bash
cd backend && pip install python-multipart tweepy sodapy
```

### No extra API keys needed for:
- **Weather**: Uses Weather.gov API (free, no key, US-only — perfect for Brooklyn)
- **Geocoding**: Uses existing Mapbox token (proxied through backend)
- **Voice**: Uses existing Groq key for Whisper
- **Hotspots**: Uses existing Brooklyn OSMnx graph + scikit-learn DBSCAN (already installed)

---

## Phase 1: Core Infrastructure — Real Time, Key Rotation, Dynamic Stats
**Goal**: Foundation fixes — replace all hardcoded/simulated values, add API key failover.

### Step 1.1 — API Key Rotation System
- **File**: Create `backend/core/key_manager.py`
- Parse comma-separated keys from env: `GROQ_API_KEYS`, `GOOGLE_AI_API_KEYS`
- Function `get_groq_key() -> str` — returns current key, rotates on 429/rate-limit
- Function `get_gemini_key() -> str` — same rotation logic
- Thread-safe index with `threading.Lock`
- On rate limit error: increment index, wrap around, log rotation
- Fallback to primary `GROQ_API_KEY` / `GOOGLE_AI_API_KEY` if rotation list empty

### Step 1.2 — Wire key rotation into all agents
- **Files**: All 6 agent files + `narrative_agent.py`
- Replace hardcoded `os.getenv("GROQ_API_KEY")` with `key_manager.get_groq_key()`
- Replace hardcoded `genai.configure(api_key=...)` with dynamic per-call configuration
- Wrap LLM calls in try/except for 429 → rotate key → retry once

### Step 1.3 — Replace simulated time with real wall-clock time
- **File**: `backend/core/feed_engine.py` (line ~210: `self._simulated_hour = 8.5`)
- In `__init__`: `self._simulated_hour = datetime.now().hour + datetime.now().minute / 60.0`
- In `_generate_tick()` (line ~249): Replace `self._simulated_hour += 1.0 / 60.0` with `self._simulated_hour = datetime.now().hour + datetime.now().minute / 60.0`
- `_time_of_day_factor()` stays unchanged — uses hour float, now reflects real time

### Step 1.4 — Compute diversion volume from flow model (not random)
- **File**: `backend/agents/routing_agent.py` (line 110)
- Replace `round(random.uniform(15, 35), 1)` with:
  ```
  blocked_density = sum(s.density for s in blocked_segments) or 1
  route_density = sum(rs["segment"].density for rs in route_segments) or 1
  diversion_volume = round(min(50, max(10, (blocked_density / route_density) * 100 / len(route_segments))), 1)
  ```

### Step 1.5 — Derive confidence scores from agent data (never use hardcoded defaults)
- **File**: `backend/agents/supervisor.py` (lines 123-130)
- Replace hardcoded `{"signal": 0.7, "routing": 0.7, "alerts": 0.8, "overall": 0.7}` with:
  - `signal`: `mean(s.confidence for s in signals)` if signals else 0.5
  - `routing`: `diversion.confidence` if diversion else 0.5
  - `alerts`: 0.9 (alerts are format-validated, deterministic)
  - `overall`: weighted average `(signal*0.3 + routing*0.35 + alerts*0.15 + density_conf*0.2)`
- Replace `cascade_risk = 0.0` with: compute from diversion route average risk vs incident risk ratio

### Step 1.6 — Update Sidebar label from "Simulated Time" to "Current Time"
- **File**: `frontend/src/components/Sidebar.tsx` (line ~81)
- Change label text from "Simulated Time" to "Current Time"

**Verification**: Backend starts → `/api/state` returns real wall-clock hour → sidebar shows "Current Time" with actual time → confidence scores differ per incident → no rate limit failures due to key rotation

---

## Phase 2: Weather Intelligence
**Goal**: Fetch real weather data, display on dashboard, factor into routing.

### Step 2.1 — Create weather service
- **File**: Create `backend/core/weather_service.py`
- Fetch from Weather.gov API (free, no key needed):
  - `GET https://api.weather.gov/points/40.6782,-73.9442` → get forecast grid endpoint
  - `GET {gridpoint}/forecast/hourly` → get hourly conditions
- Parse: temperature_f, precipitation_probability, wind_speed_mph, condition (rain/snow/fog/clear)
- Cache response for 15 minutes (avoid hammering API)
- Return `WeatherCondition(condition, temp_f, precip_pct, wind_mph, is_severe)`
- Identify severity: `is_severe = precip_pct > 60 or wind_mph > 30 or condition in ("snow","ice","heavy_rain")`

### Step 2.2 — Weather-prone road classification
- **File**: Same `weather_service.py`
- Define Brooklyn weather-vulnerable roads (from SOP `03_flooding_weather.txt`):
  - **Flood-prone** (near Gowanus Canal, Shore Parkway, low-lying): Belt Parkway, Shore Parkway, 3rd Ave near Gowanus, Smith St near canal
  - **Ice/wind-prone** (bridges, elevated): Williamsburg Bridge Approach, BQE, Brooklyn Bridge, Prospect Expressway
  - **Snow-accumulation** (wide exposed avenues): Eastern Parkway, Ocean Parkway, Linden Boulevard
- Function `get_weather_penalty(street_name, lat, lon, weather) -> float`:
  - Returns multiplier 1.0 (clear) to 3.0 (severe weather + vulnerable road)
  - Rain + flood-prone → 2.5x
  - Snow + snow-accumulation → 2.0x
  - Ice + bridge/elevated → 3.0x
  - Normal road + any weather → 1.2x (minor penalty for reduced visibility)

### Step 2.3 — Add weather endpoint + schema
- **File**: `backend/models/schemas.py` — add `WeatherCondition(condition, temp_f, precip_pct, wind_mph, is_severe, timestamp)`
- **File**: `backend/main.py` — add `GET /api/weather` → returns current `WeatherCondition`
- Cache in global state, refresh every 15 min

### Step 2.4 — Frontend weather display
- **File**: `frontend/src/components/Sidebar.tsx`
- Add weather section below "Current Time": icon (Sun/Cloud/Rain/Snow) + temp + condition
- Color-coded: green=clear, yellow=light rain, orange=heavy rain, red=snow/ice
- **File**: `frontend/src/lib/store.ts` — add `weather: WeatherCondition | null`
- **File**: `frontend/src/lib/types.ts` — add `WeatherCondition` interface
- **File**: `frontend/src/lib/api.ts` — add `getWeather()` method
- Poll weather every 5 minutes from frontend

**Verification**: Sidebar shows real Brooklyn weather → weather data accessible via `/api/weather` → weather penalties ready for routing

---

## Phase 3: Hotspot Prediction System (DBSCAN)
**Goal**: Predict accident hotspot zones using historical data patterns + DBSCAN clustering.

### Step 3.1 — Create hotspot predictor
- **File**: Create `backend/core/hotspot_predictor.py`
- Load Brooklyn graph from `backend/data/brooklyn.graphml`
- Generate N=500 synthetic accident records, weighted by:
  - **Road type**: primary/trunk × 8, secondary × 5, tertiary × 3, residential × 1 (from OSMnx `highway` attribute)
  - **Proximity to known hotspots**: Accidents cluster near the 21 hotspots in `risk_scorer.py` — use Gaussian jitter (σ=0.0003°) around hotspot coords
  - **Time of day**: More accidents during peak hours (8-10, 17-20)
  - **Severity**: weighted random — minor 60%, moderate 30%, severe 10%
- Interpolate accident position along edge: `lat = u_lat + t*(v_lat - u_lat) + gaussian_noise`
- DBSCAN clustering: `DBSCAN(eps=0.0008, min_samples=4, metric="haversine", algorithm="ball_tree")` on radian-converted coords
- Per cluster: compute `center_lat`, `center_lng`, `accident_count`, `avg_severity`, `risk_score = count * avg_severity`, `radius_m`
- Cache results (recompute hourly or on demand)
- Reference the code pattern from user's provided script (Section 9 — DBSCAN)

### Step 3.2 — Add hotspot endpoint + schema
- **File**: `backend/models/schemas.py` — add `HotspotCluster(cluster_id, center_lat, center_lon, accident_count, severity_score, risk_score, radius_m, peak_hours)`
- **File**: `backend/main.py` — add `GET /api/hotspots/predicted` → returns list of `HotspotCluster`
- Different from existing `GET /api/hotspots` (which returns static 21 known hotspots)

### Step 3.3 — Frontend hotspot visualization
- **File**: `frontend/src/components/TrafficMap.tsx`
- Add hotspot prediction layer: semi-transparent circles (graduated red) at cluster centers
- Circle radius proportional to `risk_score`
- Tooltip: "Predicted Hotspot — {accident_count} incidents, risk score {risk_score}"
- Toggle visibility with layer control
- **File**: `frontend/src/lib/store.ts` — add `predictedHotspots: HotspotCluster[]`
- **File**: `frontend/src/lib/api.ts` — add `getPredictedHotspots()` method
- Fetch on dashboard load and refresh every 60 seconds

**Verification**: Map shows predicted hotspot zones as red circles → tooltip shows cluster stats → `/api/hotspots/predicted` returns DBSCAN clusters → clusters align with high-incident intersections

---

## Phase 4: Route Intelligence — Toggle Mode, Geocoding, Priority, Weather, Coloring
**Goal**: Dual-mode dashboard (Overview vs Route), search boxes, priority routing for emergency vehicles, weather-aware scoring, green/yellow/red coloring. All routes follow actual roads.

### Step 4.1 — Create `backend/core/route_finder.py`
- Load Brooklyn graph from `backend/data/brooklyn.graphml`
- **CRITICAL FIX**: Convert MultiDiGraph → DiGraph:
  ```python
  G_simple = nx.DiGraph()
  for u, v, k, data in G.edges(keys=True, data=True):
      weight = data.get("length", 1e9)
      if not G_simple.has_edge(u, v) or weight < G_simple[u][v].get("length", 1e9):
          G_simple.add_edge(u, v, **data)
  for n, d in G.nodes(data=True):
      G_simple.nodes[n].update(d)
  ```
  This fixes the `NetworkXNotImplemented: not implemented for multigraph type` crash.
- `find_routes(origin_lat, origin_lon, dest_lat, dest_lon, k=3, feed_snapshot, risk_map, vehicle_type="normal", weather=None)`:
  - Snap coords to nearest graph nodes: `ox.nearest_nodes(G, X=lon, Y=lat)`
  - Build live edge weights per edge (u,v):
    - Find nearest feed segment (by lat/lon) → get live speed and density
    - `base_time = length / (live_speed_m_per_s)` (convert mph to m/s)
    - `risk_factor = 1 + risk_score` (from risk_map, matched by nearest segment)
    - `weather_penalty = get_weather_penalty(street_name, lat, lon, weather)` (from Phase 2)
    - **Vehicle type multiplier**:
      - `normal`: 1.0 (no adjustment)
      - `ambulance`: 0.6 (can go 40% faster, signal preemption)
      - `police`: 0.65 (can go 35% faster)
      - `fire_brigade`: 0.7 (large vehicle, slightly less speed advantage)
    - **Priority routing**: For emergency vehicles, also:
      - Reduce risk_factor weighting (emergency vehicles accept more risk): `risk_factor = 1 + risk_score * 0.3`
      - Use emergency corridor data from SOP `04_emergency_corridor.txt` to boost hospital-route edges
    - Final edge weight: `base_time * risk_factor * weather_penalty * vehicle_multiplier`
    - Store as `live_cost` attribute on G_simple edges
  - Use `nx.shortest_simple_paths(G_simple, orig_node, dest_node, weight="live_cost")` with `itertools.islice(paths, k)`
  - For each path: extract coords from graph nodes (lat/lon = node `y`,`x`) → these follow actual roads
  - Per-segment metrics: street_name, length, speed, density, accident_score (from 21 hotspots), weather_penalty
  - Composite score: `0.25×norm_density + 0.30×norm_travel_time + 0.25×norm_accident + 0.20×norm_weather`
  - Rank routes by composite score → assign colors:
    - Route with lowest score → `rank: "optimal"` → **GREEN** (#22c55e)
    - Middle route → `rank: "moderate"` → **YELLOW** (#f59e0b)
    - Worst route → `rank: "risky"` → **RED** (#ef4444)
  - Return list of CandidateRoute objects with rank and color fields
  - If emergency vehicle: also return signal preemption recommendations (which intersections along route need green extended)

### Step 4.2 — Add Mapbox Geocoding reverse-proxy
- **File**: `backend/main.py`
- `GET /api/geocode?q={query}` — proxies to `https://api.mapbox.com/search/geocode/v6/forward` with `MAPBOX_TOKEN`
- Restrict to Brooklyn bbox: `-74.05,40.57,-73.83,40.74`
- Returns `[{place_name, lat, lon}]`
- SSRF-safe: hardcoded target domain (api.mapbox.com only)

### Step 4.3 — Add Pydantic schemas
- **File**: `backend/models/schemas.py`
- `RouteRequest(origin_lat, origin_lon, dest_lat, dest_lon, k=3, vehicle_type="normal")`
  - vehicle_type: Literal["normal", "ambulance", "police", "fire_brigade"]
- `RouteSegmentMetric(street_name, lat, lon, length_m, speed_mph, travel_time_min, density, accident_score, weather_penalty, data_source)`
- `CandidateRoute(route_index, rank, color, street_names, coords, segments, total_length_km, total_travel_time_min, avg_density, avg_accident_score, avg_weather_penalty, composite_score, is_optimal, signal_preemptions)`
  - rank: Literal["optimal", "moderate", "risky"]
  - color: str (#22c55e / #f59e0b / #ef4444)
  - signal_preemptions: Optional — list of intersections needing green extension (only for emergency vehicles)
- `RouteResponse(routes, origin, destination, vehicle_type, weather_condition)`
- `GeocodeSuggestion(place_name, lat, lon)`

### Step 4.4 — Add route endpoints
- **File**: `backend/main.py`
- `POST /api/routes` — accepts RouteRequest, gets live snapshot + risk map + weather, calls `find_routes()`, returns RouteResponse
- `GET /api/routes/csv` — StreamingResponse CSV of last computed routes with all segment metrics including weather_penalty
- Global `_last_route_response` for CSV

### Step 4.5 — Frontend types + store
- **File**: `frontend/src/lib/types.ts` — add all route types + `GeocodeSuggestion` + `VehicleType`
- **File**: `frontend/src/lib/store.ts` — add:
  - `dashboardMode: "overview" | "route"` ← NEW toggle
  - `routeOrigin: {lat: number, lon: number, name: string} | null`
  - `routeDestination: {lat: number, lon: number, name: string} | null`
  - `candidateRoutes: CandidateRoute[]`
  - `selectedRouteIndex: number`
  - `routeLoading: boolean`
  - `vehicleType: "normal" | "ambulance" | "police" | "fire_brigade"`
  - Setters for all; `setDashboardMode("overview")` resets all route state

### Step 4.6 — Frontend API methods
- **File**: `frontend/src/lib/api.ts`
- `geocodeSearch(query: string)` → GET /api/geocode?q=...
- `findRoutes(origin, dest, k, vehicleType)` → POST /api/routes
- `downloadRoutesCsv()` → GET /api/routes/csv

### Step 4.7 — Dashboard toggle: Overview vs Route mode
- **File**: `frontend/src/app/dashboard/page.tsx`
- Add segmented control in top bar: `[Map Overview | Route Planning]`
  - Map Overview: full analysis mode — all segments, risk heatmap, hotspots, weather overlay, no search boxes
  - Route Planning: search boxes appear, click-to-set, route computation
- Add vehicle type selector (only visible in Route mode): dropdown `[Normal | Ambulance | Police | Fire Brigade]`
  - Shows emergency icon (Siren) when emergency vehicle selected
- Uses `dashboardMode` from store

### Step 4.8 — Search boxes + map interaction in TrafficMap.tsx
- **File**: `frontend/src/components/TrafficMap.tsx`
- **Only visible when `dashboardMode === "route"`**:
  - Two search input boxes (absolute positioned, top-right of map, stacked):
    - Origin: green circle marker icon, placeholder "Starting point or click map..."
    - Destination: red circle marker icon, placeholder "Destination or click map..."
    - On type (debounced 300ms): call `api.geocodeSearch()`, show dropdown with max 5 suggestions
    - On select: set origin/destination in store, place marker on map
  - Also supports click-to-set: first click → origin (green marker), second click → destination (red marker + triggers route computation)
  - Show instruction text when in route mode but no points set: "Search or click the map"
- **Route layers** (visible in route mode when candidateRoutes exist):
  - Render each route as LineString layer using coords from `candidateRoutes[i].coords`
  - **Color by rank**: 
    - optimal → GREEN line (#22c55e), 5px solid
    - moderate → YELLOW line (#f59e0b), 3px solid
    - risky → RED line (#ef4444), 3px dashed
  - Selected route: +2px width, full opacity
  - Click a route line to select it (updates `selectedRouteIndex`)
- Origin marker (green pin + "START"), Destination marker (red pin + "END")
- **Hotspot overlay** (visible in BOTH modes): semi-transparent red circles from predicted hotspots
- Map cursor: crosshair in route mode
- In overview mode: existing layers (speed circles, risk heatmap, diversion route) shown as before

### Step 4.9 — Route intelligence cards in RoutingPanel.tsx
- **File**: `frontend/src/components/RoutingPanel.tsx`
- **Route mode** (when `candidateRoutes.length > 0`):
  - Route cards (one per candidate):
    - Left color bar matching route color (green/yellow/red)
    - "OPTIMAL" / "MODERATE" / "RISKY" badge
    - 4-metric grid: Time (min), Distance (km), Density (avg), Risk (composite score)
    - Weather penalty indicator (if > 1.0): "⚠️ Weather impact: +{penalty}%"
    - Street name sequence: "Flatbush Ave → Atlantic Ave → ..."
    - If emergency vehicle: show signal preemption list ("🚨 Preemption at: Intersection A, B, C")
  - CSV Export button at bottom
  - Vehicle type badge showing selected type
- **Overview mode / no routes**: show existing diversion info (unchanged)

### Step 4.10 — Trigger route computation on both points set
- When both `routeOrigin` and `routeDestination` are set in store:
  - Automatically call `api.findRoutes(origin, dest, 3, vehicleType)`
  - Show loading spinner on map
  - On response: set `candidateRoutes` in store → routes render on map + panel

**Verification**: Toggle "Route Planning" → select "Ambulance" → search "Kings County Hospital" → search "Flatbush Ave" → 3 routes appear (green/yellow/red following actual roads) → green route is fastest considering emergency priority → panel shows signal preemptions → weather penalty visible if raining → CSV exports all metrics

---

## Phase 5: RAG-Powered Chat
**Goal**: Chat agent answers using SOP knowledge, not just live data.

### Step 5.1 — Inject RAG into narrative agent
- **File**: `backend/agents/narrative_agent.py` (in `chat()` method, ~line 132)
- Before building context, add:
  ```python
  from rag.retriever import retrieve_sops
  rag_docs = retrieve_sops(user_message, top_k=2)
  if rag_docs:
      context_parts.append("RELEVANT STANDARD OPERATING PROCEDURES:\n" + "\n---\n".join(rag_docs))
  ```
- Now questions like "What's the emergency corridor protocol?" or "How do we handle flooding?" get answered with actual SOP content from the 12 documents (including `03_flooding_weather.txt` and `04_emergency_corridor.txt`)

### Step 5.2 — Return RAG sources in chat response
- **File**: `backend/models/schemas.py` — add `rag_sources: list[str] = []` to `ChatResponse`
- **File**: `backend/main.py` — in `/api/chat` endpoint, call `retrieve_sops(message)` and include document names in response

### Step 5.3 — Show RAG source badges in ChatInterface
- **File**: `frontend/src/components/ChatInterface.tsx`
- Below assistant messages that have `rag_sources`: show collapsible "📄 Sources" badges
- Click to show which SOP document was referenced

**Verification**: Ask "What's the protocol for flooding?" → response cites SOP content from `03_flooding_weather.txt` → Sources badge visible

---

## Phase 6: Social Media Auto-Posting via LangGraph
**Goal**: Alert agent's tweet auto-posts to Twitter/X.

### Step 6.1 — Create Twitter poster
- **File**: Create `backend/integrations/__init__.py` + `backend/integrations/twitter_poster.py`
- Uses `tweepy` with OAuth 1.0a; env vars: `TWITTER_API_KEY`, `TWITTER_API_SECRET`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_SECRET`
- `post_tweet(text: str) -> dict` — posts tweet, returns `{tweet_id, url, status}`
- Gracefully returns `{status: "skipped", reason: "Twitter credentials not configured"}` if no keys

### Step 6.2 — Integrate into LangGraph pipeline
- **File**: `backend/core/graph.py` — in `_run_agents()`, after alerts complete:
  - If auto-post enabled and `alerts.tweet` exists: call `post_tweet(alerts.tweet)`
  - Add timeline entry: "📱 Tweet posted: {url}" or "Tweet skipped: no credentials"

### Step 6.3 — Auto-post toggle
- **File**: `backend/main.py` — `POST /api/settings/auto-post`, `GET /api/settings`
- **File**: `frontend/src/components/Sidebar.tsx` — toggle switch in sidebar

### Step 6.4 — Add `tweepy>=4.14.0` to `backend/requirements.txt`

**Verification**: Simulate incident → tweet auto-posts (or "skipped") → timeline shows status

---

## Phase 7: Voice Chat (Whisper STT + Browser TTS)
**Goal**: Speak questions, hear answers.

### Step 7.1 — Voice endpoint
- **File**: `backend/main.py`
- `POST /api/chat/voice` — accepts `UploadFile` audio
- Transcribes via Groq Whisper (`whisper-large-v3-turbo`) using key from `key_manager.get_groq_key()`
- Passes transcript to `narrative_agent.chat()`
- Returns `{transcript, response, rag_sources}`

### Step 7.2 — Mic + TTS in ChatInterface
- **File**: `frontend/src/components/ChatInterface.tsx`
- Mic button: `MediaRecorder` → webm → send to `/api/chat/voice`
- Red pulsing indicator while recording
- TTS toggle: `window.speechSynthesis.speak()` for all assistant responses

### Step 7.3 — API method
- **File**: `frontend/src/lib/api.ts` — `sendVoiceChat(blob: Blob)`

### Step 7.4 — Add `python-multipart>=0.0.18` to requirements.txt

**Verification**: Mic → speak → transcript + response appears → TTS speaks

---

## Phase 8: Branding — Logo + Favicon
**Goal**: Custom TrafficMind branding.

### Step 8.1 — Create SVG logo
- **File**: `frontend/public/logo.svg` — traffic signal + brain/neural network fusion, emerald/blue tones
- **File**: `frontend/src/app/icon.svg` — simplified 32x32 version (Next.js App Router auto-favicon)

### Step 8.2 — Update Sidebar logo
- **File**: `frontend/src/components/Sidebar.tsx` (lines 46-55)
- Replace `<Zap>` with `<Image src="/logo.svg">` or inline SVG

### Step 8.3 — Update layout metadata
- **File**: `frontend/src/app/layout.tsx` — add `icons: { icon: "/icon.svg" }`

**Verification**: Browser tab shows custom favicon → sidebar shows new logo

---

## Phase 9: Final Polish + E2E Verification
**Goal**: Everything works together, no regressions.

### Step 9.1 — Backend checks
- `cd backend && python3 -c "from main import app; print('OK')"`
- `cd backend && python3 -c "from core.route_finder import find_routes; print('OK')"`
- `cd backend && python3 -c "from core.hotspot_predictor import predict_hotspots; print('OK')"`
- `cd backend && python3 -c "from core.weather_service import get_weather; print('OK')"`
- `cd backend && python3 -c "from core.key_manager import get_groq_key; print('OK')"`

### Step 9.2 — Frontend type check
- `cd frontend && npx tsc --noEmit` (NOT `next build` — Turbopack hangs)

### Step 9.3 — Full E2E flow
1. Open dashboard in "Map Overview" mode → see all segments, risk heatmap, predicted hotspot zones, weather in sidebar, real time
2. Toggle to "Route Planning" → search boxes appear
3. Select "Ambulance" vehicle type
4. Search "Kings County Hospital" as origin → autocomplete → select
5. Search "Brooklyn Bridge" as destination → select
6. 3 routes appear: GREEN (optimal), YELLOW (moderate), RED (risky) — all following actual roads
7. Panel shows time/distance/density/risk + signal preemptions for ambulance
8. Click CSV Export → downloads
9. Toggle back to "Map Overview" → routes disappear, full analysis view returns
10. Simulate Incident → all agent panels update → confidence scores dynamic → cascade risk computed
11. Chat: "What's the emergency corridor protocol?" → cites SOP → Sources badge
12. Mic → speak → transcript + TTS response
13. Weather shown in sidebar with real conditions
14. Hotspot prediction circles on map
15. Favicon in browser tab

---

## Relevant Files

### Backend — CREATE
- `backend/core/key_manager.py` — API key rotation (Groq + Gemini failover)
- `backend/core/route_finder.py` — Route computation (MultiDiGraph→DiGraph fix, Yen's K-shortest, priority routing, weather-aware)
- `backend/core/weather_service.py` — Weather.gov API integration + road vulnerability classification
- `backend/core/hotspot_predictor.py` — DBSCAN accident hotspot prediction from OSMnx graph
- `backend/integrations/__init__.py` — Package init
- `backend/integrations/twitter_poster.py` — Twitter/X posting via tweepy
- `frontend/public/logo.svg` — Custom logo
- `frontend/src/app/icon.svg` — Custom favicon

### Backend — MODIFY
- `backend/core/feed_engine.py` — Real wall-clock time (lines ~210, ~249)
- `backend/agents/routing_agent.py` — Flow-based diversion volume (line 110)
- `backend/agents/supervisor.py` — Dynamic confidence scores (lines 123-130)
- `backend/agents/narrative_agent.py` — RAG injection in chat (~line 132)
- `backend/agents/signal_agent.py` — Key rotation
- `backend/agents/alert_agent.py` — Key rotation
- `backend/agents/density_agent.py` — Key rotation
- `backend/models/schemas.py` — Add RouteRequest, CandidateRoute, RouteResponse, WeatherCondition, HotspotCluster, GeocodeSuggestion, update ChatResponse
- `backend/main.py` — Add endpoints: /api/routes, /api/routes/csv, /api/chat/voice, /api/geocode, /api/weather, /api/hotspots/predicted, /api/settings/auto-post
- `backend/requirements.txt` — Add tweepy, python-multipart, sodapy

### Frontend — MODIFY
- `frontend/src/lib/types.ts` — Add route types, WeatherCondition, HotspotCluster, GeocodeSuggestion, VehicleType
- `frontend/src/lib/store.ts` — Add dashboardMode, route state, vehicleType, weather, predictedHotspots
- `frontend/src/lib/api.ts` — Add geocodeSearch, findRoutes, downloadRoutesCsv, sendVoiceChat, getWeather, getPredictedHotspots
- `frontend/src/components/TrafficMap.tsx` — Search boxes, route layers (green/yellow/red), hotspot circles, mode-aware rendering, click interaction
- `frontend/src/components/RoutingPanel.tsx` — Route intelligence cards with color bars, weather penalty, signal preemptions
- `frontend/src/components/ChatInterface.tsx` — Mic, TTS, RAG sources
- `frontend/src/components/Sidebar.tsx` — Logo, weather section, "Current Time" label, auto-post toggle
- `frontend/src/app/dashboard/page.tsx` — Mode toggle, vehicle type selector
- `frontend/src/app/layout.tsx` — Favicon metadata

### Reference (read-only)
- `backend/core/risk_scorer.py` — 21 Brooklyn hotspots + `_haversine()` + `get_hotspots()`
- `backend/rag/retriever.py` — `retrieve_sops()` for RAG
- `backend/rag/documents/03_flooding_weather.txt` — Flooding SOP (weather-vulnerable roads)
- `backend/rag/documents/04_emergency_corridor.txt` — Emergency corridor SOP (hospital routes, signal preemption)
- `backend/data/brooklyn.graphml` — Cached OSMnx Brooklyn road graph

---

## Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dashboard mode | Segmented control: Overview / Route | Clean UX — overview = full analysis, route = focused planning |
| Priority routing | Edge weight multiplier per vehicle type | Ambulances legitimately go faster + accept more risk |
| Emergency corridors | Reference SOP 04 data for hospital routes | Already have Brooklyn hospital routes in SOP docs |
| Weather API | Weather.gov (free, no key) | Perfect for Brooklyn, no cost, reliable |
| Weather routing | Road vulnerability classification + weather multiplier | Flood-prone, ice-prone, snow-prone roads get penalized |
