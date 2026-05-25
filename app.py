"""
AI Coach Feedback System — Flask app for Render + Supabase
=============================================================
Deploy: push to GitHub → connect in Render dashboard
Database: Supabase PostgreSQL (free tier)
"""
import os, json
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse

app = Flask(__name__, static_folder="static")

# ── Database connection ──
DATABASE_URL = os.environ.get("DATABASE_URL", "")
# Render may provide the connection string as a direct URL
# Supabase gives: postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres
conn_pool = None


def get_db():
    global conn_pool
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        print(f"[DB] Connection error: {e}")
        return None


def init_db():
    """Create table if not exists."""
    conn = get_db()
    if not conn:
        print("[DB] No database configured — running in memory-only mode")
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id BIGSERIAL PRIMARY KEY,
                overall INTEGER NOT NULL CHECK (overall >= 1 AND overall <= 5),
                difficulty TEXT DEFAULT '',
                length TEXT DEFAULT '',
                strengthen TEXT[] DEFAULT '{}',
                favorite TEXT DEFAULT '',
                best_day TEXT DEFAULT '',
                worst_day TEXT DEFAULT '',
                format TEXT[] DEFAULT '{}',
                role TEXT DEFAULT '',
                open_feedback TEXT DEFAULT '',
                submitted_at TIMESTAMPTZ DEFAULT NOW(),
                ip TEXT DEFAULT ''
            );
        """)
        conn.commit()
        cur.close()
        print("[DB] Table initialized")
        return True
    except Exception as e:
        print(f"[DB] Init error: {e}")
        return False
    finally:
        conn.close()


# ── Fallback: in-memory storage (when no DB) ──
memory_store = []
memory_enabled = False


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

    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO feedback
                   (overall, difficulty, length, strengthen, favorite,
                    best_day, worst_day, format, role, open_feedback, ip)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    overall,
                    data.get("difficulty", ""),
                    data.get("length", ""),
                    data.get("strengthen", []),
                    data.get("favorite", ""),
                    data.get("bestDay", ""),
                    data.get("worstDay", ""),
                    data.get("format", []),
                    data.get("role", ""),
                    data.get("openFeedback", ""),
                    request.remote_addr or "",
                ),
            )
            conn.commit()
            row_id = cur.fetchone()
            cur.close()
            conn.close()
            return jsonify({"ok": True, "id": row_id[0] if row_id else 0})
        except Exception as e:
            conn.close()
            return jsonify({"ok": False, "error": str(e)}), 500
    else:
        # Fallback: in-memory
        record = {
            "id": len(memory_store) + 1,
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
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "ip": request.remote_addr or "",
        }
        memory_store.append(record)
        return jsonify({"ok": True, "id": record["id"]})


@app.route("/api/stats")
def get_stats():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT COUNT(*) as total FROM feedback")
            total = cur.fetchone()["total"]

            if total == 0:
                cur.close()
                conn.close()
                return jsonify({"total": 0})

            # Overall average
            cur.execute("SELECT ROUND(AVG(overall)::numeric, 1) as avg FROM feedback")
            overall_avg = float(cur.fetchone()["avg"] or 0)

            # Overall distribution
            cur.execute(
                "SELECT overall, COUNT(*) as cnt FROM feedback GROUP BY overall ORDER BY overall"
            )
            overall_dist = {str(r["overall"]) + "★": r["cnt"] for r in cur.fetchall()}

            # Difficulty
            cur.execute(
                "SELECT difficulty, COUNT(*) as cnt FROM feedback GROUP BY difficulty ORDER BY cnt DESC"
            )
            difficulty = {r["difficulty"] or "未填": r["cnt"] for r in cur.fetchall()}

            # Length
            cur.execute(
                "SELECT length, COUNT(*) as cnt FROM feedback GROUP BY length ORDER BY cnt DESC"
            )
            length = {r["length"] or "未填": r["cnt"] for r in cur.fetchall()}

            # Strengthen (unnest array)
            cur.execute(
                """SELECT unnest(strengthen) as val, COUNT(*) as cnt
                   FROM feedback GROUP BY val ORDER BY cnt DESC"""
            )
            strengthen = {r["val"]: r["cnt"] for r in cur.fetchall()}

            # Favorite
            cur.execute(
                "SELECT favorite, COUNT(*) as cnt FROM feedback GROUP BY favorite ORDER BY cnt DESC"
            )
            favorite = {r["favorite"] or "未填": r["cnt"] for r in cur.fetchall()}

            # Format (unnest array)
            cur.execute(
                """SELECT unnest(format) as val, COUNT(*) as cnt
                   FROM feedback GROUP BY val ORDER BY cnt DESC"""
            )
            fmt = {r["val"]: r["cnt"] for r in cur.fetchall()}

            # Role
            cur.execute(
                "SELECT role, COUNT(*) as cnt FROM feedback GROUP BY role ORDER BY cnt DESC"
            )
            role = {r["role"] or "未填": r["cnt"] for r in cur.fetchall()}

            # Best day
            cur.execute(
                "SELECT best_day, COUNT(*) as cnt FROM feedback WHERE best_day != '' GROUP BY best_day ORDER BY cnt DESC"
            )
            best_day = {r["best_day"]: r["cnt"] for r in cur.fetchall()}

            # Worst day
            cur.execute(
                "SELECT worst_day, COUNT(*) as cnt FROM feedback WHERE worst_day != '' GROUP BY worst_day ORDER BY cnt DESC"
            )
            worst_day = {r["worst_day"]: r["cnt"] for r in cur.fetchall()}

            cur.close()
            conn.close()

            return jsonify(
                {
                    "total": total,
                    "overall_avg": overall_avg,
                    "overall": overall_dist,
                    "difficulty": difficulty,
                    "length": length,
                    "strengthen": strengthen,
                    "favorite": favorite,
                    "format": fmt,
                    "role": role,
                    "bestDay": best_day,
                    "worstDay": worst_day,
                }
            )
        except Exception as e:
            conn.close()
            return jsonify({"total": 0, "error": str(e)}), 500
    else:
        # In-memory fallback
        return compute_stats_memory()


def compute_stats_memory():
    responses = memory_store
    n = len(responses)
    if n == 0:
        return jsonify({"total": 0})

    overall = {}
    difficulty = {}
    length = {}
    strengthen = {}
    favorite = {}
    fmt = {}
    role = {}
    best_day = {}
    worst_day = {}

    for r in responses:
        o = r.get("overall", 0)
        k = f"{o}★"
        overall[k] = overall.get(k, 0) + 1

        d = r.get("difficulty", "") or "未填"
        difficulty[d] = difficulty.get(d, 0) + 1

        l = r.get("length", "") or "未填"
        length[l] = length.get(l, 0) + 1

        for s in r.get("strengthen", []):
            strengthen[s] = strengthen.get(s, 0) + 1

        f = r.get("favorite", "") or "未填"
        favorite[f] = favorite.get(f, 0) + 1

        for fm in r.get("format", []):
            fmt[fm] = fmt.get(fm, 0) + 1

        ro = r.get("role", "") or "未填"
        role[ro] = role.get(ro, 0) + 1

        bd = r.get("best_day", "")
        if bd:
            best_day[bd] = best_day.get(bd, 0) + 1

        wd = r.get("worst_day", "")
        if wd:
            worst_day[wd] = worst_day.get(wd, 0) + 1

    overall_avg = round(
        sum(r.get("overall", 0) for r in responses) / n, 1
    )

    return jsonify(
        {
            "total": n,
            "overall_avg": overall_avg,
            "overall": overall,
            "difficulty": dict(sorted(difficulty.items(), key=lambda x: -x[1])),
            "length": dict(sorted(length.items(), key=lambda x: -x[1])),
            "strengthen": dict(sorted(strengthen.items(), key=lambda x: -x[1])),
            "favorite": dict(sorted(favorite.items(), key=lambda x: -x[1])),
            "format": dict(sorted(fmt.items(), key=lambda x: -x[1])),
            "role": dict(sorted(role.items(), key=lambda x: -x[1])),
            "bestDay": dict(sorted(best_day.items(), key=lambda x: -x[1])),
            "worstDay": dict(sorted(worst_day.items(), key=lambda x: -x[1])),
        }
    )


@app.route("/data/responses")
def get_responses():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM feedback ORDER BY submitted_at DESC LIMIT 100")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify([dict(r, submitted_at=str(r["submitted_at"])) for r in rows])
        except Exception as e:
            conn.close()
            return jsonify([])
    else:
        return jsonify(list(reversed(memory_store)))


@app.route("/health")
def health():
    conn = get_db()
    db_ok = conn is not None
    if conn:
        conn.close()
    return jsonify({"ok": True, "database": db_ok, "responses": len(memory_store)})


# ── Startup ──
def main():
    global memory_enabled
    db_ok = init_db()
    if not db_ok:
        memory_enabled = True
        print("[START] No database — using in-memory storage (data lost on restart)")

    port = int(os.environ.get("PORT", 8080))
    print(f"[START] Server running on port {port}")
    print(f"[START] Survey   → http://0.0.0.0:{port}/")
    print(f"[START] Dashboard→ http://0.0.0.0:{port}/dashboard")
    print(f"[START] Health   → http://0.0.0.0:{port}/health")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()