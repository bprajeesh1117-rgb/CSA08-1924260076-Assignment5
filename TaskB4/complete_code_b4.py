POSITIVE = {"good", "clean", "fast", "helpful", "improved"}
NEGATIVE = {"bad", "dirty", "slow", "rude", "smoke", "broken"}
NEGATORS = {"not", "never", "no"}

def score(text):
    """+1 per positive word, -1 per negative word; preceding negator flips it."""
    words = text.lower().replace(".", " ").replace(",", " ").split()
    total = 0
    # TODO 1 completed: find each word's score, flip it after a negator, and add it.
    for index, word in enumerate(words):
        value = 1 if word in POSITIVE else -1 if word in NEGATIVE else 0
        if index > 0 and words[index-1] in NEGATORS:
            value *= -1
        total += value
    return total

def label(text):
    s = score(text)
    return "positive" if s > 0 else "negative" if s < 0 else "neutral"

for c in ["Roads are clean and the bus was fast.",
          "Smoke from the factory, air is bad.",
          "The staff were not helpful.",
          "Not bad, service improved."]:
    print(f"{label(c):8} | {c}")
