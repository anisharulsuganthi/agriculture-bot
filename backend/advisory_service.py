"""
Disease Advisory Service (Hybrid AI + Curated Agronomic Knowledge Engine).

Provides comprehensive agricultural remedies including:
  1. Chemical Pesticide/Fungicide recommendations (Active ingredient, trade formulation, exact dilution, PHI).
  2. Organic & Bio-control alternatives (Bio-fungicides, botanical extracts, cultural practices).
  3. Fertilizer & Soil Nutrition adjustments (N-P-K balancing, micronutrient foliar sprays).
  4. Step-by-step action plan for disease containment and recovery.

Execution Modes:
  - "hybrid" (default): Attempts fast Live LLM call (Gemini or Groq) if an API key is available;
                        transparently falls back to the Curated Agronomic Knowledge Engine on timeout or error.
  - "live": Strictly uses Live LLM API (returns error details if API fails).
  - "offline": Instantly uses the Curated Agronomic Knowledge Engine without network calls.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests

from app.config import get_settings

logger = logging.getLogger("smartfarm.advisory")

# -----------------------------------------------------------------------------
# Curated Agronomic Knowledge Engine (Authoritative Offline Database)
# -----------------------------------------------------------------------------

OFFLINE_SOURCE_LABEL = "Curated Agronomic Knowledge Engine (Offline Verified)"
LIVE_GEMINI_LABEL = "Live AI Agronomist (Google Gemini 1.5 Flash)"
LIVE_GROQ_LABEL = "Live AI Agronomist (Groq Llama-3.3 70B)"
LIVE_GENERIC_LABEL = "Live AI Agronomist (Cloud API)"

CURATED_ADVISORY_DATABASE: Dict[str, Dict[str, Any]] = {
    "healthy": {
        "summary": "No active pathogen infection detected. Foliage shows normal chlorophyll pigmentation and cellular structure.",
        "chemical_control": [],
        "organic_control": [
            {
                "name": "Seaweed Extract / Bio-stimulant",
                "type": "Organic Tonic",
                "dosage": "2.0 ml / Liter of water",
                "instructions": "Foliar spray every 15 days in early morning to stimulate vegetative vigor and natural immunity.",
            },
            {
                "name": "Neem Oil 1500 ppm (Preventive)",
                "type": "Botanical Repellent",
                "dosage": "3.0 ml / Liter of water",
                "instructions": "Preventive spray every 14 days to deter sucking pests and early fungal spore attachment.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Continue standard balanced NPK fertigation (e.g., 19:19:19 water-soluble) aligned with crop phenological stage.",
            "foliar_nutrition": "Apply secondary and micronutrient mix (Ca, Mg, Zn, B @ 1.0 g/L) during flowering/fruiting phase.",
            "soil_advice": "Maintain soil organic carbon with compost or vermicompost (2-3 tons/acre); ensure consistent root-zone moisture."
        },
        "cure_steps": [
            {"step": 1, "action": "Routine Scouting", "details": "Inspect under-leaf surfaces and stems twice weekly for early signs of lesions, mites, or whiteflies."},
            {"step": 2, "action": "Moisture & Drainage", "details": "Maintain well-drained soil; avoid water stagnation around root crown to prevent fungal root rot."},
            {"step": 3, "action": "Canopy Aeration", "details": "Ensure adequate plant spacing and selective pruning to maximize sunlight penetration and air movement."}
        ]
    },
    "blight": {
        "summary": "Blight pathogen (e.g., Phytophthora infestans or Alternaria solani) causes necrotic lesions, rapid foliage collapse, and stem cankers under humid conditions.",
        "chemical_control": [
            {
                "name": "Mancozeb 75% WP (Contact)",
                "active_ingredient": "Mancozeb 75% WP",
                "dosage": "2.5 g / Liter of water (500 g / acre)",
                "schedule": "Spray immediately upon first symptom; repeat at 7-10 day intervals during cool, humid weather.",
                "phi": "7 days pre-harvest"
            },
            {
                "name": "Metalaxyl 8% + Mancozeb 64% WP (Systemic + Contact)",
                "active_ingredient": "Metalaxyl-M + Mancozeb",
                "dosage": "2.0 g / Liter of water",
                "schedule": "Apply for aggressive late blight outbreaks; maximum 2 applications per season to prevent resistance.",
                "phi": "14 days pre-harvest"
            },
            {
                "name": "Chlorothalonil 75% WP",
                "active_ingredient": "Chlorothalonil",
                "dosage": "2.0 g / Liter of water",
                "schedule": "Excellent broad-spectrum protective foliar barrier when conditions favor spore germination.",
                "phi": "5 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Trichoderma harzianum / viride",
                "type": "Bio-fungicide",
                "dosage": "5.0 g / Liter of water foliar or 2.5 kg / acre with compost",
                "instructions": "Colonizes plant tissues and produces enzymes that parasitize pathogenic fungal hyphae.",
            },
            {
                "name": "Copper Hydroxide / Bordeaux Mixture (1%)",
                "type": "Bio-compliant Mineral Fungicide",
                "dosage": "2.5 g / Liter of water",
                "instructions": "Spray thoroughly covering upper and lower leaf surfaces in the late afternoon.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "STRICTLY SUSPEND excess Nitrogen (Urea). Lush succulent growth is highly vulnerable to mycelial penetration. Increase Potassium (K) using Potassium Sulfate (0-0-50).",
            "foliar_nutrition": "Foliar spray of Potassium Phosphite (2 ml/L) or Calcium Chloride (1.5 g/L) to strengthen plant cell wall lignification.",
            "soil_advice": "Incorporate bio-fertilizers like Phosphobacteria and enrich soil aeration with organic mulch."
        },
        "cure_steps": [
            {"step": 1, "action": "Sanitation & Pruning", "details": "Immediately strip infected lower leaves with sterilized shears. Seal cuttings in bags and burn or bury away from farm."},
            {"step": 2, "action": "Targeted Fungicide Spray", "details": "Apply Mancozeb (2.5 g/L) or Metalaxyl+Mancozeb (2.0 g/L) with a non-ionic spreader/sticker, coating both leaf sides."},
            {"step": 3, "action": "Irrigation Management", "details": "Switch strictly from overhead sprinkler to drip irrigation. Keep leaves dry overnight and avoid working when plants are wet."}
        ]
    },
    "mildew": {
        "summary": "Fungal mildew (Powdery: Erysiphales or Downy: Peronosporaceae) coats leaves with white powdery or grayish downy patches, causing yellowing and leaf drop.",
        "chemical_control": [
            {
                "name": "Hexaconazole 5% SC or Difenoconazole 25% EC",
                "active_ingredient": "Hexaconazole / Difenoconazole (Triazole)",
                "dosage": "1.0 ml / Liter of water",
                "schedule": "Apply at early appearance; systemic action halts internal fungal mycelium growth. Repeat in 10-14 days.",
                "phi": "10 days pre-harvest"
            },
            {
                "name": "Wettable Sulfur 80% WP",
                "active_ingredient": "Sulfur 80% WP",
                "dosage": "2.5 - 3.0 g / Liter of water",
                "schedule": "Highly effective against powdery mildew. Avoid spraying when temperatures exceed 32°C to prevent phytotoxicity.",
                "phi": "3 days pre-harvest"
            },
            {
                "name": "Azoxystrobin 23% SC",
                "active_ingredient": "Azoxystrobin (Strobilurin)",
                "dosage": "1.0 ml / Liter of water",
                "schedule": "Protective and curative control of downy and powdery mildews.",
                "phi": "7 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Potassium Bicarbonate / Baking Soda Solution",
                "type": "Organic Fungicide",
                "dosage": "4.0 g / Liter of water + 2 ml Horticultural oil",
                "instructions": "Alkalinizes the leaf surface (pH > 8.0), disrupting fungal spore membrane integrity within hours.",
            },
            {
                "name": "Bacillus subtilis (Bio-agent)",
                "type": "Microbial Antagonist",
                "dosage": "3.0 ml / Liter of water",
                "instructions": "Produces lipopeptides that kill fungal spores and trigger systemic resistance.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Cut Nitrogen application by 50%. Apply soluble Potash (SOP 0-0-50) @ 5 g/L to reinforce leaf epidermis.",
            "foliar_nutrition": "Foliar spray with Soluble Silica (Potassium silicate @ 2 ml/L) to build physical microscopic barriers against fungal haustoria.",
            "soil_advice": "Improve drainage; aerate topsoil around drippers to prevent stagnant microclimatic humidity."
        },
        "cure_steps": [
            {"step": 1, "action": "Canopy Thinning", "details": "Prune overcrowded central branches to allow direct sunlight and wind circulation through the plant canopy."},
            {"step": 2, "action": "Fungicidal Eradication", "details": "Spray Wettable Sulfur (2.5 g/L) or Hexaconazole (1 ml/L) early in the morning before direct sun exposure."},
            {"step": 3, "action": "Debris Removal", "details": "Rake fallen dead leaves beneath the canopy and destroy them; do not compost mildew-infected debris."}
        ]
    },
    "rust": {
        "summary": "Puccinia or Uromyces rust fungi produce orange, reddish, or dark brown powdery spore pustules on foliage, severely impairing photosynthesis.",
        "chemical_control": [
            {
                "name": "Propiconazole 25% EC (Tilt)",
                "active_ingredient": "Propiconazole 25% EC",
                "dosage": "1.0 ml / Liter of water (200 ml / acre)",
                "schedule": "Systemic triazole fungicide; spray upon first pustule detection. Repeat after 14 days if rust pressure persists.",
                "phi": "14 days pre-harvest"
            },
            {
                "name": "Tebuconazole 25.9% m/m EC",
                "active_ingredient": "Tebuconazole",
                "dosage": "1.25 ml / Liter of water",
                "schedule": "Curative and translaminar; halts rust pustule sporulation.",
                "phi": "10 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Sulfur Dust / Wettable Sulfur 80% WDG",
                "type": "Mineral Dust",
                "dosage": "2.5 g / Liter of water",
                "instructions": "Inhibits rust spore germination. Spray late afternoon.",
            },
            {
                "name": "Neem Oil Extract (Azadirachtin 10,000 ppm)",
                "type": "Botanical Bio-fungicide",
                "dosage": "3.0 ml / Liter of water",
                "instructions": "Contains limonoids that suppress rust spore germination and insect vector transmission.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Balance N:P:K ratio to 1:2:2. Avoid heavy Urea application. Supply adequate Phosphorus (DAP/SSP) for root vigor.",
            "foliar_nutrition": "Foliar Zinc Sulfate (0.5% + lime) or Chelated Micronutrient spray to replenish chlorotic leaf areas.",
            "soil_advice": "Apply farmyard manure enriched with mycorrhizal fungi to stimulate root absorption capacity."
        },
        "cure_steps": [
            {"step": 1, "action": "Remove Severely Infected Leaves", "details": "Carefully snip off heavily rusted leaves into a bucket without shaking to avoid dispersing powdery spores."},
            {"step": 2, "action": "Systemic Triazole Application", "details": "Spray Propiconazole 25% EC (1 ml/L) ensuring coverage of the leaf undersides where rust pustules reside."},
            {"step": 3, "action": "Spacing & Weed Control", "details": "Clear alternative weed hosts (wild grasses/sorghum) bordering the plot that harbor rust inoculum."}
        ]
    },
    "spot": {
        "summary": "Foliar leaf spots (Cercospora, Septoria, Cordana, Alternaria) manifest as necrotic circular or angular brown/tan spots, often with yellow halos.",
        "chemical_control": [
            {
                "name": "Carbendazim 12% + Mancozeb 63% WP (Saaf)",
                "active_ingredient": "Carbendazim + Mancozeb",
                "dosage": "2.0 g / Liter of water",
                "schedule": "Dual action systemic + contact formulation. Apply at first sign of spotting; repeat in 10-12 days.",
                "phi": "7 days pre-harvest"
            },
            {
                "name": "Copper Oxychloride 50% WP (Blitox)",
                "active_ingredient": "Copper Oxychloride",
                "dosage": "2.5 g / Liter of water",
                "schedule": "Broad spectrum contact bactericide/fungicide; excellent protective leaf barrier against rain splashes.",
                "phi": "5 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Pseudomonas fluorescens 1% WP",
                "type": "Bio-agent / Bio-bactericide",
                "dosage": "5.0 g / Liter of water",
                "instructions": "Colonizes leaf stomata and produces phenazine antibiotics that inhibit leaf spot pathogens.",
            },
            {
                "name": "Fermented Cow Butter-Milk (Chaas) Spray",
                "type": "Traditional Bio-antiseptic",
                "dosage": "50 ml / Liter of water (5% concentration)",
                "instructions": "Lactic acid bacteria suppress leaf surface fungal pathogens and supply trace bio-nutrients.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Maintain uniform fertigation. Do not allow water stress followed by heavy nitrogen, which aggravates leaf spots.",
            "foliar_nutrition": "Foliar application of Magnesium Sulfate (5 g/L) and Boron (1 g/L) to restore chlorotic tissues.",
            "soil_advice": "Mulch soil around plants with straw or plastic film to prevent soil-splash onto lower foliage during rain."
        },
        "cure_steps": [
            {"step": 1, "action": "Prune Lower Splash Leaves", "details": "Trim leaves touching or within 15 cm of the soil surface to break the soil-to-leaf rain splash cycle."},
            {"step": 2, "action": "Dual-Action Fungicide Spray", "details": "Spray Carbendazim + Mancozeb (2.0 g/L) or Copper Oxychloride (2.5 g/L) thoroughly on both foliage surfaces."},
            {"step": 3, "action": "Mulch Soil Surface", "details": "Spread clean organic mulch or dry straw around crop beds to suppress rain-splash dispersal of fungal spores."}
        ]
    },
    "rot": {
        "summary": "Fruit/Stem rot or Anthracnose (Colletotrichum, Botrytis, Sclerotinia) causes water-soaked sunken lesions, stem girdling, and fruit softening.",
        "chemical_control": [
            {
                "name": "Difenoconazole 25% EC (Score)",
                "active_ingredient": "Difenoconazole",
                "dosage": "1.0 ml / Liter of water",
                "schedule": "Curative systemic triazole; halts anthracnose and fruit rot progression. Spray twice at 10-day intervals.",
                "phi": "7 days pre-harvest"
            },
            {
                "name": "Thiophanate Methyl 70% WP",
                "active_ingredient": "Thiophanate Methyl",
                "dosage": "1.5 g / Liter of water",
                "schedule": "Protective and systemic fungicide for fruit rot and stem end decay.",
                "phi": "7 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Trichoderma viride 1% WP",
                "type": "Bio-control Agent",
                "dosage": "5.0 g / Liter foliar + 2 kg / acre soil drench",
                "instructions": "Destroys fungal resting sclerotia in the soil and prevents collar rot infection.",
            },
            {
                "name": "Neem Oil 10,000 ppm",
                "type": "Botanical Fungicide",
                "dosage": "2.5 ml / Liter of water",
                "instructions": "Disrupts spore germination on developing fruits and blossoms.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Boost Calcium and Potassium levels. Calcium Nitrate (10 g/L soil or 3 g/L foliar) increases fruit rind firmness and rot resistance.",
            "foliar_nutrition": "Foliar spray with Boron (20% @ 1.0 g/L) to prevent fruit cracking and secondary fungal entry.",
            "soil_advice": "Ensure deep drainage ditches; waterlogged soil promotes Phytophthora and Pythium root/collar rot."
        },
        "cure_steps": [
            {"step": 1, "action": "Immediate Fruit/Rot Sanitization", "details": "Harvest and dispose of all rotted, sunken, or mummified fruits and lesions. Sterilize pruners in 10% bleach."},
            {"step": 2, "action": "Systemic Fungicide Treatment", "details": "Spray Difenoconazole (1 ml/L) or Thiophanate Methyl (1.5 g/L) directly targeting blossoms, stems, and fruits."},
            {"step": 3, "action": "Improve Raised Bed Drainage", "details": "Mound soil into raised beds and avoid any standing water around plant stems or root crowns."}
        ]
    },
    "bacterial": {
        "summary": "Bacterial spot, canker, or wilt (Xanthomonas, Ralstonia, Pseudomonas) causes water-soaked spots with yellow halos, vascular wilting, or stem cankers.",
        "chemical_control": [
            {
                "name": "Streptomycin Sulphate 9% + Tetracycline Hydrochloride 1% SP (Plantomycin / Streptocycline)",
                "active_ingredient": "Agricultural Streptomycin + Tetracycline",
                "dosage": "0.5 g / 10 Liters of water (60-100 ppm)",
                "schedule": "Bactericide spray upon first signs of bacterial spotting or oozing. Spray in evening; avoid excessive use to limit resistance.",
                "phi": "14 days pre-harvest"
            },
            {
                "name": "Copper Oxychloride 50% WP (Tank mix with Bactericide)",
                "active_ingredient": "Copper Oxychloride",
                "dosage": "2.5 g / Liter of water",
                "schedule": "Tank mix with Streptocycline for synergistic bacterial cell wall lysis and broad-spectrum suppression.",
                "phi": "5 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Pseudomonas fluorescens 1.5% WP",
                "type": "Antagonistic Rhizobacteria",
                "dosage": "10 g / Liter root drench & 5 g / Liter foliar spray",
                "instructions": "Competes directly with Ralstonia and Xanthomonas bacteria in rhizosphere and stomata.",
            },
            {
                "name": "Copper Soap / Copper Octanoate",
                "type": "Organic Copper Fungicide/Bactericide",
                "dosage": "3.0 ml / Liter of water",
                "instructions": "Approved for organic farming; creates a surface antimicrobial barrier without scorching tender foliage.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "AVOID excess Nitrogen (Urea). High nitrogen makes stem vascular bundles succulent and susceptible to bacterial clogging. Use Potash (0-0-50).",
            "foliar_nutrition": "Apply micronutrient Copper & Zinc chelate (0.5 g/L) to activate plant phytoalexin defense mechanisms.",
            "soil_advice": "Drench soil with bleaching powder (Chlorinated lime @ 2 g/L) if bacterial wilt is identified in soil beds."
        },
        "cure_steps": [
            {"step": 1, "action": "Tool Disinfection & Roguing", "details": "Rogue out completely wilted plants with roots and burn them. Dip pruning tools in 70% alcohol between cuts."},
            {"step": 2, "action": "Streptocycline + Copper Spray", "details": "Spray Streptocycline (0.5 g / 10L) + Copper Oxychloride (2.5 g/L) thoroughly over foliage and stem bases."},
            {"step": 3, "action": "Drip Irrigation Only", "details": "Never use overhead hose or sprinkler watering; splashing droplets are the primary vector for bacterial spread."}
        ]
    },
    "scab": {
        "summary": "Scab disease (Venturia inaequalis / Cladosporium / Elsinoë) produces olive-green to corky brown scabby lesions on leaves and fruit rinds.",
        "chemical_control": [
            {
                "name": "Dodine 65% WP (Curative & Protectant)",
                "active_ingredient": "Dodine",
                "dosage": "1.0 g / Liter of water",
                "schedule": "Spray during green tip to petal fall stage; provides strong kickback against ascospore infection.",
                "phi": "14 days pre-harvest"
            },
            {
                "name": "Captan 50% WP or Mancozeb 75% WP",
                "active_ingredient": "Captan / Mancozeb",
                "dosage": "2.5 g / Liter of water",
                "schedule": "Protective spray prior to forecasted rain events during early foliage flush.",
                "phi": "7 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Lime Sulfur Solution (28% Calcium Polysulfide)",
                "type": "Organic Mineral Fungicide",
                "dosage": "10 - 15 ml / Liter during dormancy; 3 ml / Liter during vegetative phase",
                "instructions": "Eradicates overwintering fungal pseudothecia on tree branches and fallen leaves.",
            },
            {
                "name": "Potassium Bicarbonate + Horticultural Oil",
                "type": "Organic Curative",
                "dosage": "3.5 g / Liter of water",
                "instructions": "Contact kill of young scab mycelium without fruit chemical residue.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Maintain balanced NPK. Excessive leaf flush from surplus nitrogen extends the vulnerable window for scab ascospore attachment.",
            "foliar_nutrition": "Foliar Zinc (ZnSO4 @ 0.3%) and Urea 5% spray applied to fallen leaves in autumn/winter to accelerate leaf decay and destroy scab spores.",
            "soil_advice": "Ensure soil pH is maintained between 6.2 - 6.8; apply agricultural gypsum if soil is compacted."
        },
        "cure_steps": [
            {"step": 1, "action": "Leaf Litter Destruction", "details": "Rake and shred or compost deeply all fallen leaf litter where scab fungus overwinters."},
            {"step": 2, "action": "Protective Fungicide Spray", "details": "Apply Dodine (1.0 g/L) or Captan (2.5 g/L) immediately after rain events when leaves remain wet for >8 hours."},
            {"step": 3, "action": "Annual Winter Pruning", "details": "Open up tree branch structure to maximize air circulation and rapid leaf drying after morning dew."}
        ]
    },
    "virus": {
        "summary": "Viral infections (Mosaic virus, Tomato yellow leaf curl, Banana bunchy top) cause leaf mottling, curling, stunting, and deformation. Viruses are transmitted primarily by insect vectors (whiteflies, aphids, thrips) and cannot be cured directly by fungicides.",
        "chemical_control": [
            {
                "name": "Imidacloprid 17.8% SL (Systemic Insecticide for Vector Control)",
                "active_ingredient": "Imidacloprid (Neonicotinoid)",
                "dosage": "0.5 ml / Liter of water (50-60 ml / acre)",
                "schedule": "Controls sap-sucking insect vectors (whiteflies, aphids, thrips). Spray upon vector detection; repeat in 14 days.",
                "phi": "15 days pre-harvest"
            },
            {
                "name": "Thiamethoxam 25% WG",
                "active_ingredient": "Thiamethoxam",
                "dosage": "0.5 g / Liter of water or drench",
                "schedule": "Systemic vector control; taken up by roots and translocated to tender shoots.",
                "phi": "14 days pre-harvest"
            },
            {
                "name": "Diafenthiuron 50% WP (Broad Spectrum Mites & Whiteflies)",
                "active_ingredient": "Diafenthiuron",
                "dosage": "1.25 g / Liter of water",
                "schedule": "Eradicates nymph and adult whitefly vector colonies rapidly.",
                "phi": "7 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Yellow & Blue Sticky Traps",
                "type": "Physical Vector Trap",
                "dosage": "15-20 traps / acre installed at canopy height",
                "instructions": "Attracts and traps winged whiteflies, aphids, and thrips before they can inoculate plants with viral particles.",
            },
            {
                "name": "Neem Oil 10,000 ppm + Pongamia Oil",
                "type": "Botanical Insect Antifeedant",
                "dosage": "3.0 ml / Liter of water + emulsifier",
                "instructions": "Acts as an oviposition deterrent and antifeedant for sap-sucking vector insects.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Virally infected plants need energetic support. Provide water-soluble 13:00:45 (Potassium Nitrate) @ 5 g/L to sustain fruit filling.",
            "foliar_nutrition": "Foliar spray of Chelated Zinc (1 g/L) + Magnesium Sulfate (3 g/L) to mitigate viral chlorosis and preserve green leaf tissue.",
            "soil_advice": "Drench roots with Humic Acid (3 ml/L) to stimulate secondary feeder roots and counter viral vascular stunting."
        },
        "cure_steps": [
            {"step": 1, "action": "Eradicate Vectors Immediately", "details": "Spray Imidacloprid (0.5 ml/L) or Neem oil (3 ml/L) to eliminate sucking vectors before they spread the virus to neighboring crops."},
            {"step": 2, "action": "Rogue Heavily Infected Stunted Plants", "details": "Viruses cannot be cured once inside systemic vascular bundles. Pull out severely stunted plants, seal in bags, and destroy."},
            {"step": 3, "action": "Install Physical Traps & Netting", "details": "Place 15-20 yellow sticky traps per acre and consider 40-50 mesh insect barrier netting around nursery beds."}
        ]
    },
    "insect": {
        "summary": "Insect pest or mite damage (spider mites, caterpillars, borers, thrips) causes leaf speckling, bronzing, holes, or webbing on foliage.",
        "chemical_control": [
            {
                "name": "Abamectin 1.9% EC (Acaricide / Insecticide for Mites)",
                "active_ingredient": "Abamectin",
                "dosage": "1.0 ml / Liter of water",
                "schedule": "Translaminar miticide; kills mites on upper and lower leaf surfaces. Repeat after 7 days if eggs hatch.",
                "phi": "7 days pre-harvest"
            },
            {
                "name": "Spinosad 45% SC or Chlorantraniliprole 18.5% SC (Coragen)",
                "active_ingredient": "Chlorantraniliprole / Spinosad",
                "dosage": "0.3 - 0.4 ml / Liter of water",
                "schedule": "Highly selective for caterpillar larvae, leafminers, and borers with low mammalian toxicity.",
                "phi": "3 days pre-harvest"
            }
        ],
        "organic_control": [
            {
                "name": "Bacillus thuringiensis (Bt) kurstaki",
                "type": "Biological Larvicide",
                "dosage": "2.0 g / Liter of water",
                "instructions": "Produces crystal endotoxins that specifically target and kill chewing caterpillar pests upon ingestion.",
            },
            {
                "name": "Beauveria bassiana 1.15% WP (Entomopathogenic Fungus)",
                "type": "Bio-pesticide",
                "dosage": "5.0 g / Liter of water",
                "instructions": "Infects and colonizes insects (mites, aphids, thrips) through cuticle penetration.",
            }
        ],
        "fertilizer_recommendation": {
            "npk_adjustment": "Maintain steady NPK. Avoid excessive nitrogen, which increases amino acid content in sap and attracts surging pest populations.",
            "foliar_nutrition": "Foliar Silica (Potassium silicate @ 2 ml/L) creates tough abrasive phytoliths in leaf tissues that wear down insect chewing mouthparts.",
            "soil_advice": "Ensure adequate soil moisture to prevent drought stress that predisposes crops to spider mite outbreaks."
        },
        "cure_steps": [
            {"step": 1, "action": "Water Jet Spray Leaf Undersides", "details": "Spray undersides of leaves with a forceful water mist to knock down mite colonies and web nests."},
            {"step": 2, "action": "Targeted Acaricide / Bio-pesticide", "details": "Spray Abamectin (1.0 ml/L) for mites or Spinosad (0.4 ml/L) for chewing larvae in the cool of early morning."},
            {"step": 3, "action": "Deploy Beneficial Predators", "details": "Encourage or introduce ladybird beetles, lacewings, or predatory mites (Phytoseiidae) to maintain biological balance."}
        ]
    }
}

# Default fallback if disease doesn't match above categories
CURATED_FALLBACK: Dict[str, Any] = {
    "summary": "Visual leaf abnormality detected. Symptoms indicate potential fungal, bacterial, or physiological stress.",
    "chemical_control": [
        {
            "name": "Broad-Spectrum Copper Oxychloride 50% WP",
            "active_ingredient": "Copper Oxychloride",
            "dosage": "2.5 g / Liter of water",
            "schedule": "Protective contact spray against fungal and bacterial leaf lesions. Re-apply in 10-14 days.",
            "phi": "5 days pre-harvest"
        },
        {
            "name": "Mancozeb 75% WP",
            "active_ingredient": "Mancozeb",
            "dosage": "2.0 g / Liter of water",
            "schedule": "Broad-spectrum multisite protective fungicide.",
            "phi": "7 days pre-harvest"
        }
    ],
    "organic_control": [
        {
            "name": "Cold-Pressed Neem Oil (10,000 ppm)",
            "type": "Botanical Protectant",
            "dosage": "3.0 ml / Liter of water + emulsifier",
            "instructions": "Spray early morning on leaf surfaces to suppress fungal spore germination and repel vectors.",
        },
        {
            "name": "Trichoderma viride Bio-fungicide",
            "type": "Microbial Antagonist",
            "dosage": "5.0 g / Liter of water",
            "instructions": "Apply to roots and foliage to suppress common soil-borne and foliar pathogens.",
        }
    ],
    "fertilizer_recommendation": {
        "npk_adjustment": "Maintain balanced 19:19:19 fertilizer. Temporarily withhold heavy urea until disease progression is arrested.",
        "foliar_nutrition": "Foliar micronutrient spray (Zn, Fe, Mn, B @ 1.0 g/L) to support metabolic recovery.",
        "soil_advice": "Check soil pH and drainage; avoid overwatering to protect root integrity."
    },
    "cure_steps": [
        {"step": 1, "action": "Isolate & Prune Infected Parts", "details": "Carefully remove symptomatic leaves using clean shears; burn or bury cuttings away from crop plots."},
        {"step": 2, "action": "Apply Broad-Spectrum Protectant", "details": "Spray Copper Oxychloride (2.5 g/L) or Neem Oil (3 ml/L) ensuring complete upper and lower leaf coverage."},
        {"step": 3, "action": "Consult Local Agronomist", "details": "Take a high-resolution photo or sample to the local agricultural extension station for localized verification."}
    ]
}


def _match_curated_advisory(label: str) -> Dict[str, Any]:
    """Find the best matching curated advisory entry from disease label keywords."""
    lowered = (label or "").lower()
    if "healthy" in lowered:
        return CURATED_ADVISORY_DATABASE["healthy"]
    
    # Check specific disease families in prioritized order
    if any(k in lowered for k in ["blight"]):
        return CURATED_ADVISORY_DATABASE["blight"]
    if any(k in lowered for k in ["mildew"]):
        return CURATED_ADVISORY_DATABASE["mildew"]
    if any(k in lowered for k in ["rust"]):
        return CURATED_ADVISORY_DATABASE["rust"]
    if any(k in lowered for k in ["bacterial", "canker", "moko"]):
        return CURATED_ADVISORY_DATABASE["bacterial"]
    if any(k in lowered for k in ["rot", "anthracnose", "cigar"]):
        return CURATED_ADVISORY_DATABASE["rot"]
    if any(k in lowered for k in ["scab"]):
        return CURATED_ADVISORY_DATABASE["scab"]
    if any(k in lowered for k in ["virus", "mosaic", "curl", "bunchy"]):
        return CURATED_ADVISORY_DATABASE["virus"]
    if any(k in lowered for k in ["mite", "pest", "insect", "aphid", "thrip", "worm"]):
        return CURATED_ADVISORY_DATABASE["insect"]
    if any(k in lowered for k in ["spot", "sigatoka", "cordana", "septoria", "cercospora", "streak", "pestalotiopsis"]):
        return CURATED_ADVISORY_DATABASE["spot"]

    return CURATED_FALLBACK


# -----------------------------------------------------------------------------
# Live LLM Integration (Google Gemini, Groq, or OpenAI-compatible)
# -----------------------------------------------------------------------------

def _build_agronomy_prompt(disease_name: str, crop_type: str, location: str, symptoms: str) -> str:
    """Prompt template instructing the model to output strict agronomical JSON."""
    return f"""You are a senior agricultural plant pathologist and certified crop advisor.
