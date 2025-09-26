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
        const score = Math.round(this.statistics.average_score * 100);
        avgScoreEl.textContent = `${score}%`;

        // Add color coding
        avgScoreEl.className = "text-lg font-medium";
        if (score >= 90) {
          avgScoreEl.classList.add("text-green-600");
        } else if (score >= 70) {
          avgScoreEl.classList.add("text-blue-600");
        } else if (score >= 50) {
          avgScoreEl.classList.add("text-yellow-600");
        } else {
          avgScoreEl.classList.add("text-red-600");
        }
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

    // Update time spent (placeholder for now)
    const timeEl = document.getElementById("stats-time");
    if (timeEl) {
      const estimatedTime = this.statistics.total_attempts * 2; // Assume 2 min per attempt
      timeEl.textContent = `${estimatedTime} min`;
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

    // Add hover and accessibility enhancements
    if (video.unlocked) {
      card.className += " hover:shadow-xl hover:scale-[1.02] cursor-pointer";
      card.setAttribute("tabindex", "0");
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `Open ${video.title} video`);
    } else {
      card.className += " opacity-75";
      card.setAttribute("aria-label", `${video.title} - Locked`);
    }

    if (video.completed) {
      card.className += " ring-2 ring-green-300";
    }

    const thumbnail = this.createVideoThumbnail(video, index);
    const info = this.createVideoInfo(video);

    card.appendChild(thumbnail);
    card.appendChild(info);

    // Add click handler
    if (video.unlocked) {
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
    } else {
      card.addEventListener("click", () => {
        window.dashboard?.showNotification(
          "Complete previous videos to unlock this one",
          "info",
        );
      });
    }

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

    // Create overlay container
    const overlay = document.createElement("div");
    overlay.className =
      "absolute inset-0 flex items-center justify-center bg-black bg-opacity-20 group-hover:bg-opacity-10 transition-all";

    if (video.completed) {
      // Completed video - show play button with green tint
      const playIcon = document.createElement("div");
      playIcon.className =
        "bg-green-500 bg-opacity-95 rounded-full p-3 transform group-hover:scale-110 transition-transform shadow-lg";
      playIcon.innerHTML = `
                <svg class="h-6 w-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                </svg>
            `;
      overlay.appendChild(playIcon);
    } else if (video.unlocked) {
      // Unlocked video - show play button
      const playIcon = document.createElement("div");
      playIcon.className =
        "bg-white bg-opacity-95 rounded-full p-3 transform group-hover:scale-110 transition-transform shadow-lg";
      playIcon.innerHTML = `
                <svg class="h-6 w-6 text-gray-800 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z"/>
                </svg>
            `;
      overlay.appendChild(playIcon);
    } else {
      // Locked video - show lock overlay
      const lockOverlay = document.createElement("div");
      lockOverlay.className =
        "absolute inset-0 bg-black bg-opacity-60 flex items-center justify-center";

      const lockIcon = document.createElement("div");
      lockIcon.className =
        "bg-white bg-opacity-90 rounded-full p-2.5 shadow-lg";
      lockIcon.innerHTML = `
                <svg class="h-5 w-5 text-gray-700" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/>
                </svg>
            `;

      lockOverlay.appendChild(lockIcon);
      overlay.appendChild(lockOverlay);
    }

    thumbnail.appendChild(overlay);

    // Add completion badge
    if (video.completed) {
      const completionBadge = document.createElement("div");
      completionBadge.className =
        "absolute top-2 right-2 bg-green-500 text-white rounded-full p-1.5 shadow-lg z-20";
      completionBadge.innerHTML = `
                <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            `;
      thumbnail.appendChild(completionBadge);
    }

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

    // Top row with equal-width badges
    const badgesRow = document.createElement("div");
    badgesRow.className = "video-badges-row";

    // Score badge
    const scoreBadge = document.createElement("span");
    if (video.best_score > 0) {
      const scorePercent = Math.round(video.best_score * 100);
      const scoreBadgeClass = this.getScoreBadgeClass(scorePercent);
      scoreBadge.className = `score-badge ${scoreBadgeClass}`;
      scoreBadge.textContent = `${scorePercent}%`;
    } else {
      scoreBadge.className = "score-badge score-badge-none";
      scoreBadge.textContent = "No Score";
    }

    // Status badge
    const statusBadge = document.createElement("span");
    statusBadge.className = "status-badge";

    if (video.completed) {
      statusBadge.className += " bg-green-100 text-green-700";
      statusBadge.innerHTML = "✓ Done";
    } else if (video.unlocked) {
      statusBadge.className += " bg-blue-100 text-blue-700";
      statusBadge.innerHTML = "▶ Available";
    } else {
      statusBadge.className += " bg-gray-100 text-gray-700";
      statusBadge.innerHTML = "🔒 Locked";
    }

    // Time spent badge (estimated based on attempts)
    const timeBadge = document.createElement("span");
    timeBadge.className = "time-badge";
    const estimatedTime = (video.attempts || 0) * 2; // 2 minutes per attempt
    timeBadge.innerHTML = `⏱️ ${estimatedTime}m`;

    badgesRow.appendChild(scoreBadge);
    badgesRow.appendChild(statusBadge);
    badgesRow.appendChild(timeBadge);

    // Video Title (clean, below badges)
    const videoTitle = document.createElement("h4");
    videoTitle.className = "font-semibold text-gray-900 text-sm leading-tight";
    videoTitle.textContent = video.title;

    info.appendChild(badgesRow);
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
                    <button class="text-gray-400 hover:text-gray-600" onclick="this.parentElement.parentElement.parentElement.remove()">
                        <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;

    document.body.appendChild(notification);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 5000);
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
