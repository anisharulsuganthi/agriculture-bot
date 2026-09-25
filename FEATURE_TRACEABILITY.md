# FEATURE TRACEABILITY MATRIX

**Project:** *An AI-Powered Agricultural Decision Intelligence System for Precision Farming*
**Continuity direction:** HarvestIQ (feature extension only — academic identity unchanged)
**Generated:** 2026-09-25 · derived from `PROJECT_AUDIT.md` + live verification

**Chain documented for every row:**
`Original project requirement → existing implementation → HarvestIQ PRD update → required enhancement → status → evidence needed for the paper`

**Status vocabulary**

| Tag | Meaning |
|---|---|
| `PRESERVE` | works today; Phase work must not regress it |
| `FIX` | exists but incorrect/insecure; correct it in place |
| `EXTEND` | partially exists; deepen it per the PRD |
| `NEW` | not implemented anywhere; build it |

**Phase** refers to the roadmap in `PROJECT_AUDIT.md` §14.

---

## A. Identity, account and access

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| A1 | Account creation and login (original) | `POST /api/auth/register`, `/login` (`main.py:113-144`), UI overlay (`app.js:1840-2045`) | keep | validation, duplicate-email handling, token issuance | FIX | 2 | login/register screenshots; API test log |
| A2 | Secure password storage | `sha256(password + hardcoded salt)` (`main.py:20-22`) | mandatory fix | bcrypt/Argon2 + per-user salt; transparent upgrade of legacy hashes at next login | FIX | 2 | before/after code + test proving legacy accounts still authenticate after migration |
| A3 | Real token/session authentication | none — client sends `X-User-Id` (`app.js:1789-1803`) | mandatory fix | JWT, `get_current_user` dependency, `/api/auth/me` | NEW | 2 | security test: spoofed header → 401 |
| A4 | User data isolation | only 4 routes filter by header; **9 routes ignore the caller** | mandatory fix | ownership checks on every `{id}` route | FIX | 2 | IDOR test matrix (user A cannot touch user B) |
| A5 | Farmer / farm profile (location, land, soil, irrigation, crop history, livestock, constraints) | none | HarvestIQ addition | profile table + CRUD API + UI, consumed by recommendations | NEW | 7 | profile screenshot + personalisation comparison |
| A6 | Per-user statistics | `GET /api/auth/user-stats` (`main.py:184-202`) | keep + extend | add profile completeness, recent activity | EXTEND | 7 | dashboard screenshot |

---

## B. Precision-agriculture intelligence

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| B1 | Plant disease detection from leaf image | MobileNetV2 pipeline, 38 classes, top-5 + base64 image (`ml_service.py`, `main.py:204-270`) | keep, harden | device-aware inference, confidence floor, uncertainty outcome, visual explanation | EXTEND | 3 | accuracy / precision / recall / F1 + confusion matrix on a held-out test set |
| B2 | Disease severity & healthy detection | derived from confidence; `is_healthy` always False (`main.py:234-235`) | fix | health flag from label semantics; severity from a defined scale | FIX | 3 | before/after example payloads |
| B3 | Disease cure / advisory steps | templated text (`grok_service.py`) | upgrade to grounded advice | cite agronomy/KB sources; keep template path as documented fallback | EXTEND | 3, 5 | example advisory with citation |
| B4 | Crop recommendation | not implemented (only 3-crop water/fertilizer rules) | HarvestIQ core module | input schema (soil, season, area, water, location) → ranked crops + explanation + confidence | NEW | 3 | recommendation screenshot + methodology + evaluation |
| B5 | Yield prediction | not implemented | HarvestIQ core module | dataset + regression model, MAE/RMSE/R², endpoint, UI | NEW | 3 | dataset card + metrics table + parity plot |
| B6 | Weather-aware advisory | `weather_service.py` current + 5-day forecast; real API verified live | keep, make honest | real `rain_probability_24h`; real solar radiation or explicit "estimated" label | FIX | 1, 3 | latency table; sample responses for 3 locations |
| B7 | Evapotranspiration / irrigation modelling | `calculate_et0()` defined but **never called** (`climate_engine.py:1-11`) | extend | wire it into watering advice with proper Hargreaves inputs, or remove and document | EXTEND | 3 | methodology + validation discussion |
| B8 | Watering recommendation | rules (`recommendation_engine.py:24-73`) with fabricated soil moisture | keep rules, fix inputs | derive soil moisture from profile/estimate; document as rule-based (not ML) | FIX | 3, 7 | rule table + sample outputs + explicit "rule-based" statement |
| B9 | Fertilizer / resource recommendation | rules for 3 crops; case-sensitive lookup | extend | crop-name normalisation, more crops, dose from area + soil, explanation | EXTEND | 3 | rule table + sample outputs |
| B10 | Fungal disease-risk advisory | `assess_disease_risk()` (`climate_engine.py:13-34`) | keep | justify thresholds with a reference; expose trigger values to the user | EXTEND | 3 | threshold table + reference |
| B11 | Farm analytics (cost/revenue/profit) | plant + animal summary/analytics endpoints, verified live | preserve | consistent currency formatting, period filters | PRESERVE | 1 | dashboard screenshots with real numbers |
| B12 | Plant session tracking (plot, area, soil, investment, harvest) | `farming_sessions` + endpoints | preserve | normalise crop names, record harvest date | PRESERVE | 1 | ER diagram + session screenshot |
| B13 | Daily farm logging | `daily_logs` + endpoints | preserve | link logs to the recommendation that was followed | PRESERVE | 1 | log screenshot |
| B14 | Animal / livestock management | animal sessions, logs, close-out, analytics | preserve (must not be removed) | — | PRESERVE | 1 | animal dashboard screenshot |
| B15 | Charts / timelines | Chart.js views + resource timelines | preserve | add predicted-vs-actual overlays | PRESERVE | 8 | chart screenshots |

