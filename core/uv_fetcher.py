# ============================================================
# Solara — core/uv_fetcher.py
# Fetches real-time UV + weather data from Open-Meteo API
# No API key required — Open-Meteo is free and open source
#
# TWO-STEP PIPELINE:
#   Step 1 — Geocoding:  city name → lat/lon/timezone
#   Step 2 — Forecast:   lat/lon  → UV index + weather data
#
# The only function app.py calls is fetch_uv_data()
# Everything else is a private helper.
# ============================================================

import requests
import time
from datetime import datetime

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL  = "https://api.open-meteo.com/v1/forecast"

# Browser-like User-Agent prevents bot-detection blocks on cloud IPs
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Solara-UV-Advisor/1.0)"
}

# Friendly error messages shown to the user
ERROR_MESSAGES = {
    "no_internet": "No internet connection. Please check your network.",
    "timeout":     "The weather API timed out. Please try again.",
    "http_400":    "Bad request sent to the weather API.",
    "http_429":    "Too many requests. Wait a moment and try again.",
}

# WMO weather code → readable description
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",  2: "Partly cloudy",   3: "Overcast",
    45: "Foggy",        48: "Icy fog",
    51: "Light drizzle",53: "Drizzle",         55: "Heavy drizzle",
    61: "Light rain",   63: "Rain",            65: "Heavy rain",
    71: "Light snow",   73: "Snow",            75: "Heavy snow",
    80: "Rain showers", 81: "Showers",         82: "Heavy showers",
    95: "Thunderstorm", 99: "Thunderstorm with hail",
}


def _get_with_retry(url: str, params: dict, timeout: int = 10) -> requests.Response:
    """
    GET request with automatic retry on HTTP 429 (rate limit).
    Waits increasingly longer between each attempt (2, 4, 6, 8, 10 sec).
    This is needed because Streamlit Cloud's shared IPs get throttled.
    """
    for wait in [2, 4, 6, 8, 10]:
        response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
        if response.status_code != 429:
            return response
        time.sleep(wait)
    return response


def _handle_error(error_code: str, detail: str = "") -> dict:
    """Returns a standardised error dict with a user-friendly message."""
    return {
        "success":    False,
        "error_type": error_code,
        "message":    ERROR_MESSAGES.get(error_code, f"Unexpected error: {error_code}"),
        "detail":     detail,
    }


