/**
 * VR Flight Training Course - Admin Module
 * Handles admin dashboard functionality and student data management
 */

class AdminManager {
  constructor() {
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

    // Add event listeners for audio playback
    this.setupAudioPlaybackListeners();
  }

  createStudentRow(student) {
    const audioFiles = student.audio_files || [];
    // Better audio files display for multiple files
    const audioFilesList =
      audioFiles.length > 0
        ? this.createAudioFilesDisplay(student.student_id, audioFiles)
        : '<span class="text-gray-400 text-xs">No recordings</span>';

    const lastActivity = student.latest_activity
      ? new Date(student.latest_activity).toLocaleDateString()
      : '<span class="text-gray-400">No activity</span>';

    const progressBar = this.createProgressBar(student.completion_rate);

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
          <div class="text-sm font-medium text-gray-900">${student.average_score.toFixed(1)}%</div>
          <div class="text-xs text-gray-500">Average</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm text-gray-900">${student.total_attempts}</div>
          <div class="text-xs text-gray-500">Total attempts</div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap">
          <div class="text-sm text-gray-900">${student.time_spent_minutes} min</div>
          <div class="text-xs text-gray-500">Total time</div>
        </td>
        <td class="px-6 py-4">
          <div class="text-sm max-w-xs overflow-hidden">
            ${audioFilesList}
          </div>
        </td>
        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
          ${lastActivity}
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

  setupAudioPlaybackListeners() {
    const playButtons = document.querySelectorAll(".play-audio-btn");

    playButtons.forEach((button) => {
      button.addEventListener("click", (e) => {
        e.preventDefault();
        const studentId = button.getAttribute("data-student-id");
        const audioFile = button.getAttribute("data-audio-file");
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
      // Update button state
      const originalText = buttonElement.innerHTML;
      buttonElement.innerHTML = "⏳ Loading...";
      buttonElement.disabled = true;

      // Get audio URL
      const audioUrl = window.api.getStudentAudio(
        studentId,
        audioFile,
        admin.student_id,
      );

      // Create and play audio
      const audio = new Audio(audioUrl);

      audio.addEventListener("loadstart", () => {
        buttonElement.innerHTML = "⏸️ Loading...";
      });

      audio.addEventListener("canplay", () => {
        buttonElement.innerHTML = "⏸️ Playing...";
        audio.play();
      });

      audio.addEventListener("ended", () => {
        buttonElement.innerHTML = originalText;
        buttonElement.disabled = false;
      });

      audio.addEventListener("error", (e) => {
        console.error("❌ Audio playback error:", e);
        buttonElement.innerHTML = "❌ Error";
        setTimeout(() => {
          buttonElement.innerHTML = originalText;
          buttonElement.disabled = false;
        }, 2000);
      });

      // Add click listener to stop audio
      const stopHandler = () => {
        audio.pause();
        audio.currentTime = 0;
        buttonElement.innerHTML = originalText;
        buttonElement.disabled = false;
        buttonElement.removeEventListener("click", stopHandler);
      };

      buttonElement.addEventListener("click", stopHandler, { once: true });
    } catch (error) {
      console.error("❌ Failed to play audio:", error);
      buttonElement.innerHTML = "❌ Error";
      setTimeout(() => {
        buttonElement.innerHTML =
          buttonElement.getAttribute("data-original-text") || "🔊 Play";
        buttonElement.disabled = false;
      }, 2000);
    }
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

  createAudioFilesDisplay(studentId, audioFiles) {
    if (audioFiles.length === 0) {
      return '<span class="text-gray-400 text-xs">No recordings</span>';
    }

    if (audioFiles.length <= 3) {
      // Show all files if 3 or fewer
      return audioFiles
        .map(
          (file) =>
            `<button class="play-audio-btn text-blue-600 hover:text-blue-800 text-xs mr-1 mb-1 px-2 py-1 bg-blue-50 rounded" 
                 data-student-id="${studentId}" 
                 data-audio-file="${file}">
           🔊 ${this.truncateFileName(file)}
         </button>`,
        )
        .join("");
    } else {
      // Show count with expandable view for many files
      const firstThree = audioFiles.slice(0, 3);
      const remaining = audioFiles.length - 3;

      return `
        <div class="audio-files-container">
          ${firstThree
            .map(
              (file) =>
                `<button class="play-audio-btn text-blue-600 hover:text-blue-800 text-xs mr-1 mb-1 px-2 py-1 bg-blue-50 rounded" 
                     data-student-id="${studentId}" 
                     data-audio-file="${file}">
               🔊 ${this.truncateFileName(file)}
             </button>`,
            )
            .join("")}
          <button class="expand-audio-btn text-gray-600 hover:text-gray-800 text-xs px-2 py-1 bg-gray-100 rounded" 
                  data-student-id="${studentId}" 
                  data-audio-files='${JSON.stringify(audioFiles)}'>
            +${remaining} more
          </button>
        </div>
      `;
    }
  }

  truncateFileName(filename) {
    // Remove common prefixes and extensions for cleaner display
    let clean = filename.replace(/\.(wav|mp3|m4a)$/i, "");
    clean = clean.replace(/^audio_|recording_|session_/i, "");

    // Truncate if too long
    if (clean.length > 15) {
      return clean.substring(0, 12) + "...";
    }
    return clean;
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
