# FEATURE TRACEABILITY MATRIX

**Project:** *An AI-Powered Agricultural Decision Intelligence System for Precision Farming*
**Continuity direction:** HarvestIQ (feature extension only — academic identity unchanged)
**Generated:** 2026-09-25 · derived from `PROJECT_AUDIT.md` + live verification
**Last revised:** 2026-09-25, after Phase 1 (stabilisation) and Phase 2 (security) — statuses below reflect the verified current state, not the original audit.

**Chain documented for every row:**
`Original project requirement → existing implementation → HarvestIQ PRD update → required enhancement → status → evidence for the paper`

**Status vocabulary**

| Tag | Meaning |
|---|---|
| `DONE` | implemented and verified by a test or a live check |
| `PRESERVE` | works today; later phases must not regress it |
| `FIX` | exists but incorrect/insecure; correct it in place |
| `EXTEND` | partially exists; deepen it per the PRD |
| `NEW` | not implemented anywhere; build it |

**Phase** refers to the roadmap in `PROJECT_AUDIT.md` §0 / §14.

---

## A. Identity, account and access

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| A1 | Account creation and login (original) | `POST /api/auth/register`, `/login` (`main.py`), token issued on both | keep | validation, duplicate-email handling, token issuance | **DONE** | 2 | `tests/test_auth.py` (26 tests); login/register screenshots |
| A2 | Secure password storage | bcrypt (`app/security.py`) with upgrade-on-login; min length 8, bcrypt 72-byte cap enforced | mandatory fix | per-user salt, transparent legacy upgrade | **DONE** | 2 | `test_legacy_account_is_upgraded_to_bcrypt_on_login`; all 7 stored hashes are bcrypt |
| A3 | Real token/session authentication | JWT HS256 (`app/security.py`), `get_current_user` dependency, `/api/auth/me` reports the scheme actually used | mandatory fix | token issuance, expiry, 401 handling | **DONE** | 2 | `test_me_rejects_a_tampered_token`; live: spoofed `X-User-Id` → 401 |
| A4 | User data isolation | ownership helpers on every `{id}` route; foreign keys enforced (migration 002) | mandatory fix | 403 on a foreign resource | **DONE** | 2 | `tests/test_authorization.py` — 21 tests incl. the IDOR matrix |
| A5 | Farmer / farm profile (location, land, soil, irrigation, crop history, livestock, constraints) | none | HarvestIQ addition | profile table + CRUD API + UI, consumed by recommendations | `NEW` | 7 | profile screenshot + personalisation comparison |
| A6 | Per-user statistics | `GET /api/auth/user-stats` | keep + extend | add profile completeness, recent activity | `EXTEND` | 7 | `test_user_stats_reflect_the_account`; dashboard screenshot |

---

