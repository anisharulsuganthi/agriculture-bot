# PROJECT AUDIT

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

<!-- CURSOR -->
