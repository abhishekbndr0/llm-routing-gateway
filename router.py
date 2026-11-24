import os

import joblib

from config import CHEAP_MODEL, EXPENSIVE_MODEL

CLASSIFIER_PATH = "router.joblib"
HARD_HINTS = ("prove", "derive", "analyze", "analyse", "design", "architecture",
              "step by step", "compare", "optimize", "debug", "implement",
              "algorithm", "trade-off", "tradeoff", "why does")

_clf = None


def _load_classifier():
    global _clf
    if _clf is None and os.path.exists(CLASSIFIER_PATH):
        _clf = joblib.load(CLASSIFIER_PATH)
    return _clf


def choose_model(prompt: str, embedding=None) -> str:
    """Version 2 (learned) if router.joblib exists, else version 1 (rules)."""
    clf = _load_classifier()
    if clf is not None and embedding is not None:
        return EXPENSIVE_MODEL if clf.predict([embedding])[0] == 1 else CHEAP_MODEL
    lowered = prompt.lower()
    if len(prompt) > 400 or any(h in lowered for h in HARD_HINTS):
        return EXPENSIVE_MODEL
    return CHEAP_MODEL