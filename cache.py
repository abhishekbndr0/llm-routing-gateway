from sentence_transformers import SentenceTransformer

from config import SIMILARITY_THRESHOLD
from db import connect

_model = None


def embed(text: str):
    """384-dim, unit-length vector from a local model (Anthropic has no embeddings API)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model.encode(text, normalize_embeddings=True)


def lookup(embedding):
    with connect() as conn:
        row = conn.execute(
            """SELECT response, model, input_tokens, output_tokens,
                      1 - (embedding <=> %s) AS similarity
               FROM cache_entries
               ORDER BY embedding <=> %s
               LIMIT 1""",
            (embedding, embedding),
        ).fetchone()
    if row and row[4] >= SIMILARITY_THRESHOLD:
        return {"response": row[0], "model": row[1], "input_tokens": row[2],
                "output_tokens": row[3], "similarity": float(row[4])}
    return None


def store(prompt, embedding, response, model, input_tokens, output_tokens):
    with connect() as conn:
        conn.execute(
            """INSERT INTO cache_entries
               (prompt, embedding, response, model, input_tokens, output_tokens)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (prompt, embedding, response, model, input_tokens, output_tokens),
        )