## B. Precision-agriculture intelligence

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| B1 | Plant disease detection from leaf image | MobileNetV2, **38 classes**, top-5, CUDA inference, annotated output, timing in the response | keep, harden | device-aware inference, uncertainty outcome, visual explanation | **DONE** (explanation limited to a caption) | 3 | live: `device: "cuda"`, `num_labels: 38`; **accuracy/precision/recall/F1 and confusion matrix still `[METRIC TO BE MEASURED]`** |
| B2 | Disease severity & healthy detection | `severity_from_label()` / `is_healthy_label()` derive both from the class name; confidence is never used for severity | fix | severity from a defined agronomic scale | **DONE** (heuristic) | 3 | `tests/test_recommendations.py::test_severity_comes_from_the_label_not_from_the_score` |
| B3 | Disease cure / advisory steps | `advisory_service.py` templates; labelled `source` | upgrade to grounded advice | cite agronomy/KB sources; keep the template path as a documented fallback | `EXTEND` | 3, 5 | example advisory with citation (Phase 5) |
| B4 | Crop recommendation | not implemented | HarvestIQ core module | input schema → ranked crops + explanation + confidence | `NEW` | 3 | recommendation screenshot + methodology + evaluation |
| B5 | Yield prediction | not implemented | HarvestIQ core module | dataset + regression model, MAE/RMSE/R², endpoint, UI | `NEW` | 3 | dataset card + metrics table + parity plot |
| B6 | Weather-aware advisory | live OpenWeatherMap current + 5-day; real `rain_probability_24h`; solar radiation reported as `None` | keep, make honest | never present fallback values as live | **DONE** | 1, 3 | `data_source`/`simulated` flags; UI provenance badge |
| B7 | Evapotranspiration / irrigation modelling | `calculate_et0()` implemented and returned, labelled as a simplified Hargreaves-type estimate | extend | wire into irrigation scheduling or document as context-only | `PARTIAL` — surfaced, not wired (documented) | 3 | methodology + `LIMITATIONS.md` 1.4 |
| B8 | Watering recommendation | rules with a deterministic soil-moisture estimate, `rule_fired`, `inputs_used` | keep rules, fix inputs | document as rule-based (not ML) | **DONE** | 3, 7 | `tests/test_recommendations.py` watering cases |
| B9 | Fertilizer / resource recommendation | rules for 12 crops, case-insensitive, fallback reported via `fallback_applied` | extend | dose from area + soil, agronomic citation | `EXTEND` | 3 | rule table + `test_unknown_crop_is_reported_not_silently_substituted` |
| B10 | Fungal disease-risk advisory | `assess_disease_risk()` current + `assess_forecast_risk()` 5-day, threshold exposed as `trigger.rule` | keep | justify thresholds with a reference | `EXTEND` (thresholds unsourced) | 3 | threshold table + reference (`LIMITATIONS.md` 1.5) |
| B11 | Farm analytics (cost/revenue/profit) | plant + animal summaries and chart endpoints; both dashboards now agree on investment | preserve | currency formatting, period filters | `DONE` (formatting/filters pending) | 1 | `test_plant_dashboard_summary_and_analytics` |
| B12 | Plant session tracking | `farming_sessions` + endpoints, `ended_at` on close-out | preserve | normalise crop names (done), record harvest date (done) | **DONE** | 1 | ER diagram + session screenshot |
| B13 | Daily farm logging | `daily_logs` + endpoints | preserve | link logs to the recommendation that was followed | `PRESERVE` (unlinked) | 1, 7 | log screenshot |
| B14 | Animal / livestock management | animal sessions, logs, close-out, analytics | preserve (must not be removed) | livestock advisory endpoint (currently static guidance) | `PRESERVE` | 1 | animal dashboard screenshot |
| B15 | Charts / timelines | Chart.js views + resource timelines | preserve | add predicted-vs-actual overlays | `PRESERVE` | 8 | chart screenshots |

---

## C. Market, notification and data quality

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| C1 | Market intelligence | `simulation_service.py` - deterministic, isolated, `data_source: "simulated"`, disclaimer, UI warning banner and per-panel "simulated" badges | must not be presented as live | a real source if legally viable, otherwise permanent labelling | **DONE as labelled simulation** | 1, 3 | `test_market_intelligence_is_labelled_as_simulated`; screenshot of the honest label |
| C2 | Email alerts for recommendations | `POST /api/sessions/{id}/notify` returns a payload again, sends only to the account address, rate limited | preserve | env-based credentials (done), delivery logging (done) | **DONE** | 1 | manual SMTP verification screenshot |
| C3 | OTP password reset | keyed-digest OTP, `secrets` generator, attempt cap, generic response | preserve + harden | all done | **DONE** | 2 | `test_otp_attempts_are_capped`, `test_otp_is_never_stored_in_plaintext` |
| C4 | Disease-prediction history | `disease_predictions.created_at`, `/api/predictions`, `/api/predictions/stats` | extend | usable research export | `PARTIAL` — the 10 legacy rows share the migration timestamp | 1, 3 | `LIMITATIONS.md` 3.2; new predictions are timestamped |
| C5 | Legacy `NULL user_id` data | migration 001 assigned orphans to user id 1; 0 orphans remain | must be handled | deterministic assignment + report | **DONE** | 1 | migration report; `PRAGMA` orphan query = 0 |
| C6 | Consistent crop naming | `app/crop_vocab.py` normalises on write and on read | must be normalised | canonical vocabulary exposed at `/api/crops` | **DONE** | 1 | `test_crop_names_are_normalised_on_write` |
| C7 | Referential integrity | migration 002: FKs on the three user-owned tables, missing indexes created, `PRAGMA foreign_keys=ON` | mandatory | — | **DONE** | 1 | `test_foreign_key_enforcement_is_enabled`; `foreign_key_check` clean |
| C8 | Open mail relay / account enumeration | fixed (see `PROJECT_AUDIT.md` §0.2) | mandatory | — | **DONE** | 2 | `test_notification_recipient_cannot_be_redirected` |

---

## D. Knowledge intelligence, RAG and conversational AI (HarvestIQ additions)

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| D1 | RAG pipeline (ingest → clean → chunk → embed → store → retrieve → rank → generate → cite) | none | HarvestIQ core addition | `rag/` package with swappable embedding + LLM backends, FAISS or Chroma store, retrieval-first flow | `NEW` | 4 | pipeline diagram + retrieval examples + latency |
| D2 | Document ingestion framework (PDF/HTML/DOCX) with metadata extraction | none | core addition | loader → extraction → cleaning → semantic chunking → metadata | `NEW` | 4 | ingestion log: N documents → M chunks |
| D3 | Official agricultural knowledge base | none (no documents in repo) | core addition | curated corpus: PM-KISAN, KCC, NABARD loans, PMFBY, AIF, Soil Health Card, PMKSY, RKVY, ministry FAQs — primary sources only | `NEW` | 5 | corpus inventory with source URLs + hit rate |
| D4 | Scheme discovery & eligibility answering | none | core addition | `/api/knowledge/schemes` + eligibility strictly from retrieved text | `NEW` | 5 | query → answer → citation screenshots |
| D5 | Loan / Kisan Credit Card information | none | core addition | retrieval + comparison with citations | `NEW` | 5 | answered query with 2+ real citations |
| D6 | Crop insurance information | none | core addition | premium/claim facts sourced only from documents | `NEW` | 5 | answered query + citation list |
| D7 | Subsidies, guidelines, required documents, application steps | none | core addition | "documents required" + "how to apply" answers from retrieval | `NEW` | 5 | checklist screenshot + citations |
| D8 | Source citation / traceability | none | core addition | every claim mapped to document + chunk id | `NEW` | 4, 5 | citation payload + UI rendering |
| D9 | Conversational assistant with intent routing | none | core addition | router → tools → explanation, never inventing tool output | `NEW` | 6 | routing accuracy table |
| D10 | Hallucination guard / "information not found" | none | core addition | relevance threshold, context limit, explicit refusal | `NEW` | 4, 6 | negative-test transcript |
| D11 | Multilingual interaction | hidden Google-Translate widget | PRD-indicated | document the real behaviour as a browser feature, not a project module | `EXTEND` (documentation) | 8 | screenshot + honest limitation note |

---

## E. Engineering, operations, QA and research packaging

