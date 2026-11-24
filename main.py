import time
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

import cache
import db
import router
from config import CHEAP_MODEL, EXPENSIVE_MODEL, PRICES, cost_usd
from translate import STOP_REASONS, extract_text, to_anthropic, to_openai

client = anthropic.Anthropic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="LLM Routing Gateway", lifespan=lifespan)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "auto"
    messages: list[dict]


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    body = req.model_dump()
    if body.get("stream"):
        raise HTTPException(400, "streaming is not supported yet")

    start = time.perf_counter()
    try:
        payload = to_anthropic(body)
    except ValueError as e:
        raise HTTPException(400, str(e))

    prompt = payload["messages"][-1]["content"]
    embedding = cache.embed(prompt)

    # Only cache standalone questions: no system prompt, no conversation history.
    cacheable = len(payload["messages"]) == 1 and "system" not in payload

    if cacheable:
        hit = cache.lookup(embedding)
        if hit:
            latency = int((time.perf_counter() - start) * 1000)
            baseline = cost_usd(EXPENSIVE_MODEL, hit["input_tokens"], hit["output_tokens"])
            db.log_request(prompt, hit["model"], "cache", True, 0, 0, 0.0, baseline, latency)
            return to_openai(hit["response"], hit["model"], 0, 0, gateway={
                "cache_hit": True, "similarity": round(hit["similarity"], 3),
                "cost_usd": 0.0, "latency_ms": latency,
            })

    if body["model"] in PRICES:               # caller asked for a specific model
        model, route = body["model"], "explicit"
    else:                                     # "auto": let the router decide
        model = router.choose_model(prompt, embedding)
        route = "cheap" if model == CHEAP_MODEL else "expensive"

    try:
        resp = client.messages.create(model=model, **payload)
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"upstream error {e.status_code}")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "could not reach Anthropic")

    text = extract_text(resp)
    in_t, out_t = resp.usage.input_tokens, resp.usage.output_tokens
    cost = cost_usd(model, in_t, out_t)
    baseline = cost_usd(EXPENSIVE_MODEL, in_t, out_t)
    latency = int((time.perf_counter() - start) * 1000)

    db.log_request(prompt, model, route, False, in_t, out_t, cost, baseline, latency)
    if cacheable:
        cache.store(prompt, embedding, text, model, in_t, out_t)

    return to_openai(text, model, in_t, out_t,
                     finish_reason=STOP_REASONS.get(resp.stop_reason, "stop"),
                     gateway={"cache_hit": False, "route": route,
                              "cost_usd": round(cost, 6), "latency_ms": latency})


@app.get("/stats")
def stats():
    return db.get_stats()