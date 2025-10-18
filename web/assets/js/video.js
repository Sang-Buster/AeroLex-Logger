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
    this.liveEvaluationTimeout = null;
    this.pendingLiveConfidence = null;
    this.lastLiveConfidence = null;
    this.hotkeyTranscriptionInterval = null;
    this.videoStartTime = null;
    this.isVRMode = false;
    this.vrVideo = null;
    this.isHotkeyPressed = false;
    this.useDualASR = true; // Use dual ASR system by default
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

      // Add error handlers for video operations
      videoPlayer.addEventListener("error", (e) => this.onVideoError(e));
      videoPlayer.addEventListener("stalled", () => this.onVideoStalled());
      videoPlayer.addEventListener("suspend", () => this.onVideoSuspend());
      videoPlayer.addEventListener("abort", () => this.onVideoAbort());

      // Handle seeking events to prevent promise rejections
      videoPlayer.addEventListener("seeking", () => this.onVideoSeeking());
      videoPlayer.addEventListener("seeked", () => this.onVideoSeeked());
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

      // Set video source and handle loading gracefully
      videoPlayer.src = video.video_url;

      // Wrap video loading in promise to catch all errors
      const loadVideo = async () => {
        try {
          videoPlayer.load();

          // Handle any pending play promises
          if (videoPlayer.readyState >= 2) {
            return Promise.resolve();
          }

          return new Promise((resolve, reject) => {
            const onCanPlay = () => {
              videoPlayer.removeEventListener("canplay", onCanPlay);
              videoPlayer.removeEventListener("error", onError);
              resolve();
            };

            const onError = (error) => {
              videoPlayer.removeEventListener("canplay", onCanPlay);
              videoPlayer.removeEventListener("error", onError);
              console.warn("⚠️ Video load error:", error);
              resolve(); // Don't reject, just resolve to continue
            };

            videoPlayer.addEventListener("canplay", onCanPlay);
            videoPlayer.addEventListener("error", onError);
          });
        } catch (error) {
          console.warn("⚠️ Video load error:", error);
        }
      };

      loadVideo().catch((error) => {
        console.warn("⚠️ Video loading failed:", error);
      });

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
        const playPromise = videoPlayer.play();
        if (playPromise !== undefined) {
          playPromise.catch((error) => {
            console.warn("⚠️ Video resume play failed:", error);
          });
        }
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
          const playPromise = this.vrVideo.play();
          if (playPromise !== undefined) {
            playPromise.catch((error) => {
              console.warn("⚠️ VR video resume play failed:", error);
            });
          }
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
              const playPromise = this.vrVideo.play();
              if (playPromise !== undefined) {
                playPromise
                  .then(() => {
                    playButton.setAttribute(
                      "text",
                      "value: ⏸ PAUSE; align: center; color: white; width: 10",
                    );
                  })
                  .catch((error) => {
                    console.warn("⚠️ VR control play failed:", error);
                  });
              } else {
                playButton.setAttribute(
                  "text",
                  "value: ⏸ PAUSE; align: center; color: white; width: 10",
                );
              }
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
      console.log(`📊 Completing session with ${duration}s duration`);
      window.api
        .completeVideoSession(this.currentSession, duration)
        .then(() => {
          console.log("✅ Session completed successfully");
        })
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
    this.pendingLiveConfidence = null;
    this.lastLiveConfidence = null;

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
      console.log("🎙️ Starting ASR transcription service...");

      // Start the ASR service via API
      const response = await window.api.startBufferedRecording(
        student.student_id,
        this.currentVideo.id,
        this.currentSession,
      );

      if (!response.success) {
        throw new Error(response.message || "Failed to start ASR service");
      }

      console.log(
        "✅ ASR service started successfully (PID:",
        response.pid,
        ")",
      );

      // Setup UI for recording
      this.setRecordingState(true);
      this.pendingLiveConfidence = null;
      this.lastLiveConfidence = null;

      // Start live transcription updates
      this.startLiveTranscription();

      this.showNotification(
        "🎤 Recording started! Speak into your microphone.",
        "success",
      );
    } catch (error) {
      console.error("❌ Error starting recording:", error);
      this.showNotification(
        "Failed to start ASR service: " + error.message,
        "error",
      );
    }
  }

  async stopRecording() {
    if (!this.isRecording) return;

    const student = window.getCurrentStudent();
    if (!student) return;

    try {
      console.log("🛑 Stopping ASR transcription service...");

      // Calculate recording duration
      const recordingDuration = this.videoStartTime
        ? Math.floor((Date.now() - this.videoStartTime) / 1000)
        : 0;

      // Stop the ASR service via API
      const response = await window.api.stopBufferedRecording(
        student.student_id,
      );

      if (response.success) {
        console.log("✅ ASR service stopped successfully");
      }

      // Record session duration to track time spent
      if (this.currentSession && recordingDuration > 0) {
        window.api
          .completeVideoSession(this.currentSession, recordingDuration)
          .catch((error) =>
            console.warn("⚠️ Error completing session:", error),
          );
        // Reset timer so subsequent recordings measure additional time deltas
        this.videoStartTime = Date.now();
      }

      // Stop live transcription
      this.stopLiveTranscription();

      // Update UI
      this.setRecordingState(false);

      // Get final evaluation
      setTimeout(() => {
        this.showFinalEvaluation();
      }, 2000);

      this.showNotification("🛑 Recording stopped", "info");
    } catch (error) {
      console.error("❌ Error stopping recording:", error);
      // Even if stop fails, update UI
      this.stopLiveTranscription();
      this.setRecordingState(false);
    }
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

    // Track the last evaluated transcript to avoid re-evaluation
    this.lastEvaluatedTranscript = null;

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

    if (this.liveEvaluationTimeout) {
      clearTimeout(this.liveEvaluationTimeout);
      this.liveEvaluationTimeout = null;
    }

    this.pendingLiveConfidence = null;
    this.lastEvaluatedTranscript = null;
  }

  queueLiveEvaluation(transcript, confidence = null, transcriptIndex = null) {
    if (!transcript || !this.currentVideo) return;

    if (this.liveEvaluationTimeout) {
      clearTimeout(this.liveEvaluationTimeout);
    }

    const numericConfidence =
      typeof confidence === "number" && Number.isFinite(confidence)
        ? confidence
        : null;

    if (numericConfidence !== null) {
      this.pendingLiveConfidence = numericConfidence;
      this.lastLiveConfidence = numericConfidence;
    } else {
      this.pendingLiveConfidence = null;
    }

    this.liveEvaluationTimeout = setTimeout(() => {
      this.runLiveEvaluation(transcript, transcriptIndex);
    }, 600); // debounce live evaluation to reduce API spam
  }

  async runLiveEvaluation(transcript, transcriptIndex = null) {
    const cleanedTranscript = transcript.trim();
    if (!cleanedTranscript) {
      this.liveEvaluationTimeout = null;
      return;
    }

    const student = window.getCurrentStudent();
    if (!student || !this.currentVideo) {
      this.liveEvaluationTimeout = null;
      return;
    }

    try {
      const liveConfidence =
        this.pendingLiveConfidence !== null
          ? this.pendingLiveConfidence
          : this.lastLiveConfidence;

      const response = await window.api.evaluateTranscript(
        student.student_id,
        this.currentVideo.id,
        cleanedTranscript,
      );

      if (response.success && response.evaluation) {
        if (liveConfidence !== null) {
          this.lastLiveConfidence = liveConfidence;
        }

        // Update the similarity badge in the live transcription
        if (transcriptIndex !== null) {
          const transcriptEl = document.getElementById("live-transcript");
          if (transcriptEl) {
            const items = transcriptEl.querySelectorAll(".transcription-item");
            if (items[transcriptIndex]) {
              const badge =
                items[transcriptIndex].querySelector(".similarity-badge");
              if (badge) {
                const similarity = response.evaluation.similarity || 0;
                const similarityPercent = (similarity * 100).toFixed(2);
                const badgeClass = this.getSimilarityBadgeClass(similarity);
                badge.className = `similarity-badge text-xs px-2 py-1 rounded whitespace-nowrap ${badgeClass}`;
                badge.textContent = `${similarityPercent}%`;
              }
            }
          }
        }

        this.displayEvaluationResults(
          {
            transcript: cleanedTranscript,
            similarity_score: response.evaluation.similarity,
            wer: response.evaluation.wer,
            matched_ground_truth:
              response.matched_ground_truth ||
              response.evaluation.matched_ground_truth ||
              "",
            evaluation: response.evaluation,
            confidence: liveConfidence,
          },
          { autoUpdateProgress: false },
        );
      }
    } catch (error) {
      console.warn("⚠️ Error performing live evaluation:", error);
    } finally {
      this.liveEvaluationTimeout = null;
      this.pendingLiveConfidence = null;
    }
  }

  getSimilarityBadgeClass(similarity) {
    if (similarity >= 0.9) return "bg-green-100 text-green-700 font-semibold";
    if (similarity >= 0.7) return "bg-blue-100 text-blue-700 font-semibold";
    if (similarity >= 0.5) return "bg-yellow-100 text-yellow-700 font-semibold";
    return "bg-red-100 text-red-700 font-semibold";
  }

  updateLiveTranscription(transcriptions) {
    const transcriptEl = document.getElementById("live-transcript");
    if (!transcriptEl || transcriptions.length === 0) return;

    // Show latest transcriptions
    const latestTranscriptions = transcriptions.slice(-5); // Last 5

    transcriptEl.innerHTML = "";

    latestTranscriptions.forEach((transcription, index) => {
      const item = document.createElement("div");
      item.className = "transcription-item";
      item.dataset.transcriptIndex = index;
      item.dataset.timestamp = transcription.timestamp;

      const isLatest = index === latestTranscriptions.length - 1;

      // Show similarity badge if already evaluated (from transcription data)
      let badgeHtml = "";
      if (transcription.similarity_score !== undefined) {
        const similarity = transcription.similarity_score;
        const similarityPercent = (similarity * 100).toFixed(2);
        const badgeClass = this.getSimilarityBadgeClass(similarity);
        badgeHtml = `<span class="similarity-badge text-xs px-2 py-1 rounded whitespace-nowrap self-start sm:self-center ${badgeClass}">${similarityPercent}%</span>`;
      } else if (
        isLatest &&
        transcription.timestamp !== this.lastEvaluatedTranscript
      ) {
        // Only show "Evaluating..." for latest transcript if not yet evaluated AND not already pending evaluation
        badgeHtml = `<span class="similarity-badge text-xs px-2 py-1 rounded bg-gray-200 text-gray-600 whitespace-nowrap self-start sm:self-center">Evaluating...</span>`;
      }

      item.innerHTML = `
                <div class="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2">
                    <span class="text-sm text-gray-800 flex-1 break-words">${transcription.transcript}</span>
                    ${badgeHtml}
                </div>
                <div class="text-xs text-gray-500 mt-1">
                    ${new Date(transcription.timestamp).toLocaleTimeString()}
                </div>
            `;

      transcriptEl.appendChild(item);
    });

    // Auto-scroll to bottom
    transcriptEl.scrollTop = transcriptEl.scrollHeight;

    const latestEntry = latestTranscriptions[latestTranscriptions.length - 1];

    // Display evaluation results if already available
    if (
      latestEntry?.similarity_score !== undefined &&
      latestEntry?.wer !== undefined
    ) {
      this.displayEvaluationResults(
        {
          transcript: latestEntry.transcript,
          similarity_score: latestEntry.similarity_score,
          wer: latestEntry.wer,
          matched_ground_truth: latestEntry.matched_ground_truth || "",
          confidence: latestEntry.confidence,
        },
        { autoUpdateProgress: false },
      );
    }
    // Only evaluate if this is a NEW transcript we haven't evaluated before
    else if (
      this.isRecording &&
      this.currentVideo &&
      latestEntry?.transcript?.trim() &&
      latestEntry.timestamp !== this.lastEvaluatedTranscript &&
      latestEntry.similarity_score === undefined
    ) {
      this.lastEvaluatedTranscript = latestEntry.timestamp;
      console.log(
        `🔍 Evaluating NEW transcript: "${latestEntry.transcript.substring(0, 50)}..."`,
      );
      this.queueLiveEvaluation(
        latestEntry.transcript,
        latestEntry.confidence,
        latestTranscriptions.length - 1,
      );
    }
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

  displayEvaluationResults(result, options = {}) {
    const { autoUpdateProgress = true } = options;

    const resultsSection = document.getElementById("results-section");
    const resultsContent = document.getElementById("evaluation-results");

    if (!resultsSection || !resultsContent) return;

    const evaluationData = result.evaluation || {};
    const similarity =
      typeof result.similarity_score === "number"
        ? result.similarity_score
        : typeof evaluationData.similarity === "number"
          ? evaluationData.similarity
          : 0;
    const wer =
      typeof result.wer === "number"
        ? result.wer
        : typeof evaluationData.wer === "number"
          ? evaluationData.wer
          : 1;
    const confidenceRaw =
      typeof result.confidence === "number"
        ? result.confidence
        : typeof evaluationData.confidence === "number"
          ? evaluationData.confidence
          : null;

    let resolvedConfidence = confidenceRaw;
    if (
      (resolvedConfidence === null || resolvedConfidence <= 0) &&
      this.lastLiveConfidence !== null
    ) {
      resolvedConfidence = this.lastLiveConfidence;
    }

    const hasConfidence =
      typeof resolvedConfidence === "number" && resolvedConfidence > 0;
    if (hasConfidence) {
      this.lastLiveConfidence = resolvedConfidence;
    }

    const groundTruthText =
      result.matched_ground_truth ||
      evaluationData.matched_ground_truth ||
      result.ground_truth ||
      "";

    const confidenceBorderClass = hasConfidence
      ? this.getScoreBorderClass(resolvedConfidence)
      : "border-gray-300";
    const confidenceColorClass = hasConfidence
      ? this.getScoreColorClass(resolvedConfidence)
      : "text-gray-500";
    const confidenceDisplay = hasConfidence
      ? `${Math.round(resolvedConfidence * 100)}%`
      : "--";
    const isLivePreview = !autoUpdateProgress;
    const confidenceSubtitle = hasConfidence
      ? isLivePreview
        ? "Live ASR confidence"
        : "ASR model confidence"
      : isLivePreview
        ? "Live evaluation (confidence unavailable)"
        : "Confidence unavailable";

    resultsContent.innerHTML = `
            <div class="space-y-4">
                <!-- Score Cards Grid - Responsive -->
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                    <!-- Similarity Card -->
                    <div class="bg-white rounded-lg border-2 ${this.getScoreBorderClass(similarity)} p-3 sm:p-4 text-center shadow-sm hover:shadow-md transition-shadow">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 sm:mb-2">Similarity</div>
                        <div class="text-3xl sm:text-4xl font-bold ${this.getScoreColorClass(similarity)}">${(similarity * 100).toFixed(2)}%</div>
                        <div class="mt-1 sm:mt-2 text-xs text-gray-600">${this.getScoreFeedback(similarity)}</div>
                    </div>
                    
                    <!-- Word Error Rate Card -->
                    <div class="bg-white rounded-lg border-2 ${this.getWerBorderClass(wer)} p-3 sm:p-4 text-center shadow-sm hover:shadow-md transition-shadow">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 sm:mb-2">Word Error Rate</div>
                        <div class="text-3xl sm:text-4xl font-bold ${this.getWerColorClass(wer)}">${(wer * 100).toFixed(2)}%</div>
                        <div class="mt-1 sm:mt-2 text-xs text-gray-600">${this.getWerFeedback(wer)}</div>
                    </div>
                    
                    <!-- Confidence Card -->
                    <div class="bg-white rounded-lg border-2 ${confidenceBorderClass} p-3 sm:p-4 text-center shadow-sm hover:shadow-md transition-shadow">
                        <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 sm:mb-2">Confidence</div>
                        <div class="text-3xl sm:text-4xl font-bold ${confidenceColorClass}">${confidenceDisplay}</div>
                        <div class="mt-1 sm:mt-2 text-xs text-gray-600">${confidenceSubtitle}</div>
                    </div>
                </div>

                <!-- Transcript Comparison -->
                <div class="bg-gray-50 rounded-lg p-3 sm:p-4 space-y-3">
                    <div class="border-l-4 border-blue-500 pl-3">
                        <div class="text-xs font-semibold text-gray-500 uppercase mb-1">Your Transcript</div>
                        <p class="text-sm text-gray-900 break-words">${result.transcript}</p>
                    </div>
                    ${
                      groundTruthText
                        ? `
                        <div class="border-l-4 border-green-500 pl-3">
                            <div class="text-xs font-semibold text-gray-500 uppercase mb-1">Expected Radio Call</div>
                            <p class="text-sm text-gray-700 break-words">${groundTruthText}</p>
                        </div>
                    `
                        : ""
                    }
                </div>
            </div>
        `;

    resultsSection.classList.remove("hidden");

    if (autoUpdateProgress && this.currentVideo) {
      // Allow backend to complete progress update, then refresh dashboard view
      setTimeout(() => {
        if (window.dashboard) {
          window.dashboard.loadDashboard();
        }
      }, 750);
    }
  }

  getScoreBorderClass(score) {
    if (score >= 0.9) return "border-green-500";
    if (score >= 0.7) return "border-blue-500";
    if (score >= 0.5) return "border-yellow-500";
    return "border-red-500";
  }

  getScoreColorClass(score) {
    if (score >= 0.9) return "text-green-600";
    if (score >= 0.7) return "text-blue-600";
    if (score >= 0.5) return "text-yellow-600";
    return "text-red-600";
  }

  getScoreFeedback(score) {
    if (score >= 0.9) return "Excellent! 🎉";
    if (score >= 0.7) return "Good job! ✅";
    if (score >= 0.5) return "Keep practicing 📚";
    return "Try again 💪";
  }

  getWerBorderClass(wer) {
    if (wer <= 0.1) return "border-green-500";
    if (wer <= 0.3) return "border-blue-500";
    if (wer <= 0.5) return "border-yellow-500";
    return "border-red-500";
  }

  getWerColorClass(wer) {
    if (wer <= 0.1) return "text-green-600";
    if (wer <= 0.3) return "text-blue-600";
    if (wer <= 0.5) return "text-yellow-600";
    return "text-red-600";
  }

  getWerFeedback(wer) {
    if (wer <= 0.1) return "Crystal clear! 🛫";
    if (wer <= 0.3) return "Solid readback ✈️";
    if (wer <= 0.5) return "Some corrections needed ✏️";
    return "Practice the phrase again 📻";
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

  // Video error handlers
  onVideoError(event) {
    console.warn("⚠️ Video error:", event);
    const videoPlayer = document.getElementById("video-player");
    if (videoPlayer && videoPlayer.error) {
      const error = videoPlayer.error;
      console.warn("Video error details:", {
        code: error.code,
        message: error.message,
      });

      // Don't show user notification for network errors during seeking
      if (error.code !== MediaError.MEDIA_ERR_NETWORK) {
        this.showNotification("Video playback error occurred", "warning");
      }
    }
  }

  onVideoStalled() {
    console.log("⏳ Video stalled (buffering)");
  }

  onVideoSuspend() {
    console.log("⏸️ Video loading suspended");
  }

  onVideoAbort() {
    console.log("🛑 Video loading aborted");
  }

  onVideoSeeking() {
    console.log("⏩ Video seeking...");
  }

  onVideoSeeked() {
    console.log("✅ Video seek completed");
  }

  toggleVideoPlayback() {
    if (this.isVRMode && this.vrVideo) {
      if (this.vrVideo.paused) {
        const playPromise = this.vrVideo.play();
        if (playPromise !== undefined) {
          playPromise.catch((error) => {
            console.warn("⚠️ VR video play failed:", error);
          });
        }
      } else {
        this.vrVideo.pause();
      }
    } else {
      const videoPlayer = document.getElementById("video-player");
      if (videoPlayer) {
        if (videoPlayer.paused) {
          const playPromise = videoPlayer.play();
          if (playPromise !== undefined) {
            playPromise.catch((error) => {
              console.warn("⚠️ Video play failed:", error);
            });
          }
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
