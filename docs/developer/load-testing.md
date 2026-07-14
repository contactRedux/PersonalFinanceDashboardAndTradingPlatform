# Load Testing with k6

QuantNexus uses [k6](https://k6.io) for load and performance testing.
Two scripts live in `tests/load/`:

| Script | Target | Scenario |
|---|---|---|
| `ws_market.js` | `GET /ws/market` (WebSocket) | 1 000 concurrent subscribers |
| `rest_auth.js` | REST API flow | 200 req/s constant arrival rate |

---

## 1. Installing k6

### macOS (Homebrew)

```bash
brew install k6
```

### Linux (Debian / Ubuntu)

```bash
sudo gpg -k
sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69

echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list

sudo apt-get update && sudo apt-get install k6
```

### Docker (no local install required)

```bash
docker run --rm -i grafana/k6 run - < tests/load/ws_market.js
docker run --rm -i grafana/k6 run - < tests/load/rest_auth.js
```

---

## 2. Running the scripts

### Quick start (local dev stack must be running)

```bash
# Start the full stack first
make dev

# In a second terminal — run both scripts sequentially
make load-test
```

### Run individually

```bash
# WebSocket market-data test
k6 run tests/load/ws_market.js

# REST auth + portfolio flow
k6 run tests/load/rest_auth.js
```

### Target a different environment

```bash
# WebSocket test against a staging server
BASE_URL=ws://staging.quantnexus.internal \
  k6 run tests/load/ws_market.js

# REST test against staging (HTTP)
BASE_URL=https://staging.quantnexus.internal \
  k6 run tests/load/rest_auth.js
```

---

## 3. Configuration environment variables

| Variable | Default | Applies to | Description |
|---|---|---|---|
| `BASE_URL` | `ws://localhost:8000` | `ws_market.js` | WebSocket server base URL (ws:// or wss://) |
| `BASE_URL` | `http://localhost:8000` | `rest_auth.js` | REST server base URL (http:// or https://) |
| `TEST_USER` | `loadtest@example.com` | `rest_auth.js` | Login e-mail for the test account |
| `TEST_PASS` | `loadtest_password` | `rest_auth.js` | Login password for the test account |

> **Note:** `BASE_URL` is shared between both scripts but carries a different
> default scheme (`ws://` vs `http://`). Always set it explicitly when both
> scripts are run against a remote environment.

---

## 4. Interpreting results

k6 prints a summary table at the end of each run. Below are the key metrics and
what they mean for QuantNexus.

### `ws_market.js` — key metrics

```
ws_msg_latency_ms.........: avg=12ms  p(90)=45ms  p(99)=87ms  ✓ threshold p(99)<100ms
ws_messages_received......: 142 890  238.15/s
ws_subscribe_errors.......: 0
```

| Metric | Threshold | Meaning |
|---|---|---|
| `ws_msg_latency_ms p(99)` | **< 100 ms** | 99 % of first-message round trips must be under 100 ms |
| `ws_subscribe_errors` | **= 0** | No failed subscription handshakes |
| `ws_messages_received` | — | Total messages pushed by the server across all VUs |

### `rest_auth.js` — key metrics

```
http_req_duration..........: avg=38ms  p(90)=120ms  p(99)=430ms  ✓ threshold p(99)<500ms
http_error_rate............: 0.00%                               ✓ threshold rate<0.001
iterations.................: 6 000   200.00/s
```

| Metric | Threshold | Meaning |
|---|---|---|
| `http_req_duration p(99)` | **< 500 ms** | 99 % of all HTTP requests complete in under 500 ms |
| `http_error_rate` | **< 0.1 %** | Fraction of requests that returned a non-2xx status |
| `iterations` | — | Completed auth→portfolio flows; should equal `rate × duration` |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All thresholds passed |
| `99` | One or more thresholds failed |
| `107` | Could not connect to the target host |

A non-zero exit code causes `make load-test` (and any CI step) to fail,
preventing a merge if performance regresses.

---

## 5. Running in CI (GitHub Actions example)

```yaml
# .github/workflows/load-test.yml
name: Load Tests

on:
  pull_request:
    branches: [main]

jobs:
  k6:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install k6
        run: |
          sudo gpg --no-default-keyring \
            --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
            --keyserver hkp://keyserver.ubuntu.com:80 \
            --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] \
            https://dl.k6.io/deb stable main" \
            | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update && sudo apt-get install -y k6

      - name: Start stack
        run: docker compose up -d --wait

      - name: Run load tests
        run: make load-test
        env:
          BASE_URL: http://localhost:8000
```

---

## 6. Running in CI

The load test job is triggered manually:
1. Go to GitHub Actions
2. Select "CI" workflow
3. Click "Run workflow"
4. The `load-test` job runs after backend and frontend checks pass

---

## 7. Extending the test suite

To add a new script:

1. Create `tests/load/<name>.js` following the patterns in the existing scripts.
2. Export an `options` object with `stages` or `scenarios` and `thresholds`.
3. Add `k6 run tests/load/<name>.js` to the `load-test` Makefile target.
4. Document the script in the table at the top of this file.
