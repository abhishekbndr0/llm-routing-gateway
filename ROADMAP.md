# LLM Routing Gateway — Build Roadmap

A middleman service that sits between an app and Claude. Every request goes through it,
and it decides: can I answer this from cache? does this need the cheap model or the
expensive one? Then it logs what everything cost.

**Provider:** Anthropic (Claude)
**Embeddings:** local, via `sentence-transformers` (free, no API key)
**Public interface:** OpenAI-compatible, so any existing app can point at it unchanged

Build the phases in order. Each one works on its own before the next one starts.
Resist jumping ahead to the fun parts — the measurement layer is what makes this
project credible, and it has to exist before the things it measures.

---

## Cost reality check

Claude Pro and the Anthropic API are **separate products with separate billing.**
Pro covers claude.ai and Claude Code (the tools you use). The API is what this
project's code calls, billed pay-as-you-go from console.anthropic.com. Buy credits
(~$5 minimum) to start.

| Model | ID | Input / 1M | Output / 1M | Role here |
|---|---|---|---|---|
| Haiku 4.5 | `claude-haiku-4-5` | $1 | $5 | cheap route |
| Sonnet 5 | `claude-sonnet-5` | $3 | $15 | optional middle tier |
| Opus 4.8 | `claude-opus-4-8` | $5 | $25 | expensive route |

Rough per-call cost for a short Q&A: **~0.2¢ on Haiku, ~0.9¢ on Opus.**
Expect **$10–30 total** for the whole project, mostly from re-running evals.

Ways to keep it down:

- Set a **spending limit** in the Anthropic console on day one. Do this before writing code.
- Cap `max_tokens` — output tokens cost 5x input.
- Use the **Batch API** for eval runs: same requests, 50% off, results within an hour.
- Swap Opus for Sonnet as the "expensive" tier if needed — the routing story is identical.
- The project cuts its own bill: once caching and routing work, eval reruns get much cheaper.

---

## Phase 0 — Setup (half a day)

- [ ] Python 3.11+ and a virtual environment (isolated package sandbox for this project)
- [ ] Get an API key from console.anthropic.com → put it in `.env`
- [ ] **Add `.env` to `.gitignore` before the first commit.** A leaked key is someone else spending your money.
- [ ] Set a spending limit in the console
- [ ] Install: `fastapi`, `uvicorn`, `anthropic`, `python-dotenv`

**Done when:** a 5-line throwaway script sends "hello" to Claude and prints the reply.

---

## Phase 1 — The pipe

One endpoint that takes a question, forwards it to one model, returns the answer.
No smarts yet.

- [ ] FastAPI app with a single POST endpoint named `/v1/chat/completions`
      (the standard URL existing apps expect — this is what makes your gateway a
      drop-in replacement rather than a toy)
- [ ] **Translation layer:** accept the OpenAI request shape, convert it to Anthropic's
      shape, call Claude, convert the response back. This is the piece that makes the
      project interesting — it's what tools like LiteLLM do.
- [ ] Forward everything to Opus for now. Routing comes later.
- [ ] *Stretch:* streaming, so tokens come back word-by-word instead of all at once.
      Genuinely fiddly — that's why it's impressive. Skip if stuck, return later.

