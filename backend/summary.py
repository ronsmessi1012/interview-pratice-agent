# backend/summary.py
from typing import Dict, Any, List
from .scoring import score_answer
from .llm import llm_generate
import json

def generate_session_summary(session) -> Dict[str, Any]:
    """
    Generate a full session summary including:
    - Average scores per rubric
    - Q/A transcript
    - Overall textual feedback
    - Identified areas for improvement
    - Recommended practice prompts & resources
    """
    transcript = []
    scores_list = []

    # 1️⃣ Collect per-question scores and transcript
    for q, a in zip(session.questions, session.answers):
        score = score_answer(a, q, session.role)
        scores_list.append(score)
        transcript.append({"question": q, "answer": a, "score": score})

    # 2️⃣ Compute average scores
    avg_scores = {}
    if scores_list:
        keys = scores_list[0].keys()
        for k in keys:
            try:
                # convert to float safely
                numeric_values = [float(s[k]) for s in scores_list if isinstance(s[k], (int, float, str)) and str(s[k]).replace('.','',1).isdigit()]
                if numeric_values:
                    avg_scores[k] = round(sum(numeric_values) / len(numeric_values), 2)
                else:
                    avg_scores[k] = None
            except Exception:
                avg_scores[k] = None

    # 3️⃣ Identify weak areas (score < 3)
    weak_areas = [k for k, v in avg_scores.items() if v is not None and v < 3]

    # 4️⃣ Generate overall feedback via LLM
    feedback_prompt = f"""
You are an expert interview coach.
Based on the following candidate session details:

Role: {session.role}
Average Scores: {avg_scores}
Transcript: {transcript}

Tasks:
1. Write a concise overall feedback paragraph summarizing performance.
2. Identify areas for improvement (e.g., communication, technical knowledge, structure).
3. Suggest 3 practice prompts similar to the answered questions.
4. Suggest 2-3 links to resources or exercises to improve skills.

Return STRICT JSON with keys:
{{
  "overall_feedback": "string summary paragraph",
  "areas_for_improvement": ["communication", "technical knowledge", "answer structure"],
  "practice_prompts": ["prompt1", "prompt2", "prompt3"],
  "resource_links": ["link1", "link2"]
}}
Constraints:
- Do NOT add extra commentary.
- Do NOT include markdown.
- Do NOT break JSON.
- Ensure every string is escaped properly.
"""
    raw_response = llm_generate(feedback_prompt)

    # 5️⃣ Parse LLM JSON safely
    try:
        llm_summary = json.loads(raw_response)
    except json.JSONDecodeError:
        # fallback
        llm_summary = {
            "overall_feedback": "Unable to generate feedback.",
            "areas_for_improvement": weak_areas or [],
            "practice_prompts": [],
            "resource_links": []
        }
    # backend/summary.py (inside generate_session_summary)
# After computing llm_summary:
    session.memory.weak_areas = llm_summary.get("areas_for_improvement", weak_areas)
    session.memory.past_avg_scores = avg_scores
    session.memory.practice_prompts = llm_summary.get("practice_prompts", [])
    session.memory.resource_links = llm_summary.get("resource_links", [])

    # Merge LLM summary with computed data
    return {
        "avg_scores": avg_scores,
        "transcript": transcript,
        "overall_feedback": llm_summary.get("overall_feedback", ""),
        "areas_for_improvement": llm_summary.get("areas_for_improvement", weak_areas),
        "practice": {
            "prompts": llm_summary.get("practice_prompts", []),
            "resources": llm_summary.get("resource_links", [])
        }
    }
