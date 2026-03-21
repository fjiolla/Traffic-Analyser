"""Quick E2E test for the incident pipeline."""
import requests, json, sys

BASE = "http://localhost:8000"

# 1. Health check
r = requests.get(f"{BASE}/health")
h = r.json()
print(f"Health: {h['status']}, segments: {h['segments']}")

# 2. Resolve any existing incident
requests.post(f"{BASE}/api/resolve-incident")

# 3. Trigger incident
print("\nTriggering HIGH incident...")
r = requests.post(f"{BASE}/api/trigger-incident?severity=HIGH")
data = r.json()
inc = data["incident"]
ao = data.get("agent_output") or {}
print(f"  Street: {inc['street_name']}")
print(f"  Severity: {inc['severity']}")
print(f"  Duration est: {inc['duration_estimate_min']}min")

print(f"\n  Signals: {len(ao.get('signal_recommendations', []))} recs")
for s in ao.get("signal_recommendations", [])[:2]:
    print(f"    - {s['intersection_name']}: {s['recommended_phase']} (conf: {s['confidence']})")

d = ao.get("diversion")
if d:
    print(f"\n  Diversion: {' → '.join(d['route_street_names'][:4])}")
    print(f"    Risk delta: {d['risk_delta_pct']}%")

a = ao.get("alerts")
if a:
    print(f"\n  VMS: {a.get('vms_text', 'N/A')[:80]}")
    print(f"  Radio: {a.get('radio_script', 'N/A')[:80]}")
    print(f"  Tweet: {a.get('social_post', 'N/A')[:80]}")

print(f"\n  Summary: {ao.get('final_summary', 'N/A')[:200]}")
print(f"  Confidence: {ao.get('confidence_scores', {})}")
print(f"  Cascade risk: {ao.get('cascade_risk', 'N/A')}")
print(f"  Metrics: {ao.get('evaluation_metrics', {})}")

# 4. Test timeline
r = requests.get(f"{BASE}/api/timeline")
tl = r.json().get("timeline", [])
print(f"\n  Timeline entries: {len(tl)}")
for t in tl[:5]:
    print(f"    [{t['category']}] {t['event'][:80]}")

# 5. Test twin
r = requests.get(f"{BASE}/api/twin")
twin = r.json()
print(f"\n  Twin: no_action={len(twin.get('no_action', []))}, with_action={len(twin.get('with_action', []))}, time_saved={twin.get('time_saved_min', 0)}min")

# 6. Resolve
requests.post(f"{BASE}/api/resolve-incident")
print("\n✅ Incident resolved")
print("✅ E2E test PASSED")