**Done when:** you can `curl` your own endpoint (or use FastAPI's free `/docs` page)
and get a real answer back through your server.

### Anthropic API gotchas (these will bite you)

- **`max_tokens` is required.** OpenAI treats it as optional; Anthropic rejects the
  request without it. Default to ~16000 for non-streaming, ~64000 when streaming.
- **The system prompt is a top-level `system=` parameter,** not a message with
  `role: "system"`. This is the #1 translation-layer bug.
- **`response.content` is a list of blocks, not a string.** Loop it and pick out the
  ones where `block.type == "text"`. Indexing `content[0].text` blindly will break.
- **Token fields are `usage.input_tokens` / `usage.output_tokens`** (OpenAI calls
  them `prompt_tokens` / `completion_tokens`). Your logging code needs the right names.
- **Message roles must alternate** user/assistant, and the first must be `user`.

---

## Phase 2 — Logging (build this before the fun stuff)

Write down every request so you can measure. This is the phase everyone skips and the
one that turns a demo into engineering.

- [ ] Install Postgres and a connector (`psycopg` or `sqlalchemy`)
- [ ] One table. One row per request: the question, model used, input tokens,
      output tokens, dollar cost, latency in milliseconds
- [ ] Compute cost yourself from tokens × the per-token prices in the table above

**Done when:** after 10 requests, one SQL query shows total spend and average latency.

Every later change now gets measured automatically. This is where your resume numbers
come from.

---

## Phase 3 — The router

Automatically send easy questions to Haiku and hard ones to Opus.

- [ ] **Version 1 — deliberately dumb.** A length or keyword rule. Get the two-model
      split working end to end first.
- [ ] **Version 2 — the impressive one.** Hand-label ~200 example questions easy/hard.
      Turn each into an embedding (see below). Train a tiny classifier —
      `scikit-learn`'s logistic regression, about 5 lines. Now the router *learned*
      the distinction instead of using hand-written rules.
- [ ] Log which route each request took (add a column to the table you already have)

**Done when:** you can run a batch of mixed questions and see in your own logs that
most went cheap. Compare total cost against all-Opus. That percentage is your headline.

### Embeddings — the one real gap

Anthropic has **no embeddings API**. Embeddings power both the router and the cache,
so you need another source. Use a **local model** — it's free, needs no API key, and
adds no network latency (which actually makes your latency numbers look better).

- [ ] `pip install sentence-transformers`
- [ ] Use `all-MiniLM-L6-v2` — small, fast, runs fine on a laptop, produces
      384-dimension vectors
- [ ] Alternatives if you ever want them: Voyage AI (Anthropic's recommended partner,
      has a free tier) or OpenAI's embeddings endpoint

An embedding is just a list of numbers representing a sentence's meaning — think GPS
coordinates in "meaning space." Similar meanings land close together.

---

## Phase 4 — The semantic cache

If a question *means the same thing* as one already answered, return the saved answer
instantly — no API call, no cost. "What's the capital of France?" and "France's capital
city?" should hit the same cache entry.

- [ ] Add the **pgvector** extension to Postgres (lets the database store embeddings
      and find nearby ones quickly)
- [ ] For each incoming question: embed it, ask pgvector for the nearest stored
      question, and if it's close enough, return that cached answer
- [ ] Otherwise proceed normally and save the new question + answer
- [ ] **Tune the similarity threshold.** Too loose returns wrong answers for merely
      similar questions; too tight never hits. Finding the balance — and being able to
      explain the tradeoff — is great interview material.

**Done when:** you ask the same thing two different ways and the second returns
instantly and free, with a cache hit visible in your logs.

---

## Phase 5 — The eval suite (the centerpiece)

Prove the cost-cutting didn't make answers worse.

- [ ] Build a fixed set of ~300 questions with known-good answers (your "gold set")
- [ ] Run the whole gateway against it; score how many answers are acceptable
- [ ] Compare all-Opus quality against routed-and-cached quality
- [ ] Use the **Batch API** (`client.messages.batches.create`) for these runs — 50% off,
      results within an hour. Results come back in arbitrary order, so key them by
      `custom_id`, never by position.

**Done when:** one command regenerates the sentence *"kept X% of quality while cutting
Y% of cost."* That sentence is the entire point of the project.

---

## Phase 6 — Prompt caching (Anthropic bonus)

A **second, independent** caching layer underneath the semantic cache. The semantic
cache stores whole answers; prompt caching stores prompt *prefixes* on Anthropic's side.

- [ ] Mark the stable part of your prompt with `cache_control: {"type": "ephemeral"}`
- [ ] Cache reads cost ~**10%** of normal input price; writes cost ~1.25x, so it pays
      for itself after two requests
- [ ] Verify it works: check `usage.cache_read_input_tokens` in the response. If it's
      zero across repeated requests, something in your prefix is changing every time
      (a timestamp, a random ID, unsorted JSON) and silently breaking the cache
- [ ] Note the minimum: prefixes under ~4096 tokens won't cache at all on Opus 4.8 or
      Haiku 4.5 — no error, it just silently doesn't happen

**Key rule:** caching is a *prefix match*. Anything that changes early in the prompt
invalidates everything after it. Keep stable content first, volatile content last.

**Done when:** your logs show a measurable cost drop from cache reads, separate from
the semantic cache's savings.

---

## The resume bullet

> Built an OpenAI-compatible LLM routing gateway (Python, FastAPI, Postgres/pgvector,
> Claude API) that cut token spend ~60% while retaining ~95%+ answer quality on a
> 300-item eval suite, using a learned easy/hard router, a local-embedding semantic
> cache, and prefix-level prompt caching.

Every number in there is something you measured and can defend for twenty minutes.
That's what separates this from a tutorial project.

---

## Notes

- Model IDs and prices shift — verify against Anthropic's pricing page when you start.
- Don't skip ahead. The cache is the fun part, but it only impresses if the logging
  underneath it can prove it worked.
- When you're ready to build a phase, come back and say which one.
