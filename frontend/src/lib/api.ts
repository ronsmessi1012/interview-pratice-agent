const API_BASE_URL = 'http://127.0.0.1:8000';


export interface StartInterviewRequest {
  name: string;
  role: string;
  branch: string;
  specialization: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

export interface StartInterviewResponse {
  session_id: string;
  next_question: string;
}

export interface AnswerRequest {
  session_id: string;
  answer: string;
}

export interface AnswerResponse {
  session_id: string;
  action: 'follow_up' | 'next_question' | 'end';
  text: string;
}

export interface EndInterviewRequest {
  session_id: string;
}

export interface QuestionScore {
  clarity: number;
  structure: number;
  examples: number;
  technical_accuracy: number;
  overall: number;
}

export interface TranscriptItem {
  question: string;
  answer: string;
  score: QuestionScore;
}

export interface PracticeRecommendations {
  prompts: string[];
  resources: string[];
}

export interface SessionSummary {
  avg_scores: QuestionScore;
  transcript: TranscriptItem[];
  overall_feedback: string;
  strengths: string[];
  weaknesses: string[];
  improvement_plan: string[];
  practice: PracticeRecommendations;
}

export interface EndInterviewResponse {
  session_id: string;
  summary: SessionSummary;
}

class InterviewAPI {
  private async request<T>(
    endpoint: string,
    method: string = 'GET',
    body?: any
  ): Promise<T> {
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, options);

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }

  async startInterview(data: StartInterviewRequest): Promise<StartInterviewResponse> {
    return this.request<StartInterviewResponse>('/start', 'POST', data);
  }

  async submitAnswer(data: AnswerRequest): Promise<AnswerResponse> {
    return this.request<AnswerResponse>('/answer', 'POST', data);
  }

  async endInterview(data: EndInterviewRequest): Promise<EndInterviewResponse> {
    return this.request<EndInterviewResponse>('/end', 'POST', data);
  }

  async generateSpeech(text: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/api/tts`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      throw new Error(`TTS API error: ${response.status} ${response.statusText}`);
    }

    return await response.blob();
  }
}

export const interviewAPI = new InterviewAPI();
