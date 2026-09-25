"""
Disease advisory service (Phase 1 rename + honesty pass).

Version 1 was named ``grok_service.py`` although it never called any LLM or API -
it produced template strings from the predicted label (PROJECT_AUDIT.md §9 B6,
§12). The module is renamed to reflect what it actually does. The original
function ``get_cure_for_disease`` is still exported with the same signature so
existing callers keep working.

Honesty rules applied here
    * the advisory text is generated from a **project-authored template**, not
      from a cited agronomic source - every output carries ``source`` so the
      paper cannot imply it is authoritative;
    * knowledge-grounded advisory arrives with the RAG knowledge base (Phase 5);
      this module is the documented fallback path.
"""
from __future__ import annotations

from typing import Any, Dict, List

SOURCE = "project_authored_general_guidance"
METHOD = "template_generation"

# Generic, non-authoritative guidance keyed by disease keyword.
GENERIC_GUIDANCE: List[tuple[tuple[str, ...], Dict[str, str]]] = [
    (
        ("blight",),
        {
            "symptom": "Dark, water-soaked lesions that enlarge rapidly; leaves may collapse.",
            "spread": "Wind-blown spores and splashing water; spreads fast in humid weather.",
            "management": "Remove and destroy affected foliage, avoid overhead irrigation, keep foliage dry.",
        },
    ),
    (
        ("rust",),
        {
            "symptom": "Orange or brown powdery pustules on the underside of leaves.",
            "spread": "Wind-dispersed spores; cool, moist conditions favour outbreaks.",
            "management": "Remove infected leaves, improve airflow, avoid excess nitrogen.",
        },
    ),
    (
        ("mildew",),
        {
            "symptom": "White to grey powdery patches on leaves and stems.",
            "spread": "Airborne spores; high humidity with moderate temperature.",
            "management": "Increase spacing and airflow, prune dense canopy, remove infected leaves.",
        },
    ),
    (
        ("rot",),
        {
            "symptom": "Dark lesions, softening or decay of fruit, stem or roots.",
            "spread": "Soil-borne and splash-dispersed; worsened by waterlogging.",
            "management": "Improve drainage, remove affected material, avoid injuring plants.",
        },
    ),
    (
        ("spot",),
        {
            "symptom": "Circular spots with dark margins, often with a lighter centre.",
            "spread": "Splashing water and contaminated tools or seed.",
            "management": "Sanitise tools, remove affected leaves, rotate crops.",
        },
    ),
]

FALLBACK_GUIDANCE = {
    "symptom": "Visual abnormality detected on the leaf surface.",
    "spread": "Not analysed - no reliable information available for this class.",
    "management": "Isolate the plant, monitor daily and consult the local agricultural extension office.",
}


def disease_profile(label: str) -> Dict[str, Any]:
    """Structured view of a predicted class for the UI/paper."""
    lowered = (label or "").lower()
    healthy = "healthy" in lowered
    guidance = FALLBACK_GUIDANCE
    for keywords, info in GENERIC_GUIDANCE:
        if any(key in lowered for key in keywords):
            guidance = info
            break
    return {
        "label": label,
        "is_healthy": healthy,
        "guidance": guidance,
        "source": SOURCE,
        "method": METHOD,
    }


def get_cure_for_disease(disease_name: str, crop_type: str, location: str) -> List[Dict[str, Any]]:
    """
    Return 3 advisory steps for a predicted class.

    Same contract as Version 1 (list of {step, action, details}) plus a
    ``source`` field on every step so the UI/paper can label it honestly.
    """
    label = str(disease_name or "Unknown")
    profile = disease_profile(label)
    display = label.replace("___", " - ").replace("_", " ").strip()
    crop = str(crop_type or "the crop").strip() or "the crop"

    if profile["is_healthy"]:
        return [
            {
                "step": 1,
                "action": "Maintain care",
                "details": f"The image matches a healthy class for {crop}. Continue the standard watering and nutrition schedule.",
                "source": SOURCE,
            },
            {
                "step": 2,
                "action": "Preventive monitoring",
                "details": "Inspect leaves and stems weekly for early signs of pests or disease.",
                "source": SOURCE,
            },
            {
                "step": 3,
                "action": "Balanced nutrition",
                "details": "Keep to the recommended fertilizer schedule to maintain plant vigour.",
                "source": SOURCE,
            },
        ]

    guidance = profile["guidance"]
    return [
        {
            "step": 1,
            "action": "Isolate and prune",
            "details": (
                f"Detected condition: {display}. {guidance['symptom']} "
                "Remove affected leaves with sterilised tools and dispose of them away from the field."
            ),
            "source": SOURCE,
        },
        {
            "step": 2,
            "action": "Reduce spread",
            "details": f"{guidance['spread']} Avoid overhead watering and avoid working in wet foliage.",
            "source": SOURCE,
        },
        {
            "step": 3,
            "action": "Management options",
            "details": (
                f"{guidance['management']} Follow the label instructions of any approved product, and confirm "
                f"locally approved treatments for {location or 'your region'} with the agricultural extension office."
            ),
            "source": SOURCE,
        },
    ]


def default_cure() -> List[Dict[str, Any]]:
    """Fallback advisory used when no prediction is available."""
    return [
        {"step": 1, "action": "Remove infected parts", "details": "Cut off affected leaves using sterilised tools.", "source": SOURCE},
        {"step": 2, "action": "Isolate the plant", "details": "Separate the plant to limit spread and monitor daily.", "source": SOURCE},
        {"step": 3, "action": "Seek local advice", "details": "Consult the nearest agricultural extension office for approved treatment.", "source": SOURCE},
    ]

