/**
 * VR Flight Training Course - Video Player Module
 * Handles video playback, ASR recording, and real-time transcription
 */

class VideoPlayerManager {
  constructor() {
    this.currentVideo = null;
    this.currentSession = null;
    this.isRecording = false;
    this.mediaRecorder = null;
    this.audioStream = null;
    this.transcriptionInterval = null;
    this.videoStartTime = null;
    this.isVRMode = false;
    this.vrVideo = null;
    this.init();
  }

  init() {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () =>
        this.setupEventListeners(),
      );
    } else {
      this.setupEventListeners();
    }
  }

  setupEventListeners() {
    // Modal controls
    const closeModalBtn = document.getElementById("close-modal");
    const startRecordingBtn = document.getElementById("start-recording");
    const stopRecordingBtn = document.getElementById("stop-recording");
    const toggleVRBtn = document.getElementById("toggle-vr-mode");

    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", () => this.closeVideo());
    }

    if (startRecordingBtn) {
      startRecordingBtn.addEventListener("click", () => this.startRecording());
    }

    if (stopRecordingBtn) {
      stopRecordingBtn.addEventListener("click", () => this.stopRecording());
    }

    if (toggleVRBtn) {
      toggleVRBtn.addEventListener("click", () => this.toggleVRMode());
    }

    // Video player events
    const videoPlayer = document.getElementById("video-player");
    if (videoPlayer) {
      videoPlayer.addEventListener("play", () => this.onVideoPlay());
      videoPlayer.addEventListener("pause", () => this.onVideoPause());
      videoPlayer.addEventListener("ended", () => this.onVideoEnd());
    }

    // VR controls
    this.setupVRControls();

    // Modal background click to close
    const modal = document.getElementById("video-modal");
    if (modal) {
      modal.addEventListener("click", (e) => {
        if (e.target === modal) {
          this.closeVideo();
        }
      });
    }

    // Keyboard shortcuts
    document.addEventListener("keydown", (e) => {
      if (this.currentVideo) {
        switch (e.key) {
          case "Escape":
            this.closeVideo();
            break;
          case " ":
            if (
              e.target.tagName !== "INPUT" &&
              e.target.tagName !== "TEXTAREA"
            ) {
              e.preventDefault();
              this.toggleVideoPlayback();
            }
            break;
          case "r":
            if (e.ctrlKey || e.metaKey) {
              e.preventDefault();
              this.toggleRecording();
            }
            break;
        }
      }
    });
  }

  async openVideo(video) {
    console.log("🎬 Opening video:", video.title);

    // Check access
    if (!video.unlocked) {
      this.showNotification(
        "This video is locked. Complete previous videos first.",
        "warning",
      );
      return;
    }

    const student = window.getCurrentStudent();
    if (!student) {
      this.showNotification("Please log in to watch videos", "error");
      return;
    }

    try {
      this.currentVideo = video;
      this.videoStartTime = Date.now();

      // Start video session
      const sessionResponse = await window.api.startVideoSession(
        video.id,
        student.student_id,
      );
      this.currentSession = sessionResponse.session_id;

      // Update modal content
      this.updateModalContent(video);

      // Show modal
      const modal = document.getElementById("video-modal");
      if (modal) {
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden"; // Prevent background scroll
      }

      // Load video
      this.loadVideo(video);

      console.log("✅ Video opened successfully");
    } catch (error) {
      console.error("❌ Error opening video:", error);
      this.showNotification("Failed to open video", "error");
    }
  }

  updateModalContent(video) {
    const titleEl = document.getElementById("modal-video-title");
    const descEl = document.getElementById("modal-video-description");

    if (titleEl) titleEl.textContent = video.title;
    if (descEl)
      descEl.textContent =
        video.description || `Training video ${video.order_index}`;
  }

  loadVideo(video) {
    // Detect if this is a VR video (360 video)
    const isVRVideo = this.isVRVideo(video);

    if (isVRVideo) {
      this.setupVRVideo(video);
      this.showVRToggleButton();
    } else {
      this.setupRegularVideo(video);
      this.hideVRToggleButton();
    }
  }

  isVRVideo(video) {
    // Check if video filename/title contains VR indicators
    const vrIndicators = ["360", "vr", "360°", "panoramic", "spherical"];
    const videoTitle = (video.title || "").toLowerCase();
    const videoFilename = (video.filename || "").toLowerCase();
    const videoUrl = (video.video_url || "").toLowerCase();

    return vrIndicators.some(
      (indicator) =>
        videoTitle.includes(indicator) ||
        videoFilename.includes(indicator) ||
        videoUrl.includes(indicator),
    );
  }

  setupRegularVideo(video) {
    const videoPlayer = document.getElementById("video-player");
    const vrContainer = document.getElementById("vr-player-container");

    if (videoPlayer && vrContainer) {
      videoPlayer.classList.remove("hidden");
      vrContainer.classList.add("hidden");
      videoPlayer.src = video.video_url;
      videoPlayer.load();
      this.isVRMode = false;
    }
  }

  setupVRVideo(video) {
    const videoPlayer = document.getElementById("video-player");
    const vrContainer = document.getElementById("vr-player-container");
    const vrVideosphere = document.getElementById("vr-videosphere");

    if (videoPlayer && vrContainer && vrVideosphere) {
      // Initially show regular video player
      videoPlayer.classList.remove("hidden");
      vrContainer.classList.add("hidden");
      videoPlayer.src = video.video_url;
      videoPlayer.load();

      // Set up VR videosphere src
      vrVideosphere.setAttribute("src", video.video_url);
      this.isVRMode = false;
    }
  }

  toggleVRMode() {
    const videoPlayer = document.getElementById("video-player");
    const vrContainer = document.getElementById("vr-player-container");
    const toggleBtn = document.getElementById("toggle-vr-mode");
    const vrVideosphere = document.getElementById("vr-videosphere");

    if (!videoPlayer || !vrContainer || !toggleBtn || !vrVideosphere) return;

    if (this.isVRMode) {
      // Switch to regular video
      const currentTime = this.vrVideo ? this.vrVideo.currentTime : 0;
      const paused = this.vrVideo ? this.vrVideo.paused : true;

      videoPlayer.classList.remove("hidden");
      vrContainer.classList.add("hidden");

      if (currentTime > 0) {
        videoPlayer.currentTime = currentTime;
      }
      if (!paused) {
        videoPlayer.play();
      }

      toggleBtn.textContent = "🥽 Switch to VR Mode";
      this.isVRMode = false;
    } else {
      // Switch to VR mode
      const currentTime = videoPlayer.currentTime;
      const paused = videoPlayer.paused;

      videoPlayer.classList.add("hidden");
      vrContainer.classList.remove("hidden");

      // Get the video element from A-Frame
      setTimeout(() => {
        this.vrVideo = vrVideosphere.components.material.material.map.image;
        if (this.vrVideo && currentTime > 0) {
          this.vrVideo.currentTime = currentTime;
        }
        if (this.vrVideo && !paused) {
          this.vrVideo.play();
        }
      }, 100);

      toggleBtn.textContent = "📺 Switch to Regular Mode";
      this.isVRMode = true;
    }
  }

  setupVRControls() {
    // Set up A-Frame VR controls when available
    document.addEventListener("DOMContentLoaded", () => {
      const playButton = document.getElementById("vr-play-button");
      if (playButton) {
        playButton.addEventListener("click", () => {
          if (this.vrVideo) {
            if (this.vrVideo.paused) {
              this.vrVideo.play();
              playButton.setAttribute(
                "text",
                "value: ⏸ PAUSE; align: center; color: white; width: 10",
              );
            } else {
              this.vrVideo.pause();
              playButton.setAttribute(
                "text",
                "value: ▶ PLAY; align: center; color: white; width: 10",
              );
            }
          }
        });
      }
    });
  }

  showVRToggleButton() {
    const toggleBtn = document.getElementById("toggle-vr-mode");
    if (toggleBtn) {
      toggleBtn.classList.remove("hidden");
    }
  }

  hideVRToggleButton() {
    const toggleBtn = document.getElementById("toggle-vr-mode");
    if (toggleBtn) {
      toggleBtn.classList.add("hidden");
    }
  }

  closeVideo() {
    console.log("🔚 Closing video");

    // Stop recording if active
    if (this.isRecording) {
      this.stopRecording();
    }

    // Complete session if active
    if (this.currentSession && this.videoStartTime) {
      const duration = Math.floor((Date.now() - this.videoStartTime) / 1000);
      window.api
        .completeVideoSession(this.currentSession, duration)
        .catch((error) => console.warn("⚠️ Error completing session:", error));
    }

    // Hide modal
    const modal = document.getElementById("video-modal");
    if (modal) {
      modal.classList.add("hidden");
      document.body.style.overflow = ""; // Restore scroll
    }

    // Reset state
    this.currentVideo = null;
    this.currentSession = null;
    this.videoStartTime = null;

    // Clear transcription
    this.clearTranscription();

    // Refresh dashboard to show updated progress
    setTimeout(() => {
      window.dashboard?.loadDashboard();
    }, 1000);
  }

  async startRecording() {
    if (this.isRecording) return;

    const student = window.getCurrentStudent();
    if (!student || !this.currentVideo) return;

    try {
      console.log("🎙️ Starting ASR recording");

      // Request microphone access
      this.audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Start ASR session
      await window.api.startASRSession(
        student.student_id,
        this.currentVideo.id,
        this.currentSession,
      );

      // Setup UI for recording
      this.setRecordingState(true);

      // Start live transcription updates
      this.startLiveTranscription();

      console.log("✅ Recording started");
    } catch (error) {
      console.error("❌ Error starting recording:", error);
      this.showNotification(
        "Failed to start recording. Please check microphone permissions.",
        "error",
      );
    }
  }

  async stopRecording() {
    if (!this.isRecording) return;

    console.log("🛑 Stopping ASR recording");

    // Stop media stream
    if (this.audioStream) {
      this.audioStream.getTracks().forEach((track) => track.stop());
      this.audioStream = null;
    }

    // Stop live transcription
    this.stopLiveTranscription();

    // Update UI
    this.setRecordingState(false);

    // Get final evaluation
    setTimeout(() => {
      this.showFinalEvaluation();
    }, 2000);

    console.log("✅ Recording stopped");
  }

  toggleRecording() {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  }

  setRecordingState(recording) {
    this.isRecording = recording;

    const startBtn = document.getElementById("start-recording");
    const stopBtn = document.getElementById("stop-recording");
    const statusEl = document.getElementById("recording-status");

    if (startBtn && stopBtn && statusEl) {
      if (recording) {
        startBtn.classList.add("hidden");
        stopBtn.classList.remove("hidden");
        statusEl.classList.remove("hidden");
      } else {
        startBtn.classList.remove("hidden");
        stopBtn.classList.add("hidden");
        statusEl.classList.add("hidden");
      }
    }
  }

  startLiveTranscription() {
    if (this.transcriptionInterval) return;

    const student = window.getCurrentStudent();
    if (!student) return;

    this.transcriptionInterval = setInterval(async () => {
      try {
        const response = await window.api.getLiveTranscription(
          student.student_id,
        );
        if (response.success && response.transcriptions.length > 0) {
          this.updateLiveTranscription(response.transcriptions);
        }
      } catch (error) {
        console.warn("⚠️ Error fetching live transcription:", error);
      }
    }, 2000); // Update every 2 seconds
  }

  stopLiveTranscription() {
    if (this.transcriptionInterval) {
      clearInterval(this.transcriptionInterval);
      this.transcriptionInterval = null;
    }
  }

  updateLiveTranscription(transcriptions) {
    const transcriptEl = document.getElementById("live-transcript");
    if (!transcriptEl || transcriptions.length === 0) return;

    // Show latest transcriptions
    const latestTranscriptions = transcriptions.slice(-5); // Last 5

    transcriptEl.innerHTML = "";

    latestTranscriptions.forEach((transcription) => {
      const item = document.createElement("div");
      item.className = "transcription-item";

      const confidence = transcription.confidence || 0;
      const confidenceClass =
        confidence > 0.8 ? "high" : confidence > 0.6 ? "medium" : "low";

      item.innerHTML = `
                <div class="flex justify-between items-start">
                    <span class="text-sm text-gray-800">${transcription.transcript}</span>
                    <span class="transcription-confidence ${confidenceClass} ml-2">
                        ${Math.round(confidence * 100)}%
                    </span>
                </div>
                <div class="text-xs text-gray-500 mt-1">
                    ${new Date(transcription.timestamp).toLocaleTimeString()}
                </div>
            `;

      transcriptEl.appendChild(item);
    });

    // Auto-scroll to bottom
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  clearTranscription() {
    const transcriptEl = document.getElementById("live-transcript");
    if (transcriptEl) {
      transcriptEl.innerHTML =
        '<p class="text-gray-400">Start speaking to see live transcription...</p>';
    }
  }

  async showFinalEvaluation() {
    if (!this.currentSession) return;

    try {
      const results = await window.api.getSessionResults(this.currentSession);

      if (results.success && results.results.length > 0) {
        const latestResult = results.results[0];
        this.displayEvaluationResults(latestResult);
      }
    } catch (error) {
      console.warn("⚠️ Error getting evaluation results:", error);
    }
  }

  displayEvaluationResults(result) {
    const resultsSection = document.getElementById("results-section");
    const resultsContent = document.getElementById("evaluation-results");

    if (!resultsSection || !resultsContent) return;

    const similarity = result.similarity_score || 0;
    const wer = result.wer || 1;
    const confidence = result.confidence || 0;

    resultsContent.innerHTML = `
            <div class="score-display">
                <div class="score-item">
                    <div class="score-value ${this.getScoreClass(similarity)}">${Math.round(similarity * 100)}%</div>
                    <div class="score-label">Similarity</div>
                </div>
                <div class="score-item">
                    <div class="score-value ${this.getScoreClass(1 - wer)}">${Math.round((1 - wer) * 100)}%</div>
                    <div class="score-label">Accuracy</div>
                </div>
                <div class="score-item">
                    <div class="score-value ${this.getScoreClass(confidence)}">${Math.round(confidence * 100)}%</div>
                    <div class="score-label">Confidence</div>
                </div>
            </div>
            <div class="mt-4">
                <p class="text-sm"><strong>Your transcript:</strong> ${result.transcript}</p>
                ${result.ground_truth ? `<p class="text-sm mt-2"><strong>Expected:</strong> ${result.ground_truth}</p>` : ""}
            </div>
        `;

    resultsSection.classList.remove("hidden");

    // Update progress if score is good
    if (similarity > 0.7) {
      const student = window.getCurrentStudent();
      if (student) {
        window.api
          .updateStudentProgress(
            student.student_id,
            this.currentVideo.id,
            true,
            similarity,
          )
          .catch((error) => console.warn("⚠️ Error updating progress:", error));
      }
    }
  }

  getScoreClass(score) {
    if (score >= 0.9) return "excellent";
    if (score >= 0.7) return "good";
    if (score >= 0.5) return "average";
    return "poor";
  }

  // Video player controls
  onVideoPlay() {
    console.log("▶️ Video started playing");
  }

  onVideoPause() {
    console.log("⏸️ Video paused");
  }

  onVideoEnd() {
    console.log("🏁 Video ended");
    // Auto-stop recording if still active
    if (this.isRecording) {
      this.stopRecording();
    }
  }

  toggleVideoPlayback() {
    if (this.isVRMode && this.vrVideo) {
      if (this.vrVideo.paused) {
        this.vrVideo.play();
      } else {
        this.vrVideo.pause();
      }
    } else {
      const videoPlayer = document.getElementById("video-player");
      if (videoPlayer) {
        if (videoPlayer.paused) {
          videoPlayer.play();
        } else {
          videoPlayer.pause();
        }
      }
    }
  }

  showNotification(message, type = "info") {
    // Reuse dashboard notification system
    if (window.dashboard) {
      window.dashboard.showNotification(message, type);
    } else {
      console.log(`${type.toUpperCase()}: ${message}`);
    }
  }
}

// Create global video player manager instance
window.videoPlayer = new VideoPlayerManager();
