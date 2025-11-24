# feedback.py
import json
from typing import Dict, Any
from scoring import score_answer
from llm import llm_generate


def build_feedback_prompt(answer: str, question: str, role: str, scores: Dict[str, Any]) -> str:
    """
    Create structured prompt that asks the LLM to generate:
    - Summary
    - Strengths (2 bullets)
    - Weaknesses (2 bullets)
    - 3 actionable improvement steps with examples
    Output must be STRICT JSON only.
    """

    prompt = f"""
You are an expert interview coach evaluating a candidate for the role: {role}.

Below is the candidate's response:

QUESTION: {question}
ANSWER: {answer}

Pre-computed rubric scores:
{json.dumps(scores)}

Your task:
Return a STRICT JSON object with the following fields:

{{
  "summary": "2–3 lines summarizing the overall answer quality",
  "strengths": ["bullet 1", "bullet 2"],
  "weaknesses": ["bullet 1", "bullet 2"],
  "improvements": [
     {{
        "title": "clear headline",
        "description": "what to improve",
        "example": "short rewritten example applying the fix"
     }},
     {{
        "title": "another improvement",
        "description": "what to improve",
        "example": "example"
     }},
     {{
        "title": "third improvement",
        "description": "what to improve",
        "example": "example"
     }}
  ]
}}

Constraints:
- DO NOT add extra commentary.
- DO NOT include markdown.
- DO NOT break JSON.
- Ensure every string is escaped properly.
"""

    return prompt


def generate_feedback(answer: str, question: str, role: str) -> Dict[str, Any]:
    """
    Main pipeline:
    1. Score using scoring.py
    2. Build feedback prompt
    3. Call LLM
    4. Parse JSON safely
    """

    # Step 1 — Score
    scores = score_answer(answer, question, role)

    # Step 2 — Prompt
    prompt = build_feedback_prompt(answer, question, role, scores)

    # Step 3 — LLM call
    raw_response = llm_generate(prompt)

    # Step 4 — Parse JSON safely
    try:
        feedback = json.loads(raw_response)
    except json.JSONDecodeError:
        # fallback safety: try to extract first valid JSON block
        try:
            start = raw_response.index("{")
            end = raw_response.rindex("}") + 1
            cleaned = raw_response[start:end]
            feedback = json.loads(cleaned)
        except Exception:
            raise ValueError("LLM returned invalid JSON. Raw: " + raw_response)

    # Final merged output
    return {
        "scores": scores,
        "feedback": feedback
    }
