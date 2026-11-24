from cache import embed

PARAPHRASES = [
    ("What's the capital of France?", "France's capital city?"),
    ("How do I reset my password?", "I forgot my password, how can I change it?"),
    ("What is 12 times 12?", "12 x 12 = ?"),
]
NEAR_MISSES = [
    ("What's the capital of France?", "What's the capital of Spain?"),
    ("What is 12 times 12?", "What is 12 times 13?"),
    ("Convert 5 km to miles.", "Convert 5 miles to km."),
]

def sim(a, b):
    return float(embed(a) @ embed(b))   # vectors are unit length, so dot product = cosine similarity

print("PARAPHRASES (should be HIGH):")
for a, b in PARAPHRASES:
    print(f"  {sim(a, b):.3f}  {a}  |  {b}")
print("NEAR MISSES (should be LOW):")
for a, b in NEAR_MISSES:
    print(f"  {sim(a, b):.3f}  {a}  |  {b}")