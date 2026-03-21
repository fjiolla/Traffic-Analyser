"""
Weather Service — Real-time weather data from Weather.gov API.
Brooklyn-specific weather-vulnerable road classification.
15-minute cache to avoid hammering the free API.
"""
from __future__ import annotations

import time
import httpx
from dataclasses import dataclass
from typing import Optional

# Brooklyn centroid for Weather.gov grid lookup
BROOKLYN_LAT = 40.6782
BROOKLYN_LON = -73.9442

# Cache
_cached_weather: Optional[dict] = None
_cache_timestamp: float = 0.0
_CACHE_TTL = 900  # 15 minutes

# Weather.gov gridpoint (pre-resolved for Brooklyn to avoid extra API call)
_GRIDPOINT_URL: Optional[str] = None

# Brooklyn weather-vulnerable roads (from SOP 03_flooding_weather.txt)
FLOOD_PRONE = {
    "belt parkway", "shore parkway", "3rd avenue", "smith street",
    "3rd ave", "gowanus expressway", "hamilton avenue", "9th street",
}
ICE_WIND_PRONE = {
    "williamsburg bridge approach", "bqe service road", "brooklyn bridge",
    "prospect expressway", "verrazzano bridge approach", "manhattan bridge",
    "bqe", "brooklyn-queens expressway",
}
SNOW_ACCUMULATION = {
    "eastern parkway", "ocean parkway", "linden boulevard",
    "ocean avenue", "kings highway", "flatbush avenue",
}


@dataclass
class WeatherCondition:
    condition: str  # clear, cloudy, rain, heavy_rain, snow, ice, fog, wind
    temp_f: float
    precip_pct: int
    wind_mph: float
    is_severe: bool
    description: str
    timestamp: str


async def _resolve_gridpoint() -> str:
    """Get the Weather.gov forecast URL for Brooklyn's grid point."""
    global _GRIDPOINT_URL
    if _GRIDPOINT_URL:
        return _GRIDPOINT_URL

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"https://api.weather.gov/points/{BROOKLYN_LAT},{BROOKLYN_LON}",
            headers={"User-Agent": "TrafficMind/1.0 (traffic@example.com)"},
        )
        resp.raise_for_status()
        data = resp.json()
        _GRIDPOINT_URL = data["properties"]["forecastHourly"]

    return _GRIDPOINT_URL


def _parse_condition(short_forecast: str) -> str:
    """Map Weather.gov short forecast to our condition enum."""
    f = short_forecast.lower()
    if "snow" in f or "blizzard" in f:
        return "snow"
    if "ice" in f or "sleet" in f or "freezing" in f:
        return "ice"
    if "fog" in f:
        return "fog"
    if "thunder" in f or "heavy rain" in f:
        return "heavy_rain"
    if "rain" in f or "shower" in f or "drizzle" in f:
        return "rain"
    if "wind" in f:
        return "wind"
    if "cloud" in f or "overcast" in f or "mostly cloudy" in f:
        return "cloudy"
    if "partly" in f:
        return "partly_cloudy"
    return "clear"


def _parse_wind_speed(wind_str: str) -> float:
    """Extract numeric wind speed from string like '10 mph'."""
    try:
        return float(wind_str.split()[0])
    except (ValueError, IndexError):
        return 0.0


async def get_weather() -> WeatherCondition:
    """Fetch current weather for Brooklyn with 15-minute cache."""
    global _cached_weather, _cache_timestamp

    now = time.time()
    if _cached_weather and (now - _cache_timestamp) < _CACHE_TTL:
        return WeatherCondition(**_cached_weather)

    try:
        grid_url = await _resolve_gridpoint()

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                grid_url,
                headers={"User-Agent": "TrafficMind/1.0 (traffic@example.com)"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Get the first (current) period
        periods = data["properties"]["periods"]
        current = periods[0]

        temp_f = current["temperature"]
        wind_mph = _parse_wind_speed(current.get("windSpeed", "0 mph"))
        precip_pct = current.get("probabilityOfPrecipitation", {}).get("value") or 0
        short_forecast = current.get("shortForecast", "Unknown")
        condition = _parse_condition(short_forecast)

        is_severe = (
            precip_pct > 60
            or wind_mph > 30
            or condition in ("snow", "ice", "heavy_rain")
        )

        weather_data = {
            "condition": condition,
            "temp_f": temp_f,
            "precip_pct": int(precip_pct),
            "wind_mph": round(wind_mph, 1),
            "is_severe": is_severe,
            "description": short_forecast,
            "timestamp": current.get("startTime", ""),
        }

        _cached_weather = weather_data
        _cache_timestamp = now

        return WeatherCondition(**weather_data)

    except Exception as e:
        print(f"Weather API error: {e}")
        # Return cached data if available, else fallback
        if _cached_weather:
            return WeatherCondition(**_cached_weather)
        return WeatherCondition(
            condition="clear",
            temp_f=55.0,
            precip_pct=0,
            wind_mph=5.0,
            is_severe=False,
            description="Weather data unavailable",
            timestamp="",
        )


def get_weather_penalty(street_name: str, condition: str) -> float:
    """Return speed penalty multiplier for weather + road vulnerability.

    Returns 1.0 (no penalty) to 3.0 (severe).
    Higher multiplier = worse conditions = higher edge cost in routing.
    """
    name = street_name.lower()

    if condition in ("clear", "partly_cloudy"):
        return 1.0

    # Check road vulnerability categories
    is_flood = any(road in name for road in FLOOD_PRONE)
    is_ice_wind = any(road in name for road in ICE_WIND_PRONE)
    is_snow_acc = any(road in name for road in SNOW_ACCUMULATION)

    if condition in ("rain", "heavy_rain"):
        if is_flood:
            return 2.5
        return 1.3 if condition == "rain" else 1.8

    if condition == "snow":
        if is_snow_acc:
            return 2.0
        if is_ice_wind:
            return 2.5
        return 1.5

    if condition == "ice":
        if is_ice_wind:
            return 3.0
        return 2.0

    if condition == "fog":
        if is_ice_wind:
            return 1.8
        return 1.3

    if condition == "wind":
        if is_ice_wind:
            return 2.0
        return 1.2

    if condition == "cloudy":
        return 1.0

    return 1.2
