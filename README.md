# Novexa AI: The Ultimate AI Interviewer

An advanced, voice-first AI interview practice agent designed to simulate realistic technical interviews. It uses local LLMs for intelligence and high-quality cloud TTS for a human-like experience.

## 🚀 Setup Instructions

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- [Ollama](https://ollama.com/) installed and running (`ollama serve`)
- Llama 3 model pulled (`ollama pull llama3.1:8b`)
- Murf.ai API Key

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in `backend/`:
```env
MURF_API_KEY=your_murf_api_key_here
```

Start the server:
```bash
uvicorn main:app --reload
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Access the app at `http://localhost:5173`.

---

## 🏗️ Architecture

The application follows a decoupled Client-Server architecture:

- **Frontend (Client)**: A React SPA (Single Page Application) that handles:
    - Real-time voice capture (Web Speech API).
    - Silence detection logic.
    - Audio playback management.
    - UI/UX for setup, interview, and reporting.
- **Backend (Server)**: A FastAPI service that acts as the brain:
    - Manages interview state (Session ID).
    - Interfaces with Ollama (Local LLM) for logic and content generation.
    - Interfaces with Murf.ai for voice generation.
    - Generates structured feedback reports.

---

## 💡 Design Decisions

### 1. Hybrid AI Approach
- **Local LLM (Ollama/Llama 3)**: Used for interview logic, question generation, and feedback.
    - *Why?* Privacy, zero cost per token, and low latency for text generation.
- **Cloud TTS (Murf.ai)**: Used for voice synthesis.
    - *Why?* Local TTS models often sound robotic. Murf provides "human-like" quality essential for a realistic interview vibe.

### 2. Voice-First UX
- The UI is designed to be minimal during the interview, focusing on the "Voice Wave" animation.
- **Live Transcript**: Displayed to give users confidence that the system "heard" them correctly.
- **Smart Silence Detection**: Instead of a manual "Stop" button, the system listens for pauses (2s threshold) to simulate a natural conversation flow.

### 3. Latency Optimization
- **Direct API Calls**: The backend uses a global `requests.Session` to reuse TCP connections to Murf.ai, significantly reducing TTS latency compared to re-initializing the SDK.
- **Optimistic UI**: The frontend shows the next question text immediately while the audio is being fetched/buffered.

### 4. Robustness
- **Minimum Duration**: The agent enforces a 10-minute minimum session to prevent premature endings, ensuring a comprehensive practice session.
- **Retry Logic**: The report generation includes retry mechanisms to handle potential JSON formatting errors from the LLM.
