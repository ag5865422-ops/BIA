from __future__ import annotations

import json


def extract_json(text: str) -> dict:
    """
    LLMs sometimes wrap JSON in markdown fences. This extracts the first JSON object.
    """
    t = text.strip()
    if t.startswith("```"):
        # remove first fence line
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rsplit("```", 1)[0]
    t = t.strip()

    # Find first '{' and last '}' for a best-effort extraction
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model output.")
    return json.loads(t[start : end + 1])