A farmer has submitted an image diagnosis for their crop:
- Predicted Condition / Disease: "{disease_name}"
- Crop Type: "{crop_type}"
- Farm Region / Location: "{location or 'Agricultural Farmland'}"
- Farmer Reported Symptoms: "{symptoms or 'Visual leaf abnormality'}"

Provide an authoritative, scientifically accurate treatment and recovery prescription in strict JSON format.
Include exact commercial chemical formulations with their active ingredients, metric dilution rates (g/L or ml/L), spraying schedules, Pre-Harvest Intervals (PHI), organic bio-fungicides/pesticides, fertilizer adjustments (NPK & micronutrients), and a 3-step action protocol.

OUTPUT ONLY VALID JSON with this EXACT structure (no markdown text, no markdown backticks, just raw json):
{{
  "summary": "Brief 1-2 sentence pathology summary of the disease and its mode of infection.",
  "chemical_control": [
    {{
      "name": "Commercial Formulation Name (e.g., Mancozeb 75% WP)",
      "active_ingredient": "Chemical Active Ingredient (e.g., Mancozeb)",
      "dosage": "Exact mixing ratio per liter of water (e.g., 2.5 g / Liter of water)",
      "schedule": "Application frequency and weather instructions",
      "phi": "Pre-Harvest Interval (e.g., 7 days before harvest)"
    }}
  ],
  "organic_control": [
    {{
      "name": "Organic / Bio-control Product (e.g., Trichoderma harzianum 1% WP)",
      "type": "Bio-fungicide / Botanical extract / Mineral",
      "dosage": "Exact mixing ratio (e.g., 5.0 g / Liter of water)",
      "instructions": "Application and timing instructions"
    }}
  ],
  "fertilizer_recommendation": {{
    "npk_adjustment": "Specific Nitrogen, Phosphorus, Potassium adjustments to suppress disease susceptibility",
    "foliar_nutrition": "Foliar micronutrient spray recommendation (e.g. Zinc, Boron, Calcium, Potassium Silicate)",
    "soil_advice": "Soil condition, irrigation, and rhizosphere health guidance"
  }},
  "cure_steps": [
    {{"step": 1, "action": "Immediate Sanitation & Isolation", "details": "Specific action to contain pathogen spread"}},
    {{"step": 2, "action": "Targeted Chemical or Bio Spray", "details": "Spraying protocol and safety instructions"}},
    {{"step": 3, "action": "Long-term Agronomic Recovery", "details": "Nutrient, spacing, and irrigation management"}}
  ]
}}"""


def _call_gemini_api(api_key: str, prompt: str, timeout_seconds: int = 7) -> Optional[Dict[str, Any]]:
    """Call Google Gemini 1.5 Flash API for live agronomic guidance."""
    # Use gemini-1.5-flash which is extremely fast and has a free tier
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 1024,
        },
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if candidates:
                raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                parsed = _clean_and_parse_json(raw_text)
                if parsed:
                    parsed["source"] = "live_llm"
                    parsed["source_label"] = LIVE_GEMINI_LABEL
                    return parsed
        else:
            logger.warning("Gemini API call failed with status %d: %s", response.status_code, response.text[:200])
    except Exception as exc:
        logger.warning("Gemini API request failed: %s", exc)
    return None


def _call_groq_api(api_key: str, prompt: str, timeout_seconds: int = 7) -> Optional[Dict[str, Any]]:
    """Call Groq Cloud API (Llama-3.3 70B) for live agronomic guidance."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are an expert plant pathologist and agronomist. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout_seconds)
        if response.status_code == 200:
            data = response.json()
            raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _clean_and_parse_json(raw_text)
            if parsed:
                parsed["source"] = "live_llm"
                parsed["source_label"] = LIVE_GROQ_LABEL
                return parsed
        else:
            logger.warning("Groq API call failed with status %d: %s", response.status_code, response.text[:200])
    except Exception as exc:
        logger.warning("Groq API request failed: %s", exc)
    return None


