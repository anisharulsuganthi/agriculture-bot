# TEST PLAN

Scope, cases and results for the automated test suite in `tests/`.

- **Suite:** `pytest` with the FastAPI `TestClient`
- **Runner:** `& "C:\Users\Dhanush\AppData\Local\Programs\Python\Python310\python.exe" -m pytest tests`
- **Configuration:** `pytest.ini` (test discovery, strict markers)
- **Isolation:** every test runs against a temporary SQLite database; the demo
  data in `backend/database.db` is never touched.

---

## 1. Why this suite exists

`PROJECT_AUDIT.md` found 12 security risks and 17 functional defects in Version 1,
including two **critical** ones: any client could impersonate any account with a
forged `X-User-Id` header, and nine routes had no ownership check at all. No test
existed, so nothing prevented those defects from returning. The suite therefore has
two jobs:

1. **Lock in the security fixes** so they cannot silently regress.
2. **Act as the Phase 1 exit gate** - the audit required proof that all 15
   previously working features still work after the stabilisation work.

---

## 2. Test files

| File | Area | Tests |
|---|---|---|
| `tests/conftest.py` | Fixtures: temp database, per-test truncation, account helpers | - |
| `tests/test_auth.py` | Registration, login, tokens, password storage, OTP reset, legacy header rejection | 26 |
| `tests/test_authorization.py` | Authentication requirements, user isolation / IDOR, upload validation, notification relay | 21 |
| `tests/test_api_smoke.py` | Regression of every Version-1 feature, dashboards, advisory, market data | 22 |
| `tests/test_recommendations.py` | Crop vocabulary, watering/fertiliser rules, soil-moisture estimate, climate rules, label semantics | 25 |
| `tests/test_config_and_migrations.py` | Path resolution, secret hygiene, production safety checks, rate limiter, migrations, FK enforcement | 14 |
| **Total** | | **108** |

---

## 3. Coverage by requirement

