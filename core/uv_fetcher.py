# ============================================================
# UV Skincare Advisor — core/uv_fetcher.py
# Responsible for: Fetching real-time UV Index data
# API Used: Open-Meteo (free, no API key required)
# Team role: DATA COLLECTOR owns this file
# ============================================================

import requests
from datetime import datetime

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL  = "https://api.open-meteo.com/v1/forecast"


def get_coordinates(city_name: str) -> dict:
    """
    Converts a city name to latitude, longitude, and timezone.
    Step 1 of our two-step pipeline.
    """
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"name": city_name, "count": 1, "language": "en", "format": "json"},
            timeout=8
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return {"error": "city_not_found"}

        top = data["results"][0]
        return {
            "lat":      top["latitude"],
            "lon":      top["longitude"],
            "city":     top.get("name", city_name),
            "country":  top.get("country", ""),
            "timezone": top.get("timezone", "UTC"),
            "elevation": top.get("elevation", 0),
        }

    except requests.exceptions.ConnectionError:
        return {"error": "no_internet"}
    except requests.exceptions.Timeout:
        return {"error": "timeout"}
    except requests.exceptions.HTTPError:
        return {"error": f"http_{response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_uv_and_weather(lat: float, lon: float, timezone: str) -> dict:
    """
    Fetches current UV Index and weather data for given coordinates.
    Step 2 of our two-step pipeline.
    """
    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude":        lat,
                "longitude":       lon,
                "timezone":        timezone,
                "forecast_days":   1,
                "hourly": ",".join([
                    "uv_index",
                    "cloud_cover",
                    "temperature_2m",
                    "weather_code",
                ]),
                "daily": ",".join([
                    "uv_index_max",
                    "temperature_2m_max",
                    "sunrise",
                    "sunset",
                ]),
                "current_weather": "true",
            },
            timeout=8
        )
        response.raise_for_status()
        data = response.json()

        # ── Find the current hour index ───────────────────────
        # Use the API's own current_weather.time (already in city's
        # local timezone) to find the correct hourly slot.
        hourly_times     = data["hourly"]["time"]
        api_current_time = data.get("current_weather", {}).get("time", "")

        if api_current_time:
            now_str = api_current_time[:13] + ":00"
        else:
            now_str = datetime.now().strftime("%Y-%m-%dT%H:00")

        current_hour_idx = 0
        for i, t in enumerate(hourly_times):
            if t == now_str:
                current_hour_idx = i
                break

        # ── Extract current hour values ───────────────────────
        uv_now    = data["hourly"]["uv_index"][current_hour_idx]
        cloud_now = data["hourly"]["cloud_cover"][current_hour_idx]
        temp_now  = data["hourly"]["temperature_2m"][current_hour_idx]
        wcode_now = data["hourly"]["weather_code"][current_hour_idx]

        # ── Daily summary ─────────────────────────────────────
        uv_max_today = data["daily"]["uv_index_max"][0]
        temp_max     = data["daily"]["temperature_2m_max"][0]
        sunrise      = data["daily"]["sunrise"][0].split("T")[1]
        sunset       = data["daily"]["sunset"][0].split("T")[1]

        # ── Hourly arrays for Charts tab ──────────────────────
        hourly_labels = [t.split("T")[1] for t in hourly_times]
        hourly_uv     = [round(v or 0, 1) for v in data["hourly"]["uv_index"]]
        hourly_cloud  = [v or 0 for v in data["hourly"]["cloud_cover"]]

        return {
            "uv_index":            round(uv_now or 0, 1),
            "uv_index_max_today":  round(uv_max_today or 0, 1),
            "cloud_cover_pct":     cloud_now or 0,
            "temperature_c":       round(temp_now or 0, 1),
            "temp_max_c":          round(temp_max or 0, 1),
            "weather_code":        wcode_now,
            "weather_description": _weather_code_to_text(wcode_now),
            "sunrise":             sunrise,
            "sunset":              sunset,
            "current_hour_idx":    current_hour_idx,
            "hourly_labels":       hourly_labels,
            "hourly_uv":           hourly_uv,
            "hourly_cloud":        hourly_cloud,
        }

    except requests.exceptions.ConnectionError:
        return {"error": "no_internet"}
    except requests.exceptions.Timeout:
        return {"error": "timeout"}
    except requests.exceptions.HTTPError:
        return {"error": f"http_{response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def fetch_uv_data(city_name: str) -> dict:
    """
    FACADE FUNCTION — the only function app.py needs to call.
    Orchestrates: city name → coordinates → UV + weather data.
    """

    # ── Step 1: Geocode ───────────────────────────────────────
    coords = get_coordinates(city_name)

    if "error" in coords:
        if coords["error"] == "city_not_found":
            return {
                "success":    False,
                "error_type": "city_not_found",
                "message":    f"Could not find '{city_name}'. Try a different spelling."
            }
        return _handle_error(coords["error"])

    # ── Step 2: Fetch UV + weather ────────────────────────────
    weather = get_uv_and_weather(coords["lat"], coords["lon"], coords["timezone"])

    if "error" in weather:
        return _handle_error(weather["error"])

    # ── Success ───────────────────────────────────────────────
    return {
        "success":             True,
        "city":                coords["city"],
        "country":             coords["country"],
        "lat":                 coords["lat"],
        "lon":                 coords["lon"],
        "elevation_m":         coords["elevation"],
        "timezone":            coords["timezone"],
        "uv_index":            weather["uv_index"],
        "uv_index_max_today":  weather["uv_index_max_today"],
        "cloud_cover_pct":     weather["cloud_cover_pct"],
        "temperature_c":       weather["temperature_c"],
        "temp_max_c":          weather["temp_max_c"],
        "weather_description": weather["weather_description"],
        "sunrise":             weather["sunrise"],
        "sunset":              weather["sunset"],
        "current_hour_idx":    weather["current_hour_idx"],
        "hourly_labels":       weather["hourly_labels"],
        "hourly_uv":           weather["hourly_uv"],
        "hourly_cloud":        weather["hourly_cloud"],
    }


def classify_uv_risk(uv_index: float) -> dict:
    """Maps UV Index to WHO risk band with colour and emoji."""
    if uv_index <= 2:
        return {"level": "Low",       "color": "#4CAF50", "emoji": "🟢"}
    elif uv_index <= 5:
        return {"level": "Moderate",  "color": "#FFC107", "emoji": "🟡"}
    elif uv_index <= 7:
        return {"level": "High",      "color": "#FF9800", "emoji": "🟠"}
    elif uv_index <= 10:
        return {"level": "Very High", "color": "#F44336", "emoji": "🔴"}
    else:
        return {"level": "Extreme",   "color": "#9C27B0", "emoji": "🟣"}


def _weather_code_to_text(code: int) -> str:
    """Converts WMO weather code to human-readable string."""
    if code is None:
        return "Unknown"
    wmo = {
        0: "Clear sky",
        1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow",
        80: "Rain showers", 81: "Showers", 82: "Heavy showers",
        95: "Thunderstorm", 99: "Thunderstorm with hail",
    }
    return wmo.get(code, f"Code {code}")


def _handle_error(error_code: str) -> dict:
    """Maps error codes to friendly messages."""
    messages = {
        "no_internet": "No internet connection. Please check your network.",
        "timeout":     "The weather API timed out. Please try again.",
        "http_400":    "Bad request sent to the weather API.",
        "http_429":    "Too many requests. Wait a moment and try again.",
    }
    return {
        "success":    False,
        "error_type": error_code,
        "message":    messages.get(error_code, f"Unexpected error: {error_code}")
    }