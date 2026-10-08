# PROJECT AUDIT

> **STATUS UPDATE - 2026-09-25, after Phase 1 + Phase 2.**
> The body of this document below is the **original Phase 0 audit** and is kept
> unchanged as the evidence record of the state of the project *before* the
> stabilisation and security work. Several of its statements are now outdated.
> **Read section 0 first** for the verified current state and for the
> disposition of every finding. `FEATURE_TRACEABILITY.md` carries the
> requirement-level status.

---

## 0. Phase 1 + Phase 2 completion audit (current state)

**Method:** static inspection of the working tree, 108 automated tests
(`tests/`, all passing), and live verification against the running instance on
`http://127.0.0.1:8000`.

**Runtime facts (measured)**

| Item | Value |
|---|---|
| Interpreter | `Python310\python.exe` (3.10) - the bundled `backend/venv` (3.10.9) predates the security work and lacks `bcrypt` |
| Backend | running, 30 routes, binds `127.0.0.1:8000` |
| Model | MobileNetV2, **38 classes**, loaded on **CUDA** |
| Database | `backend/database.db`, 9 tables, migration version 2, `integrity_check = ok`, `foreign_key_check` clean |
| Data preserved | 7 users, 7 plant sessions, 2 animal sessions, 10 predictions, 4 + 2 daily logs - unchanged |
| Repository | `master`, 4 commits, working tree clean at the time of writing |

### 0.1 Disposition of the Phase 0 findings

| ID | Finding | Status now | Evidence |
|---|---|---|---|
| S1 | Identity spoofing via `X-User-Id` | **CLOSED** | `app/config.py` defaults `ALLOW_LEGACY_USER_HEADER=false`; `app/deps.py:56` only honours it when enabled. Live: `GET /api/sessions` with `X-User-Id: 1` -> **401**. `tests/test_auth.py::test_legacy_user_id_header_is_rejected` |
| S2 | IDOR on 9 routes | **CLOSED** | Every `{id}` route loads through `get_owned_plant_session` / `get_owned_animal_session`. `tests/test_authorization.py` (21 tests) |
| S3 | Weak SHA-256 hashing | **CLOSED** | bcrypt with upgrade-on-login (`app/security.py`). All 7 stored hashes are bcrypt. `test_legacy_account_is_upgraded_to_bcrypt_on_login` |
| S4 | Hardcoded weather key / Gmail app password in source | **CLOSED in source** | Removed from the working tree and from `docs/archive/*`. The values remain in git history commit `cbac227` - **the credentials must be rotated**. |
| S5 | Live LLM key in `.env`, unread by any code | **OPEN (low)** | The `GROK_API_KEY` fallback is gone; `LLM_API_KEY` is read but no LLM call exists until Phase 4. The key is unused - remove it. |
| S6 | Wildcard CORS | **CLOSED** | Explicit origin list from config. `test_api_smoke.py::test_health` + config tests |
| S7 | Unrestricted upload | **CLOSED** | MIME + extension allow-list, 8 MB streaming cap (413), min-dimension and pixel caps. `test_authorization.py` upload tests |
| S8 | No rate limiting on auth routes | **CLOSED with a caveat** | `app/rate_limit.py` on register/login/forgot/reset/notify. Per-process only, and `X-Forwarded-For` is ignored unless `TRUST_PROXY_HEADERS=true`. See `LIMITATIONS.md` 5.1 |
| S9 | Account enumeration on forgot-password | **CLOSED** | Generic response for unknown e-mail; delivery failures are logged, not returned as 500. `test_forgot_password_does_not_reveal_whether_an_account_exists` |
| S10 | Plaintext OTP | **CLOSED** | Stored as an HMAC-SHA256 digest keyed with `JWT_SECRET`, generated with `secrets.randbelow`, with an attempt cap. `test_otp_is_never_stored_in_plaintext` |
| S11 | No CSRF / no HTTPS | **ACCEPTED (local deployment)** | Token-based auth, loopback bind. Documented in `LIMITATIONS.md` 5.4-5.6 |
| S12 | `/api/sessions` returned every user's data | **CLOSED** | All list routes require the authenticated user. `test_sessions_are_scoped_to_the_caller` |
| B1 | `is_healthy` always false | **CLOSED** | Derived from label semantics (`is_healthy_label`) |
| B2 | Severity from confidence | **CLOSED** | `severity_from_label()` maps the class name; confidence is never used |
| B3 | No confidence floor | **CLOSED** | `status: "uncertain"` below `ML_CONFIDENCE_FLOOR`, surfaced in the UI as *Uncertain - expert review needed* |
| B4 | Output image not annotated | **CLOSED** | A caption with the top label, score, device and timing is drawn onto the image |
| B5 | CPU-only inference | **CLOSED** | Device auto-resolves to CUDA. Live: `device: "cuda"` |
| B6 | Dead `___` label parsing | **CLOSED** | `advisory_service.py` replaces `grok_service.py` (shim retained) |
| B7 | Random soil moisture | **CLOSED** | Deterministic estimate, `source: "estimated"`, stable across identical calls (`test_recommendations_are_stable_and_explain_themselves`) |
| B8 | Notify forced soil moisture 50 | **CLOSED** | The notify route now derives moisture from the same log history as the dashboard |
| B9 | `rain_probability_24h` hardcoded 0 | **CLOSED** | Derived from the 3-hourly forecast; solar radiation reported as `None` instead of a random number |
| B10 | Fabricated market data | **CLOSED (labelled)** | Isolated in `simulation_service.py`, deterministic, `data_source: "simulated"`, badged in the UI, warning banner on the market view |
| B11 | Case-sensitive crop lookup | **CLOSED** | `app/crop_vocab.py` normalises on write; the fallback row states `fallback_applied` and `requested_crop` |
| B12 | Dead `calculate_et0` | **CLOSED (surfaced, not wired)** | Returned by the advisory endpoint with its `method` and `limitations`. It still does not drive the watering thresholds - stated in the module docstring and `LIMITATIONS.md` 1.4 |
| B13 | Write-only `recommendation_logs` | **OPEN (by design)** | Still written, never read. `LIMITATIONS.md` 3.5 |
| B14 | Unused `twilio`, unread `.env` | **CLOSED** | `twilio` and `timm` removed; `requirements.txt` pinned to the verified versions; `load_dotenv` active through `app/config.py` |
| B15 | Deprecated startup hook, duplicate imports | **CLOSED** | `lifespan` context manager; imports deduplicated |
| B16 | No request/error logging | **CLOSED** | `app/logging_config.py` with rotation, secret redaction, latency header, slow-request and 5xx logging |
| B17 | Stale/duplicate artefacts | **CLOSED** | `index_backup.html` archived, `add_js.py` and the duplicate root `models/` copy deleted (verified byte-identical to the copy the code loads), stale logs removed |
| D1 | Legacy `NULL user_id` rows | **CLOSED** | Migration 001; 0 orphans remain |
| D2 | Inconsistent crop casing | **CLOSED** | Only `Tomato` and `Potato` remain; normalisation enforced on write |
| D3 | Predictions without a timestamp | **CLOSED with a caveat** | Column added. The 10 legacy rows carry the migration timestamp, so they are unusable as a time series (`LIMITATIONS.md` 3.2) |
| D4 | Mixed TEXT/DateTime columns | **OPEN** | Preserved deliberately: the Version-1 data is stored that way. `to_date_key()` normalises reads (`LIMITATIONS.md` 3.3) |
| D5 | Unvalidated `disease_predictions.user_id` | **CLOSED** | Set from the authenticated user only |
| D6 | Duplicate/typo accounts | **OPEN (data)** | Demo data; not auto-deleted because no data may be destroyed |
| D7 | Unbounded `recommendation_logs` growth | **OPEN** | No read path, no retention (`LIMITATIONS.md` 3.5) |
| D8 | No harvest date/loss/quality fields | **OPEN** | `ended_at` was added, but yield-prediction ground truth still cannot be assembled (`LIMITATIONS.md` 3.4) |
| D9 | No FK on `sessions.user_id` | **CLOSED** | Migration 002 rebuilt the three tables; `PRAGMA foreign_key_check` is clean. `daily_logs` / `recommendation_logs` remain FK-free by design |
| D10 | Trivially guessable demo passwords | **MITIGATED** | Hashed with bcrypt; `PASSWORD_MIN_LENGTH` raised to 8. The demo accounts themselves remain - do not cite this data as a user study |

