"""
AI Coach Feedback System — Flask app for Render + Supabase
=============================================================
Database via Supabase REST API (no psycopg2 needed)
"""
import os, json, urllib.request, urllib.error, urllib.parse
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timezone

app = Flask(__name__, static_folder="static")

# ── Supabase config ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://emvtxprnsrycfevpkfym.supabase.co")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtdnR4cHJuc3J5Y2ZldnBrZnltIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk2ODc5MzksImV4cCI6MjA5NTI2MzkzOX0."
    "Vb8MP85N9alfSraH4KL72_7GDeSRrPi0UkhS9snCSBY"
)

REST_URL = f"{SUPABASE_URL}/rest/v1/feedback"
HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Prefer": "return=representation",
}


def supabase_request(method, path="", params=None, body=None):
    """Helper to call Supabase REST API."""
    url = REST_URL + path
    if params:
        qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
        url += "?" + qs

    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        print(f"[Supabase] HTTP {e.code}: {e.read().decode()[:200]}")
        return {"error": e.code}
    except Exception as e:
        print(f"[Supabase] Error: {e}")
        return {"error": str(e)}


def db_healthy():
    """Quick check if Supabase is reachable."""
    r = supabase_request("GET", "", {"select": "count", "limit": "1"})
    return isinstance(r, list)


# ── In-memory fallback ──
memory_store = []
MEMORY_ONLY = False


# ── Routes ──

@app.route("/")
def serve_survey():
    return send_from_directory(app.static_folder, "survey.html")


@app.route("/dashboard")
def serve_dashboard():
    return send_from_directory(app.static_folder, "dashboard.html")


@app.route("/api/submit", methods=["POST"])
def submit_feedback():
    data = request.get_json(force=True)
    if not data or not data.get("overall"):
        return jsonify({"ok": False, "error": "Missing overall rating"}), 400

    overall = int(data["overall"])
    if overall < 1 or overall > 5:
        return jsonify({"ok": False, "error": "Invalid rating (1-5)"}), 400

    record = {
        "overall": overall,
        "difficulty": data.get("difficulty", ""),
        "length": data.get("length", ""),
        "strengthen": data.get("strengthen", []),
        "favorite": data.get("favorite", ""),
        "best_day": data.get("bestDay", ""),
        "worst_day": data.get("worstDay", ""),
        "format": data.get("format", []),
        "role": data.get("role", ""),
        "open_feedback": data.get("openFeedback", ""),
        "ip": request.remote_addr or "",
    }

    # Try Supabase
    if not MEMORY_ONLY:
        r = supabase_request("POST", "", body=record)
        if isinstance(r, dict) and r.get("error"):
            print(f"[Submit] Supabase failed, falling to memory: {r}")
            memory_store.append({**record, "id": len(memory_store) + 1, "submitted_at": datetime.now(timezone.utc).isoformat()})
            return jsonify({"ok": True, "id": len(memory_store)})
        if isinstance(r, list) and len(r) > 0:
            return jsonify({"ok": True, "id": r[0].get("id", 0)})
        return jsonify({"ok": True, "id": 0})

    memory_store.append({**record, "id": len(memory_store) + 1})
    return jsonify({"ok": True, "id": len(memory_store)})


@app.route("/api/stats")
def get_stats():
    if MEMORY_ONLY:
        return jsonify(compute_stats_memory())

    # Get all records from Supabase
    r = supabase_request("GET", "")
    if not isinstance(r, list):
        return jsonify({"total": 0, "error": "db unavailable"})

    return jsonify(compute_stats(r))


def compute_stats(rows):
    n = len(rows)
    if n == 0:
        return {"total": 0}

    overall = {}
    difficulty = {}
    length = {}
    strengthen = {}
    favorite = {}
    fmt = {}
    role = {}
    best_day = {}
    worst_day = {}
    total_overall = 0

    for r in rows:
        o = r.get("overall", 0)
        total_overall += o
        overall_key = f"{o}★"
        overall[overall_key] = overall.get(overall_key, 0) + 1

        d = r.get("difficulty", "") or "未填"
        difficulty[d] = difficulty.get(d, 0) + 1

        l = r.get("length", "") or "未填"
        length[l] = length.get(l, 0) + 1

        for s in _parse_pgarray(r.get("strengthen", [])):
            strengthen[s] = strengthen.get(s, 0) + 1

        f = r.get("favorite", "") or "未填"
        favorite[f] = favorite.get(f, 0) + 1

        for fm in _parse_pgarray(r.get("format", [])):
            fmt[fm] = fmt.get(fm, 0) + 1

        ro = r.get("role", "") or "未填"
        role[ro] = role.get(ro, 0) + 1

        bd = r.get("best_day", "")
        if bd:
            best_day[bd] = best_day.get(bd, 0) + 1

        wd = r.get("worst_day", "")
        if wd:
            worst_day[wd] = worst_day.get(wd, 0) + 1

    return {
        "total": n,
        "overall_avg": round(total_overall / n, 1) if n else 0,
        "overall": dict(sorted(overall.items())),
        "difficulty": dict(sorted(difficulty.items(), key=lambda x: -x[1])),
        "length": dict(sorted(length.items(), key=lambda x: -x[1])),
        "strengthen": dict(sorted(strengthen.items(), key=lambda x: -x[1])),
        "favorite": dict(sorted(favorite.items(), key=lambda x: -x[1])),
        "format": dict(sorted(fmt.items(), key=lambda x: -x[1])),
        "role": dict(sorted(role.items(), key=lambda x: -x[1])),
        "bestDay": dict(sorted(best_day.items(), key=lambda x: -x[1])),
        "worstDay": dict(sorted(worst_day.items(), key=lambda x: -x[1])),
    }


def compute_stats_memory():
    """Fallback stats from in-memory store."""
    return compute_stats(memory_store)


def _parse_pgarray(val):
    """Parse PostgreSQL text array {a,b,c} into list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.startswith("{"):
        return [v.strip() for v in val.strip("{}").split(",") if v.strip()]
    return []


@app.route("/data/responses")
def get_responses():
    if MEMORY_ONLY:
        return jsonify(list(reversed(memory_store)))
    r = supabase_request("GET", "", {"order": "submitted_at.desc", "limit": "100"})
    if isinstance(r, list):
        return jsonify(r)
    return jsonify([])


@app.route("/health")
def health():
    # Detailed debug
    info = {
        "ok": True,
        "supabase_url": SUPABASE_URL,
        "anon_key_set": bool(SUPABASE_ANON_KEY),
        "rest_url": REST_URL,
        "memory_fallback": MEMORY_ONLY,
    }
    try:
        r = supabase_request("GET", "", {"select": "count", "limit": "1"})
        info["db_raw_response"] = str(r)[:200]
        info["database"] = isinstance(r, list)
    except Exception as e:
        info["db_error"] = str(e)
        info["database"] = False
    return jsonify(info)


# ── Startup ──
def main():
    global MEMORY_ONLY
    if not db_healthy():
        MEMORY_ONLY = True
        print("[START] Supabase unreachable — using in-memory (data lost on restart)")

    port = int(os.environ.get("PORT", 8080))
    print(f"[START] Server running on port {port}")
    print(f"[START] Survey   → http://0.0.0.0:{port}/")
    print(f"[START] Dashboard→ http://0.0.0.0:{port}/dashboard")
    print(f"[START] DB Mode  → {'Supabase REST' if not MEMORY_ONLY else 'In-Memory'}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()