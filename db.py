import psycopg
from pgvector.psycopg import register_vector

from config import DATABASE_URL

REQUESTS_TABLE = """
CREATE TABLE IF NOT EXISTS requests (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    prompt TEXT,
    model TEXT,
    route TEXT,
    cache_hit BOOLEAN,
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(12, 6),
    baseline_cost_usd NUMERIC(12, 6),
    latency_ms INT
)
"""

CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS cache_entries (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    prompt TEXT,
    embedding vector(384),
    response TEXT,
    model TEXT,
    input_tokens INT,
    output_tokens INT
)
"""


def init_db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(REQUESTS_TABLE)
        conn.execute(CACHE_TABLE)


def connect():
    conn = psycopg.connect(DATABASE_URL)
    register_vector(conn)
    return conn


def log_request(prompt, model, route, cache_hit, input_tokens, output_tokens,
                cost_usd, baseline_cost_usd, latency_ms):
    with connect() as conn:
        conn.execute(
            """INSERT INTO requests
               (prompt, model, route, cache_hit, input_tokens, output_tokens,
                cost_usd, baseline_cost_usd, latency_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (prompt, model, route, cache_hit, input_tokens, output_tokens,
             cost_usd, baseline_cost_usd, latency_ms),
        )


def get_stats() -> dict:
    with connect() as conn:
        total, hits, cost, baseline, avg_latency = conn.execute(
            """SELECT count(*),
                      count(*) FILTER (WHERE cache_hit),
                      coalesce(sum(cost_usd), 0),
                      coalesce(sum(baseline_cost_usd), 0),
                      coalesce(avg(latency_ms), 0)
               FROM requests"""
        ).fetchone()
        routes = conn.execute("SELECT route, count(*) FROM requests GROUP BY route").fetchall()
    cost, baseline = float(cost), float(baseline)
    return {
        "total_requests": total,
        "cache_hit_rate": round(hits / total, 3) if total else 0,
        "total_cost_usd": round(cost, 6),
        "all_opus_baseline_cost_usd": round(baseline, 6),
        "cost_saved_pct": round(100 * (1 - cost / baseline), 1) if baseline else 0,
        "avg_latency_ms": round(float(avg_latency)),
        "requests_by_route": {r: n for r, n in routes},
    }