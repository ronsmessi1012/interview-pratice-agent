from typing import Dict, Any
from .llm import llm_generate

def score_answer(answer: str, question: str, role: str) -> Dict[str, float]:
    """
    Score an answer in context of a specific question and role.
    Returns a numeric rubric:
    - clarity (1-5)
    - structure (1-5)
    - examples (1-5)
    - technical_accuracy (1-5)
    - overall (computed)
    """

    prompt = f"""
You are an expert interviewer for {role}.
Question: {question}
Candidate Answer: {answer}

Score the answer on a 1-5 scale for:
1. Clarity: How clear and understandable the answer is
2. Structure: Logical flow or STAR structure
3. Examples: Presence of concrete examples
4. Technical Accuracy: Correctness of technical points

Return STRICT JSON ONLY:
{{
  "clarity": 0,
  "structure": 0,
  "examples": 0,
  "technical_accuracy": 0,
  "overall": 0
}}
"""

    raw = llm_generate(prompt)
    import json
    try:
        scores = json.loads(raw)
        # Ensure all keys exist
        for k in ["clarity","structure","examples","technical_accuracy","overall"]:
            scores[k] = float(scores.get(k, 0))
    except Exception:
        # fallback numeric scoring
        scores = {
            "clarity": 3.0,
            "structure": 3.0,
            "examples": 3.0,
            "technical_accuracy": 3.0,
            "overall": 3.0
        }

    # recompute overall as average if not provided
    if scores.get("overall", 0) == 0:
        scores["overall"] = round(sum([scores[k] for k in ["clarity","structure","examples","technical_accuracy"]])/4, 2)

    return scores
