# ARCHITECTURE

**Project:** *An AI-Powered Agricultural Decision Intelligence System for Precision
Farming*

Layered architecture of the running system, with the component, request, data and
authentication flows. Companion documents: [`API_DOCUMENTATION.md`](API_DOCUMENTATION.md),
[`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md), [`LIMITATIONS.md`](LIMITATIONS.md).

---

## 1. Design goals

1. **Local-first.** The whole system runs on one machine with no container
   orchestration, no external database server and no cloud dependency.
2. **Replaceable intelligence.** Weather, ML inference, advisory rules, market
   data and notifications are separate modules behind narrow interfaces, so a
   provider can be swapped without touching the API layer.
3. **Honest data.** Every value carries its provenance: `data_source`,
   `simulated`, `method`, `source`, `rule_fired`. A caller can always tell a
   measurement from an estimate and a simulation from a live feed.
4. **Secure by construction.** Identity comes from a signed token, every
   user-owned row is reached through an ownership-checked helper, and no secret
   is written in source.

---

## 2. Component diagram

```
+------------------------------------------------------------------+
|  Presentation layer - static SPA (no build step)                  |
|  index.html | css/style.css | js/api.js | js/app.js | particles.js|
|  - one API base URL (apiUrl)      - Bearer token in localStorage  |
|  - escapeHtml / textContent       - delegated actions, no inline  |
|    handlers (no user data in code)      onclick strings           |
+-----------------------------+------------------------------------+
                              | JSON over HTTP
                              | Authorization: Bearer <jwt>
                              v
+------------------------------------------------------------------+
|  API layer - FastAPI (backend/main.py)                            |
|  routers as tagged endpoints, Pydantic request models            |
|  timing middleware (X-Process-Time-Ms), global error handler      |
+---+-------------+---------------+--------------+-----------------+
    |             |               |              |
    v             v               v              v
+-----------+  +-----------+  +------------+  +-----------------+
| Auth      |  | Advisory  |  | ML / CV    |  | Notification    |
| app/      |  | climate_  |  | ml_service |  | notification_   |
| security  |  | engine    |  | (MobileNetV2|  | service         |
| app/deps  |  | recommend |  |  pipeline, |  | (SMTP advisory  |
| app/      |  | ation_    |  |  CUDA/CPU) |  |  + OTP)         |
| rate_limit|  | engine    |  +------------+  +-----------------+
| app/      |  | advisory_ |
| logging_  |  | service   |  +------------+  +-----------------+
| config    |  +-----------+  | simulation |  | External APIs   |
+-----------+                | service    |  | OpenWeatherMap  |
                             +------------+  | Gmail SMTP      |
                                              +-----------------+
                              |
                              v
                    +-------------------+
                    | Data layer         |
                    | database.py        |
                    | SQLAlchemy 2.x     |
                    | SQLite (absolute   |
                    | path, FK enforced) |
                    | migrations/ (v1,v2)|
                    +-------------------+
```

---

## 3. Layer responsibilities

| Layer | Module | Responsibility | Must not |
|---|---|---|---|
| Presentation | `frontend/js/api.js` | API base URL, token storage, `Authorization` header, 401 handling, HTML escaping | Know about business rules |
| Presentation | `frontend/js/app.js` | Views, rendering, chart setup, form handling | Contain secrets, build HTML from unescaped API data |
| API | `backend/main.py` | Routing, request validation, response shaping, orchestration | Contain hard-coded config, secrets or SQL |
| API | `backend/app/deps.py` | Resolve the caller, enforce ownership | Trust client-asserted identity |
| Auth | `backend/app/security.py` | bcrypt hashing, legacy-hash upgrade, JWT issue/verify | Store plaintext or unsalted digests |
| Config | `backend/app/config.py` | Every environment-dependent value; production safety checks | Contain a real secret or a machine-specific path |
| Intelligence | `recommendation_engine.py`, `climate_engine.py` | Rule-based watering/fertiliser/risk/ET0 | Claim to be learned models |
| ML | `ml_service.py` | Model loading, device selection, inference, uncertainty, caption | Invent confidence or severity from a score |
| Integration | `weather_service.py` | Current + forecast, labelled fallback | Present simulated values as live |
| Integration | `notification_service.py` | SMTP advisory and OTP | Log credentials |
| Data | `database.py`, `migrations/` | Schema, migrations with backup, FK enforcement | Destroy user data |

---

## 4. Request flow (worked example: a plant advisory)

```
1. Browser            GET /api/sessions/3/recommendations
2. api.js             attaches Authorization: Bearer <jwt>
3. FastAPI            resolves get_current_user -> User(id=7)
4. main.py            get_owned_plant_session(3, user) -> verifies session.user_id == 7
5. weather_service    OpenWeatherMap current + 5-day forecast
                        on provider failure -> labelled simulated payload
6. main.py            reads the session's daily logs, derives days_since_watering
7. recommendation_    estimate_soil_moisture(...)  -> {value, source: "estimated"}
                      generate_watering_recommendation(...) -> rule_fired, inputs_used
                      generate_fertilizing_recommendation(...)
8. climate_engine     assess_disease_risk(...) and assess_forecast_risk(...)
9. database           appends two recommendation_logs rows (audit trail)
10. Response          {soil_moisture_detail, watering, fertilizing, disease_risk,
                       et0_estimate, inputs_summary{method: rule_based_decision_engine}}
11. api.js            401 -> clear session and show the login view
12. app.js            renders the cards, escaping every value
```

The same ownership check guards the write routes (`daily_logs`, `harvest`,
`animals/{id}/daily_logs`, `animals/{id}/close`, `notify`). A caller who does not
own the row receives **403** and the attempt is logged.

---

## 5. Authentication flow

```
 register/login
     |  email + password
     v
 validate strength (>= 8 chars, <= 72 bytes)
     |
     +--> bcrypt.verify(stored, password)
     |        |
     |        +--> legacy sha256 record? verify, then REHASH to bcrypt (upgrade on login)
     |
     +--> issue JWT {sub, email, name, iat, exp, iss="smartfarm-adis"} signed with JWT_SECRET
     |
     v
 client stores access_token + profile in localStorage
     |
 every request: Authorization: Bearer <token>
     |
     v
 get_current_user: verify signature/issuer/expiry -> load user -> else 401
```

Design decisions and their consequences:

| Decision | Why | Consequence |
|---|---|---|
| Stateless HS256 JWT | No server-side session store for a single-machine app | Tokens cannot be revoked before expiry (see `LIMITATIONS.md` 5.2) |
| `X-User-Id` disabled by default | It was a client-asserted identity: any caller could set another account's id | The header is only honoured when `ALLOW_LEGACY_USER_HEADER=true`, and every use is logged |
| Ownership checked in a dependency, not per route | Nine Version-1 routes forgot the check | One helper per resource type, used by every route |
| Legacy hashes kept verifiable | Version-1 accounts must keep working | A weak hash survives until that account next logs in |
| OTP stored as a keyed HMAC | A leaked database row must not be replayable | Rotating `JWT_SECRET` invalidates all outstanding OTPs |
| Advisory mail always to the account address | A free-text recipient was an open relay | The client cannot choose a recipient at all |

---

## 6. Data flow and ownership

```
users ──1:N──> farming_sessions ──1:N──> daily_logs
       │                │
       │                └──1:N──> recommendation_logs   (write-only today)
       ├──1:N──> animal_sessions ──1:N──> animal_daily_logs
       └──1:N──> disease_predictions
```

- Ownership is the `user_id` column on `farming_sessions`, `animal_sessions` and
  `disease_predictions`; the first and last now carry real foreign keys (migration
  002) and `PRAGMA foreign_keys=ON` is set on every connection.
- Legacy rows created before authentication existed were assigned to a single
  account by migration 001, so no data was lost and no row is orphaned.
- `disease_predictions.created_at` makes detection history analysable; the 10
  legacy rows share the migration timestamp and are excluded from any time-series
  analysis.

---

## 7. Intelligence layer

| Component | Type | Inputs | Output | Honesty marker |
|---|---|---|---|---|
| Disease classification | Fine-tuned CNN (MobileNetV2, 38 classes) | Leaf image | top-k labels + scores | `status`, `confidence_floor`, `device`, `inference_ms` |
| Soil moisture | Heuristic estimate | soil type, rain probability, temperature, irrigation history | percentage | `source: "estimated"` |
| Watering advice | Rule engine | moisture, rain probability, temperature, humidity, soil | dose + schedule | `rule_fired`, `inputs_used`, `method` |
| Fertiliser advice | Rule engine | moisture, rain probability, temperature, crop | product + frequency | `rule_fired`, `inputs_used`, `method` |
| Fungal risk | Rule engine | humidity, temperature | risk band + action | `trigger.rule`, `method` |
| ET0 | Hargreaves-type estimate | mean/min temperature, optional radiation | mm/day | `method`, `limitations` |
| Cure steps | Template engine | predicted label, crop, location | ordered steps | `source` per step |
| Market data | Deterministic simulation | commodity, day | prices, mandis, advice | `data_source: "simulated"`, `disclaimer` |

The planned RAG pipeline (Phase 4-5) slots in beside these as a *retrieval* layer:
ingestion → cleaning → semantic chunking → embeddings → vector store → similarity
retrieval → context ranking → grounded answer → citation, with a pluggable
embedding backend and a pluggable LLM backend so the system still answers without
any external API (`LLM_PROVIDER=extractive`).

---

## 8. Error handling

- Typed errors: `HTTPException` with a human-readable `detail`; unhandled
  exceptions are logged with a stack trace and returned as a generic 500 so
  internals never reach the client.
- Consistent shape: `{"detail": "..."}` for errors, plus FastAPI's 422 payload
  for validation failures.
- Weather provider failure → `503` (or a labelled simulated payload when
  `ALLOW_SIMULATED_WEATHER` is on).
- Email not configured → `503` before any delivery is attempted.
- Model failure → `500` with a retry message; the API stays up.
- Frontend: every fetch goes through `readJson`, which converts a non-2xx
  response into a thrown `Error` carrying the server's message, and a 401 during
  an authenticated request clears the session and returns to the login view.

---

## 9. Observability

- Rotating file log (`backend/logs/smartfarm.log`, 2 MB x 3) plus console.
- A redacting filter removes registered secrets and anything shaped like a JWT
  or provider key before a record is written.
- `X-Process-Time-Ms` on every response; requests slower than 4 s are logged as
  slow, 5xx responses are logged as errors.
- Startup logs the migration report, the bind address and any configuration
  problem from `settings.validate_startup()`.

---

## 10. Configuration flow

```
backend/.env  ──load_dotenv──>  app/config.py  ──> settings (single cached instance)
 process env  ────────────────┘                        |
                                                      v
                          every module imports `settings` (never os.getenv directly)
```

Relative paths are resolved against the project root, so the app behaves the same
whether it is started with `python main.py`, `uvicorn main:app`, pytest or an IDE
runner. `validate_startup()` reports unsafe production combinations (missing
`JWT_SECRET`, legacy header auth enabled, simulated weather enabled, `0.0.0.0`
without a trusted proxy) as warnings at boot.

---

## 11. Planned evolution

| Phase | Addition | Architectural position |
|---|---|---|
| 3 | Crop recommendation, yield prediction | New intelligence modules beside the rules, same provenance contract |
| 4-5 | RAG pipeline + knowledge base | New retrieval layer, pluggable embeddings/LLM, offline extractive default |
| 6 | Conversational assistant | Intent router that calls existing tools; it may never invent a tool result |
| 7 | Farmer profile | Profile table feeding the advisory inputs (soil, irrigation, area, livestock) |
| 8 | UI views for the new modules | New views on the existing SPA shell and `apiFetch` |
| 9 | Evaluation | Scripts that emit measured metrics into `research_paper_data/` |
