"""Send one shop turn to Langfuse. Missing keys leave the chat unchanged."""
import base64
import hashlib
import json
import os
import threading
import time
import urllib.request
import uuid

_SECRET_KEYS = {
    "phone", "address", "email", "password", "token", "cookie",
    "authorization", "api_key", "secret", "secret_key",
}


def _scrub(value, depth=0):
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        kept = {}
        for key, item in value.items():
            if str(key).casefold() in _SECRET_KEYS:
                continue
            kept[key] = _scrub(item, depth + 1)
        return kept
    if isinstance(value, list):
        return [_scrub(item, depth + 1) for item in value[:8]]
    if isinstance(value, str):
        if value.startswith("sk-") and len(value) > 12:
            return "[redacted]"
        return value[:2000]
    return value


def _dump(value):
    return json.dumps(_scrub(value), ensure_ascii=False, default=str)


def _keys():
    public_set = "LANGFUSE_PUBLIC_KEY" in os.environ
    secret_set = "LANGFUSE_SECRET_KEY" in os.environ
    public = os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
    secret = os.environ.get("LANGFUSE_SECRET_KEY", "").strip()
    base = (os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST") or "").strip()
    if public and secret:
        return public, secret, base or "https://cloud.langfuse.com"
    # An explicit empty key disables tracing. The file is only for a server
    # that started before the keys were written into .env.
    if public_set or secret_set:
        return None
    path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    found = {}
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key in {"LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL", "LANGFUSE_HOST"}:
                    found[key] = value.strip().strip('"').strip("'")
    except OSError:
        return None
    public = public or found.get("LANGFUSE_PUBLIC_KEY", "")
    secret = secret or found.get("LANGFUSE_SECRET_KEY", "")
    base = base or found.get("LANGFUSE_BASE_URL") or found.get("LANGFUSE_HOST") or "https://cloud.langfuse.com"
    if not public or not secret:
        return None
    return public, secret, base


def _attr(key, value):
    return {"key": key, "value": {"stringValue": value}}


def _step_io(step):
    kind = step.get("type") or "SPAN"
    if kind == "TOOL":
        return "tool", _dump({"sent": step.get("sent"), "ran": step.get("ran")}), _dump(step.get("result"))
    if kind == "GENERATION":
        return "generation", _dump(step.get("input")), _dump({"text": step.get("text") or ""})
    output = {
        "text": step.get("text") or "",
        "requirements": step.get("arguments"),
        "tool": step.get("tool") or "",
        "model_action": step.get("model_action") or "",
    }
    return "span", _dump(step.get("input")), _dump(output)


def _payload(question, spoken, user):
    steps = list(spoken.get("trace") or [])
    end_ms = 0.0
    for step in steps:
        try:
            end_ms = max(end_ms, float(step.get("t1") or 0))
        except (TypeError, ValueError):
            continue
    now = time.time()
    origin = now - (end_ms / 1000.0)

    def nano(ms):
        return str(int((origin + (float(ms) / 1000.0)) * 1_000_000_000))

    trace_id = uuid.uuid4().hex
    root_id = uuid.uuid4().hex[:16]
    user_id = ""
    if isinstance(user, dict) and user.get("id") is not None:
        user_id = "shop-" + str(user.get("id"))
    token = (user or {}).get("token") if isinstance(user, dict) else ""
    session_id = hashlib.sha256(str(token).encode()).hexdigest()[:16] if token else ""
    shared = [
        _attr("langfuse.trace.name", "octopus-shop"),
        _attr("langfuse.user.id", user_id),
        _attr("langfuse.session.id", session_id),
    ]
    spans = [{
        "traceId": trace_id,
        "spanId": root_id,
        "name": (question or "octopus-shop")[:80],
        "kind": 1,
        "startTimeUnixNano": nano(0),
        "endTimeUnixNano": nano(end_ms or 1),
        "attributes": shared + [
            _attr("langfuse.observation.type", "agent"),
            _attr("langfuse.observation.input", _dump({"question": question or ""})),
            _attr("langfuse.observation.output", _dump({
                "text": spoken.get("text") or "",
                "text_from": spoken.get("text_from") or "",
            })),
            _attr("langfuse.trace.input", _dump({"question": question or ""})),
            _attr("langfuse.trace.output", _dump({"text": spoken.get("text") or ""})),
        ],
        "status": {"code": 1},
    }]
    for step in steps:
        obs_type, obs_input, obs_output = _step_io(step)
        attributes = shared + [
            _attr("langfuse.observation.type", obs_type),
            _attr("langfuse.observation.input", obs_input),
            _attr("langfuse.observation.output", obs_output),
        ]
        if obs_type == "generation" and step.get("name"):
            attributes.append(_attr("gen_ai.request.model", str(step.get("name"))))
        spans.append({
            "traceId": trace_id,
            "spanId": uuid.uuid4().hex[:16],
            "parentSpanId": root_id,
            "name": str(step.get("name") or obs_type)[:80],
            "kind": 1,
            "startTimeUnixNano": nano(step.get("t0") or 0),
            "endTimeUnixNano": nano(step.get("t1") or step.get("t0") or 0),
            "attributes": attributes,
            "status": {"code": 1},
        })
    return {
        "resourceSpans": [{
            "resource": {"attributes": [_attr("service.name", "octopus-store")]},
            "scopeSpans": [{"scope": {"name": "octopus-shop"}, "spans": spans}],
        }]
    }


def _post(url, body, public, secret):
    token = base64.b64encode((public + ":" + secret).encode()).decode()
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", "Basic " + token)
    request.add_header("x-langfuse-ingestion-version", "4")
    with urllib.request.urlopen(request, timeout=4) as response:
        response.read()


def publish_turn(question, spoken, user=None, send=None):
    """One customer turn becomes one Langfuse trace. A missing key does not raise."""
    found = _keys()
    if not found:
        return False
    public, secret, base = found
    body = _payload(question, spoken or {}, user)
    url = base.rstrip("/") + "/api/public/otel/v1/traces"
    if send is not None:
        send(url, body, {
            "Content-Type": "application/json",
            "x-langfuse-ingestion-version": "4",
        })
        return True
    threading.Thread(target=_safe_post, args=(url, body, public, secret), daemon=True).start()
    return True


def _safe_post(url, body, public, secret):
    try:
        _post(url, body, public, secret)
    except Exception:
        return
