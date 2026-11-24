import httpx

QUESTIONS = [
    "What's the capital of France?",
    "France's capital city?",                       # paraphrase: should hit the cache
    "What is 12 times 12?",
    "Design a rate limiter for a multi-tenant API and compare the trade-offs of token bucket vs sliding window.",
    "What's the capital of France?",                # exact repeat: cache hit
    "Tell me a one-line joke.",
]

for q in QUESTIONS:
    r = httpx.post("http://localhost:8000/v1/chat/completions", timeout=120,
                   json={"model": "auto", "messages": [{"role": "user", "content": q}]}).json()
    print(f"{q[:55]:55} -> {r['x_gateway']}")

print(httpx.get("http://localhost:8000/stats").json())