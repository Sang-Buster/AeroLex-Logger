/**
 * VR Flight Training Course - API Client
 * Handles all communication with the FastAPI backend
 */

class APIClient {
  constructor(baseURL = "http://127.0.0.1:8000") {
    this.baseURL = baseURL;
    this.currentStudent = null;
  }

  /**
   * Generic fetch wrapper with error handling
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    };

    try {
      // Only log non-polling requests to reduce noise
      if (!url.includes("/live-transcription")) {
        console.log(`🌐 API Request: ${config.method || "GET"} ${url}`);
      }

      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: "Unknown error" }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();

      // Only log successful transcription responses or non-polling requests
      if (
        !url.includes("/live-transcription") ||
        (data.transcriptions && data.transcriptions.length > 0)
      ) {
        console.log(`✅ API Response:`, data);
      }
      return data;
    } catch (error) {
      console.error(`❌ API Error:`, error);
      throw error;
    }
  }

  /**
   * Authentication endpoints
   */
  async login(name, studentId, password = null) {
    const requestBody = {
      name: name.trim(),
      student_id: studentId.trim(),
    };

    // Add password for admin login
    if (password) {
      requestBody.password = password;
    }

    const response = await this.request("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(requestBody),
    });

    if (response.success) {
      this.currentStudent = response.student;
      this.currentStudent.is_admin = response.is_admin;
      localStorage.setItem(
        "currentStudent",
        JSON.stringify(this.currentStudent),
      );
    }

