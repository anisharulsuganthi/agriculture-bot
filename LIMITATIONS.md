# LIMITATIONS

Honest statement of what this system does **not** do, what is approximated, and
what has not been measured. Every entry is evidence-based: it was found in the
code or measured during testing. Nothing here is speculative.

Referenced by `backend/climate_engine.py`, `backend/recommendation_engine.py`,
`README.md` and the research paper.

---

## 1. Methodology limitations

### 1.1 The advisory modules are rule-based, not learned
`recommendation_engine.py` (watering, fertiliser) and `climate_engine.py` (fungal
risk) are explicit `if/elif` decision trees carrying the original project's
agronomic assumptions. They are **not** trained on data, they are **not**
validated against field trials or expert review, and they are **not** machine
learning models. Every response states `method: "rule_based_decision_engine"` and
names the rule that fired, so the UI and the paper cannot imply otherwise.

### 1.2 The crop requirement table is unsourced
`CROP_REQUIREMENTS` (litres/plant, fertiliser type, frequency for 12 crops) comes
from the original project. It is not cited to an agronomic publication and has
not been validated. Doses are per plant and ignore plot area, plant density,
soil test results and crop stage.

### 1.3 Soil moisture is estimated, never measured
No in-field sensor is deployed. `estimate_soil_moisture()` derives a percentage
from a base value, a soil-retention coefficient, irrigation history, temperature
and forecast rain probability. It is a heuristic, it is not calibrated against any
soil, and `source` is always `"estimated"`.

### 1.4 ET0 is a simplified approximation
`calculate_et0()` implements a Hargreaves-type temperature-range estimate, **not**
FAO-56 Penman-Monteith. Wind speed, latitude, canopy resistance and day-of-year
are not modelled, and solar radiation is usually unavailable (`None`). It is
reported in the advisory for context and does **not** currently drive the
watering thresholds.

### 1.5 Fungal-risk thresholds are heuristics
The humidity/temperature bands (high: >80 % and 25-32 °C; medium: >60 % and
20-35 °C) encode common fungal conditions but are not derived from a published
disease-decision-support system and have not been sensitivity-tested.

### 1.6 Disease severity is derived from the class name
`severity_from_label()` maps keywords in the predicted label to a band. It is not
a validated disease-severity scale and does not consider lesion size, plant
growth stage or infection timing. Confidence (a softmax score) is deliberately
**not** used for severity - that was a Version-1 defect.

---

## 2. Machine-learning limitations

### 2.1 No training provenance in the repository
The MobileNetV2 weights in `backend/models/plant_disease_model/` arrived
pre-trained. There is no training script, notebook, dataset reference, split,
hyperparameter list or training log. The dataset name and the split used to
produce these weights are currently **unknown** and must be supplied by the
author or re-established by evaluation.

### 2.2 No measured model performance
No accuracy, precision, recall, F1 or confusion matrix has been computed on a
held-out test set. The only number the system produces at runtime is the softmax
score of the top class for a single image. Any performance figure in the paper
must come from an evaluation script, not from this README.

### 2.3 The confidence floor is a heuristic threshold
`ML_CONFIDENCE_FLOOR` (default 40 %) decides when a result is reported as
*uncertain* instead of a disease. It has not been calibrated against an operating
characteristic curve, so its sensitivity and specificity are unknown.

### 2.4 Out-of-distribution behaviour is limited
The classifier is applied to whatever image the user uploads. A photograph that
contains no leaf can still receive a ranked disease list; the only protection is
the confidence floor. There is no leaf/plant detector gating the model, and no
Grad-CAM or other saliency explanation - `annotated_image_base64` is the input
image with a caption drawn on it, not a localisation.

### 2.5 Preprocessing configuration is inconsistent
`config.json` declares `image_size: 224` while `preprocessor_config.json` carries
`size: 512` plus stray `YolosFeatureExtractor` / `coco_detection` fields copied
from an unrelated configuration. The pipeline currently uses the transformers
image processor defaults, so the practical input size should be confirmed and the
preprocessor file cleaned before any metric is reported.

### 2.6 Single-label classification only
38 mutually exclusive classes. A plant with two simultaneous diseases, or a
disease outside the 38 classes, cannot be represented.

---

## 3. Data limitations

### 3.1 The disease model has no public dataset in the repository
See 2.1. The demo database (10 prediction rows) is application data, not an
evaluation set.

### 3.2 Historical prediction timestamps are synthetic
Migration 001 added `disease_predictions.created_at` to the existing rows by
backfilling the migration timestamp, because the Version-1 table had no timestamp
column. All 10 legacy rows therefore share one timestamp and **cannot** be used
for time-series or seasonal analysis. New predictions are timestamped correctly.

### 3.3 Mixed temporal types
`farming_sessions.created_at` and `daily_logs.date` are ISO **TEXT**, while
`animal_sessions.created_at` and `animal_daily_logs.date` are **DATETIME**. Read
paths normalise through `to_date_key()`, but sorting and joining remain
string-dependent in places.

### 3.4 No harvest date, no loss or quality data
Close-out records only yield and market price. Yield-prediction ground truth
cannot be assembled from the farm records, and partial-crop-loss or quality
grading cannot be represented.

