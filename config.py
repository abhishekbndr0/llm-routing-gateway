import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://gateway:gateway@localhost:5432/gateway")

CHEAP_MODEL = "claude-haiku-5-5"
EXPENSIVE_MODEL = "claude-opus-5-5"

# USD per 1M tokens: (input, output). Verified against Anthropic's pricing page, Nov 2026.
PRICES = {
    CHEAP_MODEL: (0.10, 0.50),
    EXPENSIVE_MODEL: (4.00, 20.00),
}

# Haiku 5.5 is priced by prompt length: prompts over 100,000 tokens cost 5x.
LONG_PROMPT_THRESHOLD = 100_000
LONG_PROMPT_PRICES = {
    CHEAP_MODEL: (0.50, 2.50),
}

SIMILARITY_THRESHOLD = 0.95   # cosine similarity needed for a cache hit
DEFAULT_MAX_TOKENS = 1024


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = PRICES[model]
    if input_tokens > LONG_PROMPT_THRESHOLD and model in LONG_PROMPT_PRICES:
        p_in, p_out = LONG_PROMPT_PRICES[model]
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000