# 👗 Weather-Based Outfit Picker

> Know what to wear before you open the door. Pulls live weather from OpenWeatherMap and recommends a complete outfit — tops, bottoms, outerwear, footwear, and accessories — based on temperature, rain probability, wind speed, UV index, and your style preference.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![CI](https://img.shields.io/github/actions/workflow/status/yourusername/weather-outfit-picker/ci.yml?style=flat-square&label=CI)
![Dependencies](https://img.shields.io/badge/dependencies-requests-orange?style=flat-square)

---

## Demo

```
────────────────────────────────────────────────────────────
  🌧️   London, GB
  Light Rain
────────────────────────────────────────────────────────────
  Temperature  11.4°C  (feels like 8.9°C)
  Humidity     84%
  Wind         22.0 km/h
  Rain chance  65%
  UV index     2
────────────────────────────────────────────────────────────

  👗  OUTFIT RECOMMENDATION

  Tops          long-sleeve T-shirt, hoodie
  Bottoms       jeans
  Outerwear     denim jacket or light bomber, waterproof rain jacket
  Footwear      ankle boots or sneakers, waterproof shoe covers
  Accessories   compact umbrella

  💡  Tips
  • High rain chance (65%) — keep a dry change of socks in your bag.
  • Feels 2°C colder than actual temp — dress one layer warmer.

  ✨  Vibe: Rainy-day ready — pragmatic chic.
```

---

## Features

- **Live weather** — OpenWeatherMap Current Weather + 5-day Forecast API
- **Smart outfit logic** — 8 temperature bands × 4 style modes × rain/wind/UV modifiers
- **4 style modes** — `casual`, `business`, `sport`, `formal`
- **3-day forecast** — optional daily summary with rain probability
- **JSON output** — pipe into other tools or scripts with `--json`
- **Persistent config** — save your city, API key, and style preference
- **Auto imperial/metric** — detects US/Liberia/Myanmar and switches automatically
- **Headless-friendly** — works in cron, CI, and pipelines

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/yourusername/weather-outfit-picker.git
cd weather-outfit-picker
pip install requests
```

### 2. Get a free API key

Sign up at [openweathermap.org](https://openweathermap.org/api) → free tier includes Current Weather + Forecast.

### 3. Run

```bash
# Simplest — pass key and city inline
python weather_outfit.py "London" --api-key YOUR_KEY

# Set env vars (recommended)
export OPENWEATHER_API_KEY=your_key
python weather_outfit.py "Tokyo"

# Save defaults so you never type them again
python weather_outfit.py "New York" --api-key YOUR_KEY --style business --save-config
python weather_outfit.py   # uses saved city + key every time
```

---

## CLI Reference

```
usage: weather_outfit [-h] [--api-key API_KEY]
                      [--units {metric,imperial}]
                      [--style {casual,business,sport,formal}]
                      [--json] [--forecast] [--save-config]
                      [city]

positional arguments:
  city                  City name (e.g. 'London', 'New York')

options:
  --api-key API_KEY     OpenWeatherMap API key
  --units               metric (°C) or imperial (°F). Default: auto
  --style               casual | business | sport | formal  [default: casual]
  --json                Output raw JSON
  --forecast            Show 3-day forecast
  --save-config         Persist --city / --api-key / --units / --style
```

### Environment variables

| Variable | Description |
|---|---|
| `OPENWEATHER_API_KEY` | Your API key |
| `WEATHER_CITY` | Default city |

---

## Project Structure

```
weather-outfit-picker/
├── weather_outfit.py    # CLI entry point + pretty-printer
├── weather_client.py    # OpenWeatherMap API wrapper
├── outfit_engine.py     # Rule-based outfit recommendation engine
├── config.py            # JSON-backed settings (~/.weather_outfit/)
├── requirements.txt
├── tests/
│   └── test_weather_outfit.py   # 30+ pytest cases
└── .github/
    └── workflows/
        └── ci.yml       # GitHub Actions CI
```

---

## How the Outfit Engine Works

```
WeatherData
    │
    ├── temp_c           → temperature band (8 bands: ≤0, ≤5, ≤10, ≤15, ≤20, ≤25, ≤30, 30+)
    ├── rain_probability → outerwear modifier (rain jacket if ≥60%, packable if ≥30%)
    ├── wind_kph         → accessories + outerwear modifier (windbreaker if ≥25 km/h)
    └── uv_index         → accessories (sunglasses ≥3, sunscreen ≥6, wide-brim hat ≥8)
         │
         ▼
    OutfitPlan
    { tops, bottoms, outerwear, footwear, accessories, tips, vibe }
```

Each category is selected from style-specific lookup tables indexed by temperature band, then modified by weather conditions.

---

## JSON Output

```bash
python weather_outfit.py "Paris" --json | jq '.outfit.outerwear'
# → ["light cardigan or denim jacket", "packable rain jacket"]
```

Full schema:

```json
{
  "city": "Paris",
  "country": "FR",
  "weather": {
    "temp": 14.2,
    "feels_like": 13.1,
    "humidity": 78,
    "wind_kph": 18.0,
    "rain_probability": 40,
    "uv_index": 3,
    "condition": "Clouds",
    "description": "broken clouds"
  },
  "units": "metric",
  "outfit": {
    "tops": ["long-sleeve T-shirt"],
    "bottoms": ["jeans"],
    "outerwear": ["light cardigan or denim jacket", "packable rain jacket"],
    "footwear": ["ankle boots or sneakers"],
    "accessories": ["compact umbrella", "sunglasses"],
    "tips": ["Some rain possible (40%) — a packable jacket is your best friend."],
    "vibe": "Layered and intentional — autumn sophistication."
  },
  "forecast": []
}
```

---

## Running Tests

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

The test suite includes 30+ cases covering temperature bands, rain/wind/UV logic, all four style modes, unit conversion, API parsing, and config persistence — no network calls required (fully mocked).

---

## Contributing

1. Fork → branch → change → `pytest tests/ -v` → PR
2. Add tests for new temperature bands or style rules in `tests/test_weather_outfit.py`

---

## License

MIT — see [LICENSE](LICENSE).