    return response;
  }

  async validateStudent(studentId) {
    return await this.request(`/api/v1/auth/validate/${studentId}`);
  }

  async logout(studentId) {
    const response = await this.request(`/api/v1/auth/logout/${studentId}`, {
      method: "POST",
    });

    this.currentStudent = null;
    localStorage.removeItem("currentStudent");
    return response;
  }

  /**
   * Student endpoints
   */
  async getStudentProgress(studentId) {
    return await this.request(`/api/v1/students/${studentId}/progress`);
  }

  async updateStudentProgress(
    studentId,
    videoId,
    completed = false,
    score = 0.0,
  ) {
    return await this.request(`/api/v1/students/${studentId}/progress`, {
      method: "POST",
      body: JSON.stringify({
        video_id: videoId,
        completed: completed,
        score: score,
      }),
    });
  }

  async getStudentStatistics(studentId) {
    return await this.request(`/api/v1/students/${studentId}/statistics`);
  }

  async getStudentASRResults(studentId, videoId = null, limit = 50) {
    let url = `/api/v1/students/${studentId}/asr-results?limit=${limit}`;
    if (videoId) {
      url += `&video_id=${videoId}`;
    }
    return await this.request(url);
  }

  async getStudentDashboard(studentId) {
    return await this.request(`/api/v1/students/${studentId}/dashboard`);
  }

  /**
   * Video endpoints
   */
  async getAllVideos() {
    return await this.request("/api/v1/videos/");
  }

  async getVideosForStudent(studentId) {
    return await this.request(`/api/v1/videos/student/${studentId}`);
  }

  async checkVideoAccess(videoId, studentId) {
    return await this.request(`/api/v1/videos/${videoId}/access/${studentId}`);
  }

  async getVideoGroundTruth(videoId) {
    return await this.request(`/api/v1/videos/${videoId}/ground-truth`);
  }

  async setVideoGroundTruth(videoId, groundTruth) {
    return await this.request(`/api/v1/videos/${videoId}/ground-truth`, {
      method: "POST",
      body: JSON.stringify({
        ground_truth: groundTruth,
      }),
    });
  }

  async getVideoMetadata(videoId) {
    return await this.request(`/api/v1/videos/${videoId}/metadata`);
  }

  async startVideoSession(videoId, studentId) {
    return await this.request(
      `/api/v1/videos/${videoId}/start-session/${studentId}`,
      {
        method: "POST",
      },
    );
  }

  async completeVideoSession(sessionId, duration = null) {
    return await this.request(`/api/v1/videos/${sessionId}/complete`, {
      method: "POST",
      body: JSON.stringify({
        duration: duration,
      }),
    });
  }

  async initializeVideos() {
    return await this.request("/api/v1/videos/initialize", {
      method: "POST",
    });
  }

  /**
   * ASR endpoints
   */
  async startASRSession(studentId, videoId, sessionId = null) {
    return await this.request("/api/v1/asr/start-session", {
      method: "POST",
      body: JSON.stringify({
        student_id: studentId,
        video_id: videoId,
        session_id: sessionId,
      }),
    });
  }

  async submitASRResult(
    sessionId,
    studentId,
    videoId,
    transcript,
    confidence = 0.0,
    audioFilePath = null,
  ) {
    return await this.request("/api/v1/asr/submit-result", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        student_id: studentId,
        video_id: videoId,
        transcript: transcript,
        confidence: confidence,
        audio_file_path: audioFilePath,
      }),
    });
  }

  async evaluateTranscript(studentId, videoId, transcript, groundTruth = null) {
    return await this.request("/api/v1/asr/evaluate", {
      method: "POST",
      body: JSON.stringify({
        student_id: studentId,
        video_id: videoId,
        transcript: transcript,
        ground_truth: groundTruth,
      }),
    });
  }

  async getSessionResults(sessionId) {
    return await this.request(`/api/v1/asr/session/${sessionId}/results`);
  }

  async getLiveTranscription(studentId) {
    return await this.request(
      `/api/v1/asr/student/${studentId}/live-transcription`,
    );
  }

  /**
   * Buffered ASR endpoints (Circular Buffer with Control+Backtick)
   */
  async startBufferedRecording(studentId, videoId, sessionId = null) {
    return await this.request("/api/v1/asr/start-buffered-recording", {
      method: "POST",
      body: JSON.stringify({
        student_id: studentId,
        video_id: videoId,
        session_id: sessionId,
      }),
    });
  }

  async stopBufferedRecording(studentId) {
    return await this.request(
      `/api/v1/asr/stop-buffered-recording?student_id=${studentId}`,
      {
        method: "POST",
      },
    );
  }

  /**
   * Admin endpoints
   */
  async getAdminOverview(adminId) {
    return await this.request(`/api/v1/admin/overview?admin_id=${adminId}`);
  }

  async getAllStudentsData(adminId) {
    return await this.request(`/api/v1/admin/students?admin_id=${adminId}`);
  }

  async getStudentDetails(studentId, adminId) {
    return await this.request(
      `/api/v1/admin/student/${studentId}/details?admin_id=${adminId}`,
    );
  }

  async getStudentAudio(studentId, audioFilename, adminId) {
    return `${this.baseURL}/api/v1/admin/student/${studentId}/audio/${audioFilename}?admin_id=${adminId}`;
  }

  async deleteStudent(studentId, adminId) {
    return await this.request(
      `/api/v1/admin/student/${studentId}?admin_id=${adminId}`,
      {
        method: "DELETE",
      },
    );
  }

  /**
   * Health check
   */
  async healthCheck() {
    return await this.request("/health");
  }

  /**
   * Helper methods
   */
  getCurrentStudent() {
    if (!this.currentStudent) {
      const stored = localStorage.getItem("currentStudent");
      if (stored) {
        this.currentStudent = JSON.parse(stored);
      }
    }
    return this.currentStudent;
  }

  clearCurrentStudent() {
    this.currentStudent = null;
    localStorage.removeItem("currentStudent");
  }

  isLoggedIn() {
    return this.getCurrentStudent() !== null;
  }
}

// Create global API client instance
window.api = new APIClient();

// Auto-restore session on page load
document.addEventListener("DOMContentLoaded", () => {
  const student = window.api.getCurrentStudent();
  if (student) {
    console.log("👤 Restored session for student:", student.name);
  }
});
