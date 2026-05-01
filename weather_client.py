"""
weather_client.py — OpenWeatherMap API client.

Wraps the Current Weather and 5-day/3-hour Forecast endpoints.
All temperatures stored internally in Celsius; display units applied separately.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

import requests

BASE_URL = "https://api.openweathermap.org/data/2.5"
TIMEOUT  = 10   # seconds


@dataclass
class WeatherData:
    """Parsed weather snapshot for a single location."""
    city:             str
    country:          str
    temp_c:           float
    feels_like_c:     float
    humidity:         int
    wind_kph:         float
    rain_probability: int           # 0–100
    condition:        str           # e.g. "Rain", "Clear"
    description:      str           # e.g. "light rain"
    uv_index:         Optional[float] = None

    # Display-unit fields (set by set_display_units)
    display_temp:       float = field(init=False)
    display_feels_like: float = field(init=False)

    def __post_init__(self):
        self.display_temp       = self.temp_c
        self.display_feels_like = self.feels_like_c

    def set_display_units(self, units: str):
        """Convert stored Celsius values to display units."""
        if units == "imperial":
            self.display_temp       = self.temp_c * 9 / 5 + 32
            self.display_feels_like = self.feels_like_c * 9 / 5 + 32
        else:
            self.display_temp       = self.temp_c
            self.display_feels_like = self.feels_like_c


class WeatherClient:
    """Thin wrapper around the OpenWeatherMap REST API."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("api_key must not be empty.")
        self._key = api_key
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ── public ────────────────────────────────────────────────────────────────

    def fetch_current(self, city: str) -> WeatherData:
        """
        Fetch current conditions for *city*.

        Raises:
            requests.exceptions.HTTPError  on 4xx / 5xx responses.
            requests.exceptions.ConnectionError on network failure.
        """
        raw = self._get(f"{BASE_URL}/weather", {
            "q":     city,
            "units": "metric",   # always fetch in metric; convert on display
            "appid": self._key,
        })
        return self._parse_current(raw)

    def fetch_forecast(self, city: str) -> list[dict]:
        """
        Fetch a 3-day daily summary derived from the 5-day/3-hour forecast.

        Returns a list of dicts with keys:
            day, date, temp_min_c, temp_max_c, description, rain_prob
        """
        raw = self._get(f"{BASE_URL}/forecast", {
            "q":     city,
            "units": "metric",
            "cnt":   40,        # max 5 days × 8 intervals
            "appid": self._key,
        })
        return self._parse_forecast(raw)

    # ── internal ──────────────────────────────────────────────────────────────

    def _get(self, url: str, params: dict) -> dict:
        resp = self._session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _parse_current(raw: dict) -> WeatherData:
        main    = raw["main"]
        weather = raw["weather"][0]
        wind    = raw.get("wind", {})
        rain    = raw.get("rain", {})

        # Rain probability: use hourly rain volume as a rough proxy
        # (the /weather endpoint doesn't expose PoP directly)
        rain_vol_1h = rain.get("1h", 0.0)
        rain_prob   = min(100, int(rain_vol_1h * 20))   # rough heuristic

        return WeatherData(
            city             = raw.get("name", "Unknown"),
            country          = raw.get("sys", {}).get("country", ""),
            temp_c           = main["temp"],
            feels_like_c     = main["feels_like"],
            humidity         = main["humidity"],
            wind_kph         = wind.get("speed", 0) * 3.6,   # m/s → km/h
            rain_probability = rain_prob,
            condition        = weather["main"],
            description      = weather["description"],
        )

    @staticmethod
    def _parse_forecast(raw: dict) -> list[dict]:
        """Collapse 3-hour intervals into daily summaries."""
        buckets: dict[str, dict] = defaultdict(lambda: {
            "temps": [], "descriptions": [], "rain_probs": []
        })

        for item in raw.get("list", []):
            dt   = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
            date = dt.strftime("%Y-%m-%d")
            day  = dt.strftime("%A")

            buckets[date]["day"]  = day
            buckets[date]["date"] = date
            buckets[date]["temps"].append(item["main"]["temp"])
            buckets[date]["descriptions"].append(
                item["weather"][0]["description"]
            )
            buckets[date]["rain_probs"].append(
                int(item.get("pop", 0) * 100)
            )

        result = []
        today  = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        for date, info in sorted(buckets.items()):
            if date == today:
                continue    # skip today (already shown in current)
            temps = info["temps"]
            # Pick the most common description
            desc_counts: dict[str, int] = defaultdict(int)
            for d in info["descriptions"]:
                desc_counts[d] += 1
            top_desc = max(desc_counts, key=lambda k: desc_counts[k])

            result.append({
                "day":         info["day"],
                "date":        date,
                "temp_min_c":  min(temps),
                "temp_max_c":  max(temps),
                "description": top_desc,
                "rain_prob":   max(info["rain_probs"]),
            })
            if len(result) >= 3:
                break

        return result