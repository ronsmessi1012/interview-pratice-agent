# Frontend Documentation

## Tech Stack
- **Framework**: React (Vite)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: Shadcn UI (Radix Primitives)
- **Routing**: React Router DOM
- **State Management**: React Hooks (`useState`, `useEffect`, `useRef`)
- **Audio/Voice**:
  - **Speech-to-Text (STT)**: Web Speech API (`webkitSpeechRecognition`)
  - **Text-to-Speech (TTS)**: HTML5 Audio (playing backend-generated MP3s)
  - **Recording**: MediaRecorder API
- **Icons**: Lucide React

## Frontend Pipeline

1.  **User Interaction**:
    - User lands on `Setup` page to enter details (Name, Role, Experience).
    - User navigates to `Interview` page to start the session.

2.  **Voice Capture & Processing**:
    - **Silence Detection**: `useSilenceDetection` hook monitors audio levels.
    - **Auto-Submit**: When silence is detected (threshold < 0.15 for 2s) or timer expires (30s), the recording stops.
    - **Speech-to-Text**: The browser's Web Speech API converts audio to text in real-time (`liveTranscript`).

3.  **Backend Communication**:
    - The recognized text is sent to the backend via `/answer` endpoint.
    - The frontend receives a JSON response containing the agent's next action (`next_question`, `follow_up`, or `end`) and the text to speak.

4.  **Response Playback**:
    - The frontend requests audio for the agent's response from `/api/tts`.
    - The audio is played using the `useSpeechSynthesis` hook (which manages the `Audio` object).
    - A "listening" state is triggered only *after* the agent finishes speaking.

5.  **Session Management**:
    - The interview flow continues until the backend signals `action: "end"`.
    - The user is redirected to the `Report` page to view the summary.
