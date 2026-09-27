# Smart Farm - An AI-Powered Agricultural Decision Intelligence System for Precision Farming

**Research project, Phase II (second review) - local full-stack implementation.**

A working precision-farming platform that combines a plant-disease classifier,
weather-aware agronomic advisory, farm/livestock cost analytics and a
rule-based decision engine, behind a real authentication and data-ownership
layer.

> **Naming.** The academic identity of this project is *"An AI-Powered
> Agricultural Decision Intelligence System for Precision Farming"*. "HarvestIQ"
> is an internal product/feature direction only and must not replace the research
> title in the paper.

---

## 1. Problem

A smallholder farmer makes irrigation, fertiliser, disease and selling decisions
with very little information: no in-field sensors, no local weather station, no
access to an agronomist. Generic mobile advice ignores the farmer's own field,
and market information is unavailable or unreliable. The result is avoidable
losses from over/under-watering, late disease detection and poor selling timing.

## 2. Objectives

1. Detect crop disease from a single leaf photograph and return ranked,
   uncertainty-aware predictions with actionable steps.
2. Convert real weather data into concrete watering, fertiliser and
   disease-risk advice for a specific plot.
3. Keep an auditable, per-user record of farm activity (plant and livestock) and
   derive cost, revenue and profit analytics from it.
4. Enforce correctness and security properties that a research deployment can
   honestly claim: real authentication, strict data isolation, deterministic
   advisory, and explicit labelling of every simulated or estimated value.

## 3. Features

| Area | Capability | Status |
|---|---|---|
| Authentication | Register / login / logout, bcrypt hashing, JWT bearer tokens, OTP password reset | Implemented |
| Authorisation | Per-user isolation enforced on every resource route | Implemented |
| Disease detection | MobileNetV2, 38 classes, top-5 ranking, confidence floor with an explicit *uncertain* outcome, annotated output image | Implemented |
| Advisory | Watering, fertiliser, fungal-disease risk (current + 5-day), ET0 estimate | Implemented (rule-based) |
| Weather | Live current conditions and 5-day forecast from OpenWeatherMap, with a labelled fallback | Implemented |
| Plant farm | Sessions, investment fields, daily logs, harvest close-out | Implemented |
| Livestock | Sessions, daily logs, close-out, separate analytics | Implemented |
| Analytics | Cost / revenue / profit, crop mix, resource timelines, leaderboards | Implemented |
| Market intelligence | Commodity scenarios, mandi comparison, selling advice | Implemented as **clearly labelled simulated data** |
| Notifications | Advisory email + password-reset OTP over SMTP | Implemented |
| Crop recommendation | Ranked crops from soil/season inputs | Planned (Phase 3) |
| Yield prediction | Regression model with MAE / RMSE / R2 | Planned (Phase 3) |
| RAG knowledge base | Document ingestion, retrieval, grounded answers, citations | Planned (Phase 4-5) |
| Conversational assistant | Intent routing to the modules above | Planned (Phase 6) |
| Farmer profile | Location, land, soil, irrigation, livestock, constraints | Planned (Phase 7) |

The authoritative status of every requirement, and the evidence each one needs
for the paper, is tracked in [`FEATURE_TRACEABILITY.md`](FEATURE_TRACEABILITY.md).

## 4. Architecture

```
Browser (static SPA: index.html + app.js + api.js, no build step)
   |  HTTPS/JSON, Authorization: Bearer <jwt>
   v
FastAPI application (backend/main.py)
   |- app/config.py       centralised settings from backend/.env
   |- app/security.py     bcrypt + JWT
   |- app/deps.py         authentication + ownership dependencies
   |- app/rate_limit.py   in-memory throttling for auth/notification routes
   |- app/logging_config.py  rotating logs with secret redaction
   |- ml_service.py       MobileNetV2 pipeline (CUDA when available)
   |- weather_service.py  OpenWeatherMap + labelled simulated fallback
   |- climate_engine.py   fungal-risk rules, ET0 estimate
   |- recommendation_engine.py  watering / fertiliser rules, soil-moisture estimate
   |- advisory_service.py template cure/advisory steps
   |- simulation_service.py   isolated, deterministic demonstration market data
   |- notification_service.py SMTP advisory + OTP
   `- database.py         SQLAlchemy 2.x -> SQLite (absolute path, FK enforced)
       migrations/        versioned schema upgrades with automatic backup