---

## C. Market, notification and data quality

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| C1 | Market intelligence | `main.py:820-909` — all values `random.randint` | must not be presented as live | real price source if legally viable, otherwise isolate simulation and label every panel "Demonstration / simulated data" | FIX | 1, 3 | screenshot of the honest label + source note |
| C2 | Email alerts for recommendations | `main.py:778-811` + SMTP (`notification_service.py:12-36`) | preserve | env-based credentials, delivery result logging, retry | FIX | 1 | test email screenshot |
| C3 | OTP password reset | `main.py:146-182`, 6-digit, 10 min | preserve + harden | attempt limit, hashed OTP at rest, no account enumeration | FIX | 2 | flow screenshots + security test |
| C4 | Disease-prediction history | `disease_predictions` table, 9 rows | extend | add `created_at`, expose history endpoint + UI, use for research analysis | EXTEND | 1, 3 | prediction-history screenshot + timestamped dataset export |
| C5 | Legacy `NULL user_id` data | 3 plant sessions, 2 animal sessions, 6 predictions orphaned | must be handled | deterministic ownership-assignment migration (configurable target user) + report | FIX | 1 | migration log before/after counts |
| C6 | Consistent crop naming | `Tomato` / `tomato` / `potato` in DB | must be normalised | canonical crop vocabulary + normalisation on write | FIX | 1 | normalisation test + updated distribution chart |

## D. Knowledge intelligence, RAG and conversational AI (HarvestIQ additions)

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| D1 | RAG pipeline (ingest → clean → chunk → embed → store → retrieve → rank → generate → cite) | none | HarvestIQ core addition | `rag/` package with swappable embedding + LLM backends, FAISS or Chroma store, retrieval-first flow | NEW | 4 | pipeline diagram + retrieval examples + latency |
| D2 | Document ingestion framework (PDF/HTML/DOCX) with metadata extraction | none | core addition | loader → text extraction → cleaning → semantic chunking → metadata (title, scheme, ministry, category, dates, source URL, version) | NEW | 4 | ingestion log: N documents → M chunks, per-document metadata |
| D3 | Official agricultural knowledge base | none (no documents in repo) | core addition | curated corpus: PM-KISAN, KCC, NABARD loans, PMFBY, AIF, Soil Health Card, PMKSY, RKVY, ministry FAQs — primary sources only | NEW | 5 | corpus inventory table with source URLs + retrieval hit rate |
| D4 | Scheme discovery & eligibility answering | none | core addition | `/api/knowledge/schemes` + eligibility reasoning strictly from retrieved text | NEW | 5 | query → answer → citation screenshots |
| D5 | Loan / Kisan Credit Card information | none | core addition | retrieval + comparison of loan options with citations | NEW | 5 | answered query with 2+ real citations |
| D6 | Crop insurance information (PMFBY etc.) | none | core addition | retrieval with premium/claim facts sourced only from documents | NEW | 5 | answered query + citation list |
| D7 | Subsidies, guidelines, required documents, application steps | none | core addition | "documents required" + "how to apply" answer templates built from retrieval | NEW | 5 | checklist screenshot + citations |
| D8 | Source citation / traceability | none | core addition | every claim mapped to document + chunk id; citations returned with the response | NEW | 4, 5 | citation payload example + UI rendering |
| D9 | Conversational assistant with intent routing | none | core addition | router: crop / disease / weather / water / fertilizer / scheme / loan / insurance / analytics / general → tool calls → LLM explanation (never invents tool output) | NEW | 6 | routing accuracy table on a test query set |
| D10 | Hallucination guard / "information not found" | none | core addition | relevance threshold, context limit, explicit refusal wording when the KB lacks evidence | NEW | 4, 6 | negative-test transcript showing refusal |
| D11 | Multilingual interaction | hidden Google-Translate widget only (`index.html:9-18`) | PRD-indicated | document the real behaviour; keep translation as a browser feature or state clearly it is not a project module | EXTEND | 8 | screenshot + honest limitation note |

