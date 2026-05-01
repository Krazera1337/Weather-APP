"""
tests/test_weather_outfit.py — Unit tests for Weather Outfit Picker.

Run with:  pytest tests/ -v
"""

import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from weather_client import WeatherClient, WeatherData
from outfit_engine  import OutfitEngine
from config         import Config


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_weather(**overrides) -> WeatherData:
    """Factory for WeatherData with sane defaults."""
    defaults = dict(
        city="London", country="GB",
        temp_c=15.0, feels_like_c=13.0,
        humidity=60, wind_kph=15.0,
        rain_probability=10,
        condition="Clouds", description="overcast clouds",
        uv_index=3.0,
    )
    defaults.update(overrides)
    return WeatherData(**defaults)


# ── WeatherData ───────────────────────────────────────────────────────────────

class TestWeatherData:
    def test_defaults_to_celsius(self):
        wd = make_weather(temp_c=20.0, feels_like_c=18.0)
        assert wd.display_temp       == 20.0
        assert wd.display_feels_like == 18.0

    def test_set_metric_noop(self):
        wd = make_weather(temp_c=20.0, feels_like_c=18.0)
        wd.set_display_units("metric")
        assert wd.display_temp       == 20.0
        assert wd.display_feels_like == 18.0

    def test_set_imperial_converts(self):
        wd = make_weather(temp_c=0.0, feels_like_c=0.0)
        wd.set_display_units("imperial")
        assert wd.display_temp       == pytest.approx(32.0)
        assert wd.display_feels_like == pytest.approx(32.0)

    def test_imperial_100c_is_212f(self):
        wd = make_weather(temp_c=100.0, feels_like_c=100.0)
        wd.set_display_units("imperial")
        assert wd.display_temp == pytest.approx(212.0)


# ── WeatherClient parsing ─────────────────────────────────────────────────────

class TestWeatherClientParsing:
    """Tests the _parse_current static method directly (no network calls)."""

    CURRENT_STUB = {
        "name": "Berlin",
        "sys":  {"country": "DE"},
        "main": {
            "temp": 8.5, "feels_like": 6.0,
            "humidity": 80,
        },
        "wind":    {"speed": 5.0},
        "weather": [{"main": "Rain", "description": "light rain"}],
        "rain":    {"1h": 0.8},
    }

    def test_parse_city_country(self):
        wd = WeatherClient._parse_current(self.CURRENT_STUB)
        assert wd.city    == "Berlin"
        assert wd.country == "DE"

    def test_parse_temp(self):
        wd = WeatherClient._parse_current(self.CURRENT_STUB)
        assert wd.temp_c       == pytest.approx(8.5)
        assert wd.feels_like_c == pytest.approx(6.0)

    def test_parse_wind_kph(self):
        wd = WeatherClient._parse_current(self.CURRENT_STUB)
        # 5.0 m/s × 3.6 = 18.0 km/h
        assert wd.wind_kph == pytest.approx(18.0)

    def test_parse_condition(self):
        wd = WeatherClient._parse_current(self.CURRENT_STUB)
        assert wd.condition   == "Rain"
        assert wd.description == "light rain"

    def test_parse_rain_probability_heuristic(self):
        wd = WeatherClient._parse_current(self.CURRENT_STUB)
        # rain vol 0.8 * 20 = 16 → capped at 100
        assert 0 <= wd.rain_probability <= 100

    def test_parse_no_rain_key(self):
        stub = dict(self.CURRENT_STUB)
        stub.pop("rain", None)
        wd = WeatherClient._parse_current(stub)
        assert wd.rain_probability == 0

    def test_parse_no_wind_key(self):
        stub = dict(self.CURRENT_STUB)
        stub.pop("wind", None)
        wd = WeatherClient._parse_current(stub)
        assert wd.wind_kph == 0.0

    def test_fetch_raises_on_bad_status(self):
        import requests
        client = WeatherClient("fake_key")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=MagicMock(status_code=401)
        )
        with patch.object(client._session, "get", return_value=mock_resp):
            with pytest.raises(requests.exceptions.HTTPError):
                client.fetch_current("Nowhere")


# ── OutfitEngine ──────────────────────────────────────────────────────────────

