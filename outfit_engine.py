"""
outfit_engine.py — Rule-based outfit recommendation engine.

Converts a WeatherData snapshot into a structured outfit suggestion
based on temperature bands, rain probability, wind, UV, and style preference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from weather_client import WeatherData


# ── Temperature bands (°C) ────────────────────────────────────────────────────

FREEZING   = 0
VERY_COLD  = 5
COLD       = 10
COOL       = 15
MILD       = 20
WARM       = 25
HOT        = 30
SCORCHING  = 35

# Rain thresholds
RAIN_LOW  = 30   # %
RAIN_MED  = 60   # %

# Wind thresholds (km/h)
WIND_BREEZY = 25
WIND_WINDY  = 45

# UV thresholds
UV_MOD  = 3
UV_HIGH = 6
UV_VERY = 8


@dataclass
class OutfitPlan:
    tops:        list[str] = field(default_factory=list)
    bottoms:     list[str] = field(default_factory=list)
    outerwear:   list[str] = field(default_factory=list)
    footwear:    list[str] = field(default_factory=list)
    accessories: list[str] = field(default_factory=list)
    tips:        list[str] = field(default_factory=list)
    vibe:        str       = ""

    def to_dict(self) -> dict:
        return {
            "tops":        self.tops,
            "bottoms":     self.bottoms,
            "outerwear":   self.outerwear,
            "footwear":    self.footwear,
            "accessories": self.accessories,
            "tips":        self.tips,
            "vibe":        self.vibe,
        }


class OutfitEngine:
    """
    Generates outfit recommendations from a WeatherData object.

    Style modes: casual | business | sport | formal
    Each method selects items appropriate to the style while
    the base temperature / rain / wind / UV logic applies universally.
    """

    def __init__(self, style: str = "casual"):
        valid = {"casual", "business", "sport", "formal"}
        if style not in valid:
            raise ValueError(f"style must be one of {valid}, got {style!r}")
        self.style = style

    def recommend(self, data: WeatherData) -> dict:
        plan = OutfitPlan()
        t    = data.temp_c

        self._pick_tops(plan, t)
        self._pick_bottoms(plan, t)
        self._pick_outerwear(plan, t, data.wind_kph, data.rain_probability)
        self._pick_footwear(plan, t, data.rain_probability)
        self._pick_accessories(plan, t, data.rain_probability,
                                data.wind_kph, data.uv_index)
        self._add_tips(plan, data)
        self._set_vibe(plan, data)

        return plan.to_dict()

    # ── tops ─────────────────────────────────────────────────────────────────

    def _pick_tops(self, plan: OutfitPlan, t: float):
        s = self.style

        if t <= FREEZING:
            plan.tops = {
                "casual":   ["thermal base layer", "heavy wool sweater"],
                "business": ["thermal undershirt", "thick dress shirt", "wool sweater vest"],
                "sport":    ["thermal compression top", "fleece mid-layer"],
                "formal":   ["dress shirt", "wool waistcoat"],
            }[s]

        elif t <= VERY_COLD:
            plan.tops = {
                "casual":   ["thermal undershirt", "chunky knit sweater"],
                "business": ["dress shirt", "merino wool sweater"],
                "sport":    ["long-sleeve base layer", "fleece pullover"],
                "formal":   ["dress shirt", "wool blazer"],
            }[s]

        elif t <= COLD:
            plan.tops = {
                "casual":   ["long-sleeve T-shirt", "hoodie"],
                "business": ["dress shirt", "light blazer"],
                "sport":    ["long-sleeve moisture-wicking top"],
                "formal":   ["dress shirt", "suit jacket"],
            }[s]

        elif t <= COOL:
            plan.tops = {
                "casual":   ["long-sleeve T-shirt"],
                "business": ["dress shirt"],
                "sport":    ["breathable long-sleeve top"],
                "formal":   ["dress shirt"],
            }[s]

        elif t <= MILD:
            plan.tops = {
                "casual":   ["T-shirt"],
                "business": ["light dress shirt"],
                "sport":    ["short-sleeve moisture-wicking top"],
                "formal":   ["dress shirt"],
            }[s]

        elif t <= WARM:
            plan.tops = {
                "casual":   ["light T-shirt"],
                "business": ["linen shirt"],
                "sport":    ["sleeveless athletic top"],
                "formal":   ["light dress shirt"],
            }[s]

        elif t <= HOT:
            plan.tops = {
                "casual":   ["breathable tank top"],
                "business": ["short-sleeve linen shirt"],
                "sport":    ["sleeveless performance top"],
                "formal":   ["lightweight dress shirt"],
            }[s]

        else:   # SCORCHING
            plan.tops = {
                "casual":   ["loose linen tank", "cotton sleeveless top"],
                "business": ["breathable linen shirt"],
                "sport":    ["ultra-light sleeveless top"],
                "formal":   ["lightweight short-sleeve dress shirt"],
            }[s]

    # ── bottoms ───────────────────────────────────────────────────────────────

    def _pick_bottoms(self, plan: OutfitPlan, t: float):
        s = self.style

        if t <= COLD:
            plan.bottoms = {
                "casual":   ["thermal leggings under jeans", "thick jeans"],
                "business": ["wool trousers"],
                "sport":    ["thermal running tights"],
                "formal":   ["wool dress trousers"],
            }[s]

        elif t <= COOL:
            plan.bottoms = {
                "casual":   ["jeans"],
                "business": ["chinos"],
                "sport":    ["running tights"],
                "formal":   ["dress trousers"],
            }[s]

        elif t <= MILD:
            plan.bottoms = {
                "casual":   ["jeans or chinos"],
                "business": ["chinos"],
                "sport":    ["lightweight joggers"],
                "formal":   ["dress trousers"],
            }[s]

        elif t <= WARM:
            plan.bottoms = {
                "casual":   ["light chinos"],
                "business": ["linen trousers"],
                "sport":    ["shorts"],
                "formal":   ["light dress trousers"],
            }[s]

        else:
            plan.bottoms = {
                "casual":   ["shorts"],
                "business": ["linen shorts or linen trousers"],
                "sport":    ["running shorts"],
                "formal":   ["lightweight linen trousers"],
            }[s]

    # ── outerwear ─────────────────────────────────────────────────────────────

    def _pick_outerwear(self, plan: OutfitPlan, t: float,
                         wind_kph: float, rain_pct: int):
        s = self.style
        windy  = wind_kph >= WIND_BREEZY
        rainy  = rain_pct >= RAIN_LOW
        pouring = rain_pct >= RAIN_MED

        if t <= FREEZING:
            plan.outerwear = {
                "casual":   ["heavy down parka"],
                "business": ["heavy wool overcoat"],
                "sport":    ["insulated running jacket"],
                "formal":   ["heavy wool topcoat"],
            }[s]

        elif t <= VERY_COLD:
            plan.outerwear = {
                "casual":   ["down jacket"],
                "business": ["wool overcoat"],
                "sport":    ["insulated windproof jacket"],
                "formal":   ["wool overcoat"],
            }[s]

        elif t <= COLD:
            coat = {
                "casual":   "denim jacket or light bomber",
                "business": "smart wool blazer",
                "sport":    "light windbreaker",
                "formal":   "sport coat",
            }[s]
            plan.outerwear = [coat]

        elif t <= COOL:
            plan.outerwear = [{
                "casual":   "light cardigan or denim jacket",
                "business": "blazer",
                "sport":    "zip-up hoodie",
                "formal":   "blazer",
            }[s]]

        elif t <= MILD:
            if rainy or windy:
                plan.outerwear = ["light layer in your bag"]
            # else no outerwear needed

        # No outerwear above MILD unless rain/wind

        # Rain overrides
        if rainy and t > VERY_COLD:
            if pouring:
                plan.outerwear = [x for x in plan.outerwear
                                   if "rain" not in x.lower()]
                plan.outerwear.insert(0, "waterproof rain jacket")
            else:
                plan.outerwear.append("packable rain jacket")

        elif windy and t > COOL:
            plan.outerwear.append("light windbreaker")

        # Deduplicate while preserving order
        seen = set()
        plan.outerwear = [
            x for x in plan.outerwear
            if not (x in seen or seen.add(x))  # type: ignore[func-returns-value]
        ]

    # ── footwear ──────────────────────────────────────────────────────────────

    def _pick_footwear(self, plan: OutfitPlan, t: float, rain_pct: int):
        s    = self.style
        rainy = rain_pct >= RAIN_LOW

        if t <= COLD:
            base = {
                "casual":   "insulated boots",
                "business": "waterproof dress boots",
                "sport":    "trail running shoes + wool socks",
                "formal":   "leather dress boots",
            }[s]
        elif t <= COOL:
            base = {
                "casual":   "ankle boots or sneakers",
                "business": "leather loafers or oxfords",
                "sport":    "running shoes",
                "formal":   "leather oxfords",
            }[s]
        elif t <= WARM:
            base = {
                "casual":   "sneakers or loafers",
                "business": "leather loafers",
                "sport":    "lightweight trainers",
                "formal":   "dress shoes",
            }[s]
        else:
            base = {
                "casual":   "sandals or breathable sneakers",
                "business": "open leather loafers",
                "sport":    "lightweight trail shoes",
                "formal":   "leather loafers",
            }[s]

        plan.footwear = [base]

        if rainy and t > COLD:
            plan.footwear.append("waterproof shoe covers or swap to waterproof shoes")

    # ── accessories ───────────────────────────────────────────────────────────

    def _pick_accessories(self, plan: OutfitPlan, t: float,
                           rain_pct: int, wind_kph: float,
                           uv_index: Optional[float]):
        acc = []

        # Cold-weather head/neck
        if t <= VERY_COLD:
            acc += ["wool beanie", "scarf", "gloves"]
        elif t <= COLD:
            acc += ["light beanie or ear warmers"]
        elif t <= COOL and wind_kph >= WIND_BREEZY:
            acc.append("light scarf")

        # Rain
        if rain_pct >= RAIN_LOW:
            acc.append("compact umbrella")

        # UV / sun
        uv = uv_index or 0
        if uv >= UV_HIGH:
            acc += ["sunglasses", "SPF 50 sunscreen", "wide-brim hat"]
        elif uv >= UV_MOD:
            acc += ["sunglasses", "sunscreen SPF 30+"]
        elif t >= HOT:
            acc.append("sunglasses")

        # Wind
        if wind_kph >= WIND_WINDY:
            if "wool beanie" not in acc and "light beanie or ear warmers" not in acc:
                acc.append("fitted hat or cap to keep hair out of face")

        plan.accessories = acc

    # ── tips ──────────────────────────────────────────────────────────────────

    def _add_tips(self, plan: OutfitPlan, data: WeatherData):
        tips = []
        t    = data.temp_c

        if data.rain_probability >= RAIN_MED:
            tips.append(
                f"High rain chance ({data.rain_probability}%) — "
                "keep a dry change of socks in your bag."
            )
        elif data.rain_probability >= RAIN_LOW:
            tips.append(
                f"Some rain possible ({data.rain_probability}%) — "
                "a packable jacket is your best friend."
            )

        if data.wind_kph >= WIND_WINDY:
            tips.append(
                f"Winds at {data.wind_kph:.0f} km/h — secure loose items "
                "and avoid wide-brim hats without a chin strap."
            )

        if data.humidity > 80 and t >= WARM:
            tips.append(
                "High humidity — favour moisture-wicking or linen fabrics "
                "to stay comfortable."
            )

        if data.uv_index is not None and data.uv_index >= UV_VERY:
            tips.append(
                f"UV index {data.uv_index:.0f} is very high. "
                "Reapply sunscreen every 2 hours."
            )

        feels_delta = t - data.feels_like_c
        if feels_delta >= 4:
            tips.append(
                f"Feels {feels_delta:.0f}°C colder than actual temp — "
                "dress one layer warmer than you think."
            )
        elif feels_delta <= -3:
            tips.append(
                f"Feels {abs(feels_delta):.0f}°C warmer than actual — "
                "lighter layers will keep you comfortable."
            )

        plan.tips = tips

    # ── vibe ─────────────────────────────────────────────────────────────────

    def _set_vibe(self, plan: OutfitPlan, data: WeatherData):
        t = data.temp_c
        c = data.condition

        if c == "Snow":
            plan.vibe = "Cosy winter wonderland — bundle up and enjoy it."
        elif c in ("Rain", "Drizzle", "Thunderstorm"):
            plan.vibe = "Rainy-day ready — pragmatic chic."
        elif t >= HOT:
            plan.vibe = "Sun-soaked and effortless — minimal is maximal."
        elif t >= WARM:
            plan.vibe = "Golden hour energy — light, breezy, confident."
        elif t >= MILD:
            plan.vibe = "Classic and composed — the perfect weather to look good."
        elif t >= COOL:
            plan.vibe = "Layered and intentional — autumn sophistication."
        elif t >= COLD:
            plan.vibe = "Sharp and bundled — cold never looked so put together."
        else:
            plan.vibe = "Arctic explorer mode — warmth is non-negotiable."