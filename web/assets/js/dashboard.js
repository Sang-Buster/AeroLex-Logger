/**
 * VR Flight Training Course - Dashboard Module
 * Handles dashboard data loading, statistics display, and video grid
 */

class DashboardManager {
  constructor() {
    this.studentData = null;
    this.videos = [];
    this.statistics = {};
    this.refreshInterval = null;
    this.activeNotifications = new Set(); // Track active notification messages
    this.init();
  }

  init() {
    // Auto-refresh dashboard data every 30 seconds
    this.refreshInterval = setInterval(() => {
      if (window.auth.isLoggedIn()) {
        this.refreshData();
      }
    }, 30000);
  }

  async loadDashboard() {
    const student = window.getCurrentStudent();
    if (!student) {
      console.warn("⚠️ No student found for dashboard");
      return;
    }

    // Don't load student dashboard if user is an admin
    if (student.is_admin) {
      console.log("👤 Admin user detected, skipping student dashboard load");
      return;
    }

    console.log("📊 Loading dashboard for:", student.name);

    try {
      // Show loading state
      this.showLoadingState();

      // Load data in parallel
      const [dashboardData, videosData, statisticsData] = await Promise.all([
        window.api.getStudentDashboard(student.student_id),
        window.api.getVideosForStudent(student.student_id),
        window.api.getStudentStatistics(student.student_id),
      ]);

      // Store data
      this.studentData = dashboardData.dashboard;
      this.videos = videosData.videos;
      this.statistics = statisticsData.statistics;

      // Update UI
      this.updateOverviewStats();
      this.renderVideoGrid();

      console.log("✅ Dashboard loaded successfully");
    } catch (error) {
      console.error("❌ Error loading dashboard:", error);
      this.showError("Failed to load dashboard data");
    }
  }

  async refreshData() {
    const student = window.getCurrentStudent();
    if (!student) return;

    // Don't refresh dashboard data if user is an admin
    if (student.is_admin) return;

    try {
      // Refresh statistics silently
      const statisticsData = await window.api.getStudentStatistics(
        student.student_id,
      );
      this.statistics = statisticsData.statistics;
      this.updateOverviewStats();
    } catch (error) {
      console.warn("⚠️ Failed to refresh dashboard data:", error);
    }
  }

  updateOverviewStats() {
    if (!this.statistics) return;

    // Update completed videos stat
    const completedEl = document.getElementById("stats-completed");
    if (completedEl) {
      completedEl.textContent = `${this.statistics.completed_videos} / ${this.statistics.total_videos}`;
    }

    // Update average score
    const avgScoreEl = document.getElementById("stats-avg-score");
    if (avgScoreEl) {
      const hasAttempts = this.statistics.total_attempts > 0;

      if (hasAttempts) {
        const score = (this.statistics.average_score * 100).toFixed(2);
        const scorePercent = parseFloat(score);
        avgScoreEl.textContent = `${score}%`;

        // Add color coding that matches video badges while keeping the green card background
        avgScoreEl.className = `text-lg font-medium ${this.getScoreColorClass(scorePercent)}`;
      } else {
        avgScoreEl.textContent = "TBD";
        avgScoreEl.className = "text-lg font-medium text-gray-500";
      }
    }

    // Update total attempts
    const attemptsEl = document.getElementById("stats-attempts");
    if (attemptsEl) {
      attemptsEl.textContent = this.statistics.total_attempts || 0;
    }

    // Update time spent (from actual session data)
    const timeEl = document.getElementById("stats-time");
    if (timeEl) {
      const timeMinutes = this.statistics.total_time_minutes || 0;
      timeEl.textContent = `${timeMinutes} min`;
    }
  }

  renderVideoGrid() {
    const videosGrid = document.getElementById("videos-grid");
    if (!videosGrid || !this.videos) return;

    videosGrid.innerHTML = "";

    this.videos.forEach((video, index) => {
      const videoCard = this.createVideoCard(video, index);
      videosGrid.appendChild(videoCard);
    });
  }

