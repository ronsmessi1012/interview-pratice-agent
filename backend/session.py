# backend/session.py
import uuid
from typing import List, Dict, Optional, Any

class InterviewSession:
    def __init__(
        self,
        role: str,
        branch: str,
        specialization: str,
        difficulty: str,
        seed_questions: Optional[List[str]] = None
    ):
        self.id: str = str(uuid.uuid4())
        self.role: str = role
        self.branch: str = branch
        self.specialization: str = specialization
        self.difficulty: str = difficulty

        # History
        self.questions: List[str] = []
        self.answers: List[str] = []

        # Seed questions (curriculum)
        self.seed_questions: List[str] = seed_questions or []

        # Index to current seed question
        self.current_seed_index: int = 0

        # Number of follow-ups served for current seed
        self.current_followup_count: int = 0

        # Completed flag
        self.completed: bool = False

    def get_current_seed(self) -> Optional[str]:
        """Return the current seed question, if any."""
        if 0 <= self.current_seed_index < len(self.seed_questions):
            return self.seed_questions[self.current_seed_index]
        return None

    def advance_seed(self) -> None:
        """Move to next seed question and reset follow-up count."""
        self.current_seed_index += 1
        self.current_followup_count = 0
        # mark complete if no more seeds
        if self.current_seed_index >= len(self.seed_questions):
            self.completed = True

    def get_transcript(self, include_scores: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Returns a list of Q/A dictionaries.
        Optionally include per-question scores if provided.
        """
        transcript = []
        for idx, (q, a) in enumerate(zip(self.questions, self.answers)):
            item = {"question": q, "answer": a}
            if include_scores and idx < len(include_scores):
                item["score"] = include_scores[idx]
            transcript.append(item)
        return transcript

    def average_scores(self, scores_list: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Compute average per-score key over all questions.
        Expects a list of dicts with the same keys.
        """
        if not scores_list:
            return {}
        keys = scores_list[0].keys()
        avg_scores = {k: round(sum(s[k] for s in scores_list)/len(scores_list), 2) for k in keys}
        return avg_scores


# -----------------------------
# In-memory store
# -----------------------------
SESSIONS: Dict[str, InterviewSession] = {}

def create_session(
    role: str,
    branch: str,
    specialization: str,
    difficulty: str,
    seed_questions: Optional[List[str]] = None
) -> str:
    session = InterviewSession(
        role=role,
        branch=branch,
        specialization=specialization,
        difficulty=difficulty,
        seed_questions=seed_questions
    )
    SESSIONS[session.id] = session
    return session.id

def get_session(session_id: str) -> Optional[InterviewSession]:
    return SESSIONS.get(session_id)
