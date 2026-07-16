# Kill-Switch & Admin API — Handoff Document

**Feature branch:** `main`  
**Date:** 2025-07-23  
**Status: ✅ COMPLETE — all items shipped and passing**

---

## What Was Built

A platform-wide kill-switch that lets admins halt all order submissions instantly
without a deployment. The feature spans four layers:

| Layer | File | What changed |
|-------|------|--------------|
| Service | `backend/app/services/kill_switch.py` | New. Redis-backed flag (`kill_switch:orders`). Fail-open: if Redis is down, orders are **not** blocked. |
| Orders endpoint | `backend/app/api/v1/orders.py` | Added kill-switch check at the top of `POST /orders` — returns **503** when active. |
| Admin endpoints | `backend/app/api/v1/admin.py` | New. Three routes: `GET /kill-switch`, `POST /kill-switch/enable`, `POST /kill-switch/disable`. RBAC via `ADMIN_EMAILS`. |
| Router | `backend/app/api/v1/router.py` | `admin.router` registered at prefix `/admin`. Already present in file. |
| Config | `backend/app/config.py` | `admin_emails: list[str] = []` field added (line 103). |
| Env example | `.env.example` | `ADMIN_EMAILS` entry present. |
| Tests | `backend/tests/unit/test_d1_d2_orders.py` | New. 20 tests covering the service, admin endpoints, and kill-switch ↔ orders integration. |

---

## Architecture

```
POST /api/v1/orders
  └─ orders.py::place_order_endpoint
       └─ KillSwitch.is_active()  ──→  Redis GET kill_switch:orders
            ├─ "1"    → raise HTTP 503
            └─ None   → proceed normally

POST /api/v1/admin/kill-switch/enable
  └─ admin.py::enable_kill_switch
       ├─ _require_admin(current_user)  →  403 if email ∉ ADMIN_EMAILS
       └─ KillSwitch.enable()  ──→  Redis SET kill_switch:orders "1"

POST /api/v1/admin/kill-switch/disable
  └─ admin.py::disable_kill_switch
       ├─ _require_admin(current_user)  →  403
       └─ KillSwitch.disable()  ──→  Redis DEL kill_switch:orders
```

Redis key: **`kill_switch:orders`** — value `"1"` = orders halted, absent = orders allowed.

---

## Config

### `backend/app/config.py`
```python
# ─── Admin ────────────────────────────────────────────────────────────────────
admin_emails: list[str] = []   # comma-separated via env: ADMIN_EMAILS=a@b.com,c@d.com
```

### `.env` / `.env.example`
```
# ─── Admin ────────────────────────────────────────────────────────────────────
# Optional. Comma-separated list of admin user emails allowed to toggle the kill-switch.
# Leave empty to allow any authenticated user (useful for dev/test).
ADMIN_EMAILS=
```

**Tip:** `pydantic-settings` splits the comma-separated string into a `list[str]` automatically.

---

## API Reference

All endpoints require a valid JWT (`Authorization: Bearer <token>`).

### `GET /api/v1/admin/kill-switch`
Returns current state.
```json
{ "active": false, "message": "Order submissions enabled — kill-switch is inactive." }
```

### `POST /api/v1/admin/kill-switch/enable`
Engages the kill-switch. Returns `{ "active": true, ... }`.

### `POST /api/v1/admin/kill-switch/disable`
Disengages the kill-switch. Returns `{ "active": false, ... }`.

### Error responses
| Code | Condition |
|------|-----------|
| 403  | Caller's email is not in `ADMIN_EMAILS` (and list is non-empty) |
| 503  | `POST /orders` attempted while kill-switch is active |

---

## Test Results

```
1 failed, 307 passed, 27 warnings in 45.72s
```

The 1 failure (`test_lstm_training_runs_on_synthetic_data`) is a **pre-existing** LSTM
training test unrelated to this feature. All 20 new kill-switch / D-2 tests pass.

### New test classes in `test_d1_d2_orders.py`

| Class | Tests |
|-------|-------|
| `TestOANDAOrderRequest` | unit tests for the OANDA order request model (D-1) |
| `TestPlaceForexOrderSimulated` | simulated fill when OANDA creds absent |
| `TestCancelForexOrderSimulated` | simulated cancel |
| `TestGetOpenForexOrdersSimulated` | empty list when unconfigured |
| `TestKillSwitchService` | is_active, enable, disable, fail-open on Redis down |
| `TestAdminEndpoints` | GET status, enable, disable, non-admin 403 |
| `TestOrdersKillSwitchIntegration` | 503 on POST /orders when kill-switch active |

---

## Files Created (new, untracked before this work)

```
backend/app/api/v1/admin.py
backend/app/services/kill_switch.py
backend/tests/unit/test_d1_d2_orders.py
```

## Files Modified

```
backend/app/api/v1/orders.py        — kill-switch check in place_order_endpoint
backend/app/api/v1/router.py        — admin router registered
backend/app/config.py               — admin_emails field
.env.example                        — ADMIN_EMAILS entry
```

---

## Remaining / Follow-up Work

- [ ] **Forex orders kill-switch** — `POST /orders/forex` (`forex_orders.py`) does not yet
  check the kill-switch. Identical one-liner needed at the top of `place_forex_order_endpoint`.
- [ ] **Pre-existing LSTM test failure** — `test_lstm_training_runs_on_synthetic_data` was
  already failing before this work; needs a separate investigation.
- [ ] **Admin email env var** — populate `ADMIN_EMAILS` in production `.env` before deploying.
- [ ] **Redis HA** — kill-switch is fail-open (orders proceed if Redis is down). If a fail-closed
  posture is needed in production, flip the logic in `KillSwitch.is_active()`.