### 3.1 Authentication
- register returns a user **and** an access token; the password is never echoed
- duplicate e-mail is rejected; malformed e-mail is rejected
- weak passwords rejected (below the minimum, blank, above bcrypt's 72-byte limit)
- login succeeds, wrong password fails, and an unknown account is
  **indistinguishable** from a wrong password (no account enumeration)
- `/api/auth/me` requires a token, accepts a valid one, rejects a tampered token
  and a token signed with another secret
- passwords are stored as bcrypt hashes; the plaintext never appears in the row
- Version-1 SHA-256 hashes still verify **and** are transparently upgraded to
  bcrypt on the next successful login
- forgot-password always answers generically, whether or not the account exists
- a wrong OTP is rejected, attempts are capped, and the OTP is stored only as a
  keyed digest (never plaintext, never a bare number)

### 3.2 Authorisation (the critical findings)
- `X-User-Id` alone authenticates **nobody** on any data route
- `X-User-Id` cannot be used to reach another account's data
- unauthenticated access to every data route returns 401
- a second account sees zero rows where the first sees data
- a second account receives **403** for another user's plant session: read logs,
  write logs, harvest, notify
- the same for animal sessions: read logs, write logs, close-out
- dashboards do not leak another account's totals
- prediction history stays private
- the advisory email recipient cannot be redirected to a third party

### 3.3 Input validation
- a non-image content type is rejected (400)
- a disallowed image extension is rejected (400)
- bytes that claim to be a PNG but are not decodable never reach the model (400)
- harvest/close-out cannot be replayed over a recorded close (409)

### 3.4 Version-1 regression (the Phase 1 exit gate)
Each of the 15 behaviours the audit verified as working before the changes:

health, crop vocabulary, create/list plant sessions, crop-name normalisation,
daily-log lifecycle, harvest with revenue, animal sessions with logs and
close-out, plant dashboard summary **and** analytics (including the requirement
that the two agree on investment), animal dashboard analytics, session weather,
recommendations (stability of the soil-moisture estimate, rule traceability,
presence of the ET0 estimate), recommendation logging, market intelligence
labelled as simulated, market determinism, and per-user statistics.

### 3.5 Decision rules
- crop names normalise case and whitespace; unknown crops are reported as
  unsupported rather than silently given another crop's advice
- watering rules: dry soil, heavy forecast rain, extreme heat
- every advice payload names the rule that fired, reports the soil-moisture
  provenance and declares `method: rule_based_decision_engine`
- the soil-moisture estimate is deterministic and responds correctly to
  irrigation, rain and soil retention
- fungal risk rises with humidity and temperature; the forecast scan finds the
  worst day; an empty forecast is handled
- ET0 is positive, rises with the temperature range, and states that it is not
  Penman-Monteith
- disease severity comes from the class name, never from the confidence score

### 3.6 Configuration, rate limiting, migrations
- relative paths resolve against the project root; absolute paths are preserved
- `as_public_dict()` exposes neither filesystem paths nor secrets
- a missing `JWT_SECRET` still yields a working ephemeral secret **and** is
  reported by `validate_startup()`
- production refuses `ALLOW_LEGACY_USER_HEADER` and `ALLOW_SIMULATED_WEATHER`
- the API binds to loopback by default; the legacy header is off by default
- the rate limiter blocks after its limit, is keyed per identity, and ignores
  `X-Forwarded-For` unless a trusted proxy is declared
- migrations are idempotent, the ledger is written, and `PRAGMA foreign_keys`
  reports 1

---

## 4. Out of scope (and why)

| Not covered | Reason |
|---|---|
| Live weather provider | The suite must pass offline. Weather is stubbed at the service boundary in `test_api_smoke.py`; the real provider is exercised manually against the running instance. |
| Real model inference | Loading 9 MB of weights and running a forward pass on every test run is slow and machine dependent. The pure helpers (`severity_from_label`, `is_healthy_label`, upload validation) are covered; end-to-end inference is verified manually. |
| SMTP delivery | No mail server in CI. The advisory path is covered up to the send call, and the SMTP service is verified manually. |
| Frontend automated tests | The SPA has no build step and no test runner. The regression gate for the frontend is the manual checklist in section 6. |
| Load/performance testing | Deferred to Phase 9, which produces the measured latency tables for the paper. |

---

## 5. Result of the latest run

```
$ python -m pytest tests
........................................................................ [ 66%]
....................................                                     [100%]
108 passed in 22.80s
```

No test is skipped, and no test asserts a behaviour that is not implemented.

---

## 6. Manual regression checklist (frontend)

Run with the backend on `:8000` and the static server on `:5500`.

| # | Step | Expected |
|---|---|---|
| 1 | Open the app, log in with an existing account | Home view renders, token stored, no console error |
| 2 | Reload the page | Session restored via the stored token, profile loads |
| 3 | Open Plant Farm, create a session | Session appears in the list and in the climate dropdown |
| 4 | Select the session in the climate dashboard | Weather, risk, watering and fertiliser cards populate; the moisture value is labelled as an estimate |
| 5 | Add a daily log, then open Manage | Log appears with its notes |
| 6 | Harvest the session | Success alert with revenue; the session moves to *Harvested* |
| 7 | Repeat the harvest | Clear "already harvested" message (no silent overwrite) |
| 8 | Open Animal Farm, add a log, close the session | Yields and sale revenue appear in the summary |
| 9 | Open Analytics | Charts render; the plant and animal investment totals agree with the summary |
| 10 | Open Market Intelligence | Every price panel is badged *simulated*; the warning banner is visible |
| 11 | Upload a leaf photo | Annotated image, top-5 table, uncertainty-aware badge, model metadata line |
| 12 | Upload a non-leaf photo | The result is badged *Uncertain - expert review needed*, not *Infected* |
| 13 | Click "Send advisory" | Confirmation that it was sent to the account address (no email prompt) |
| 14 | Log out, then press browser Back | Protected views require login again |

---

## 7. Adding tests

- Put shared fixtures in `tests/conftest.py`; keep test files focused on one area.
- Anything that needs the network or the model must stub the service boundary
  (`monkeypatch.setattr("main.get_current_weather", ...)`) rather than skip.
- New security fixes must arrive with a test that fails on the old code. The
  `test_legacy_user_id_header_is_rejected` family is the model: it documents the
  Version-1 defect and the behaviour that replaces it.
- Mark genuinely slow cases with `@pytest.mark.slow` so they can be deselected
  with `-m "not slow"`.
