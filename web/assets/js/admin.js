/**
 * VR Flight Training Course - Admin Module
 * Handles admin dashboard functionality and student data management
 */

class AdminManager {
  constructor() {
    this.recordingsModal = null;
    this.recordingsContent = null;
    this.recordingsStatus = null;
    this.recordingsTitle = null;
    this.recordingsMeta = null;
    this.activeAudio = null;
    this.activeAudioButton = null;
    this.init();
  }

  init() {
    // Wait for DOM to be ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () =>
        this.setupEventListeners(),
      );
    } else {
      this.setupEventListeners();
    }
  }

  setupEventListeners() {
    // Get refresh button
    const refreshBtn = document.getElementById("refresh-data-btn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => this.loadAdminDashboard());
    }

    this.recordingsModal = document.getElementById("admin-recordings-modal");
    this.recordingsContent = document.getElementById(
      "admin-recordings-content",
    );
    this.recordingsStatus = document.getElementById("admin-recordings-status");
    this.recordingsTitle = document.getElementById("admin-recordings-title");
    this.recordingsMeta = document.getElementById("admin-recordings-meta");

    const closeModalBtn = document.getElementById("admin-recordings-close");
    if (closeModalBtn) {
      closeModalBtn.addEventListener("click", () =>
        this.closeRecordingsModal(),
      );
    }

    if (this.recordingsModal) {
      this.recordingsModal.addEventListener("click", (event) => {
        if (event.target === this.recordingsModal) {
          this.closeRecordingsModal();
        }
      });
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && this.recordingsModal) {
        const isHidden = this.recordingsModal.classList.contains("hidden");
        if (!isHidden) {
          this.closeRecordingsModal();
        }
      }
    });

    console.log("🔧 Admin manager initialized");
  }

  async loadAdminDashboard() {
    const admin = window.api.getCurrentStudent();

    if (!admin || !admin.is_admin) {
      console.error("❌ Admin access required");
      return;
    }

    try {
      // Load overview data and students data in parallel
      const [overviewData, studentsData] = await Promise.all([
        window.api.getAdminOverview(admin.student_id),
        window.api.getAllStudentsData(admin.student_id),
      ]);

      // Update overview stats
      this.updateOverviewStats(overviewData);

      // Update students table
      this.updateStudentsTable(studentsData);

      console.log("✅ Admin dashboard loaded successfully");
    } catch (error) {
      console.error("❌ Failed to load admin dashboard:", error);
      this.showError("Failed to load admin data. Please try again.");
    }
  }

  updateOverviewStats(data) {
    // Update overview statistics
    const elements = {
      "admin-total-students": data.total_students || 0,
      "admin-active-students": data.active_students || 0,
      "admin-class-average": `${data.class_average || 0}%`,
    };

    Object.entries(elements).forEach(([id, value]) => {
      const element = document.getElementById(id);
      if (element) {
        element.textContent = value;
      }
    });
  }

  updateStudentsTable(studentsData) {
    const tableBody = document.getElementById("students-table-body");

    if (!tableBody) {
      console.error("❌ Students table body not found");
      return;
    }

    if (!studentsData || studentsData.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-4 text-center text-gray-500">
            No students found
          </td>
        </tr>
      `;
      return;
    }

    // Generate table rows
    const rows = studentsData
      .map((student) => this.createStudentRow(student))
      .join("");
    tableBody.innerHTML = rows;

    this.setupRecordingsButtons();
    // Add event listeners for audio playback
    this.setupAudioPlaybackListeners();
  }

  createStudentRow(student) {
    const audioFilesList = this.createAudioFilesDisplay(student);

    const hasRecentActivity = Boolean(student.latest_activity);
    const lastActivity = hasRecentActivity
      ? this.formatTimestamp(student.latest_activity)
      : "No activity";
    const lastActivityClass = hasRecentActivity
      ? "text-gray-900"
      : "text-gray-400";

    const progressBar = this.createProgressBar(student.completion_rate);
    const averageScore = this.formatScore(student.average_score);
    const totalAttempts = Number(student.total_attempts || 0).toLocaleString();
    const timeSpent = this.formatMinutes(student.time_spent_minutes);

    return `
      <tr class="hover:bg-gray-50">
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm font-medium text-gray-900">${student.name}</div>
          <div class="text-sm text-gray-500">ID: ${student.student_id}</div>
          <div class="text-xs text-gray-400">Joined: ${new Date(student.created_at).toLocaleDateString()}</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm text-gray-900">
            ${student.completed_videos}/${student.total_videos} videos
          </div>
          ${progressBar}
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm font-medium text-gray-900">${averageScore}</div>
          <div class="text-xs text-gray-500">Average</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm text-gray-900">${totalAttempts}</div>
          <div class="text-xs text-gray-500">Total attempts</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm text-gray-900">${timeSpent}</div>
          <div class="text-xs text-gray-500">Total time</div>
        </td>
        <td class="px-6 py-4">
          <div class="text-sm max-w-xs overflow-hidden">
            ${audioFilesList}
          </div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm">
          <span class="${lastActivityClass}">${lastActivity}</span>
        </td>
      </tr>
    `;
  }

  createProgressBar(completionRate) {
    const percentage = Math.min(100, Math.max(0, completionRate));
    const colorClass =
      percentage >= 80
        ? "bg-green-500"
        : percentage >= 50
          ? "bg-yellow-500"
          : "bg-red-500";

    return `
      <div class="w-full bg-gray-200 rounded-full h-2 mt-1">
        <div class="${colorClass} h-2 rounded-full" style="width: ${percentage}%"></div>
      </div>
      <div class="text-xs text-gray-500 mt-1">${percentage.toFixed(1)}% complete</div>
    `;
  }

  setupRecordingsButtons() {
    const viewButtons = document.querySelectorAll(".view-recordings-btn");

    viewButtons.forEach((button) => {
      if (button.dataset.listenerAttached === "true") {
        return;
      }

      button.dataset.listenerAttached = "true";

      button.addEventListener("click", (event) => {
        event.preventDefault();
        const studentId = button.getAttribute("data-student-id");
        const studentName =
          button.getAttribute("data-student-name") || "Student";
        const recordingCount = Number(
          button.getAttribute("data-recording-count") || 0,
        );

        if (!studentId) {
          console.warn("⚠️ Missing student id for recordings modal trigger");
          return;
        }

        this.openRecordingsModal({
          studentId,
          studentName,
          recordingCount,
        });
      });
    });
  }

  setupAudioPlaybackListeners() {
    const playButtons = document.querySelectorAll(".play-audio-btn");

    playButtons.forEach((button) => {
      if (button.dataset.listenerAttached === "true") {
        return;
      }

      button.dataset.listenerAttached = "true";
      button.dataset.audioState = button.dataset.audioState || "idle";

      button.addEventListener("click", (event) => {
        event.preventDefault();
        const studentId = button.getAttribute("data-student-id");
        const audioFile = button.getAttribute("data-audio-file");

        if (!studentId || !audioFile) {
          console.warn("⚠️ Missing audio metadata on admin playback button");
          return;
        }

        const state = button.dataset.audioState;

        if (state === "playing") {
          this.stopActiveAudio(button);
          return;
        }

        if (state === "paused") {
          this.resumeActiveAudio();
          return;
        }

        if (state === "loading") {
          return;
        }

        this.playAudio(studentId, audioFile, button);
      });
    });
  }

  async playAudio(studentId, audioFile, buttonElement) {
    const admin = window.api.getCurrentStudent();

    if (!admin || !admin.is_admin) {
      console.error("❌ Admin access required");
      return;
    }

    try {
      // Stop any existing playback first
      if (this.activeAudio) {
        this.stopActiveAudio();
        // Wait a bit for cleanup
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      // Update button state
      const originalText =
        buttonElement.dataset.originalText || buttonElement.innerHTML;
      buttonElement.dataset.originalText = originalText;
      buttonElement.innerHTML = "⏳ Loading...";
      buttonElement.disabled = true;
      buttonElement.dataset.audioState = "loading";

      // Get audio URL
      const audioUrl = await window.api.getStudentAudio(
        studentId,
        audioFile,
        admin.student_id,
      );

      // Create and play audio with proper event handling
      const audio = new Audio();
      audio.preload = "auto";
      audio.src = audioUrl;

      // Store references BEFORE adding event listeners
      this.activeAudio = audio;
      this.activeAudioButton = buttonElement;

      // Store button reference in a closure to ensure it's available
      const self = this;
      const buttonRef = buttonElement;

      // Handle successful loading
      const onCanPlay = () => {
        buttonRef.innerHTML = '<span class="text-orange-600">⏸️ Stop</span>';
        buttonRef.disabled = false;
        buttonRef.dataset.audioState = "playing";
      };

      // Handle playback end
      const onEnded = () => {
        // Use the stored button reference
        if (buttonRef) {
          self.resetAudioButton(buttonRef);
        }
        self.activeAudio = null;
        self.activeAudioButton = null;
      };

      // Handle errors
      const onError = (error) => {
        console.error("❌ Audio playback error:", error);
        if (buttonRef) {
          buttonRef.innerHTML = "❌ Error";
          buttonRef.disabled = true;
          setTimeout(() => self.resetAudioButton(buttonRef), 2000);
        }
        self.activeAudio = null;
        self.activeAudioButton = null;
      };

      // Attach event listeners
      audio.addEventListener("canplay", onCanPlay, { once: true });
      audio.addEventListener("ended", onEnded, { once: true });
      audio.addEventListener("error", onError, { once: true });

      // Start playback
      try {
        await audio.play();
        // Update button state after successful play
        buttonRef.innerHTML = '<span class="text-orange-600">⏸️ Stop</span>';
        buttonRef.disabled = false;
        buttonRef.dataset.audioState = "playing";
      } catch (error) {
        console.error("❌ Unable to start audio playback:", error);
        // Clear references on play error
        self.activeAudio = null;
        self.activeAudioButton = null;
        buttonRef.innerHTML = "❌ Error";
        buttonRef.disabled = true;
        buttonRef.dataset.audioState = "error";
      }
    } catch (error) {
      console.error("❌ Failed to play audio (outer catch):", error);
      this.activeAudio = null;
      this.activeAudioButton = null;
      buttonElement.innerHTML = "❌ Error";
      buttonElement.disabled = true;
      buttonElement.dataset.audioState = "error";
    }
  }

  pauseActiveAudio() {
    if (!this.activeAudio || !this.activeAudioButton) {
      return;
    }

    try {
      this.activeAudio.pause();

      // Update button to show "Resume"
      this.activeAudioButton.innerHTML =
        '<span class="text-green-600">▶️ Resume</span>';
      this.activeAudioButton.dataset.audioState = "paused";
      this.activeAudioButton.disabled = false;

      // Add visual feedback
      this.activeAudioButton.classList.add("bg-blue-100");
      setTimeout(() => {
        if (this.activeAudioButton) {
          this.activeAudioButton.classList.remove("bg-blue-100");
        }
      }, 200);
    } catch (error) {
      console.error("❌ Error pausing audio:", error);
    }
  }

  resumeActiveAudio() {
    if (!this.activeAudio || !this.activeAudioButton) {
      return;
    }

    try {
      this.activeAudio.play();

      // Update button to show "Stop"
      this.activeAudioButton.innerHTML =
        '<span class="text-orange-600">⏸️ Stop</span>';
      this.activeAudioButton.dataset.audioState = "playing";
      this.activeAudioButton.disabled = false;
    } catch (error) {
      console.error("❌ Error resuming audio:", error);
    }
  }

  stopActiveAudio(buttonElement = null) {
    // Use the passed button element if instance variable is null
    const buttonToReset = buttonElement || this.activeAudioButton;
    const audioToStop = this.activeAudio;

    // Clear references first
    this.activeAudio = null;
    this.activeAudioButton = null;

    // Stop audio completely
    if (audioToStop) {
      try {
        audioToStop.pause();
        audioToStop.currentTime = 0;
        audioToStop.src = ""; // Clear source
      } catch (error) {
        console.warn("⚠️ Error stopping audio:", error);
      }
    }

    // Reset button UI
    if (buttonToReset) {
      this.resetAudioButton(buttonToReset);
    }
  }

  resetAudioButton(button) {
    if (!button) {
      return;
    }

    const originalText = button.dataset.originalText || "🔊 Play";
    button.innerHTML = originalText;
    button.disabled = false;
    button.dataset.audioState = "idle";

    // Add visual feedback for state change
    button.classList.add("bg-blue-100");
    setTimeout(() => {
      button.classList.remove("bg-blue-100");
    }, 200);
  }

  async openRecordingsModal({ studentId, studentName, recordingCount }) {
    if (!this.recordingsModal || !studentId) {
      return;
    }

    const admin = window.api.getCurrentStudent();
    if (!admin || !admin.is_admin) {
      console.error("❌ Admin access required to view recordings");
      return;
    }

    this.stopActiveAudio();

    this.recordingsModal.classList.remove("hidden");
    document.body.classList.add("overflow-hidden");

    if (this.recordingsTitle) {
      this.recordingsTitle.textContent = `${studentName}'s Recordings`;
    }

    if (this.recordingsMeta) {
      const label = recordingCount === 1 ? "recording" : "recordings";
      this.recordingsMeta.textContent =
        recordingCount > 0 ? `${recordingCount} ${label}` : "No recordings yet";
    }

    if (this.recordingsStatus) {
      this.recordingsStatus.textContent = "Loading recordings...";
      this.recordingsStatus.classList.remove("hidden");
    }

    if (this.recordingsContent) {
      this.recordingsContent.classList.add("hidden");
      this.recordingsContent.innerHTML = "";
    }

    try {
      const details = await window.api.getStudentDetails(
        studentId,
        admin.student_id,
      );

      const recordings = details?.asr_results || [];

      if (recordings.length === 0) {
        if (this.recordingsStatus) {
          this.recordingsStatus.textContent =
            "No recordings yet for this student.";
        }
        if (this.recordingsMeta) {
          this.recordingsMeta.textContent = "No recordings yet";
        }
        return;
      }

      if (this.recordingsStatus) {
        this.recordingsStatus.classList.add("hidden");
      }

      if (this.recordingsMeta) {
        const latestTimestamp = recordings[0]?.timestamp;
        const label = recordings.length === 1 ? "recording" : "recordings";
        const lastUpdated = latestTimestamp
          ? this.formatTimestamp(latestTimestamp)
          : "";
        this.recordingsMeta.textContent =
          lastUpdated !== ""
            ? `${recordings.length} ${label} • Last updated ${lastUpdated}`
            : `${recordings.length} ${label}`;
      }

      if (this.recordingsContent) {
        this.recordingsContent.classList.remove("hidden");
        this.recordingsContent.innerHTML = this.renderRecordingsTable(
          studentId,
          recordings,
        );
      }

      this.setupAudioPlaybackListeners();
      this.setupVideoAccordionListeners();
    } catch (error) {
      console.error("❌ Failed to load recordings for admin modal:", error);
      if (this.recordingsStatus) {
        this.recordingsStatus.textContent =
          "Failed to load recordings. Please try again.";
      }
    }
  }

  renderRecordingsTable(studentId, recordings) {
    if (!recordings || recordings.length === 0) {
      return '<p class="text-sm text-gray-500">No recordings found.</p>';
    }

    // Group recordings by video
    const recordingsByVideo = {};
    recordings.forEach((record) => {
      const videoId = record.video_id || "unknown";
      if (!recordingsByVideo[videoId]) {
        recordingsByVideo[videoId] = [];
      }
      recordingsByVideo[videoId].push(record);
    });

    // Sort video IDs
    const sortedVideoIds = Object.keys(recordingsByVideo).sort();

    // Generate accordion-style video sections
    const videoSections = sortedVideoIds
      .map((videoId, videoIndex) => {
        const videoRecordings = recordingsByVideo[videoId];
        const videoLabel = this.formatVideoLabel(videoId);
        const recordingCount = videoRecordings.length;
        const avgScore = this.calculateAvgScore(videoRecordings);
        const sectionId = `video-section-${videoIndex}`;
        const collapseId = `collapse-${videoIndex}`;

        const rows = videoRecordings
          .map((record, recordIndex) => {
            const similarityCell =
              record.similarity_percent !== null &&
              record.similarity_percent !== undefined
                ? this.renderSimilarityPill(record.similarity_percent)
                : '<span class="text-gray-400">—</span>';

            const transcriptText = record.transcript || "";
            const fullTranscript = transcriptText
              ? this.escapeHtml(transcriptText)
              : '<span class="text-gray-400 italic">No transcript</span>';

            const timestampText = this.escapeHtml(
              this.formatTimestamp(record.timestamp),
            );
            const audioFilename = record.audio_filename;

            const playButton = audioFilename
              ? `<button class="play-audio-btn text-blue-600 hover:text-blue-800 text-xs px-2 py-1 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded transition-all font-medium"
                       data-student-id="${this.escapeAttribute(studentId)}"
                       data-audio-file="${this.escapeAttribute(audioFilename)}"
                       data-original-text="🔊 Play">
                   🔊 Play
                 </button>`
              : '<span class="text-gray-400 text-xs italic">No audio</span>';

            return `
            <tr class="hover:bg-gray-50 transition-colors">
              <td class="px-3 py-2 text-xs text-gray-900 whitespace-nowrap">${recordIndex + 1}</td>
              <td class="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">${timestampText}</td>
              <td class="px-3 py-2 text-xs">
                <div class="max-w-2xl text-gray-700 leading-relaxed">${fullTranscript}</div>
              </td>
              <td class="px-3 py-2 text-xs whitespace-nowrap text-center">${similarityCell}</td>
              <td class="px-3 py-2 text-xs text-right">${playButton}</td>
            </tr>
          `;
          })
          .join("");

        const scoreColor =
          avgScore >= 80
            ? "text-green-600"
            : avgScore >= 60
              ? "text-yellow-600"
              : "text-red-600";

        return `
        <div class="border border-gray-200 rounded-lg mb-3 overflow-hidden">
          <button 
            class="w-full px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 hover:from-blue-100 hover:to-indigo-100 transition-colors text-left flex items-center justify-between"
            data-accordion-toggle="${collapseId}"
          >
            <div class="flex items-center gap-4">
              <span class="text-lg font-semibold text-gray-900">${this.escapeHtml(videoLabel)}</span>
              <span class="text-sm text-gray-600 bg-white px-2 py-1 rounded-full">${recordingCount} recording${recordingCount !== 1 ? "s" : ""}</span>
              ${avgScore !== null ? `<span class="text-sm font-medium ${scoreColor}">Avg: ${avgScore.toFixed(1)}%</span>` : ""}
            </div>
            <svg class="w-5 h-5 text-gray-600 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
            </svg>
          </button>
          <div id="${collapseId}" class="hidden">
            <div class="overflow-x-auto">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">#</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Time</th>
                    <th class="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Transcript</th>
                    <th class="px-3 py-2 text-center text-xs font-semibold text-gray-600 uppercase tracking-wide">Score</th>
                    <th class="px-3 py-2 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Audio</th>
                  </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-100">
                  ${rows}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      `;
      })
      .join("");

    return `
      <div class="space-y-2">
        ${videoSections}
      </div>
    `;
  }

  setupTranscriptToggleListeners() {
    const toggleButtons = document.querySelectorAll(".toggle-transcript");

    toggleButtons.forEach((btn) => {
      if (btn.dataset.listenerAttached === "true") {
        return;
      }

      btn.dataset.listenerAttached = "true";

      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const container = btn.closest("td").querySelector(".max-w-md");
        const short = container.querySelector(".transcript-short");
        const full = container.querySelector(".transcript-full");
        short.classList.toggle("hidden");
        full.classList.toggle("hidden");
        btn.textContent = short.classList.contains("hidden")
          ? "Show less"
          : "Show full";
      });
    });
  }

  setupVideoAccordionListeners() {
    const accordionButtons = document.querySelectorAll(
      "[data-accordion-toggle]",
    );

    accordionButtons.forEach((btn) => {
      if (btn.dataset.listenerAttached === "true") {
        return;
      }

      btn.dataset.listenerAttached = "true";

      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const targetId = btn.getAttribute("data-accordion-toggle");
        const target = document.getElementById(targetId);
        const arrow = btn.querySelector("svg");

        if (target) {
          target.classList.toggle("hidden");
          if (arrow) {
            arrow.style.transform = target.classList.contains("hidden")
              ? "rotate(0deg)"
              : "rotate(180deg)";
          }
        }
      });
    });
  }

  formatVideoLabel(videoId) {
    // Convert video ID to readable format
    // e.g., "01_7l_departure_north" -> "01: 7L Departure North"
    if (!videoId) return "Unknown Video";

    const parts = videoId.split("_");
    if (parts.length === 0) return videoId;

    const number = parts[0];
    const rest = parts
      .slice(1)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");

    return `${number}: ${rest}`;
  }

  calculateAvgScore(recordings) {
    if (!recordings || recordings.length === 0) return null;

    const validScores = recordings
      .map((r) => r.similarity_percent)
      .filter((s) => s !== null && s !== undefined && Number.isFinite(s));

    if (validScores.length === 0) return null;

    const sum = validScores.reduce((acc, score) => acc + Number(score), 0);
    return sum / validScores.length;
  }

  renderSimilarityPill(scorePercent) {
    const score = Number(scorePercent);
    if (!Number.isFinite(score)) {
      return '<span class="text-gray-400">—</span>';
    }

    let colorClass = "bg-red-100 text-red-700 border border-red-200";
    if (score >= 80) {
      colorClass = "bg-green-100 text-green-700 border border-green-200";
    } else if (score >= 70) {
      colorClass = "bg-blue-100 text-blue-700 border border-blue-200";
    } else if (score >= 50) {
      colorClass = "bg-yellow-100 text-yellow-700 border border-yellow-200";
    }

    return `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${colorClass}">${score.toFixed(1)}%</span>`;
  }

  truncateTranscript(text, maxLength = 140) {
    if (!text) {
      return null;
    }

    const clean = text.trim();
    if (clean.length <= maxLength) {
      return clean;
    }

    return `${clean.slice(0, maxLength - 1)}…`;
  }

  formatScore(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "—";
    }
    return `${numeric.toFixed(1)}%`;
  }

  formatMinutes(minutes) {
    const total = Number(minutes);
    if (!Number.isFinite(total) || total <= 0) {
      return "0.0 min";
    }
    return `${total.toFixed(1)} min`;
  }

  formatTimestamp(value) {
    if (!value) {
      return "No activity";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  closeRecordingsModal() {
    if (!this.recordingsModal) {
      return;
    }

    this.stopActiveAudio();
    this.recordingsModal.classList.add("hidden");
    document.body.classList.remove("overflow-hidden");
  }

  escapeHtml(value) {
    if (value === null || value === undefined) {
      return "";
    }

    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  escapeAttribute(value) {
    return this.escapeHtml(value);
  }

  showError(message) {
    // Simple error display - you could enhance this with better UI
    console.error("❌ Admin Error:", message);

    // You could add a toast notification or error banner here
    const tableBody = document.getElementById("students-table-body");
    if (tableBody) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-4 text-center text-red-600">
            ❌ ${message}
          </td>
        </tr>
      `;
    }
  }

  createAudioFilesDisplay(student) {
    const audioFiles = student.audio_files || [];

    if (audioFiles.length === 0) {
      return '<span class="text-gray-400 text-xs">No recordings</span>';
    }

    const count = audioFiles.length;
    const label = count === 1 ? "recording" : "recordings";

    return `
      <button class="view-recordings-btn text-blue-600 hover:text-blue-800 text-xs px-3 py-1.5 bg-blue-50 border border-blue-100 rounded-md transition"
              data-student-id="${this.escapeAttribute(student.student_id)}"
              data-student-name="${this.escapeAttribute(student.name)}"
              data-recording-count="${count}">
        🔍 View ${count} ${label}
      </button>
    `;
  }

  // Utility function to format dates
  formatDate(dateString) {
    if (!dateString) return "N/A";

    const date = new Date(dateString);
    return (
      date.toLocaleDateString() +
      " " +
      date.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    );
  }

  // Utility function to format file sizes (if needed in future)
  formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";

    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }
}

// Create global admin manager instance
window.admin = new AdminManager();

// Export for external use
window.loadAdminDashboard = () => window.admin.loadAdminDashboard();