### 0.2 New findings introduced and fixed during Phase 1-2

| Finding | Fix |
|---|---|
| `POST /api/sessions/{id}/notify` returned `null` (no `return` statement) and accepted **any** recipient - an open mail relay | Always sends to the authenticated account's address; returns a payload; 502/503 on failure; rate limited |
| Harvest and livestock close-out could be replayed, silently overwriting a recorded result | 409 on a second close |
| Stored/DOM XSS: plot names, session names, notes, medicine names and cure steps were interpolated into `innerHTML` and into single-quoted inline `onclick` handlers | `escapeHtml()` on every API-derived value, `textContent` for lists, `data-*` attributes plus one delegated click handler |
| 35 hard-coded `http://localhost:8000` literals in `app.js` | `apiUrl()` in `js/api.js`; the SPA also no longer sends `X-User-Id` |
| UI claimed "YOLOv8", "Live" market prices and "24/7 climate monitoring" | Corrected to MobileNetV2 (38 classes), *simulated* market data with a warning banner, 5-day forecast |
| Simulated weather and low-confidence predictions were not labelled in the UI | Provenance badge, moisture-source note, *Uncertain* badge, model metadata line |
| `forgot-password` returned 500 when mail delivery failed, re-enabling account enumeration | Failure logged only; the response stays generic |
| `X-Forwarded-For` was trusted unconditionally, so the rate limiter was bypassable | Only trusted when `TRUST_PROXY_HEADERS=true` |
| Model inference ran inside the event loop | Moved to the thread pool via `run_in_threadpool` |
| `/api/system/info` exposed absolute database and model paths | Removed from the public settings block; `model_info()` returns the folder name only |
| `Settings` read the environment at import time, so configuration could not be tested | Converted to an instantiable class; `validate_startup()` added |
| bcrypt's 72-byte limit was unenforced, so a long password could raise a 500 | Rejected at validation with a clear message |
| The declared foreign keys and two indexes did not exist in the live database (`ALTER TABLE ADD COLUMN` cannot add a constraint) | Migration 002 rebuilds the three tables; verified on a copy first: 7/2/10 rows preserved, `foreign_key_check` clean |

### 0.3 Still open

- Credentials exposed in git history must be **rotated** (outside the repository).
- S5, B13, D4, D6, D7, D8 remain open by design and are documented in `LIMITATIONS.md`.
- No evaluation of the disease model, no latency study, no RAG layer - Phases 3-10.
- The original paper, First Review PPT, HarvestIQ PRD and Review Circular are not in the repository.

---

# ORIGINAL PHASE 0 AUDIT (state before Phase 1 + Phase 2)

**Project (research identity — unchanged):**
*An AI-Powered Agricultural Decision Intelligence System for Precision Farming*

**Continuity product direction:** HarvestIQ (internal/updated feature direction only — the academic title is not renamed)

**Audit date:** 2026-09-25
**Audit method:** static inspection of the repository **plus live verification against a running instance** (backend `http://localhost:8000`, frontend `http://localhost:5500`).
**Rule applied:** nothing below is assumed. Claims carry evidence (`file:line`, live API response, or database query).