```

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the component, request, data and
authentication flows, and [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md) for the
schema.

## 5. Technology stack

| Layer | Technology |
|---|---|
| Frontend | Static HTML/CSS/JS, Bootstrap 5.3, Chart.js, no bundler |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Database | SQLAlchemy 2.x + SQLite (WAL-free, foreign keys enforced) |
| Auth | bcrypt, PyJWT (HS256) |
| ML/CV | PyTorch, Hugging Face Transformers (MobileNetV2 image classification) |
| Integrations | OpenWeatherMap REST, Gmail SMTP |
| Tests | pytest, FastAPI TestClient |

## 6. Setup

### Requirements

- Windows 10/11 (paths in the commands are Windows-specific but nothing else is)
- **CPython 3.10** - the version the project is verified against
- ~2 GB free disk space for the virtual environment plus the 9 MB model

### 1. Install dependencies

```powershell
# canonical interpreter for this project
$py = "C:\Users\Dhanush\AppData\Local\Programs\Python\Python310\python.exe"
& $py -m pip install -r backend\requirements.txt
```

> The bundled `backend\venv` predates the Phase 2 security work and is missing
> `bcrypt`. Either recreate it (`& $py -m venv backend\venv` then install the
> requirements into it) or keep using the canonical interpreter as above.

### 2. Configure the environment

```powershell
Copy-Item backend\.env.example backend\.env
```

Then edit `backend/.env` and set at least:

| Variable | Why |
|---|---|
| `JWT_SECRET` | Signs access tokens. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Without it the app starts with an ephemeral secret and every restart invalidates issued tokens. |
| `OPENWEATHER_API_KEY` | Enables live weather. Without it the API returns clearly labelled simulated weather. |
| `SENDER_EMAIL` / `EMAIL_APP_PASSWORD` | Enables advisory and OTP email. Use a Gmail **App Password**, never the account password. |

`backend/.env` is gitignored. Never commit it, and never paste a real key into
documentation, source code or a chat message.

### 3. Prepare the database

The database is created and migrated automatically on first start. To apply
migrations without starting the API:

```powershell
Push-Location backend; & $py -c "from migrations import run_all; print(run_all())"; Pop-Location
```

### 4. Run the backend

```powershell
Push-Location backend
& $py main.py            # http://127.0.0.1:8000  (docs at /docs)
```

The API binds to **127.0.0.1** by default. Set `API_HOST=0.0.0.0` only for a
deliberate LAN demo, and set `TRUST_PROXY_HEADERS=true` if a reverse proxy sits
in front of it.

### 5. Run the frontend

```powershell
& $py -m http.server 5500 --directory frontend
```

Open <http://localhost:5500>. The frontend calls the API at
`http://localhost:8000`; to point it elsewhere set `window.APP_CONFIG_API_BASE`
before `js/api.js` loads, or call `APP_CONFIG.setApiBase(url)` in the console.

### 6. Run the tests

```powershell
& $py -m pytest tests
```

## 7. Environment variables

Every setting is documented inline in [`backend/.env.example`](backend/.env.example).
Groups: application, database, authentication, rate limiting, CORS, machine
learning, uploads, weather, email, knowledge base/RAG, legacy data ownership.
Relative paths are resolved against the project root, never the working
directory.

## 8. API documentation

- Interactive reference: <http://127.0.0.1:8000/docs>
- Written reference: [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md)

Authentication flow: `POST /api/auth/register` or `POST /api/auth/login` returns
an `access_token`; send it as `Authorization: Bearer <token>` on every other
request. The Version-1 `X-User-Id` header is rejected unless an operator
explicitly sets `ALLOW_LEGACY_USER_HEADER=true`, and every use of it is logged.

## 9. Research methodology

- **Disease classification** - a fine-tuned MobileNetV2 image classifier over
  **38 crop-disease classes** (`backend/models/plant_disease_model/config.json`).
  The API returns the top-k scores, the device used, the inference time and an
  explicit *uncertain* status when the top score falls below the configured
  confidence floor.
- **Advisory** - watering, fertiliser and fungal-risk outputs come from an
  explicit **rule-based decision engine**, not a learned model. Every response
  carries `method: "rule_based_decision_engine"`, the rule that fired and the
  exact inputs used.
- **Soil moisture** - an **estimate** derived from weather, soil type and
  irrigation history. No soil sensor is deployed; the response says so in
  `soil_moisture_detail.source = "estimated"`.
- **ET0** - a simplified Hargreaves-type estimate, explicitly *not* FAO-56
  Penman-Monteith, reported for context and not yet used in the irrigation
  thresholds.
- **Market data** - deterministic **simulated** values for demonstration and
  protocol purposes. No live mandi feed is integrated and the UI says so.

Known methodological limitations are listed in [`LIMITATIONS.md`](LIMITATIONS.md).

## 10. Results and metrics

No accuracy figure is claimed in this README. The repository currently contains
no held-out evaluation of the disease model and no latency study; those
measurements are produced by scripts under `research_paper_data/` and recorded
in `research_paper_data/metrics.md` once Phase 9 runs. Anything not produced by
a script is not reported.

## 11. Repository layout

```
backend/            FastAPI application, services, migrations, ML weights
backend/app/        configuration, security, dependencies, logging
backend/models/     fine-tuned MobileNetV2 weights (9 MB)
frontend/           static SPA (index.html, css/, js/api.js, js/app.js)
tests/              pytest suite (auth, authorisation, API regression, rules)
docs/archive/       Version-1 source snapshots kept for provenance
research_evidence/  screenshots, charts and measurements for the paper
research_paper_data/ dataset cards, experiment and metric records
```

## 12. Testing

See [`TEST_PLAN.md`](TEST_PLAN.md) for scope, coverage and how to run the suite.
Current state: 108 automated tests covering authentication, authorisation/IDOR,
input validation, the full Version-1 regression set and the decision rules.

## 13. Limitations

See [`LIMITATIONS.md`](LIMITATIONS.md). The most important ones: the advisory
rules are unvalidated heuristics, the disease model has no recorded evaluation or
training provenance in the repository, market data is simulated, soil moisture is
estimated, the rate limiter is per-process, and tokens are not revocable.

## 14. Future work

Crop recommendation and yield prediction modules; RAG-based government scheme
knowledge with citations; a conversational assistant that routes questions to the
existing modules; a farmer profile that personalises the advisory; Grad-CAM style
explanations; a proper held-out evaluation of the classifier; multi-process rate
limiting and token revocation.
#   a g r i c u l t u r e - b o t  
 