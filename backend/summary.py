from typing import Dict, Any, List
from scoring import score_answer
from llm import llm_generate
import json


def clean_json_output(raw_text: str) -> str:
    """
    Remove markdown code blocks (e.g. ```json ... ```) and extra whitespace.
    """
    text = raw_text.strip()
    # Remove ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        # Find first newline
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline+1:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def generate_session_summary(session) -> Dict[str, Any]:
    """
    Generate full structured summary:
    - Average rubric scores
    - Transcript with per-question scores
    - Strengths
    - Weaknesses
    - Improvement plan (3–4 items)
    - Practice prompts & resource links
    """

    transcript = []
    scores_list = []

    # -------------------------------------------------------
    # 1. Transcript + per-answer scoring
    # -------------------------------------------------------
    for q, a in zip(session.questions, session.answers):
        # Skip meta-questions
        q_lower = q.lower()
        if "are you sure" in q_lower or "want to end" in q_lower:
            continue

        score = score_answer(a, q, session.role)
        scores_list.append(score)
        transcript.append({
            "question": q,
            "answer": a,
            "score": score
        })

    # -------------------------------------------------------
    # 2. Average rubric scores
    # -------------------------------------------------------
    avg_scores = {}
    if scores_list:
        keys = scores_list[0].keys()
        for k in keys:
            try:
                nums = []
                for s in scores_list:
                    v = s[k]
                    if isinstance(v, (int, float)):
                        nums.append(float(v))
                    elif isinstance(v, str) and v.replace(".", "", 1).isdigit():
                        nums.append(float(v))

                avg_scores[k] = round(sum(nums) / len(nums), 2) if nums else None
            except Exception:
                avg_scores[k] = None

    # -------------------------------------------------------
    # 3. Weak rubric areas (score < 3)
    # -------------------------------------------------------
    weak_areas = [k for k, v in avg_scores.items() if v is not None and v < 3]

    # -------------------------------------------------------
    # 4. LLM summary with strengths + weaknesses + improvements
    # -------------------------------------------------------
    feedback_prompt = f"""
You are an expert interview evaluator.

Given:
Role: {session.role}
Average Scores: {avg_scores}
Transcript: {transcript}

Generate a STRICT JSON summary with keys:

{{
  "overall_feedback": "1–2 paragraph summary",
  "strengths": [
      "point1",
      "point2"
  ],
  "weaknesses": [
      "point1",
      "point2"
  ],
  "improvement_plan": [
      "step1",
      "step2",
      "step3"
  ],
  "practice_prompts": [
      "prompt1",
      "prompt2",
      "prompt3"
  ],
  "resource_links": [
      "https://example.com/resource1",
      "https://example.com/resource2"
  ]
}}

Rules:
- JSON only, no markdown.
- Each list must contain 2–4 short, actionable bullet points.
- Strengths and weaknesses must be based on actual transcript and scores.
"""

    llm_summary = {
        "overall_feedback": "Feedback unavailable.",
        "strengths": [],
        "weaknesses": weak_areas,
        "improvement_plan": [],
        "practice_prompts": [],
        "resource_links": []
    }

    # Retry loop for robust JSON parsing
    max_retries = 3
    for attempt in range(max_retries):
        raw = llm_generate(feedback_prompt)
        cleaned = clean_json_output(raw)
        try:
            llm_summary = json.loads(cleaned)
            break  # Success
        except json.JSONDecodeError:
            if attempt == max_retries - 1:
                print(f"Failed to parse summary JSON after {max_retries} attempts.")
            continue

    # Save memory (optional)
    session.memory.weak_areas = llm_summary.get("weaknesses", weak_areas)
    session.memory.past_avg_scores = avg_scores
    session.memory.practice_prompts = llm_summary.get("practice_prompts", [])
    session.memory.resource_links = llm_summary.get("resource_links", [])

    # -------------------------------------------------------
    # FINAL MERGED STRUCTURED OUTPUT
    # -------------------------------------------------------
    return {
        "avg_scores": avg_scores,
        "transcript": transcript,
        "overall_feedback": llm_summary.get("overall_feedback", ""),

        "strengths": llm_summary.get("strengths", []),
        "weaknesses": llm_summary.get("weaknesses", weak_areas),
        "improvement_plan": llm_summary.get("improvement_plan", []),

        "practice": {
            "prompts": llm_summary.get("practice_prompts", []),
            "resources": llm_summary.get("resource_links", [])
        }
    }