Legend: ✅ implemented & verified · 🟡 partially implemented · ❌ missing · ⚠️ implemented but incorrect/risky

---

## 1. Current architecture

```
Browser (static SPA)
   |  fetch -> http://localhost:8000   (hardcoded in 25 distinct call sites)
   v
FastAPI app "Smart Farm API"  (backend/main.py, 913 lines, 25 routes)
   |-- SQLAlchemy ORM -> SQLite (backend/database.db, 8 tables)
   |-- ML: transformers pipeline image-classification
   |        MobileNetV2ForImageClassification, 38 labels, local weights
   |-- Weather: OpenWeatherMap REST (current + 5day/3h forecast) + mock fallback
   |-- Decision rules: climate_engine.py, recommendation_engine.py
   |-- Text generation: grok_service.py (rule templates - NO LLM call)
   `-- Notification: Gmail SMTP (alerts + password-reset OTP)
```

### 1.1 Runtime facts measured during the audit

| Item | Value | Evidence |
|---|---|---|
| Backend process | PID 14348, `python main.py`, already running | `Get-NetTCPConnection -LocalPort 8000`; `/api/health` -> `{"status":"ok"}` |
| Interpreter in use | global `...\Python310\python.exe` (not the bundled venv) | `Win32_Process.CommandLine` |
| Bundled venv | `backend/venv`, Python **3.10.9**, torch 2.14.0, transformers 5.17.0, fastapi 0.141.1 | `pip list` |
| Global interpreter | torch **2.5.1+cu121**, transformers 5.2.0, fastapi 0.135.1 | `pip list` |
| GPU | **CUDA available, 1 device** - but inference runs on CPU (no `device=` passed) | `torch.cuda.is_available() -> True`; `ml_service.py:33-36` |
| Frontend | static files on :5500, no build step | live `GET /index.html -> 200 (87 021 B)` |
| Version control | **no project repository exists** (only an empty repo at `C:\Users\Dhanush`, 0 commits) | `git rev-parse`, `git log` |
| Model classes | **38 labels**, image size 224 (PRD says "27+") | `backend/models/plant_disease_model/config.json` |

### 1.2 File inventory (project files only, `venv` excluded)

| Path | Size | Lines | Role |
|---|---|---|---|
| `backend/main.py` | 34 109 B | 913 | all 25 API routes, Pydantic schemas, startup |
| `backend/database.py` | 6 170 B | 173 | 8 ORM models, engine, `init_db`, ad-hoc migrations |
| `backend/ml_service.py` | 1 828 B | 70 | MobileNetV2 loader + `predict_image()` |
| `backend/weather_service.py` | 4 764 B | 121 | OpenWeatherMap client + mock fallbacks |
| `backend/climate_engine.py` | 1 411 B | 34 | ET0 (unused) + fungal-risk rules |
| `backend/recommendation_engine.py` | 4 221 B | 107 | watering / fertilizing decision rules |
| `backend/grok_service.py` | 1 994 B | 27 | template "cure steps" (misleading name) |
| `backend/notification_service.py` | 3 467 B | 96 | Gmail SMTP alerts + OTP mail |
| `backend/models/plant_disease_model/` | 9.3 MB | - | `model.safetensors`, `config.json` (38 labels), `preprocessor_config.json` |
| `backend/database.db` | 106 496 B | - | live SQLite data (6 users, 7 plant + 2 animal sessions, 9 predictions) |
| `backend/requirements.txt` | 105 B | 11 | **unpinned** deps; includes unused `twilio` |
| `backend/.env` | 98 B | 1 | a live LLM API key that **no code reads** |
| `frontend/index.html` | 87 021 B | 1 705 | the whole SPA (7 views + modals) |
| `frontend/js/app.js` | 91 019 B | 2 084 | all frontend logic |
| `frontend/css/style.css` | 42 881 B | 1 821 | theme |
| `frontend/js/particles.js` | 7 072 B | 217 | animated background |
| `frontend/index_backup.html` | 61 113 B | - | stale duplicate of the SPA |
| `frontend/project.md` | - | - | the HarvestIQ PRD (source of truth for this work) |
| `add_js.py` | 3 557 B | - | one-off script that appended JS to `app.js` (content already present) |
| `models/plant_disease_model/` | 9.3 MB | - | **duplicate, unreferenced** model copy at repo root |
| `backend/*.log` (5 files) | 4.4 KB | - | stale run artifacts (traceback in `error.log` is from a different machine/user, Python 3.13) |

---

## 2. Existing features (implemented, evidence-based)

| # | Feature | Status | Evidence |
|---|---|---|---|
| 1 | Email/password registration, login, logout | ✅ | `main.py:113-144`; live `POST /api/auth/login` -> `success`, user id 5 |
| 2 | Forgot-password with 6-digit OTP (10 min validity) | ✅ | `main.py:146-182`; `notification_service.py:62-96` (live send **not executed** to avoid side effects) |
| 3 | Per-user statistics | ✅ | `main.py:184-202`; live `GET /api/auth/user-stats` -> counts |
| 4 | Plant disease detection from image | ✅ | `ml_service.py`; live `POST /api/predict/disease` on a PNG -> 5 detections, 173 KB base64 image, 3 cure steps |
| 5 | Top-k prediction list (k=5) | ✅ | live response contained exactly 5 detections |
| 6 | Cure / advisory step generation | 🟡 | `grok_service.py` - templated from label + crop + location; **no LLM call, no verified agronomy source** |
| 7 | Crop (plant) sessions with investment fields | ✅ | `main.py:280-300`, `database.py:26-48`; live `GET /api/sessions` |
| 8 | Daily farm logs (watered / fertilized / weather / notes) | ✅ | `main.py:302-325`; live `GET /api/sessions/1/daily_logs` -> 1 row |
| 9 | Harvest close-out (yield + market price) | ✅ | `main.py:327-337` |
| 10 | Animal sessions + daily logs + close-out | ✅ | `main.py:343-391`; live `GET /api/animals`, `GET /api/animals/1/daily_logs` |
| 11 | Plant cost/revenue/profit analytics | ✅ | `main.py:550-710`; live `/api/dashboard/summary` -> investment 248 602, profit −137 389 |
| 12 | Animal cost/revenue/profit analytics | ✅ | `main.py:393-548`; live `/api/animals/dashboard/summary` |
| 13 | Yield / resource timeline aggregates for charts | ✅ | `main.py:674-709`; Chart.js in `index.html` |
| 14 | Current weather + 5-day forecast | 🟡 | live `/api/sessions/1/weather` -> 29.0 °C, 63 % RH (real API) but **`rain_probability_24h` hardcoded 0** and solar radiation random |
| 15 | Fungal disease-risk advisory from weather | ✅ | `climate_engine.py:13-34` (rule-based) |
| 16 | Watering recommendation | 🟡 | `recommendation_engine.py:24-73` (rules) but **soil moisture is `random.randint(20,80)`** at `main.py:731-732`, hardcoded 50 at `main.py:787` |
| 17 | Fertilizer recommendation | 🟡 | `recommendation_engine.py:75-107`; only 3 crops known; a mis-cased crop name silently falls back to Tomato requirements |
| 18 | Email alert of recommendations | ✅ logic (not executed) | `main.py:778-811` |
| 19 | Market intelligence dashboard | ⚠️ | `main.py:820-909` - **every value is `random.randint`** yet presented as market data |
| 20 | Session/plot management UI + analytics UI | ✅ | `index.html` (7 views), `app.js` 2 084 lines; all assets return 200 |
| 21 | Bilingual hooks (hidden Google Translate widget) | 🟡 | `index.html:9-18` |

**Views present:** Home, Disease Prediction, Climate Dashboard, Plant Farm, Animal Farm, Analytics Dashboard, Market + auth overlay (`index.html:167-188`).
**Views absent:** Crop Recommendation, Yield Prediction, Government Schemes/Loans/Insurance, AI Assistant, Farmer Profile.

---

## 3. Existing APIs (25 routes)

Every route is defined directly on the app object. **No route uses real authentication** — the only identity signal is an optional `X-User-Id` header.

| # | Method | Path | Identity handling | Purpose |
|---|---|---|---|---|
| 1 | GET | `/api/health` | none | liveness |
| 2 | POST | `/api/auth/register` | none | create account |
| 3 | POST | `/api/auth/login` | none | login (returns user object, **no token**) |
| 4 | POST | `/api/auth/forgot-password` | none | send OTP |
| 5 | POST | `/api/auth/reset-password` | none | reset password with OTP |
| 6 | GET | `/api/auth/user-stats` | `X-User-Id`, 401 if absent | per-user counters |
| 7 | POST | `/api/predict/disease` | `X-User-Id` optional, unvalidated | classification + cure steps |
| 8 | GET | `/api/sessions` | optional `X-User-Id` | list plant sessions |
| 9 | POST | `/api/sessions` | optional `X-User-Id` | create plant session |
| 10 | POST | `/api/sessions/{id}/daily_logs` | **none** | add daily log |
| 11 | GET | `/api/sessions/{id}/daily_logs` | **none** | list daily logs |
| 12 | POST | `/api/sessions/{id}/harvest` | **none** | close plant session |
| 13 | POST | `/api/animals` | optional `X-User-Id` | create animal session |
| 14 | GET | `/api/animals` | optional `X-User-Id` | list animal sessions |
| 15 | POST | `/api/animals/{id}/daily_logs` | **none** | add animal log |
| 16 | GET | `/api/animals/{id}/daily_logs` | **none** | list animal logs |
| 17 | POST | `/api/animals/{id}/close` | **none** | close animal session |
| 18 | GET | `/api/animals/dashboard/summary` | optional `X-User-Id` | animal KPIs |
| 19 | GET | `/api/animals/dashboard/analytics` | optional `X-User-Id` | animal charts |
| 20 | GET | `/api/dashboard/summary` | optional `X-User-Id` | plant KPIs |
| 21 | GET | `/api/dashboard/analytics` | optional `X-User-Id` | plant charts |
| 22 | GET | `/api/sessions/{id}/weather` | **none** | current weather for a plot |
| 23 | GET | `/api/sessions/{id}/recommendations` | **none** | watering + fertilizing + disease risk |
| 24 | POST | `/api/sessions/{id}/notify` | **none** | email the recommendation |
| 25 | GET | `/api/market/intelligence` | optional `X-User-Id` | simulated market data |

**Live verification:** 12 GET routes returned `200` with real database content; `POST /api/predict/disease` returned a complete payload; `POST /api/auth/login` succeeded for an existing account.

---

## 4. Existing database tables (SQLite, 8 tables)

Verified by direct query of `backend/database.db` (`sqlite_master`).

| Table | Key columns | Rows (live) | Notes |
|---|---|---|---|
| `users` | `id, name, email (unique), hashed_password, otp, otp_expiry, created_at` | **6** | password = `sha256(password + static_salt)`; OTP stored in plaintext |
| `farming_sessions` | `id, user_id, crop_type, plot_name, area_cents, soil_type, location, created_at(Text), seed_qty, cost_per_seed, total_land_cost, fertilizer_qty, cost_per_fertilizer, is_active, harvest_yield, market_price` | **7** | 3 rows have `user_id = NULL` |
| `daily_logs` | `id, session_id, date(Text), watered, water_reason, fertilized, fertilizer_amount, weather_condition, notes` | **1** | `session_id` has **no FK constraint** |
| `animal_sessions` | `id, user_id, animal_type, session_name, animal_count, cost_per_animal, initial_food_qty, cost_per_food_qty, medicine_cost, shelter_cost, is_active, animals_sold, sell_price_per_animal, total_sale_revenue, created_at(DateTime)` | **2** | both rows `user_id = NULL` |
| `animal_daily_logs` | `id, session_id(FK), date(DateTime), food_given_qty, food_cost_today, yield_amount, yield_selling_price, medicine_given, medicine_name, medicine_cost, medicine_reason, deaths_today, notes` | **1** | |
| `disease_predictions` | `id, user_id, crop_type, symptoms, location, disease_name, confidence_score, is_healthy, severity, cure_data(JSON text)` | **9** | **no `created_at` / timestamp column** |
| `recommendation_logs` | `id, session_id, date(Text), action_type, recommendation, reason, is_completed` | **0** | written on every recommendation call (`main.py:757`), **never read by any endpoint** |
| 12 × `ix_*` indexes | - | - | auto-created by SQLAlchemy |

**Ownership distribution observed:** plant sessions -> `NULL, NULL, NULL, 4, 4, 5, 6`; animal sessions -> `NULL, NULL`; predictions -> 6 × `NULL`, 1 × `5`, 2 × `6`.

**Migration mechanism:** `database.py:128-162` `run_migrations()` runs `ALTER TABLE ... ADD COLUMN user_id` inside `try/except sqlite3.OperationalError`. There is **no migration framework** (no Alembic) and no schema-version table.

---

## 5. Existing ML model

| Property | Value | Evidence |
|---|---|---|
| Architecture | `MobileNetV2ForImageClassification` | `models/plant_disease_model/config.json:architectures` |
| Weights | `model.safetensors`, 9 264 680 bytes | file size |
| Output classes | **38 labels** (`id2label` 0-37) | `config.json` |
| Label style | human-readable, e.g. `"Apple Scab"`, `"Corn (Maize) with Common Rust"`, `"Healthy Apple"` | `config.json` |
| Input pre-processing | pipeline default resize; `preprocessor_config.json` declares `do_normalize=true` + ImageNet mean/std, but also contains a stray `feature_extractor_type: YolosFeatureExtractor`, `format: coco_detection`, `size: 512` copied from an unrelated config (unused by the classification pipeline) | `preprocessor_config.json` |
| Loaded from | `backend/models/plant_disease_model` (absolute path from `__file__`) | `ml_service.py:30-36` |
| Provenance | **NOT in the repository** - no training script, notebook, dataset, split, hyperparameters or metrics | repository search |
| Duplicate copy | repo-root `models/plant_disease_model/` is **unreferenced dead weight** | no code references it |

**Consequence for the research paper:** accuracy / precision / recall / F1 / confusion matrix and the dataset cannot currently be reported because no evaluation artifacts exist in the project. Recorded in section 13 as `[METRIC TO BE MEASURED]` - not fabricated.

---

## 6. Existing ML pipeline (as implemented)

```
upload (FastAPI UploadFile)
  -> content-type must start with "image/" (main.py:213)   [client-supplied MIME only, no size limit]
  -> bytes -> PIL open + convert("RGB")                    (ml_service.py:43)
  -> transformers pipeline("image-classification")         (ml_service.py:33)
  -> list[{label, score%, box=None}] sorted desc           (ml_service.py:47-60)
  -> re-encode the SAME image to JPEG base64               (ml_service.py:62-65)
  -> top-1 drives is_healthy / severity / cure steps       (main.py:230-242)
  -> row inserted into disease_predictions                 (main.py:244-257)
```

Measured on a live request: 5 detections (pipeline default `top_k=5`), 3 cure steps, 173 060-character base64 payload.

**Correctness problems (all evidence-backed):**

| ID | Problem | Where |
|---|---|---|
| B1 | `is_healthy` is **always `False`** whenever any detection exists - even when the top label is `Healthy Apple` / `Healthy Grape Plant` | `main.py:234` |
| B2 | `severity` is derived from **confidence** (`>90 Severe`, `>70 Moderate`, else `Mild`); confidence is not severity, and this would produce invalid claims in the paper | `main.py:235` |
| B3 | No confidence floor / out-of-distribution handling: an unrelated photo still yields 5 disease labels (audit top score was 8.28 %) | `main.py:226-242` |
| B4 | `annotated_image_base64` is **not annotated** - the original image is merely re-encoded; `box` is always `None`; no heatmap / bounding box exists | `ml_service.py:56-65` |
| B5 | Inference device is never set, so it runs on **CPU** even though CUDA is available | `ml_service.py:33-36` |
| B6 | The top-1 label wording is human-readable (`"Potato with Early Blight"`) but `grok_service.py:13-15` splits on `___` and replaces `_`, a leftover from PlantVillage-style folder names - dead parsing path | `grok_service.py:13-15` |

---

## 7. Existing frontend modules

| Module | Location | Notes |
|---|---|---|
| Single-page shell + 7 views | `frontend/index.html` (1 705 lines) | views toggled by `showView(...)`; nav at `index.html:167-188` |
| Auth overlay (login / register / forgot / reset) | `index.html` + `app.js:1840-2045` | writes `localStorage['smartfarm_user']` |
| Global fetch interceptor injecting `X-User-Id` | `app.js:1789-1803` | the entire client-side "authentication" mechanism |
| Disease upload + result rendering | `app.js:60-190` | drag-drop `#drop-zone`, `#result-section` |
| Plant farm (sessions, daily logs, harvest) | `app.js:640-760` | `#newSessionModal` |
| Animal farm (sessions, daily logs, close-out) | `app.js:~760-1250` | `#newAnimalSessionModal`, `#closeAnimalSessionModal` |
| Analytics dashboards (plant + animal) | `app.js:530-640`, `app.js:1200-1300` | Chart.js canvases |
| Market intelligence view | `app.js:1452-1600` | renders simulated values as market prices |
| Analytics sidebar loaders | `app.js:1729-1785` | appended by `add_js.py` (already applied) |
| Theme + animations | `css/style.css` (1 821 lines), `js/particles.js` (217 lines) | dark glassmorphism theme, particle background |
| Third-party | Bootstrap 5.3 + Chart.js via jsDelivr CDN | `index.html:7` and script tags |

**Frontend weaknesses:** `http://localhost:8000` is hardcoded in **25 distinct call sites** (no `API_BASE`); several views have no failure path for a rejected fetch; `index_backup.html` is a stale 61 KB duplicate that will silently drift from the SPA.

---

## 8. Working functionality (verified live during this audit)

Verified against the running instance, not by reading code:

1. `GET /api/health` -> `{"status":"ok"}`
2. `GET /api/sessions` -> 7 sessions with values from `database.db`
3. `GET /api/animals` -> 2 sessions
4. `GET /api/dashboard/summary` -> `{"total_investment":248602.0,"total_yield":1954.0,"total_revenue":111213.0,"net_profit":-137389.0,"profit_margin_percent":-55.26,"active_sessions":3,"completed_sessions":4}`
5. `GET /api/animals/dashboard/summary` -> `{"total_investment":4065384.0,...,"net_profit":59759.0,"profit_margin_percent":1.47,...}`
6. `GET /api/dashboard/analytics`, `/api/animals/dashboard/analytics` -> correct JSON envelope (empty arrays for a user with no data in scope)
7. `GET /api/sessions/1/weather` -> real OpenWeatherMap values (temperature 29.0, humidity 63, wind 38.0 km/h)
8. `GET /api/sessions/1/recommendations` -> `current_weather`, `soil_moisture`, `watering`, `fertilizing`, `disease_risk`
9. `GET /api/sessions/1/daily_logs`, `/api/animals/1/daily_logs` -> rows returned
10. `GET /api/market/intelligence` -> payload (values simulated, see B-19/§12)
11. `GET /api/auth/user-stats` -> counters
12. `POST /api/predict/disease` (PNG upload) -> 5 detections + base64 image + 3 cure steps
13. `POST /api/auth/login` with an existing account -> `success`
14. User scoping works **when the header is supplied**: `GET /api/sessions` with `x-user-id: 5` -> exactly 1 session
15. Frontend asset serving: `/`, `/index.html`, `/css/style.css`, `/js/app.js`, `/js/particles.js`, `/images/*.png` -> all `200`

**Conclusion:** the existing application is functional. Phase 1 must preserve every one of the 15 items above.

---

## 9. Broken / partially broken functionality

| ID | Symptom | Root cause | Location |
|---|---|---|---|
| B1 | Healthy plants reported as diseased (`is_healthy` always `False`) | unconditional `is_healthy = False` in the `if detections:` branch | `main.py:234` |
| B2 | Meaningless severity ("Moderate" for confidence 71 %) | severity computed from confidence | `main.py:235` |
| B3 | Confident disease label for a photo that is not a leaf (audit: top 8.28 %) | no confidence floor, no OOD/uncertainty handling | `main.py:226-242` |
| B4 | Output image is not annotated although the field is named `annotated_image_base64` | original bytes re-encoded; `box` always `None` | `ml_service.py:56-65` |
| B5 | Slower inference than necessary | pipeline created without `device=` although CUDA is present | `ml_service.py:33-36` |
| B6 | Dead label-parsing branch | splits on `___` / `_` from PlantVillage folder naming | `grok_service.py:13-15` |
| B7 | Watering advice changes between two calls in the same minute | fabricated soil moisture `random.randint(20,80)` | `main.py:731-732` |
| B8 | Alert email can contradict the dashboard advice | notify path hardcodes soil moisture `50` | `main.py:787` |
| B9 | Rain-based watering rule can never trigger from current weather | `rain_probability_24h` hardcoded `0` | `weather_service.py:30` |
| B10 | Fabricated "market prices", "mandis", "news" | `random.randint` for price, trend, distance, reasons | `main.py:850-903` |
| B11 | Wrong crop advice for a valid crop | `CROP_REQUIREMENTS` lookup is case-sensitive with a silent Tomato fallback; DB contains `Tomato`, `tomato`, `potato` | `recommendation_engine.py:25,76`; DB rows |
| B12 | Dead code | `calculate_et0()` is defined but never called | `climate_engine.py:1-11` |
| B13 | Write-only table | `recommendation_logs` inserted on every call, never read | `main.py:756-765` |
| B14 | Dead dependency + inert config | `twilio` in requirements, never imported; `python-dotenv` declared but `load_dotenv()` is never called, so `backend/.env` has no effect | `requirements.txt:11`; repo-wide search |
| B15 | Deprecated lifecycle hook, duplicate imports | `@app.on_event("startup")`; `import random` twice (7, 817); `from datetime import timedelta` twice (8, 818) | `main.py:101,7,817,8,818` |
| B16 | No request logging or error logging; only `print()` and a traceback file write | `main.py:220-224` | - |
| B17 | Stale/duplicate artifacts | `frontend/index_backup.html`, `add_js.py`, 5 log files, duplicate model tree | filesystem |

---

## 10. Security risks

| ID | Risk | Severity | Evidence |
|---|---|---|---|
| S1 | **Total identity spoofing**: any client can send `X-User-Id: <any>` and read another account's data (verified: header `4` vs `5` returns different sessions). Login returns no token, so nothing binds a request to a user. | **Critical** | `main.py:185-188, 273-277, 344-347, 355-358` + live test |
| S2 | **IDOR on 9 routes**: daily logs, harvest, animal logs, close-out, weather, recommendations, notify accept a raw `{id}` with no ownership check. | **Critical** | route table §3 rows 10-12, 15-17, 22-24 |
| S3 | **Weak password hashing**: single-round `sha256(password + hardcoded salt)`; no per-user salt, no work factor. During the audit three demo accounts were matched to a trivial 6-digit password almost instantly (value deliberately not recorded in this document). | **High** | `main.py:20-22` + audit finding |
| S4 | **Hardcoded secrets in source**: a live OpenWeatherMap key, and a Gmail app password used as a default fallback (a real app password is committed in the file). | **High** | `weather_service.py:5`; `notification_service.py:10` |
| S5 | A live LLM API key sits in `backend/.env` while **no code path reads it** - credential exposure with zero benefit. | **High** | `backend/.env`; no `load_dotenv` / client call anywhere |
| S6 | **Permissive CORS** `allow_origins=["*"]` together with `allow_credentials=True`. | **High** | `main.py:93-99` |
| S7 | **Unrestricted upload**: content-type is trusted from the client, no size cap, no pixel cap, image is fully decoded in memory (decompression-bomb / memory DoS). | **High** | `main.py:204-219`; `ml_service.py:43` |
| S8 | **No rate limiting** on `/api/auth/login`, `/api/auth/forgot-password`, `/api/auth/reset-password` -> brute force and email-spam abuse; OTP has no attempt counter. | **High** | `main.py:134-182` |
| S9 | **Account enumeration**: forgot-password returns `404 "No account found with this email."`. | **Medium** | `main.py:149-150` |
| S10 | OTP stored in plaintext in the users table. | **Medium** | `database.py:124` |
| S11 | No CSRF/state protection because there is no session concept at all; no HTTPS (local dev). | **Medium** | architecture |
| S12 | Sensitive data can be over-shared: `GET /api/sessions` without a header returns **all** users' sessions. | **High** | `main.py:274-278` + live test (7 rows, mixed owners) |

> Every secret above is intentionally **not reproduced** in this document.

---

## 11. Data-quality issues

| ID | Issue | Evidence | Impact |
|---|---|---|---|
| D1 | **Legacy rows with `user_id = NULL`**: 3/7 plant sessions, 2/2 animal sessions, 6/9 predictions | live DB query | Logged-in users cannot see the original demo data; their dashboards show zeros (`/api/dashboard/analytics` returned empty arrays for user 5) |
| D2 | **Inconsistent crop naming/casing**: `Tomato`, `tomato`, `potato` stored for the same crops | `farming_sessions.crop_type` rows | Chart buckets split per casing; the case-sensitive requirement lookup silently returns Tomato advice for `Potato` |
| D3 | **No timestamp on disease predictions** | `database.py:12-24` | Time-series/seasonal research analysis on detections is impossible without adding the column |
| D4 | **Mixed temporal types**: `farming_sessions.created_at` is `Text` ISO, `animal_sessions.created_at` is `DateTime`, `daily_logs.date` is `Text`, `animal_daily_logs.date` is `DateTime` | `database.py:36,83,55,90` | Sorting/joining is string-dependent; timeline aggregation relies on `.split("T")` |
| D5 | `disease_predictions.user_id` is unvalidated: any integer is accepted and stored | `main.py:245` | Orphan records possible |
| D6 | Duplicate/near-duplicate accounts, incl. a typo domain (`@gmai.com`) and a repeated name | users table rows 2-4 | Confusing analytics/reporting |
| D7 | `recommendation_logs` accumulates writes with no consumer and no retention rule | `main.py:756-765` | Unbounded growth, no research value as-is |
| D8 | Harvest close-out records only yield + price; no harvest date, no loss/quality fields | `main.py:327-337` | Yield-prediction ground truth cannot be assembled from farm data yet |
| D9 | `sessions.user_id` has no FK constraint to `users` (only the predictions/animal-log columns declare FKs) | `database.py:16,30,67` | No referential integrity |
| D10 | Demo password material is trivially guessable for several accounts | audit finding | Any data exported from this DB is not trustworthy as a "real user study" |

---

## 12. Missing PRD functionality (HarvestIQ extensions)

| PRD capability | Status | Notes |
|---|---|---|
| Farmer / farm profile (location, land, soil, irrigation, preferences, livestock) | ❌ | No table, no endpoint, no UI. `location`/`soil_type` exist only per session |
| Crop recommendation module | ❌ | Only watering/fertilizing rules for 3 crops exist; no crop-selection engine with input schema, ranking or explanation |
| Yield prediction | ❌ | No dataset, no model, no endpoint, no UI |
| Prediction/recommendation explanation (XAI) | ❌ | No feature attribution, no rule trace shown to the user |
| Centralised configuration | ❌ | No config module; DB path relative to CWD; secrets hardcoded |
| RAG pipeline (ingest → chunk → embed → vector store → retrieve → ground → answer) | ❌ | Nothing implemented; no ingestion script, no vector DB |
| Knowledge base / official documents | ❌ | No documents in the repository |
| Government scheme discovery + eligibility | ❌ | - |
| Loans / KCC / insurance / subsidies information | ❌ | - |
| Source citations & traceability | ❌ | - |
| Conversational assistant + intent router | ❌ | - |
| "Information not found" / hallucination guard | ❌ | - |
| Market intelligence from a real source (or honest simulation label) | ❌ | Currently random values presented as market data (`main.py:850-903`) |
| Secure auth (bcrypt/Argon2 + token) & authorization | ❌ | See S1-S3, S12 |
| Tests (unit, API, security, RAG) | ❌ | No test framework, no test files |
| Observability (structured logging, request ids) | ❌ | `print()` + one traceback file |
| API documentation | 🟡 | FastAPI auto-docs at `/docs` only; no `API_DOCUMENTATION.md`, no tags/summaries |
| README / `.env.example` / pinned requirements | ❌ | - |
| Repository cleanup | ❌ | Duplicate model, backup HTML, one-off script, logs |
| Performance work (device selection, model warm-up, response-time measurement) | ❌ | GPU unused; no timing instrumentation |

---

## 13. Missing research-paper functionality

| Requirement | Status | Detail |
|---|---|---|
| Dataset documentation for the disease model | ❌ MISSING | No dataset, no split, no preprocessing description in the repo. `[METRIC TO BE MEASURED]` |
| Model evaluation metrics (accuracy, precision, recall, F1, confusion matrix) | ❌ MISSING | Only a per-request softmax score exists; nothing evaluated on a held-out test set |
| Training provenance (script/notebook, hyperparameters, epochs) | ❌ MISSING | Not in the repo; the weights arrived pre-trained |
| Yield-prediction dataset + regression metrics (MAE/RMSE/R²) | ❌ MISSING | Needs an external dataset (e.g. public crop-yield records) and a documented split |
| Crop-recommendation evaluation | ❌ MISSING | No model, no labelled data, nothing to evaluate |
| Decision-rule validation (watering/fertilizer) | ❌ MISSING | Rules are unsourced; no agronomy reference, no expert validation, no ablation |
| RAG retrieval metrics (hit rate/precision, groundedness, citation correctness, latency) | ❌ MISSING | RAG does not exist yet |
| System performance measurements (API latency, inference time, memory) | ❌ MISSING | No instrumentation; and the GPU is unused |
| Comparative analysis vs. existing systems | ❌ MISSING | Requires reproducible numbers first |
| Literature survey (~20-25 papers, thematic, gap-mapped) | ❌ NOT IN REPO | The existing paper/PPT/review circular were not present anywhere in the project — must be supplied |
| Architecture diagram / figures for the paper | ❌ MISSING | To be produced in Phase 10 |
| Dataset statistics & confusion-matrix figures | ❌ MISSING | Phase 9/10 |
| Honest labelling of simulated vs. real data in the paper | ❌ | Market data, soil moisture and solar radiation must be labelled simulated |

**Corrections the paper must carry (evidence-based):** the model has **38 classes**, not "27+".

---

## 14. Recommended implementation order

Mapped 1:1 to the PRD's ten phases, with the concrete deliverables per phase.

| Phase | Scope | Key deliverables | Gate before moving on |
|---|---|---|---|
| **0 (done now)** | Safety + audit | `.gitignore`, git checkpoint, DB backup, `PROJECT_AUDIT.md`, `FEATURE_TRACEABILITY.md` | checkpoint commit exists; DB backup verified |
| **1** | Stabilise | `app/config.py` + `.env.example`; absolute DB path; pinned `requirements.txt`; logging module; remove dead code/dupes (`calculate_et0`, duplicate imports, `twilio`); move secrets to env **without** breaking the running app; `README.md` | all 15 verified features still pass; frontend + API healthy |
| **2** | Security & architecture | bcrypt hashing + migration of existing hashes; JWT access tokens; `get_current_user` dependency; per-resource ownership checks on all 9 IDOR routes; CORS allow-list; upload validation (size/MIME/pixels); rate limiting; routers split by domain; `API_DOCUMENTATION.md` | `security` tests pass (spoof attempt -> 401/403); legacy logins still work |
| **3** | Improve existing AI/ML | device-aware inference; fix B1/B2; confidence floor with "uncertain" outcome; real top-k control; heatmap explanation; crop-name normalisation; dataset + evaluation script for the disease model -> real accuracy/precision/recall/F1 + confusion matrix; crop recommendation module + yield prediction (with dataset) | measured metrics recorded in `research_paper_data/metrics.md` |
| **4** | RAG pipeline | `rag/` package: loaders (PDF/HTML/DOCX) -> cleaning -> semantic chunking -> embeddings -> vector store -> retriever -> grounded generator -> citations; abstraction so the LLM backend can be swapped | retrieval + citation tests pass on seeded docs |
| **5** | Government knowledge | `data/knowledge_base/` metadata schema (title, scheme, ministry, category, eligibility, benefits, documents, dates, source URL, version); ingestion CLI; `/api/knowledge/*` endpoints | every answer returns >=1 real citation; "not found" path works |
| **6** | Conversational assistant | intent router (crop / disease / weather / water / fertilizer / scheme / loan / insurance / general) -> tools -> LLM explanation -> citations; `/api/assistant/chat`; chat UI | no tool result is invented by the LLM; refusal path verified |
| **7** | Personalisation | farmer profile table + endpoints + UI; recommendations become profile-aware (soil, irrigation, area, crop history, livestock) | personalised vs. generic advice differs measurably |
| **8** | UI/UX | one `API_BASE` constant; new views (Crop Recommendation, Yield Prediction, Schemes, Assistant, Profile); consistent error surfaces; single "Agricultural Decision Intelligence" narrative | regression pass on all pre-existing views |
| **9** | Testing & evaluation | `tests/` (unit, API, authz, security, ML, RAG), `TEST_PLAN.md`, measured latency tables, RAG evaluation set | reproducible test report committed |
| **10** | Research documentation | `ARCHITECTURE.md`, `DATABASE_SCHEMA.md`, `API_DOCUMENTATION.md`, `research_evidence/`, `research_paper_data/`, `FINAL_PROJECT_REPORT.md`, updated literature survey | every paper claim traceable to a file or measurement |

**Hard dependency:** Phase 2 (auth + ownership) must land before Phase 5-7 endpoints are written, otherwise each new endpoint would have to be re-secured.

---

*End of audit. This document contains no secrets, no estimated metrics and no claims about unused features.*






