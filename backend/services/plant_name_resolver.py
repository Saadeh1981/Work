import re

GENERIC_PHRASES = [
    "photovoltaic system",
    "contact information",
    "single line diagram",
    "as-built",
    "as built",
    "title sheet",
    "site plan",
    "electrical plan",
]

ADDRESS_WORDS = [
    "street", "st.", "avenue", "ave", "road", "rd", "suite", "ste",
    "blvd", "drive", "dr", "lane", "ln", "city", "state", "zip",
    "california", "texas", "arizona", "nevada", "new york",
]

COMPANY_WORDS = [
    "capital", "energy", "inc", "llc", "ltd", "corporation", "company",
    "engineering", "consulting",
]

PHONE_RE = re.compile(r"\(\d{3}\)\s*\d{3}[-\s]?\d{4}|\d{3}[-\s]?\d{3}[-\s]?\d{4}")

def score_line(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return -1.0

    tl = t.lower()

    score = 0.0

    if 4 <= len(t) <= 60:
        score += 1.0
    else:
        score -= 1.0

    if any(p in tl for p in GENERIC_PHRASES):
        score -= 2.0

    if any(w in tl for w in ADDRESS_WORDS):
        score -= 1.5

    if any(w in tl for w in COMPANY_WORDS):
        score -= 1.0

    if PHONE_RE.search(t):
        score -= 2.0

    digits = sum(ch.isdigit() for ch in t)
    if digits == 0:
        score += 0.5
    elif digits <= 2:
        score += 0.1
    else:
        score -= 0.8

    upper = sum(ch.isupper() for ch in t)
    letters = sum(ch.isalpha() for ch in t)
    if letters > 0 and (upper / letters) >= 0.7:
        score += 0.6

    if "-" in t or "_" in t:
        score += 0.3

    return score

def pick_plant_name(lines_top_band: list[dict]) -> dict:
    scored = []
    for ln in lines_top_band:
        text = ln.get("text", "")
        s = score_line(text)
        scored.append({"text": text, "score": s, "evidence": ln.get("evidence")})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:3]

    best = top[0] if top else {"text": None, "score": -1.0, "evidence": None}

    best_text = best["text"]
    best_score = best["score"]

    confidence = 0.0
    if best_score >= 1.2:
        confidence = 0.9
    elif best_score >= 0.6:
        confidence = 0.75
    elif best_score >= 0.2:
        confidence = 0.6
    else:
        confidence = 0.4

    return {
        "plant_name": best_text,
        "confidence": confidence,
        "candidates": top,
        "evidence": best.get("evidence"),
    }
