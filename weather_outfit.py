"""
weather_outfit.py — Weather-Based Outfit Picker
Fetches current weather + forecast from OpenWeatherMap and recommends
what to wear today based on temperature, rain probability, wind, and UV index.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Optional

import requests

from outfit_engine import OutfitEngine
from weather_client import WeatherClient, WeatherData
from config import Config


# ── ANSI colour helpers ────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"


def _col(text: str, colour: str) -> str:
    """Wrap text in a colour code (skipped when not a TTY)."""
    if not sys.stdout.isatty():
        return text
    return f"{colour}{text}{RESET}"


# ── pretty printer ─────────────────────────────────────────────────────────────

def print_weather(data: WeatherData, unit_label: str):
    """Render a weather summary block."""
    icons = {
        "Clear": "☀️ ", "Clouds": "☁️ ", "Rain": "🌧️ ",
        "Drizzle": "🌦️ ", "Thunderstorm": "⛈️ ", "Snow": "❄️ ",
        "Mist": "🌫️ ", "Fog": "🌫️ ", "Haze": "🌫️ ",
    }
    icon = icons.get(data.condition, "🌡️ ")

    print()
    print(_col("─" * 52, DIM))
    print(_col(f"  {icon}  {data.city}, {data.country}", BOLD + WHITE))
    print(_col(f"  {data.description.title()}", DIM))
    print(_col("─" * 52, DIM))

    temp_colour = (
        BLUE   if data.temp_c < 5  else
        CYAN   if data.temp_c < 15 else
        GREEN  if data.temp_c < 25 else
        YELLOW if data.temp_c < 32 else
        RED
    )
    print(
        f"  Temperature  {_col(f'{data.display_temp:.1f}{unit_label}', temp_colour + BOLD)}"
        f"  (feels like {data.display_feels_like:.1f}{unit_label})"
    )
    print(f"  Humidity     {data.humidity}%")
    print(f"  Wind         {data.wind_kph:.1f} km/h")

    rain_col = RED if data.rain_probability > 60 else (
               YELLOW if data.rain_probability > 30 else GREEN)
    print(f"  Rain chance  {_col(str(data.rain_probability) + '%', rain_col)}")

    if data.uv_index is not None:
        uv_col = RED if data.uv_index >= 8 else (
                 YELLOW if data.uv_index >= 3 else GREEN)
        print(f"  UV index     {_col(str(data.uv_index), uv_col)}")

    print(_col("─" * 52, DIM))


def print_outfit(outfit: dict):
    """Render the outfit recommendation."""
    print()
    print(_col("  👗  OUTFIT RECOMMENDATION", BOLD + CYAN))
    print()

    categories = [
        ("Tops",       outfit.get("tops", [])),
        ("Bottoms",    outfit.get("bottoms", [])),
        ("Outerwear",  outfit.get("outerwear", [])),
        ("Footwear",   outfit.get("footwear", [])),
        ("Accessories",outfit.get("accessories", [])),
    ]
    for label, items in categories:
        if items:
            joined = ", ".join(items)
            print(f"  {_col(f'{label:<12}', DIM)}  {joined}")

    tips = outfit.get("tips", [])
    if tips:
        print()
        print(_col("  💡  Tips", BOLD))
        for tip in tips:
            print(f"  • {tip}")

    print()
    vibe = outfit.get("vibe", "")
    if vibe:
        print(_col(f"  ✨  Vibe: {vibe}", MAGENTA))

    print()


def print_forecast_summary(forecasts: list[dict], unit_label: str):
    """Print a compact 3-day summary."""
    if not forecasts:
        return
    print(_col("  📅  Next 3 days", BOLD))
    print()
    for f in forecasts[:3]:
        rain_tag = f" 🌧 {f['rain_prob']}%" if f["rain_prob"] > 20 else ""
        print(
            f"  {_col(f['day']:<10, DIM)}"
            f"  {f['display_min']:.0f}–{f['display_max']:.0f}{unit_label}"
            f"  {f['description'].title()}{rain_tag}"
        )
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="weather_outfit",
        description="Weather-Based Outfit Picker — know what to wear before you open the door.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("city", nargs="?",
                        help="City name (e.g. 'London', 'New York'). "
                             "Overrides WEATHER_CITY env var.")
    parser.add_argument("--api-key", dest="api_key",
                        help="OpenWeatherMap API key. Overrides OPENWEATHER_API_KEY env var.")
    parser.add_argument("--units", choices=["metric", "imperial"], default=None,
                        help="Temperature units (metric=°C, imperial=°F). "
                             "Default: auto-detect from city country.")
    parser.add_argument("--style", choices=["casual", "business", "sport", "formal"],
                        default="casual", help="Dress style preference.")
    parser.add_argument("--json", dest="output_json", action="store_true",
                        help="Output raw JSON instead of pretty-printed text.")
    parser.add_argument("--forecast", action="store_true",
                        help="Show a 3-day forecast summary.")
    parser.add_argument("--save-config", action="store_true",
                        help="Save --city / --units / --style as defaults.")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    cfg = Config()

    # Resolve settings: CLI flag > env var > saved config > interactive prompt
    api_key = (
        args.api_key
        or os.environ.get("OPENWEATHER_API_KEY")
        or cfg.api_key
    )
    city = (
        args.city
        or os.environ.get("WEATHER_CITY")
        or cfg.city
    )
    style = args.style or cfg.style or "casual"

    if not api_key:
        print(_col("No API key found.", RED))
        print("  Set OPENWEATHER_API_KEY environment variable, or pass --api-key.")
        print("  Get a free key at https://openweathermap.org/api")
        sys.exit(1)

    if not city:
        city = input("Enter city name: ").strip()
        if not city:
            print(_col("No city provided. Exiting.", RED))
            sys.exit(1)

    # Save config if requested
    if args.save_config:
        cfg.api_key = api_key
        cfg.city    = city
        cfg.style   = style
        if args.units:
            cfg.units = args.units
        cfg.save()
        print(_col(f"  ✓ Config saved to {cfg.config_path}", GREEN))

    # Fetch weather
    client = WeatherClient(api_key)
    try:
        data = client.fetch_current(city)
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            print(_col("Invalid API key. Check OPENWEATHER_API_KEY.", RED))
        elif e.response is not None and e.response.status_code == 404:
            print(_col(f"City not found: '{city}'. Try a different spelling.", RED))
        else:
            print(_col(f"API error: {e}", RED))
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(_col("Network error — are you connected to the internet?", RED))
        sys.exit(1)

    # Resolve units (flag > auto-detect from country)
    units = args.units or cfg.units or _auto_units(data.country)
    data.set_display_units(units)

    # Build outfit
    engine = OutfitEngine(style=style)
    outfit  = engine.recommend(data)

    # Forecast
    forecasts = []
    if args.forecast:
        raw_forecasts = client.fetch_forecast(city)
        forecasts = [
            {**f, **_apply_units(f, units)}
            for f in raw_forecasts
        ]

    # Output
    unit_label = "°C" if units == "metric" else "°F"

    if args.output_json:
        out = {
            "city":    data.city,
            "country": data.country,
            "weather": {
                "temp":            data.display_temp,
                "feels_like":      data.display_feels_like,
                "humidity":        data.humidity,
                "wind_kph":        data.wind_kph,
                "rain_probability":data.rain_probability,
                "uv_index":        data.uv_index,
                "condition":       data.condition,
                "description":     data.description,
            },
            "units":   units,
            "outfit":  outfit,
            "forecast":forecasts,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print_weather(data, unit_label)
    print_outfit(outfit)
    if args.forecast:
        print_forecast_summary(forecasts, unit_label)


def _auto_units(country: str) -> str:
    """Use imperial for US, Liberia, Myanmar; metric elsewhere."""
    return "imperial" if country in ("US", "LR", "MM") else "metric"


def _apply_units(forecast: dict, units: str) -> dict:
    """Convert forecast min/max temps to display units."""
    if units == "imperial":
        return {
            "display_min": forecast["temp_min_c"] * 9 / 5 + 32,
            "display_max": forecast["temp_max_c"] * 9 / 5 + 32,
        }
    return {
        "display_min": forecast["temp_min_c"],
        "display_max": forecast["temp_max_c"],
    }


if __name__ == "__main__":
    main()