"""
Risk Scorer — Pure Python, no LLM.
Formula: score = (speed_dev × 0.5) + (historical_incident_rate × 0.3) + (time_of_day_weight × 0.2)
Cited: PLOS One 2025, CEPT/ATP survey methodology.
"""
from __future__ import annotations

import os
import json
from typing import Optional
from models.schemas import SegmentSpeed, RiskEntry

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HOTSPOTS_PATH = os.path.join(DATA_DIR, "brooklyn_hotspots.json")

# Top 21 high-incident locations in Brooklyn (from NYC collision data patterns)
BROOKLYN_HOTSPOTS = [
    {"name": "Flatbush Ave & Atlantic Ave", "lat": 40.6862, "lon": -73.9778, "rate": 0.92},
    {"name": "Flatbush Ave & Grand Army Plaza", "lat": 40.6741, "lon": -73.9708, "rate": 0.88},
    {"name": "Atlantic Ave & 4th Ave", "lat": 40.6845, "lon": -73.9785, "rate": 0.85},
    {"name": "Eastern Pkwy & Utica Ave", "lat": 40.6690, "lon": -73.9312, "rate": 0.83},
    {"name": "Kings Highway & Ocean Ave", "lat": 40.6032, "lon": -73.9615, "rate": 0.80},
    {"name": "Linden Blvd & Pennsylvania Ave", "lat": 40.6580, "lon": -73.8960, "rate": 0.79},
    {"name": "Broadway & Flushing Ave", "lat": 40.6990, "lon": -73.9415, "rate": 0.77},
    {"name": "Fulton St & Nostrand Ave", "lat": 40.6820, "lon": -73.9502, "rate": 0.75},
    {"name": "4th Ave & 9th St", "lat": 40.6710, "lon": -73.9830, "rate": 0.73},
    {"name": "Myrtle Ave & Broadway", "lat": 40.6955, "lon": -73.9415, "rate": 0.72},
    {"name": "Belt Parkway & Coney Island Ave", "lat": 40.5890, "lon": -73.9650, "rate": 0.70},
    {"name": "Prospect Expwy & Ocean Pkwy", "lat": 40.6502, "lon": -73.9730, "rate": 0.68},
    {"name": "Church Ave & Flatbush Ave", "lat": 40.6510, "lon": -73.9620, "rate": 0.66},
    {"name": "BQE & Atlantic Ave", "lat": 40.6862, "lon": -73.9880, "rate": 0.65},
    {"name": "Bushwick Ave & Broadway", "lat": 40.7000, "lon": -73.9380, "rate": 0.63},
    {"name": "Metropolitan Ave & Graham Ave", "lat": 40.7145, "lon": -73.9445, "rate": 0.61},
    {"name": "DeKalb Ave & Flatbush Ave", "lat": 40.6904, "lon": -73.9712, "rate": 0.59},
    {"name": "Liberty Ave & Pennsylvania Ave", "lat": 40.6745, "lon": -73.8960, "rate": 0.57},
    {"name": "Pitkin Ave & Ralph Ave", "lat": 40.6710, "lon": -73.9228, "rate": 0.55},
    {"name": "Bay Pkwy & 86th St", "lat": 40.6130, "lon": -73.9785, "rate": 0.53},
    {"name": "Sutter Ave & Rockaway Pkwy", "lat": 40.6420, "lon": -73.9020, "rate": 0.50},
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _get_historical_rate(lat: float, lon: float) -> float:
    """Find closest hotspot and return its incident rate (0-1), decayed by distance."""
    min_dist = float("inf")
    closest_rate = 0.1  # baseline

    for hs in BROOKLYN_HOTSPOTS:
        dist = _haversine(lat, lon, hs["lat"], hs["lon"])
        if dist < min_dist:
            min_dist = dist
            closest_rate = hs["rate"]

    # Decay: full rate within 200m, linear decay to baseline at 2km
    if min_dist < 0.2:
        return closest_rate
    elif min_dist < 2.0:
        decay = 1.0 - (min_dist - 0.2) / 1.8
        return 0.1 + (closest_rate - 0.1) * decay
    else:
        return 0.1


def _get_tod_weight(hour: float) -> float:
    """Time-of-day risk weight (higher during peak hours)."""
    if 8.0 <= hour <= 10.5 or 17.5 <= hour <= 20.5:
        return 0.9
    elif 6.0 <= hour < 8.0 or 15.0 <= hour < 17.5:
        return 0.6
    elif 22.0 <= hour or hour <= 5.0:
        return 0.3  # Late night — lower volume but higher per-incident severity
    else:
        return 0.4


def compute_risk_map(
    snapshot: list[SegmentSpeed],
    hour: float = 9.0,
) -> list[RiskEntry]:
    """
    Compute risk score for every segment.
    Formula: score = (speed_dev × 0.5) + (historical_rate × 0.3) + (tod_weight × 0.2)
    """
    risk_entries = []

    for seg in snapshot:
        # Speed deviation: how much slower than free flow (0 = at free flow, 1 = stopped)
        if seg.free_flow_speed > 0:
            speed_dev = max(0.0, 1.0 - (seg.speed / seg.free_flow_speed))
        else:
            speed_dev = 0.5

        historical_rate = _get_historical_rate(seg.lat, seg.lon)
        tod_weight = _get_tod_weight(hour)

        score = (speed_dev * 0.5) + (historical_rate * 0.3) + (tod_weight * 0.2)
        score = round(min(1.0, max(0.0, score)), 3)

        risk_entries.append(RiskEntry(
            segment_id=seg.segment_id,
            street_name=seg.street_name,
            score=score,
            speed_deviation=round(speed_dev, 3),
            historical_rate=round(historical_rate, 3),
            tod_weight=round(tod_weight, 3),
            lat=seg.lat,
            lon=seg.lon,
        ))

    return risk_entries


def get_hotspots() -> list[dict]:
    """Return Brooklyn hotspot data for frontend heatmap."""
    return BROOKLYN_HOTSPOTS