### 3.5 `recommendation_logs` is write-only
Every advisory call appends rows that no endpoint reads. There is no consumer and
no retention policy, so the table grows without bound. It is a candidate source
for "was the advice followed?" analysis once a read path exists.

### 3.6 `daily_logs` and `recommendation_logs` have no foreign keys
`daily_logs.session_id` and `recommendation_logs.session_id` are plain indexed
integers. Migration 002 gave `farming_sessions`, `animal_sessions` and
`disease_predictions` real foreign keys, but these two were left as they are
because daily logs are frequently posted for sessions that predate the auth
layer. Orphan rows are possible.

### 3.7 The demo dataset is small and not a user study
7 accounts, 7 plant sessions, 2 livestock sessions. Several demo accounts have
trivially weak passwords. This data supports demonstration and UI testing; it is
**not** evidence of field adoption and must not be presented as a user study.

### 3.8 No ground truth for the advisory rules
Because the rules are heuristics, there is no labelled data against which their
correctness could be measured. Rule validation (expert review, ablation, or a
comparison with a published decision-support system) is still missing.

---

## 4. Market-data limitations

`simulation_service.py` produces **deterministic simulated** values. There is no
mandi or commodity-price feed. Prices, trends, mandi distances, "news" items and
forecasts are generated for demonstration and for exercising the UI. They are
labelled `data_source: "simulated"` in the API and badged as simulated in the UI,
and they must never be used for real trading decisions or quoted as market
evidence in the paper.

---

## 5. Engineering and security limitations

| # | Limitation | Consequence |
|---|---|---|
| 5.1 | The rate limiter is in-process and in-memory | Each worker keeps its own counters; a multi-worker or multi-machine deployment multiplies the effective limit. `backend/app/rate_limit.py` |
| 5.2 | Access tokens are not revocable | A token stays valid until it expires (default 12 h). Logout only clears the client copy. Fixing this needs a denylist or short-lived tokens plus refresh. |
| 5.3 | Tokens are stored in `localStorage` | Any successful XSS would expose them. The frontend now escapes all API data, but `localStorage` remains weaker than an `HttpOnly` cookie. |
| 5.4 | The API is served over plain HTTP | Acceptable for a local research deployment only. A remote deployment needs TLS. |
| 5.5 | Legacy SHA-256 password hashes remain verifiable | Required so Version-1 accounts keep working. They upgrade to bcrypt on the next successful login, but any account that never logs in again keeps the weak hash. |
| 5.6 | No CSRF protection | The API is token-based rather than cookie-based, so classical CSRF does not apply, but there is also no `SameSite` cookie policy to rely on if the auth model changes. |
| 5.7 | OTP codes have no delivery guarantee | Delivery failures are logged, not surfaced, to avoid account enumeration. A user with a misconfigured mailbox sees a success message and no email. |
| 5.8 | CORS and the bind address are configuration, not enforcement | Defaults are safe (loopback bind, explicit origin list), but `API_HOST=0.0.0.0` exposes the service. `settings.validate_startup()` warns about the unsafe combinations. |
| 5.9 | `SYSTEM` endpoint exposes runtime settings | `/api/system/info` returns configuration that is not secret. It is intentionally free of paths and credentials. |
| 5.10 | The image is fully decoded before pixel limits apply | `PIL.Image.open().verify()` runs after allocation, so a decompression bomb is caught but has already consumed memory. Mitigated by the 8 MB upload cap. |
| 5.11 | No dependency scanning or CI | `requirements.txt` is pinned, but there is no automated vulnerability scan and no continuous integration pipeline. |
| 5.12 | The bundled `backend/venv` is stale | It lacks `bcrypt` and `pytest`; the canonical interpreter is the one named in the README. |

---

## 6. UI limitations

- The livestock "climate" cards show **static husbandry guidance**, not a computed
  assessment: the backend has no livestock advisory endpoint. This is stated in
  the UI.
- The disease page reports top-k classes and a caption; there is no heatmap or
  bounding box.
- The frontend is a single large `app.js` (about 2,100 lines) with no build step,
  no bundler and no type checking.
- Bootstrap and Chart.js are loaded from a CDN without subresource integrity.
- There is no offline mode and no service worker.

---

## 7. Not implemented (planned phases)

Crop recommendation engine, yield prediction, RAG knowledge base, government
scheme / loan / insurance retrieval, citations, conversational assistant, farmer
profile personalisation, Grad-CAM explainability, held-out model evaluation, and
the research-evidence package. These are tracked with their required evidence in
`FEATURE_TRACEABILITY.md`.

---

## 8. What must be supplied by the author

1. Disease-model training provenance: dataset name and source, split,
   hyperparameters, training script or notebook.
2. The original research paper, the First Review PPT, the HarvestIQ PRD and the
   Review Circular / Second Review checklist - none of these are in the
   repository.
3. A yield-prediction dataset.
4. Official government documents to ingest, and approval to fetch them if the
   sources are not provided.
5. Confirmation of which credentials should remain configured.

---

*Nothing in this document is an estimate presented as a measurement. Items that
require measurement are marked `[METRIC TO BE MEASURED]` in
`research_paper_data/metrics.md` rather than estimated here.*
