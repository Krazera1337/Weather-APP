"""
config.py — Persistent user preferences for Weather Outfit Picker.

Stored at ~/.weather_outfit/config.json
"""

import json
from pathlib import Path
from typing import Optional

CONFIG_DIR  = Path.home() / ".weather_outfit"
CONFIG_FILE = CONFIG_DIR  / "config.json"


class Config:
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.api_key: Optional[str] = None
        self.city:    Optional[str] = None
        self.units:   Optional[str] = None   # "metric" | "imperial" | None (auto)
        self.style:   str           = "casual"
        self.config_path = CONFIG_FILE
        self._load()

    def _load(self):
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                self.api_key = data.get("api_key")
                self.city    = data.get("city")
                self.units   = data.get("units")
                self.style   = data.get("style", "casual")
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        payload = {
            "api_key": self.api_key,
            "city":    self.city,
            "units":   self.units,
            "style":   self.style,
        }
        CONFIG_FILE.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )