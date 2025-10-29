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
    this.activeRecordingStudentId = null;
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
    const enterVRBtn = document.getElementById("enter-vr-button");
    const exitVRBtn = document.getElementById("exit-vr-button");

    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", () => this.closeVideo());
    }

    if (startRecordingBtn) {
      startRecordingBtn.addEventListener("click", () => this.startRecording());
    }

    if (stopRecordingBtn) {
      stopRecordingBtn.addEventListener("click", () => this.stopRecording());
    }

    if (enterVRBtn) {
      enterVRBtn.addEventListener("click", () => this.enterVRMode());
    }

    if (exitVRBtn) {
      exitVRBtn.addEventListener("click", () => this.exitVRMode());
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
            // Exit VR mode if active, otherwise close video
            if (this.isVRMode) {
              e.preventDefault();
              this.exitVRMode();
            } else {
              this.closeVideo();
            }
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
    const videoPlayer = document.getElementById("video-player");
    const vrVideosphere = document.getElementById("vr-videosphere");

    if (!videoPlayer) return;

    // Always load the regular video player
    videoPlayer.src = video.video_url;
    
    // Explicitly pause to prevent autoplay
    videoPlayer.pause();

    // Wrap video loading in promise to catch all errors
    const loadVideoAsync = async () => {
      try {
        videoPlayer.load();
        
        // Ensure video is paused after loading
        videoPlayer.pause();

        // Handle any pending play promises
        if (videoPlayer.readyState >= 2) {
          return Promise.resolve();
        }

        return new Promise((resolve) => {
          const onCanPlay = () => {
            videoPlayer.removeEventListener("canplay", onCanPlay);
            videoPlayer.removeEventListener("error", onError);
            // Make sure video doesn't autoplay
            videoPlayer.pause();
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

    loadVideoAsync().catch((error) => {
      console.warn("⚠️ Video loading failed:", error);
    });

    // Setup VR videosphere with the same source (for VR headset viewing)
    if (vrVideosphere) {
      vrVideosphere.setAttribute("src", video.video_url);
      vrVideosphere.setAttribute("autoplay", "false");
      
      // Also pause the underlying video element if accessible
      setTimeout(() => {
        const vrVideoEl = vrVideosphere.components?.material?.material?.map?.image;
        if (vrVideoEl && typeof vrVideoEl.pause === 'function') {
          vrVideoEl.pause();
        }
      }, 100);
    }

    // Detect if this is a VR/360 video and show VR button
    const isVRVideo = this.isVRVideo(video);
    if (isVRVideo) {
      this.showVRButton();
    } else {
      this.hideVRButton();
    }
  }

  isVRVideo(video) {
    // OPTION A: Make ALL videos show VR mode (no keyword check)
    return true;

    // OPTION B: Check if video filename/title contains VR indicators (currently disabled)
    // const vrIndicators = ["360", "vr", "360°", "panoramic", "spherical", "flight", "training"];
    // const videoTitle = (video.title || "").toLowerCase();
    // const videoFilename = (video.filename || "").toLowerCase();
    // const videoUrl = (video.video_url || "").toLowerCase();
    //
    // return vrIndicators.some(
    //   (indicator) =>
    //     videoTitle.includes(indicator) ||
    //     videoFilename.includes(indicator) ||
    //     videoUrl.includes(indicator),
    // );
  }

  /**
   * Enter VR mode - Uses A-Frame's VR presentation API
   * Regular video stays visible on desktop for controls
   * VR scene shows in headset for immersive viewing
   */
  async enterVRMode() {
    const scene = document.getElementById("vr-scene");
    const sceneContainer = document.getElementById("vr-scene-container");
    const videoPlayer = document.getElementById("video-player");
    const vrVideosphere = document.getElementById("vr-videosphere");

    if (!scene || !sceneContainer || !videoPlayer || !vrVideosphere) {
      console.warn("⚠️ VR scene elements not found");
      this.showNotification("VR scene not available", "error");
      return;
    }

    if (!videoPlayer.src) {
      console.warn("⚠️ No video loaded");
      this.showNotification("Please wait for video to load", "warning");
      return;
    }

    try {
      console.log("🥽 Entering VR mode...");

      // Sync VR video with regular video before entering VR
      const currentTime = videoPlayer.currentTime;
      const paused = videoPlayer.paused;

      // Make scene visible
      sceneContainer.classList.remove("hidden");

      // Ensure videosphere has the correct source
      const videoUrl = videoPlayer.src;
      console.log("📹 Setting VR video source:", videoUrl);
      vrVideosphere.setAttribute("src", videoUrl);

      // Wait for scene to be ready
      await new Promise((resolve) => {
        if (scene.hasLoaded) {
          resolve();
        } else {
          scene.addEventListener("loaded", resolve, { once: true });
          // Timeout fallback
          setTimeout(resolve, 2000);
        }
      });

      // Wait a moment for the videosphere to process the video
      await new Promise((resolve) => setTimeout(resolve, 500));

      // Get the actual video element from A-Frame videosphere
      this.vrVideo = vrVideosphere.components?.material?.material?.map?.image;

      if (!this.vrVideo) {
        console.error("❌ Failed to get VR video element");
        throw new Error("VR video element not found");
      }

      console.log("✅ VR video element found");

      // Sync time and playback state
      this.vrVideo.currentTime = currentTime;

      // Make sure video plays if it was playing
      if (!paused) {
        console.log("▶️ Playing VR video");
        const playPromise = this.vrVideo.play();
        if (playPromise !== undefined) {
          playPromise.catch((error) => {
            console.warn("⚠️ VR video play failed:", error);
            this.showNotification(
              "Click on the video to start playback",
              "info",
            );
          });
        }
      }

      // Set up continuous sync between regular video and VR video
      this.setupVRVideoSync();

      this.isVRMode = true;
      console.log("✅ VR mode active");

      // Enter VR presentation mode if headset available
      if (scene.hasWebXR) {
        scene.enterVR();
        console.log("🥽 Entered VR headset mode");

        // Listen for VR exit
        scene.addEventListener(
          "exit-vr",
          () => {
            this.exitVRMode();
          },
          { once: true },
        );
      } else {
        console.log("🖥️ VR mode active (no WebXR headset detected)");
        this.showNotification("VR mode active (press ESC to exit)", "info");
      }
    } catch (error) {
      console.error("❌ Error entering VR mode:", error);
      this.showNotification(
        "Failed to enter VR mode: " + error.message,
        "error",
      );
      sceneContainer.classList.add("hidden");
      this.isVRMode = false;
    }
  }

  /**
   * Exit VR mode - Called automatically when user exits VR in headset or clicks exit button
   */
  exitVRMode() {
    if (!this.isVRMode) {
      return; // Already exited
    }

    console.log("🚪 Exiting VR mode...");

    const scene = document.getElementById("vr-scene");
    const sceneContainer = document.getElementById("vr-scene-container");
    const videoPlayer = document.getElementById("video-player");

    // Exit VR presentation mode if active
    if (scene && scene.is && scene.is("vr-mode")) {
      try {
        scene.exitVR();
      } catch (error) {
        console.warn("⚠️ Error exiting VR presentation:", error);
      }
    }

    // Hide VR scene
    if (sceneContainer) {
      sceneContainer.classList.add("hidden");
    }

    // Clear VR video sync
    if (this.vrSyncInterval) {
      clearInterval(this.vrSyncInterval);
      this.vrSyncInterval = null;
    }

    // Sync back to regular video
    if (this.vrVideo && videoPlayer) {
      try {
        const vrTime = this.vrVideo.currentTime;
        const vrPaused = this.vrVideo.paused;

        if (!isNaN(vrTime)) {
          videoPlayer.currentTime = vrTime;
        }

        if (!vrPaused && videoPlayer.paused) {
          const playPromise = videoPlayer.play();
          if (playPromise !== undefined) {
            playPromise.catch((error) => {
              console.warn("⚠️ Video play failed:", error);
            });
          }
        }
      } catch (error) {
        console.warn("⚠️ Error syncing video on exit:", error);
      }
    }

    this.isVRMode = false;
    this.vrVideo = null;
    console.log("✅ Exited VR mode");
    this.showNotification("Exited VR mode", "info");
  }

  /**
   * Sync regular video controls with VR video
   * Allows desktop controls to work while in VR headset
   */
  setupVRVideoSync() {
    const videoPlayer = document.getElementById("video-player");

    if (!videoPlayer || !this.vrVideo) return;

    // Clear any existing sync
    if (this.vrSyncInterval) {
      clearInterval(this.vrSyncInterval);
    }

    // Sync play/pause from regular video to VR video
    const syncPlayPause = () => {
      if (!this.vrVideo || !videoPlayer) return;

      if (videoPlayer.paused && !this.vrVideo.paused) {
        this.vrVideo.pause();
      } else if (!videoPlayer.paused && this.vrVideo.paused) {
        const playPromise = this.vrVideo.play();
        if (playPromise !== undefined) {
          playPromise.catch((error) => {
            console.warn("⚠️ VR video sync play failed:", error);
          });
        }
      }
    };

    // Sync seeking from regular video to VR video
    const syncSeeking = () => {
      if (!this.vrVideo || !videoPlayer) return;

      const timeDiff = Math.abs(
        videoPlayer.currentTime - this.vrVideo.currentTime,
      );
      if (timeDiff > 0.5) {
        // Only sync if difference is significant
        this.vrVideo.currentTime = videoPlayer.currentTime;
      }
    };

    videoPlayer.addEventListener("play", syncPlayPause);
    videoPlayer.addEventListener("pause", syncPlayPause);
    videoPlayer.addEventListener("seeked", syncSeeking);

    // Periodic sync to handle any drift
    this.vrSyncInterval = setInterval(() => {
      syncPlayPause();
      syncSeeking();
    }, 500);
  }

  setupVRControls() {
    // VR controls are handled through desktop video player
    // No in-headset controls needed since desktop controls work
  }

  showVRButton() {
    const enterVRBtn = document.getElementById("enter-vr-button");
    if (enterVRBtn) {
      enterVRBtn.classList.remove("hidden");
    }
  }

  hideVRButton() {
    const enterVRBtn = document.getElementById("enter-vr-button");
    if (enterVRBtn) {
      enterVRBtn.classList.add("hidden");
    }
  }

  async closeVideo(options = {}) {
    const { silentStop = false } = options;
    console.log("🔚 Closing video");

    // Exit VR mode if active
    if (this.isVRMode) {
      const scene = document.getElementById("vr-scene");
      if (scene && scene.is("vr-mode")) {
        scene.exitVR();
      }
      this.exitVRMode();
    }

    // Stop recording if active
    await this.stopRecordingIfActive({ silent: silentStop });

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

    // Refresh dashboard to show updated progress (only if not in admin mode)
    if (!options.silentStop) {
      setTimeout(() => {
        const currentStudent = window.api?.getCurrentStudent();
        if (currentStudent && !currentStudent.is_admin) {
          window.dashboard?.loadDashboard();
        }
      }, 1000);
    }
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
      this.activeRecordingStudentId = student.student_id;

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

  async stopRecording(options = {}) {
    const { silent = false } = options;
    if (!this.isRecording) return;

    const student = window.getCurrentStudent();
    const studentId = student?.student_id || this.activeRecordingStudentId;
    if (!studentId) {
      console.warn("⚠️ Unable to determine student ID when stopping recording");
      return;
    }

    try {
      console.log("🛑 Stopping ASR transcription service...");

      // Calculate recording duration
      const recordingDuration = this.videoStartTime
        ? Math.floor((Date.now() - this.videoStartTime) / 1000)
        : 0;

      // Stop the ASR service via API
      const response = await window.api.stopBufferedRecording(studentId);

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
      if (!silent) {
        setTimeout(() => {
          this.showFinalEvaluation();
        }, 2000);

        this.showNotification("🛑 Recording stopped", "info");
      }
    } catch (error) {
      console.error("❌ Error stopping recording:", error);
      // Even if stop fails, update UI
      this.stopLiveTranscription();
      this.setRecordingState(false);
    } finally {
      this.activeRecordingStudentId = null;
    }
  }

  toggleRecording() {
    if (this.isRecording) {
      this.stopRecording();
    } else {
      this.startRecording();
    }
  }

  async stopRecordingIfActive(options = {}) {
    const { silent = false } = options;

    if (this.isRecording) {
      await this.stopRecording({ silent });
      return;
    }

    if (this.activeRecordingStudentId) {
      try {
        await window.api.stopBufferedRecording(this.activeRecordingStudentId);
        console.log(
          "🛑 Force-stopped buffered recording for student",
          this.activeRecordingStudentId,
        );
      } catch (error) {
        console.warn("⚠️ Failed to force stop buffered recording:", error);
      } finally {
        this.activeRecordingStudentId = null;
        this.setRecordingState(false);
        this.stopLiveTranscription();
      }
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

    // Filter transcriptions by current video ID
    const currentVideoId = this.currentVideo?.id;
    const filteredTranscriptions = currentVideoId
      ? transcriptions.filter((t) => t.video_id === currentVideoId)
      : transcriptions;

    // Show latest transcriptions
    const latestTranscriptions = filteredTranscriptions.slice(-5); // Last 5

    transcriptEl.innerHTML = "";

    // If no transcriptions match the current video, show placeholder
    if (latestTranscriptions.length === 0) {
      transcriptEl.innerHTML =
        '<p class="text-gray-400">Start speaking to see live transcription...</p>';
      return;
    }

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
    // Always control the regular video player
    // VR video will sync automatically if VR mode is active
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