---

## E. Engineering, operations, QA and research packaging

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| E1 | Centralised configuration | none; DB path relative to CWD; secrets inline | mandatory | `backend/app/config.py` reading `.env`/env vars: DB path, model path, vector-store path, API URLs, JWT secret, LLM provider/model, CORS list, limits | NEW | 1 | config table in `README.md` |
| E2 | Secret handling | keys hardcoded in `weather_service.py:5`, `notification_service.py:10`; unused key in `.env` | mandatory | move all secrets to env vars, add `.env.example`, document rotation | FIX | 1 | `.env.example` (placeholder values only) |
| E3 | Database path & schema integrity | `sqlite:///./database.db` (`database.py:6`); ad-hoc `run_migrations()` | mandatory | absolute path from project root, FK constraints, `created_at` on predictions, deterministic migration + backup | FIX | 1 | `DATABASE_SCHEMA.md` + migration log |
| E4 | Logging & observability | `print()` + one traceback file | required | structured logging (request id, latency, failure reason) with credential redaction | NEW | 1, 9 | sample log lines + latency table |
| E5 | Error handling & validation | bare `except Exception` → 500 with raw message; uploads unvalidated | required | typed errors, consistent JSON error shape, upload validation (size/MIME/pixels), frontend error surfaces | FIX | 1, 2 | error-case table with responses |
| E6 | Performance | GPU present but unused; no timing | required if <5 s target | device-aware inference, warm-up at startup, response-time instrumentation | FIX | 3, 9 | measured inference + API latency (p50/p95) |
| E7 | Automated tests (unit/API/authz/ML/RAG) | none | required | `tests/` with pytest + TestClient, fixtures on a temp DB, security tests | NEW | 9 | `TEST_PLAN.md` + test run output |
| E8 | API documentation | auto `/docs` only | required | `API_DOCUMENTATION.md` (method, path, auth, request, response, errors, example) + tags/summaries in code | NEW | 2, 10 | doc excerpt + `/docs` screenshot |
| E9 | Setup documentation | none | required | `README.md`: problem, objectives, features, architecture, stack, modules, setup, env vars, running, testing, methodology, results, limitations, future work | NEW | 1 | README link in the paper |
| E10 | Dependency management | unpinned 11-line `requirements.txt` incl. unused `twilio` | required | pinned versions, Python version note, system prerequisites, removal of unused packages | FIX | 1 | dependency table |
| E11 | Repository cleanup | duplicate model tree, `index_backup.html`, `add_js.py`, 5 log files, caches | required | archive/remove after confirming unused; keep a documented `docs/archive/` for provenance | FIX | 1 | cleanup log (what moved, why) |
| E12 | Architecture documentation | none | required | `ARCHITECTURE.md` with component/data/request/RAG/auth flows + diagram suitable for paper/PPT | NEW | 10 | diagram file in `research_evidence/` |
| E13 | Dataset + experiment records | none | required | `research_paper_data/datasets.md`, `models.md`, `experiments.md`, `metrics.md`, `results.md` | NEW | 9, 10 | dataset cards + metric tables (measured only) |
| E14 | Literature survey (~20-25 papers) | not in repo (existing paper/PPT unavailable to the agent) | required by review | thematic survey (crop recommendation, yield prediction, disease detection, precision agriculture, XAI, decision support, LLMs, RAG, conversational agri-systems) with gap mapping to implemented modules | EXTEND | 10 | reference list + gap table |
| E15 | Evidence package for the second review | none | required | `research_evidence/` with numbered screenshots, charts, confusion matrix, retrieval examples, latency charts | NEW | 10 | numbered evidence files |
| E16 | Final report | none | required | `FINAL_PROJECT_REPORT.md` (before/after, features, fixes, security, architecture, ML, RAG, datasets, results, tests, limitations, readiness) | NEW | 10 | report link |

---

## Summary counts

| Status | Count | Meaning |
|---|---|---|
| `PRESERVE` | 6 | must not regress |
| `FIX` | 14 | existing but incorrect/insecure/honesty-critical |
| `EXTEND` | 12 | partially present, deepen per PRD |
| `NEW` | 25 | not implemented anywhere |

**Reading order for the review:** `PROJECT_AUDIT.md` (§8 working, §9 bugs, §10 security) → this matrix (§A/§B/§C continuity, §D new intelligence layer) → `ARCHITECTURE.md`.

**Honesty rules carried into the paper**

1. No metric is reported unless produced by a script in `research_paper_data/` or `tests/`.
2. Simulated values (market prices, soil moisture, solar radiation) are labelled simulated wherever they appear.
3. The watering/fertilizer/climate modules are described as **rule-based decision engines**, not learned models.
4. The disease model is reported with **38 classes** and its dataset/evaluation is only described once measured.
5. Anything still unfinished is listed in `limitations.md` / `future_work.md`, not implied as complete.

---