def _get_coordinates(city_name: str) -> dict:
    """
    Step 1 — Geocoding.
    Converts city name to lat, lon, timezone, and elevation.
    Returns a dict with location data, or {"error": ...} on failure.
    """
    try:
        response = _get_with_retry(
            GEOCODING_URL,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return {"error": "city_not_found"}

        top = data["results"][0]
        return {
            "lat":       top["latitude"],
            "lon":       top["longitude"],
            "city":      top.get("name", city_name),
            "country":   top.get("country", ""),
            "timezone":  top.get("timezone", "UTC"),
            "elevation": top.get("elevation", 0),
        }

    except requests.exceptions.ConnectionError as e:
        return {"error": "no_internet", "detail": str(e)}
    except requests.exceptions.Timeout:
        return {"error": "timeout"}
    except requests.exceptions.HTTPError:
        return {"error": f"http_{response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def _get_weather(lat: float, lon: float, timezone: str) -> dict:
    """
    Step 2 — Forecast.
    Fetches UV Index, weather, and hourly arrays for the Charts tab.
    Returns a dict with all weather data, or {"error": ...} on failure.
    """
    try:
        response = _get_with_retry(
            FORECAST_URL,
            params={
                "latitude":        lat,
                "longitude":       lon,
                "timezone":        timezone,
                "forecast_days":   1,
                "hourly":          "uv_index,cloud_cover,temperature_2m,weather_code",
                "daily":           "uv_index_max,temperature_2m_max,sunrise,sunset",
                "current_weather": "true",
            },
        )
        response.raise_for_status()
        data = response.json()

        hourly = data["hourly"]
        daily  = data["daily"]

        # Find which hourly index matches "now" in the city's local timezone.
        # We use the API's own current_weather.time (already in local time)
        # instead of datetime.now() which would use the server's timezone.
        api_time     = data.get("current_weather", {}).get("time", "")
        now_str      = (api_time[:13] + ":00") if api_time else datetime.now().strftime("%Y-%m-%dT%H:00")
        current_idx  = next((i for i, t in enumerate(hourly["time"]) if t == now_str), 0)

        return {
            "uv_index":            round(hourly["uv_index"][current_idx]   or 0, 1),
            "uv_index_max_today":  round(daily["uv_index_max"][0]          or 0, 1),
            "cloud_cover_pct":     hourly["cloud_cover"][current_idx]      or 0,
            "temperature_c":       round(hourly["temperature_2m"][current_idx] or 0, 1),
            "temp_max_c":          round(daily["temperature_2m_max"][0]    or 0, 1),
            "weather_description": WEATHER_CODES.get(hourly["weather_code"][current_idx], "Unknown"),
            "sunrise":             daily["sunrise"][0].split("T")[1],
            "sunset":              daily["sunset"][0].split("T")[1],
            "current_hour_idx":    current_idx,
            # Hourly arrays used by the Charts tab
            "hourly_labels":       [t.split("T")[1] for t in hourly["time"]],
            "hourly_uv":           [round(v or 0, 1) for v in hourly["uv_index"]],
            "hourly_cloud":        [v or 0 for v in hourly["cloud_cover"]],
        }

    except requests.exceptions.ConnectionError as e:
        return {"error": "no_internet", "detail": str(e)}
    except requests.exceptions.Timeout:
        return {"error": "timeout"}
    except requests.exceptions.HTTPError:
        return {"error": f"http_{response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ── Public functions ──────────────────────────────────────────

def fetch_uv_data(city_name: str) -> dict:
    """
    Facade function — the only function app.py calls.
    Runs the full two-step pipeline and returns one clean dict.
    """
    # Step 1: city name → coordinates
    coords = _get_coordinates(city_name)
    if "error" in coords:
        if coords["error"] == "city_not_found":
            return {"success": False, "error_type": "city_not_found",
                    "message": f"Could not find '{city_name}'. Try a different spelling."}
        return _handle_error(coords["error"], coords.get("detail", ""))

    # Step 2: coordinates → UV + weather
    weather = _get_weather(coords["lat"], coords["lon"], coords["timezone"])
    if "error" in weather:
        return _handle_error(weather["error"], weather.get("detail", ""))

    # Merge into one flat result dict
    return {
        "success":             True,
        "city":                coords["city"],
        "country":             coords["country"],
        "lat":                 coords["lat"],
        "lon":                 coords["lon"],
        "elevation_m":         coords["elevation"],
        "timezone":            coords["timezone"],
        **{k: weather[k] for k in [
            "uv_index", "uv_index_max_today", "cloud_cover_pct",
            "temperature_c", "temp_max_c", "weather_description",
            "sunrise", "sunset", "current_hour_idx",
            "hourly_labels", "hourly_uv", "hourly_cloud",
        ]},
    }


def classify_uv_risk(uv_index: float) -> dict:
    """Maps UV Index value to WHO risk level, colour, and emoji."""
    if uv_index <= 2:  return {"level": "Low",       "color": "#4CAF50", "emoji": "🟢"}
    if uv_index <= 5:  return {"level": "Moderate",  "color": "#FFC107", "emoji": "🟡"}
    if uv_index <= 7:  return {"level": "High",      "color": "#FF9800", "emoji": "🟠"}
    if uv_index <= 10: return {"level": "Very High", "color": "#F44336", "emoji": "🔴"}
    return             {"level": "Extreme",   "color": "#9C27B0", "emoji": "🟣"}