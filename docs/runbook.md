# Factory — Operational Runbook

Reference for anyone on-call or debugging a live issue.
Start at the alert or symptom. Follow the section. Know when to escalate.

---

## Log access

```bash
# Live tail on the VPS
journalctl -u factory -f

# Last 100 lines
journalctl -u factory -n 100

# Since a specific time
journalctl -u factory --since "2025-03-04 14:00:00"

# Filter to a single session
journalctl -u factory -f | grep '"session_id": "a1b2c3d4"'

# Filter to Claude calls only
journalctl -u factory | grep claude.call

# Filter to warnings and above
journalctl -u factory -p warning
```

In development (`JSON_LOGS=false`), logs are coloured console output.
In production (`JSON_LOGS=true`), every log line is a JSON object on stdout.

---

## Key log events

| Event                      | Level        | When                                              |
|----------------------------|--------------|---------------------------------------------------|
| `factory.startup`          | INFO         | App started — confirms model and debug flag       |
| `factory.shutdown`         | INFO         | Graceful shutdown                                 |
| `http.request`             | INFO/WARNING | Every HTTP request — method, path, status, duration_ms |
| `session.created`          | INFO         | New session started                               |
| `claude.call`              | INFO         | Every Claude API call — tokens in/out, latency    |
| `claude.call_failed`       | ERROR        | Claude call threw an exception                    |
| `claude.json_parse_failed` | WARNING      | Claude returned non-JSON — prompt injection canary|
| `stage.assessed`           | INFO         | Verdict recorded for a stage                      |
| `session.flagged`          | WARNING      | Probe limit hit — human review needed             |
| `session.complete`         | INFO         | Session reached EVALUATE state                    |
| `health.anthropic_key_missing` | WARNING  | ANTHROPIC_API_KEY not set                         |

---

## Health check

```bash
# From VPS
curl -s http://localhost:8391/health | python3 -m json.tool

# Expected healthy response
{ "status": "ok" }

# Degraded response (something is wrong)
{ "status": "degraded", "checks": { "session_store": false } }
```

The health endpoint is public (no API key needed).
The deploy workflow checks it after every deployment.

---

## Alerts to set (Anthropic dashboard)

| Alert         | Threshold           | Action                          |
|---------------|---------------------|---------------------------------|
| Monthly spend | 50% of budget       | First warning before overage    |
| Monthly spend | 80% of budget       | Lower rate limits immediately   |
| Daily spend   | > expected daily    | Possible abuse or runaway session |

Configured in the Anthropic dashboard under Billing → Alerts. No code change needed.

---

## Incident playbooks

### Claude calls are failing

**Symptom:** `claude.call_failed` in logs. Users see 500 on stage submission.

```bash
# 1. Confirm the error
journalctl -u factory | grep claude.call_failed | tail -5

# 2. Check the API key is set
grep ANTHROPIC_API_KEY /app/.env

# 3. Test the key directly
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $(grep ANTHROPIC_API_KEY /app/.env | cut -d= -f2)" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}'
```

**If the key is invalid:** Rotate in the Anthropic dashboard → update `/app/.env` → `sudo systemctl restart factory`

**If Anthropic is down:** Check status.anthropic.com. Sessions in progress will fail on the next Claude call. The FSM preserves state — they can resume once the API recovers.

---

### Rate limit being hit unexpectedly

**Symptom:** 429 responses in logs. Legitimate users blocked.

```bash
# See which API key is hitting the limit
journalctl -u factory | grep '"status_code": 429' | grep api_key_id

# Count 429s in the last hour
journalctl -u factory --since "1 hour ago" | grep '"status_code": 429' | wc -l
```

**If legitimate traffic is high:** Raise limits in `/app/.env`:
```bash
RATE_LIMIT_SESSIONS_PER_HOUR=50
RATE_LIMIT_SUBMITS_PER_HOUR=200
```
Then `sudo systemctl reload factory`.

---

### Claude returning non-JSON

**Symptom:** `claude.json_parse_failed` warnings in logs. Users see errors on stage submission.

```bash
journalctl -u factory | grep claude.json_parse_failed
```

Each warning includes `template` (which Jinja2 template) and `preview` (first 200 chars of the response).

**Sporadic (< 1% of calls):** Claude occasionally wraps JSON in markdown fences. The parser handles this automatically.

**Frequent:** Candidate input may be breaking the prompt contract. Check the `preview` field for injected instructions.

---

### App crashed / not responding

```bash
sudo systemctl status factory
sudo systemctl restart factory
journalctl -u factory -f

# If restart fails — check for port conflict
ss -tlnp | grep 8391
sudo fuser -k 8391/tcp
sudo systemctl start factory
```

---

### Session flagged — needs human review

**Symptom:** `session.flagged` in logs. Candidate stuck on flagged page.

```bash
journalctl -u factory | grep session.flagged
```

Review at `GET /session/{id}/flagged`.
Resolve via `POST /session/{id}/flagged/review` with `{"action": "retry" | "skip" | "evaluate"}`.

---

### High latency on stage submission

**Symptom:** `http.request` shows `duration_ms` > 3000ms on POST `.../submit`.

```bash
journalctl -u factory | grep http.request | grep submit | tail -20
journalctl -u factory | grep claude.call | tail -20
```

Claude p50 ~800ms, p95 ~2500ms. Consistently over 4000ms is unusual.

Check: status.anthropic.com — elevated latency on their end.
Check: `htop` on the droplet — CPU/memory pressure.
Check: `prompt_chars` in the `claude.call` log line — unusually long prompt.

---

## Manual deploy

```bash
cd /app
git pull
uv sync --frozen --no-dev
sudo systemctl restart factory
curl -s http://localhost:8391/health
```

---

## Rotating FACTORY_API_KEY

```bash
# 1. Generate new key
python3 -c "import secrets; print(secrets.token_hex(32))"

# 2. Update .env
nano /app/.env

# 3. Reload — reads .env without dropping connections
sudo systemctl reload factory

# 4. Verify
curl http://localhost:8391/health

# 5. Update all clients with the new key
```

---

## Checking token spend

```bash
# Total Claude calls today
journalctl -u factory --since today | grep claude.call | wc -l

# Token totals today
journalctl -u factory --since today -o json \
  | python3 -c "
import sys, json
total_in = total_out = 0
for line in sys.stdin:
    try:
        entry = json.loads(line)
        msg = entry.get('MESSAGE', '')
        if isinstance(msg, str) and 'claude.call' in msg:
            data = json.loads(msg)
            total_in  += data.get('input_tokens', 0)
            total_out += data.get('output_tokens', 0)
    except: pass
print(f'Input tokens today:  {total_in:,}')
print(f'Output tokens today: {total_out:,}')
"
```
