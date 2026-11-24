# LLM Routing Gateway

An OpenAI-compatible gateway that sits between an app and Anthropic's Claude API. Each request is
checked against a semantic cache, routed to a cheaper or more capable model, and logged with its
cost and latency.

> **Status: working prototype.** The core pipeline below is built and tested. Streaming, auth,
> and a quality evaluation are not built yet (see [Limitations](#limitations) and [Next steps](#next-steps)).

## How it works

```
client -> POST /v1/chat/completions
            |
            +-- translate OpenAI request -> Anthropic request   (translate.py)
            +-- embed the question locally                      (cache.py)
            +-- semantic cache lookup in Postgres/pgvector      (cache.py)
            |       hit  -> return stored answer, cost $0
            |       miss -> continue
            +-- choose Haiku 5.5 or Opus 5.5                    (router.py)
            +-- call Claude                                     (main.py)
            +-- log tokens, cost, latency, route                (db.py)
            +-- store answer in the cache, translate back to OpenAI format
```

Any app that already speaks the OpenAI chat API can point at this gateway by changing its base URL.

## Features

- **OpenAI-compatible endpoint** (`POST /v1/chat/completions`) that translates to and from Anthropic's
  Messages API. The translation handles the top-level `system` field, the required `max_tokens`,
  alternating roles, content blocks, temperature range, stop sequences, and token field names.
- **Semantic cache** using local `all-MiniLM-L6-v2` embeddings (384 dimensions) and pgvector cosine
  similarity. Only standalone questions (one message, no system prompt) are cached.
- **Tiered router**: a rule-based baseline (prompt length and keywords), replaced automatically by a
  scikit-learn logistic regression over the same embeddings once `router.joblib` exists.
- **Cost and latency logging** to Postgres for every request, including a baseline of what the request
  would have cost on the expensive model. `GET /stats` summarizes totals.

## Models and pricing

| Role | Model | Input / output per 1M tokens |
|---|---|---|
| Cheap route | `claude-haiku-5-5` | $0.10 / $0.50 (prompts up to 100K tokens), $0.50 / $2.50 above |
| Expensive route | `claude-opus-5-5` | $4 / $20 |

Prices live in `config.py`. Verify them against Anthropic's pricing page, since they change.

## Setup

Requires Python 3.11+ and Postgres with the pgvector extension.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file (never commit it):

```
ANTHROPIC_API_KEY=your-key-here
DATABASE_URL=postgresql://localhost/gateway
```

Create the database, either with a local Postgres (`brew install postgresql@16 pgvector`, then
`createdb gateway`) or with the included `docker-compose.yml`. The gateway creates its tables and the
vector extension on startup.

Optionally train the learned router (otherwise the rule-based router is used):

```bash
python train_router.py
```

## Run

```bash
uvicorn main:app --reload
```

Open http://localhost:8000/docs, or run the demo in a second terminal:

```bash
python scripts/demo.py
```

Use it from the OpenAI SDK:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")
client.chat.completions.create(model="auto", messages=[{"role": "user", "content": "Hello"}])
```

Set `model` to `auto` to let the router choose, or to a specific model name to force it.

## Tests

```bash
python -m pytest
```

The unit tests cover the translation layer only (system prompt placement, `max_tokens` default,
role merging, temperature clamping, stop sequences, content flattening, token totals).

## Results so far

- **Router:** on a held-out set of 41 labeled questions the classifier scored about 98% accuracy
  (one error: a hard question sent to the cheap model). The 203 labeled examples are synthetic
  (generated with Claude's help and reviewed), so treat this as an early signal, not a benchmark.
- **Cache threshold:** a small experiment (`scripts/threshold_check.py`, 3 paraphrase pairs and
  3 near-miss pairs) showed the similarity ranges overlap. Example: "Convert 5 km to miles" vs
  "Convert 5 miles to km" scores 0.986, so a similarity threshold alone cannot prevent wrong cache
  hits. The threshold is set conservatively at 0.95, trading a lower hit rate for fewer wrong answers.
- **Cost savings:** not measured reliably yet. Every request logs its cost against an all-expensive
  baseline, but the demo run is too small to quote a percentage.

## Limitations

- No streaming (requests with `stream: true` return a 400).
- No authentication or rate limiting.
- Only text messages; no tool calls or images.
- A new database connection is opened per query (no connection pool).
- No cache expiry or invalidation.
- The cache ignores which model was requested, so an explicit model request can receive a cached
  answer from a different model.
- Semantic caching can return a wrong answer for near-identical questions that differ in a number,
  direction, or negation (see Results).
- No quality evaluation yet: it is not measured whether routing and caching change answer quality.

## Next steps

- Gold-set evaluation comparing all-expensive against routed-and-cached answers.
- Verification step on cache hits (cross-encoder or small-model check).
- Streaming support, a connection pool, and cache TTLs.
- Prompt caching on the Anthropic side as a second caching layer.

## Project layout

| File | Purpose |
|---|---|
| `main.py` | FastAPI app and the request pipeline |
| `translate.py` | OpenAI <-> Anthropic request and response translation |
| `cache.py` | Local embeddings and the pgvector semantic cache |
| `router.py` | Rule-based and learned model selection |
| `db.py` | Schema, request logging, `/stats` query |
| `config.py` | Models, prices, similarity threshold |
| `train_router.py` | Trains the easy/hard classifier from `data/labels.csv` |
| `scripts/` | `demo.py` (end-to-end demo), `threshold_check.py` (cache threshold experiment) |
| `test_translate.py` | Unit tests for the translation layer |
