# backend/session.py
import uuid
from typing import List, Dict, Optional, Any

class InterviewMemory:
    """
    Stores long-term information about the user:
    - Weak areas
    - Past scores
    - Suggested practice prompts
    """
    def __init__(self):
        self.weak_areas: List[str] = []
        self.past_avg_scores: Dict[str, float] = {}
        self.practice_prompts: List[str] = []
        self.resource_links: List[str] = []

class InterviewSession:
    def __init__(self, role, branch, specialization, difficulty, seed_questions=None):
        self.id: str = str(uuid.uuid4())
        self.role = role
        self.branch = branch
        self.specialization = specialization
        self.difficulty = difficulty

        # Q/A history
        self.questions: List[str] = []
        self.answers: List[str] = []

        # Seed questions
        self.seed_questions: List[str] = seed_questions or []
        self.current_seed_index: int = 0
        self.current_followup_count: int = 0
        self.next_question_count: int = 0  # Tracks next-question actions separately
        self.completed: bool = False

        # Memory object
        self.memory: InterviewMemory = InterviewMemory()

    # -----------------------------
    # Seed question handling
    # -----------------------------
    def get_current_seed(self) -> Optional[str]:
        """Return the current seed question, if any."""
        if 0 <= self.current_seed_index < len(self.seed_questions):
            return self.seed_questions[self.current_seed_index]
        return None

    def advance_seed(self) -> None:
        """Move to next seed question, reset follow-ups, and increment next_question_count."""
        self.current_seed_index += 1
        self.current_followup_count = 0
        self.next_question_count += 1

        # Mark completed only if all seeds are done
        if self.current_seed_index >= len(self.seed_questions):
            self.completed = True

    # -----------------------------
    # Transcript & scoring
    # -----------------------------
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