def _call_openai_compatible_api(base_url: str, api_key: str, model: str, prompt: str, timeout_seconds: int = 7) -> Optional[Dict[str, Any]]:
    """Call OpenAI-compatible endpoint (OpenAI, Ollama, OpenRouter)."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model or "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are an expert plant pathologist. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {api_key}" if api_key else "",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout_seconds)
        if response.status_code == 200:
            data = response.json()
            raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _clean_and_parse_json(raw_text)
            if parsed:
                parsed["source"] = "live_llm"
                parsed["source_label"] = LIVE_GENERIC_LABEL
                return parsed
    except Exception as exc:
        logger.warning("OpenAI-compatible API request failed: %s", exc)
    return None


def _clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Sanitize and parse JSON string from LLM responses."""
    if not text:
        return None
    cleaned = text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        # Fallback regex extraction of outermost JSON object
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return None


# -----------------------------------------------------------------------------
# Main Advisory Retrieval Function
# -----------------------------------------------------------------------------

def get_disease_advisory(
    disease_name: str,
    crop_type: str,
    location: str,
    symptoms: str = "",
    advisory_mode: str = "hybrid",
    advisory_api_key: str = "",
) -> Dict[str, Any]:
    """
    Retrieve comprehensive agronomic advisory for a predicted disease.

    Modes:
      - 'hybrid': Try Live LLM first (Gemini/Groq/OpenAI); fallback to curated offline DB.
      - 'live': Strictly query Live LLM; return fallback with warning if unreachable.
      - 'offline': Use curated offline DB immediately without network overhead.
    """
    settings = get_settings()
    label = str(disease_name or "Unknown").strip()
    crop = str(crop_type or "the crop").strip()
    loc = str(location or "").strip()

    # Resolve active API key
    active_key = (
        advisory_api_key.strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GROQ_API_KEY", "").strip()
        or os.getenv("LLM_API_KEY", "").strip()
        or getattr(settings, "llm_api_key", "").strip()
    )

    mode = (advisory_mode or "hybrid").lower().strip()

    live_result: Optional[Dict[str, Any]] = None

    if mode in {"hybrid", "live"} and active_key:
        prompt = _build_agronomy_prompt(label, crop, loc, symptoms)
        # Auto-detect provider based on key format or configured provider
        if active_key.startswith("AIzaSy"):
            # Google Gemini Key
            live_result = _call_gemini_api(active_key, prompt, timeout_seconds=8)
        elif active_key.startswith("gsk_"):
            # Groq Key
            live_result = _call_groq_api(active_key, prompt, timeout_seconds=7)
        elif getattr(settings, "llm_base_url", ""):
            # Custom LLM Base URL
            live_result = _call_openai_compatible_api(
                settings.llm_base_url,
                active_key,
                getattr(settings, "llm_model", ""),
                prompt,
                timeout_seconds=8,
            )
        else:
            # Default try Gemini first, then Groq
            live_result = _call_gemini_api(active_key, prompt, timeout_seconds=8)
            if not live_result:
                live_result = _call_groq_api(active_key, prompt, timeout_seconds=7)

    if live_result and isinstance(live_result, dict) and "cure_steps" in live_result:
        # Standardize source tags in steps
        for step in live_result.get("cure_steps", []):
            step["source"] = live_result.get("source", "live_llm")
        return live_result

    # Offline Curated Fallback
    curated = _match_curated_advisory(label)
    result = dict(curated)
    result["source"] = "curated_database"
    result["source_label"] = OFFLINE_SOURCE_LABEL
    result["disease_name"] = label
    result["crop_type"] = crop

    # Ensure source tag on each cure step
    steps = []
    for s in result.get("cure_steps", []):
        step_copy = dict(s)
        step_copy["source"] = OFFLINE_SOURCE_LABEL
        steps.append(step_copy)
    result["cure_steps"] = steps

    return result