  createVideoCard(video, index) {
    const card = document.createElement("div");
    card.className =
      "bg-white rounded-lg shadow-md overflow-hidden transition-all duration-200 hover:shadow-lg";
    card.dataset.videoId = video.id;

    // Always allow access - no locking logic
    card.className += " hover:shadow-xl hover:scale-[1.02] cursor-pointer";
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Open ${video.title} video`);

    const thumbnail = this.createVideoThumbnail(video, index);
    const info = this.createVideoInfo(video);

    card.appendChild(thumbnail);
    card.appendChild(info);

    // Add click handler - always enabled
    const handleOpen = () => {
      window.videoPlayer?.openVideo(video);
    };

    card.addEventListener("click", handleOpen);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        handleOpen();
      }
    });

    return card;
  }

  createVideoThumbnail(video, index) {
    const thumbnail = document.createElement("div");
    thumbnail.className =
      "relative aspect-video rounded-t-lg overflow-hidden group bg-gray-200";

    // Create image element for thumbnail
    const thumbnailImage = document.createElement("img");
    thumbnailImage.className = "w-full h-full object-cover";
    const thumbnailFilename = video.filename.replace(".mp4", ".jpg");
    thumbnailImage.src = `/static/assets/img/thumbnails/${encodeURIComponent(thumbnailFilename)}`;
    thumbnailImage.alt = `${video.title} thumbnail`;

    // Add error fallback for missing thumbnails
    thumbnailImage.addEventListener("error", (e) => {
      console.warn(`❌ Failed to load thumbnail: ${e.target.src}`);
      thumbnailImage.src =
        "data:image/svg+xml," +
        encodeURIComponent(`
                <svg xmlns="http://www.w3.org/2000/svg" width="400" height="225" viewBox="0 0 400 225">
                    <rect width="400" height="225" fill="#374151"/>
                    <text x="200" y="112" text-anchor="middle" fill="white" font-family="Arial" font-size="16">Video ${video.order_index}</text>
                </svg>
            `);
    });

    thumbnail.appendChild(thumbnailImage);

    // Create overlay container - always show play button
    const overlay = document.createElement("div");
    overlay.className =
      "absolute inset-0 flex items-center justify-center bg-black bg-opacity-20 group-hover:bg-opacity-10 transition-all";

    // Always show unlocked play button
    const playIcon = document.createElement("div");
    playIcon.className =
      "bg-white bg-opacity-95 rounded-full p-3 transform group-hover:scale-110 transition-transform shadow-lg";
    playIcon.innerHTML = `
            <svg class="h-6 w-6 text-gray-800 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z"/>
            </svg>
        `;
    overlay.appendChild(playIcon);

    thumbnail.appendChild(overlay);

    // Add video number indicator
    const videoNumber = document.createElement("div");
    videoNumber.className =
      "absolute top-2 left-2 bg-black bg-opacity-70 text-white px-2 py-1 rounded text-xs font-medium z-20";
    videoNumber.textContent = `${video.order_index}`;
    thumbnail.appendChild(videoNumber);

    return thumbnail;
  }

  createVideoInfo(video) {
    const info = document.createElement("div");
    info.className = "p-4";

    // Video Title (only show title, no badges)
    const videoTitle = document.createElement("h4");
    videoTitle.className = "font-semibold text-gray-900 text-sm leading-tight";
    videoTitle.textContent = video.title;

    info.appendChild(videoTitle);

    return info;
  }

  getScoreColorClass(scorePercent) {
    if (scorePercent >= 80) {
      return "text-green-600";
    } else if (scorePercent >= 70) {
      return "text-blue-600";
    } else if (scorePercent >= 50) {
      return "text-yellow-600";
    } else {
      return "text-red-600";
    }
  }

  showLoadingState() {
    const videosGrid = document.getElementById("videos-grid");
    if (videosGrid) {
      videosGrid.innerHTML = "";

      // Create skeleton cards matching equal-width badge layout
      for (let i = 0; i < 6; i++) {
        const skeleton = document.createElement("div");
        skeleton.className =
          "animate-pulse bg-white rounded-lg shadow-md overflow-hidden";
        skeleton.innerHTML = `
                    <div class="bg-gray-300 aspect-video rounded-t-lg"></div>
                    <div class="p-4">
                      <!-- Perfect equal-width badges row skeleton -->
                      <div class="video-badges-row">
                        <div class="score-badge bg-gray-300"></div>
                        <div class="status-badge bg-gray-300"></div>
                        <div class="status-badge bg-gray-300"></div>
                        <div class="time-badge bg-gray-300"></div>
                      </div>
                      <!-- Title skeleton -->
                      <div class="h-5 bg-gray-300 rounded w-3/4"></div>
                    </div>
                `;
        videosGrid.appendChild(skeleton);
      }
    }

    // Clear stats
    [
      "stats-completed",
      "stats-avg-score",
      "stats-attempts",
      "stats-time",
    ].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = "Loading...";
    });
  }

  showError(message) {
    this.showNotification(message, "error");
  }

  showNotification(message, type = "info") {
    // Check if this message is already being shown
    const notificationKey = `${type}:${message}`;
    if (this.activeNotifications.has(notificationKey)) {
      return; // Don't show duplicate notifications
    }

    // Mark this notification as active
    this.activeNotifications.add(notificationKey);

    // Create notification element
    const notification = document.createElement("div");
    notification.className = `notification ${type}`;

    const icon = type === "error" ? "❌" : type === "success" ? "✅" : "ℹ️";
    notification.innerHTML = `
            <div class="flex">
                <div class="flex-shrink-0">
                    <span class="text-lg">${icon}</span>
                </div>
                <div class="ml-3">
                    <p class="text-sm font-medium text-gray-900">${message}</p>
                </div>
                <div class="ml-auto pl-3">
                    <button class="notification-close text-gray-400 hover:text-gray-600">
                        <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;

    // Add close button handler
    const closeButton = notification.querySelector(".notification-close");
    closeButton.addEventListener("click", () => {
      notification.remove();
      this.activeNotifications.delete(notificationKey);
    });

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
      // Remove from active notifications
      this.activeNotifications.delete(notificationKey);
    }, 5000);
  }

  // Helper function to get score badge color class
  getScoreBadgeClass(scorePercent) {
    if (scorePercent >= 80) return "score-badge-excellent"; // Excellent - green
    if (scorePercent >= 70) return "score-badge-good"; // Good - blue
    if (scorePercent >= 50) return "score-badge-average"; // OK - yellow
    return "score-badge-poor"; // Needs work - red
  }

  // Cleanup
  destroy() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }
}

// Create global dashboard manager instance
window.dashboard = new DashboardManager();
