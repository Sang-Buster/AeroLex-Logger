/**
 * VR Flight Training Course - Main Application
 * Application initialization and global coordination
 */

class VRFlightApp {
  constructor() {
    this.initialized = false;
    this.init();
  }

  async init() {
    console.log("🚀 Initializing VR Flight Training App...");

    // Wait for DOM to be ready
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", () => this.startup());
    } else {
      this.startup();
    }
  }

  async startup() {
    try {
      // Initialize backend connection
      await this.initializeBackend();

      // Setup error handling
      this.setupGlobalErrorHandling();

      // Setup service worker (if available)
      this.setupServiceWorker();

      // Mark as initialized
      this.initialized = true;

      console.log("✅ VR Flight Training App initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize app:", error);
      this.showError(
        "Failed to initialize application. Please refresh the page.",
      );
    }
  }

  async initializeBackend() {
    console.log("🔧 Initializing backend connection...");

    try {
      // Test backend connection
      const healthCheck = await window.api.healthCheck();
      console.log("✅ Backend connection established:", healthCheck);

      // Initialize video database
      await window.api.initializeVideos();
      console.log("✅ Video database initialized");
    } catch (error) {
      console.warn("⚠️ Backend initialization failed:", error);
      throw new Error("Cannot connect to backend service");
    }
  }

  setupGlobalErrorHandling() {
    // Global error handler for unhandled promises
    window.addEventListener("unhandledrejection", (event) => {
      console.error("❌ Unhandled promise rejection:", event.reason);

      // Don't show error for network timeouts or common fetch errors
      if (
        event.reason instanceof TypeError &&
        event.reason.message.includes("fetch")
      ) {
        return;
      }

      this.showError("An unexpected error occurred. Please try again.");
    });

    // Global error handler for JavaScript errors
    window.addEventListener("error", (event) => {
      console.error("❌ Global JavaScript error:", event.error);

      // Don't show error for script loading errors
      if (event.filename && event.filename.includes(".js")) {
        return;
      }

      this.showError("An unexpected error occurred. Please refresh the page.");
    });

    // Handle offline/online status
    window.addEventListener("offline", () => {
      this.showError(
        "You are now offline. Some features may not work properly.",
        "warning",
      );
    });

    window.addEventListener("online", () => {
      this.showSuccess("You are back online!");
    });
  }

  setupServiceWorker() {
    // Service Worker disabled for local development
    // Can be enabled later for offline support
    console.log("ℹ️ Service Worker disabled for local development");
  }

  // Utility methods
  showError(message, type = "error") {
    this.showNotification(message, type);
  }

  showSuccess(message) {
    this.showNotification(message, "success");
  }

  showWarning(message) {
    this.showNotification(message, "warning");
  }

  showInfo(message) {
    this.showNotification(message, "info");
  }

  showNotification(message, type = "info") {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = `fixed top-4 right-4 z-50 max-w-sm w-full bg-white rounded-lg shadow-lg border-l-4 p-4 ${this.getNotificationClass(type)}`;
    notification.style.animation = "slideIn 0.3s ease-out";

    const icon = this.getNotificationIcon(type);
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
                        <svg class="h-5 w-5" stroke="currentColor" fill="none" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;

    document.body.appendChild(notification);

    // Auto-remove after delay
    const delay = type === "error" ? 8000 : 5000;
    setTimeout(() => {
      if (notification.parentElement) {
        notification.style.animation = "fadeOut 0.3s ease-in";
        setTimeout(() => notification.remove(), 300);
      }
    }, delay);
  }

  getNotificationClass(type) {
    switch (type) {
      case "success":
        return "border-green-500 bg-green-50";
      case "error":
        return "border-red-500 bg-red-50";
      case "warning":
        return "border-yellow-500 bg-yellow-50";
      case "info":
      default:
        return "border-blue-500 bg-blue-50";
    }
  }

  getNotificationIcon(type) {
    switch (type) {
      case "success":
        return "✅";
      case "error":
        return "❌";
      case "warning":
        return "⚠️";
      case "info":
      default:
        return "ℹ️";
    }
  }

  // App state methods
  isInitialized() {
    return this.initialized;
  }

  getVersion() {
    return "1.0.0";
  }

  // Debug methods
  debug() {
    return {
      initialized: this.initialized,
      currentStudent: window.api?.getCurrentStudent(),
      isLoggedIn: window.auth?.isLoggedIn(),
      version: this.getVersion(),
    };
  }

  // Performance monitoring
  startPerformanceMonitoring() {
    // Monitor page load performance
    window.addEventListener("load", () => {
      setTimeout(() => {
        const perfData = performance.getEntriesByType("navigation")[0];
        if (perfData) {
          console.log("📊 Page load performance:", {
            domContentLoaded: Math.round(
              perfData.domContentLoadedEventEnd -
                perfData.domContentLoadedEventStart,
            ),
            loadComplete: Math.round(
              perfData.loadEventEnd - perfData.loadEventStart,
            ),
            totalTime: Math.round(
              perfData.loadEventEnd - perfData.navigationStart,
            ),
          });
        }
      }, 0);
    });

    // Monitor memory usage (if available)
    if (performance.memory) {
      setInterval(() => {
        const memInfo = performance.memory;
        if (memInfo.usedJSHeapSize > memInfo.totalJSHeapSize * 0.9) {
          console.warn("⚠️ High memory usage detected");
        }
      }, 30000); // Check every 30 seconds
    }
  }
}

// Initialize the application
const vrFlightApp = new VRFlightApp();

// Make app globally available for debugging
window.app = vrFlightApp;

// Add some useful global utilities
window.utils = {
  formatTime: (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  },

  formatScore: (score) => {
    return `${Math.round(score * 100)}%`;
  },

  formatDate: (dateString) => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  },

  formatDateTime: (dateString) => {
    return new Date(dateString).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  },

  downloadJSON: (data, filename) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  },

  copyToClipboard: async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      window.app.showSuccess("Copied to clipboard!");
    } catch (error) {
      console.warn("⚠️ Clipboard API not available:", error);
      window.app.showWarning("Unable to copy to clipboard");
    }
  },
};

// Add CSS animations for notifications
const style = document.createElement("style");
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
    }
`;
document.head.appendChild(style);

// Start performance monitoring in development
if (
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1"
) {
  vrFlightApp.startPerformanceMonitoring();
}

console.log(
  "🎓 VR Flight Training Course v" + vrFlightApp.getVersion() + " loaded",
);

// Expose debugging information
window.debugInfo = () => console.table(vrFlightApp.debug());