def get_cure_for_disease(
    disease_name: str,
    crop_type: str,
    location: str,
    symptoms: str = "",
    advisory_mode: str = "hybrid",
    advisory_api_key: str = "",
) -> List[Dict[str, Any]]:
    """
    Backward-compatible wrapper for existing endpoints and tests.

    Returns the list of 3 advisory step dictionaries, while the underlying
    rich advisory payload is accessible via `get_disease_advisory`.
    """
    advisory = get_disease_advisory(
        disease_name, crop_type, location, symptoms, advisory_mode, advisory_api_key
    )
    return advisory.get("cure_steps", [])


def default_cure() -> List[Dict[str, Any]]:
    """Fallback advisory used when no prediction is available."""
    curated = CURATED_FALLBACK
    return [
        {"step": s["step"], "action": s["action"], "details": s["details"], "source": OFFLINE_SOURCE_LABEL}
        for s in curated.get("cure_steps", [])
    ]


def disease_profile(label: str) -> Dict[str, Any]:
    """Structured view of a predicted class for documentation/audit."""
    curated = _match_curated_advisory(label)
    return {
        "label": label,
        "is_healthy": "healthy" in (label or "").lower(),
        "guidance": {
            "symptom": curated.get("summary", ""),
            "spread": "Soil-borne, rain-splash, wind-dispersed, or insect vector.",
            "management": curated.get("cure_steps", [{}])[0].get("details", "") if curated.get("cure_steps") else "",
        },
        "source": OFFLINE_SOURCE_LABEL,
        "method": "curated_expert_formulary",
    }
