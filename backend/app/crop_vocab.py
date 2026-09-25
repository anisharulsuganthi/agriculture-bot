"""
Canonical crop vocabulary (Phase 1).

Version 1 stored crop names inconsistently ("Tomato", "tomato", "potato"),
which split analytics buckets and silently produced Tomato advice for other
crops (see PROJECT_AUDIT.md §11 D2 / §9 B11). Every write path now passes
through :func:`normalize_crop_type`.
"""
from __future__ import annotations

from typing import Dict, List

# canonical name -> accepted aliases (compared case-insensitively, underscores
# and hyphens treated as spaces)
_ALIASES: Dict[str, List[str]] = {
    "Tomato": ["tomato", "tomatoes", "thakkali", "tomato plant"],
    "Brinjal": ["brinjal", "eggplant", "aubergine", "kathiri"],
    "Corn": ["corn", "maize", "makka cholam", "sweet corn"],
    "Potato": ["potato", "potatoes", "urulaikizhangu", "aloo"],
    "Onion": ["onion", "onions", "vengayam", "ulli"],
    "Chilli": ["chilli", "chili", "chillies", "mirchi", "milagai"],
    "Banana": ["banana", "bananas", "vazhai"],
    "Groundnut": ["groundnut", "peanut", "peanuts", "verkadalai"],
    "Sugarcane": ["sugarcane", "sugar cane", "karumbu"],
    "Cotton": ["cotton", "paruthi"],
    "Paddy": ["paddy", "rice", "nel"],
    "Wheat": ["wheat", "godhumai"],
    "Millet": ["millet", "ragi", "finger millet", "kambu"],
    "Turmeric": ["turmeric", "manjal"],
    "Ginger": ["ginger", "inji"],
    "Mango": ["mango", "manga"],
    "Grapes": ["grape", "grapes", "grapes plant"],
    "Apple": ["apple", "apples"],
    "Peach": ["peach", "peaches"],
    "Cherry": ["cherry", "cherries"],
    "Strawberry": ["strawberry", "strawberries"],
    "Blueberry": ["blueberry", "blueberries"],
    "Raspberry": ["raspberry", "raspberries"],
    "Soybean": ["soybean", "soya", "soy"],
    "Pepper": ["pepper", "bell pepper", "capsicum", "kudai milagai"],
    "Squash": ["squash", "pumpkin", "poosanikai"],
    "Orange": ["orange", "oranges", "citrus"],
    "Potato Plant": ["potato plant"],
}

_SUPPORTED: List[str] = sorted(_ALIASES.keys())
_LOOKUP: Dict[str, str] = {}
for _canonical, _names in _ALIASES.items():
    _LOOKUP[_canonical.lower()] = _canonical
    for _alias in _names:
        _LOOKUP[_alias.lower()] = _canonical


def _clean(value: str) -> str:
    return " ".join(str(value).strip().replace("_", " ").replace("-", " ").lower().split())


def normalize_crop_type(value: str | None) -> str:
    """
    Return the canonical crop name.

    Unknown values are returned title-cased rather than silently remapped, so a
    genuinely new crop is visible instead of being answered with wrong advice.
    """
    if value is None:
        return "Unknown"
    cleaned = _clean(value)
    if not cleaned:
        return "Unknown"
    return _LOOKUP.get(cleaned, cleaned.title())


def is_known_crop(value: str | None) -> bool:
    return _clean(value or "") in _LOOKUP


def supported_crops() -> List[str]:
    """Canonical crops that have documented agronomic requirements."""
    return ["Tomato", "Brinjal", "Corn", "Potato", "Onion", "Chilli", "Banana", "Groundnut", "Sugarcane", "Cotton", "Paddy", "Millet"]


def canonical_crops() -> List[str]:
    return list(_SUPPORTED)