class TestOutfitEngine:
    def _rec(self, **weather_kwargs) -> dict:
        engine = OutfitEngine(style="casual")
        return engine.recommend(make_weather(**weather_kwargs))

    # Structure
    def test_output_has_all_keys(self):
        out = self._rec()
        for key in ("tops", "bottoms", "outerwear", "footwear", "accessories", "tips", "vibe"):
            assert key in out

    def test_lists_are_nonempty(self):
        out = self._rec(temp_c=15.0)
        assert len(out["tops"])    > 0
        assert len(out["bottoms"]) > 0
        assert len(out["footwear"]) > 0
        assert isinstance(out["vibe"], str) and out["vibe"]

    # Temperature extremes
    def test_freezing_has_heavy_layers(self):
        out = self._rec(temp_c=-5.0, rain_probability=0)
        tops_str = " ".join(out["tops"]).lower()
        assert any(w in tops_str for w in ("thermal", "wool", "heavy", "fleece"))

    def test_hot_has_light_tops(self):
        out = self._rec(temp_c=35.0, rain_probability=0)
        tops_str = " ".join(out["tops"]).lower()
        assert any(w in tops_str for w in ("tank", "linen", "light", "sleeveless"))

    def test_scorching_has_shorts(self):
        out = self._rec(temp_c=36.0, rain_probability=0)
        bottoms_str = " ".join(out["bottoms"]).lower()
        assert "short" in bottoms_str

    # Rain logic
    def test_heavy_rain_includes_rain_jacket(self):
        out = self._rec(temp_c=15.0, rain_probability=75, condition="Rain")
        outer_str = " ".join(out["outerwear"]).lower()
        assert "rain" in outer_str or "waterproof" in outer_str

    def test_light_rain_includes_umbrella(self):
        out = self._rec(temp_c=18.0, rain_probability=35)
        acc_str = " ".join(out["accessories"]).lower()
        assert "umbrella" in acc_str

    def test_no_rain_no_umbrella(self):
        out = self._rec(temp_c=22.0, rain_probability=5)
        acc_str = " ".join(out["accessories"]).lower()
        assert "umbrella" not in acc_str

    # UV logic
    def test_high_uv_includes_sunscreen_and_hat(self):
        out = self._rec(temp_c=28.0, uv_index=9.0, rain_probability=0)
        acc_str = " ".join(out["accessories"]).lower()
        assert "sunscreen" in acc_str or "sunglasses" in acc_str

    def test_moderate_uv_includes_sunglasses(self):
        out = self._rec(temp_c=22.0, uv_index=4.0, rain_probability=0)
        acc_str = " ".join(out["accessories"]).lower()
        assert "sunglasses" in acc_str

    def test_no_uv_no_sunscreen(self):
        out = self._rec(temp_c=10.0, uv_index=1.0, rain_probability=0)
        acc_str = " ".join(out["accessories"]).lower()
        assert "sunscreen" not in acc_str

    # Cold accessories
    def test_very_cold_has_gloves_and_scarf(self):
        out = self._rec(temp_c=2.0, rain_probability=0)
        acc_str = " ".join(out["accessories"]).lower()
        assert "gloves" in acc_str
        assert "scarf"  in acc_str

    # Feels-like tips
    def test_feels_much_colder_triggers_tip(self):
        out = self._rec(temp_c=20.0, feels_like_c=14.0)  # delta=6
        tips_str = " ".join(out["tips"]).lower()
        assert "colder" in tips_str or "layer" in tips_str

    def test_feels_much_warmer_triggers_tip(self):
        out = self._rec(temp_c=10.0, feels_like_c=14.0)  # delta=-4
        tips_str = " ".join(out["tips"]).lower()
        assert "warmer" in tips_str or "lighter" in tips_str

    # Style variants
    @pytest.mark.parametrize("style", ["casual", "business", "sport", "formal"])
    def test_all_styles_produce_valid_output(self, style):
        engine = OutfitEngine(style=style)
        out = engine.recommend(make_weather(temp_c=15.0))
        assert out["tops"] and out["bottoms"] and out["footwear"]

    def test_invalid_style_raises(self):
        with pytest.raises(ValueError):
            OutfitEngine(style="pirate")

    # Vibe
    def test_snow_vibe(self):
        out = self._rec(temp_c=-2.0, condition="Snow")
        assert "winter" in out["vibe"].lower() or "cosy" in out["vibe"].lower()

    def test_rain_vibe(self):
        out = self._rec(temp_c=14.0, condition="Rain", rain_probability=80)
        assert "rain" in out["vibe"].lower()


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_defaults(self, tmp_path, monkeypatch):
        import config as cfg_mod
        monkeypatch.setattr(cfg_mod, "CONFIG_DIR",  tmp_path)
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", tmp_path / "config.json")
        c = Config()
        assert c.style   == "casual"
        assert c.api_key is None
        assert c.city    is None

    def test_save_and_reload(self, tmp_path, monkeypatch):
        import config as cfg_mod
        cf = tmp_path / "config.json"
        monkeypatch.setattr(cfg_mod, "CONFIG_DIR",  tmp_path)
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cf)

        c = Config()
        c.api_key = "TEST_KEY"
        c.city    = "Tokyo"
        c.units   = "metric"
        c.style   = "formal"
        c.save()

        c2 = Config()
        assert c2.api_key == "TEST_KEY"
        assert c2.city    == "Tokyo"
        assert c2.units   == "metric"
        assert c2.style   == "formal"

    def test_corrupted_json_uses_defaults(self, tmp_path, monkeypatch):
        import config as cfg_mod
        cf = tmp_path / "config.json"
        cf.write_text("{{{invalid json", encoding="utf-8")
        monkeypatch.setattr(cfg_mod, "CONFIG_DIR",  tmp_path)
        monkeypatch.setattr(cfg_mod, "CONFIG_FILE", cf)
        c = Config()
        assert c.style == "casual"