| # | Requirement (origin) | Existing implementation | PRD update | Required enhancement | Status | Phase | Evidence for the paper |
|---|---|---|---|---|---|---|---|
| E1 | Centralised configuration | `app/config.py` — instantiable, CWD-independent path resolution, `validate_startup()` | mandatory | all paths, limits, URLs, keys | **DONE** | 1 | `tests/test_config_and_migrations.py`; config table in `README.md` |
| E2 | Secret handling | all keys in `backend/.env` via env vars; `.env.example` placeholders only; live values stripped from `docs/archive` | mandatory | rotate the credentials exposed in git history | **DONE in code, rotation outstanding** | 1 | `.env.example`; `PROJECT_AUDIT.md` §0.3 |
| E3 | Database path & schema integrity | absolute path, versioned migrations with automatic backup, FK enforcement (migration 002) | mandatory | documented schema | **DONE** | 1 | `DATABASE_SCHEMA.md`; migration report |
| E4 | Logging & observability | `app/logging_config.py` — rotation, secret redaction, `X-Process-Time-Ms`, slow-request and 5xx logging | required | request ids, latency percentiles | `PARTIAL` | 1, 9 | sample log lines (Phase 9 adds percentiles) |
| E5 | Error handling & validation | consistent `{"detail": ...}`, generic 500 with the detail in the log, upload validation, `readJson` on the client | required | frontend error surfaces per view | `PARTIAL` | 1, 2 | `test_system_info_exposes_no_filesystem_paths_or_secrets`, upload tests |
| E6 | Performance | CUDA inference, warm-up at startup, latency header, inference runs off the event loop | required if <5 s target | measured p50/p95 study | `PARTIAL` — instrumented but not yet measured | 3, 9 | **measured latency tables pending Phase 9** |
| E7 | Automated tests | `tests/` — 108 pytest tests: auth, authorisation/IDOR, validation, Version-1 regression, rules, config, migrations | required | security, ML and RAG suites | `PARTIAL` | 9 | `TEST_PLAN.md` + run output; ML/RAG suites pending |
| E8 | API documentation | 30 endpoints documented in `API_DOCUMENTATION.md`; OpenAPI tags and summaries live at `/docs` | required | keep in sync with the code | **DONE** | 2, 10 | `API_DOCUMENTATION.md` |
| E9 | Setup documentation | `README.md` — problem, objectives, features, architecture, stack, modules, setup, env vars, running, testing, methodology, limitations, future work | required | — | **DONE** | 1 | README link in the paper |
| E10 | Dependency management | `requirements.txt` pinned to the verified versions; `twilio`/`timm` removed; canonical interpreter documented | required | automated scanning / CI | `DONE` (scanning pending) | 1 | dependency table in the README |
| E11 | Repository cleanup | archive of Version-1 sources, duplicate model tree and one-off script deleted, `.gitignore` added, live DB and secrets excluded | required | — | **DONE** | 1 | cleanup log in `PROJECT_AUDIT.md` §0.1 (B17) |
| E12 | Architecture documentation | `ARCHITECTURE.md` — components, layers, request/data/auth flows, error handling, observability | required | paper/PPT diagram | **DONE** (diagram file pending) | 10 | `ARCHITECTURE.md` |
| E13 | Dataset + experiment records | `LIMITATIONS.md` records what is missing and why | required | `research_paper_data/*.md` | `PARTIAL` | 9, 10 | dataset cards (Phase 9) |
| E14 | Literature survey (~20-25 papers) | not in the repository (the original paper and PPT were never provided) | required by review | thematic survey with gap mapping | `NEW` — **blocked on the author** | 10 | reference list + gap table |
| E15 | Evidence package for the second review | none | required | `research_evidence/` with numbered screenshots and measurements | `NEW` | 10 | numbered evidence files |
| E16 | Final report | none | required | `FINAL_PROJECT_REPORT.md` | `NEW` | 10 | report link |

---

## Summary counts

| Status | Count | Meaning |
|---|---|---|
| `DONE` | 22 | implemented and verified by a test or a live check |
| `PRESERVE` | 4 | working; later phases must not regress it |
| `PARTIAL` | 7 | substantially present, a documented gap remains |
| `EXTEND` | 7 | present, to be deepened per the PRD |
| `FIX` | 0 | no outstanding incorrect/insecure implementation |
| `NEW` | 13 | not implemented anywhere |

**Reading order for the review:** `PROJECT_AUDIT.md` §0 (current state) → this
matrix → `ARCHITECTURE.md` → `API_DOCUMENTATION.md` → `DATABASE_SCHEMA.md` →
`TEST_PLAN.md` → `LIMITATIONS.md`.

**Honesty rules carried into the paper**

1. No metric is reported unless produced by a script in `research_paper_data/` or `tests/`.
2. Simulated values (market prices, soil moisture, solar radiation, livestock guidance) are labelled simulated or estimated wherever they appear.
3. The watering/fertiliser/climate modules are described as **rule-based decision engines**, not learned models.
4. The disease model is reported with **38 classes** and MobileNetV2, and its accuracy is reported only after a held-out evaluation exists.
5. Anything still unfinished is listed in `LIMITATIONS.md` and in the `PARTIAL`/`NEW` rows above, not implied as complete.

---

## Phase 1 + Phase 2 exit criteria

| Criterion | Result |
|---|---|
| All 15 Version-1 features still work | **PASS** — `tests/test_api_smoke.py` plus a manual frontend checklist in `TEST_PLAN.md` §6 |
| Authentication is secure | **PASS** — bcrypt + JWT, spoofed header rejected (live 401) |
| User data isolation works | **PASS** — 21 authorisation tests, FKs enforced |
| Database works reliably | **PASS** — 108 tests, migration 002 applied, `integrity_check = ok` |
| Existing ML model works | **PASS** — live prediction path, CUDA, 38 classes |
| Market data is not falsely represented as live | **PASS** — labelled in API and UI |
| No secret in source | **PASS** — rotation still required |
| Documentation exists | **PASS** for README, ARCHITECTURE, API, DATABASE_SCHEMA, TEST_PLAN, LIMITATIONS; **pending** the research package |
| Measured metrics | **NOT YET** — `[METRIC TO BE MEASURED]`, Phase 9 |

---



