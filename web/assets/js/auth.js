/**
 * VR Flight Training Course - Authentication Module
 * Handles login, logout, and session management
 */

class AuthManager {
  constructor() {
    this.loginForm = null;
    this.loginScreen = null;
    this.dashboardScreen = null;
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
    // Get DOM elements
    this.loginForm = document.getElementById("login-form");
    this.loginScreen = document.getElementById("login-screen");
    this.dashboardScreen = document.getElementById("dashboard-screen");
    this.adminScreen = document.getElementById("admin-screen");
    this.logoutBtn = document.getElementById("logout-btn");
    this.adminLogoutBtn = document.getElementById("admin-logout-btn");
    this.studentIdField = document.getElementById("student-id");
    this.passwordField = document.getElementById("admin-password-field");

    if (!this.loginForm || !this.loginScreen || !this.dashboardScreen) {
      console.error("❌ Required DOM elements not found for AuthManager");
      return;
    }

    // Setup form submission
    this.loginForm.addEventListener("submit", (e) => this.handleLogin(e));

    // Setup logout buttons
    if (this.logoutBtn) {
      this.logoutBtn.addEventListener("click", () => this.handleLogout());
    }
    if (this.adminLogoutBtn) {
      this.adminLogoutBtn.addEventListener("click", () => this.handleLogout());
    }

    // Show/hide password field based on student ID
    if (this.studentIdField && this.passwordField) {
      this.studentIdField.addEventListener("input", (e) => {
        if (e.target.value.toLowerCase() === "admin") {
          this.passwordField.classList.remove("hidden");
          document.getElementById("admin-password").required = true;
        } else {
          this.passwordField.classList.add("hidden");
          document.getElementById("admin-password").required = false;
        }
      });
    } else {
      console.error("❌ Student ID field or password field not found:", {
        studentIdField: !!this.studentIdField,
        passwordField: !!this.passwordField,
      });
    }

    // Initialize form state
    this.resetPasswordField();

    // Check if user is already logged in
    this.checkExistingSession();
  }

  async checkExistingSession() {
    const student = window.api.getCurrentStudent();

    if (student) {
      console.log("👤 Found existing session:", student);

      try {
        // For admin, skip validation since it's session-based
        if (student.is_admin) {
          this.showAdminDashboard(student);
        } else {
          // Validate regular student session with backend
          await window.api.validateStudent(student.student_id);
          this.showDashboard(student);
        }
      } catch (error) {
        console.warn("⚠️ Session validation failed:", error);
        this.showLogin();
        window.api.clearCurrentStudent();
      }
    } else {
      console.log("👤 No existing session found, showing login");
      this.showLogin();
    }
  }

  async handleLogin(event) {
    event.preventDefault();

    const formData = new FormData(this.loginForm);
    const name = formData.get("name")?.trim();
    const studentId = formData.get("student_id")?.trim();
    const password = formData.get("password")?.trim();

    // Validate inputs
    if (!name || !studentId) {
      this.showMessage("Please fill in all fields", "error");
      return;
    }

    // Validate admin password if provided
    if (password && studentId.toLowerCase() !== "admin") {
      this.showMessage("Password is only for admin login", "error");
      return;
    }

    if (studentId.toLowerCase() === "admin" && !password) {
      this.showMessage("Admin password is required", "error");
      return;
    }

    // Show loading state
    this.setLoading(true);
    this.showMessage("Logging in...", "info");

    try {
      const response = await window.api.login(name, studentId, password);

      if (response.success) {
        this.showMessage(
          response.message,
          response.is_admin ? "success" : response.is_new ? "success" : "info",
        );

        // Small delay to show the message
        setTimeout(() => {
          if (response.is_admin) {
            this.showAdminDashboard(response.student);
          } else {
            this.showDashboard(response.student);
          }
        }, 1000);
      } else {
        this.showMessage("Login failed", "error");
      }
    } catch (error) {
      console.error("❌ Login error:", error);
      this.showMessage(
        error.message || "Login failed. Please try again.",
        "error",
      );
    } finally {
      this.setLoading(false);
    }
  }

  async handleLogout() {
    if (window.videoPlayer?.closeVideo) {
      try {
        await window.videoPlayer.closeVideo({ silentStop: true });
      } catch (error) {
        console.warn("⚠️ Error closing video during logout:", error);
      }
    }

    const student = window.api.getCurrentStudent();

    if (student) {
      try {
        await window.api.logout(student.student_id);
        console.log("👋 User logged out");
      } catch (error) {
        console.warn("⚠️ Logout error:", error);
      }
    }

    this.showLogin();
  }

  showLogin() {
    if (this.loginScreen && this.dashboardScreen) {
      this.loginScreen.classList.remove("hidden");
      this.dashboardScreen.classList.add("hidden");
      if (this.adminScreen) {
        this.adminScreen.classList.add("hidden");
      }

      // Clear form
      if (this.loginForm) {
        this.loginForm.reset();
      }

      // Hide password field and reset requirements
      this.resetPasswordField();

      // Clear any messages
      this.clearMessage();

      console.log("📱 Showing login screen");
    }
  }

  resetPasswordField() {
    if (this.passwordField) {
      this.passwordField.classList.add("hidden");
      const passwordInput = document.getElementById("admin-password");
      if (passwordInput) {
        passwordInput.required = false;
        passwordInput.value = "";
      }
    }
  }

  showDashboard(student) {
    if (this.loginScreen && this.dashboardScreen) {
      this.loginScreen.classList.add("hidden");
      this.dashboardScreen.classList.remove("hidden");
      if (this.adminScreen) {
        this.adminScreen.classList.add("hidden");
      }

      // Update navigation with student info
      this.updateNavigation(student);

      // Load dashboard data
      window.dashboard?.loadDashboard();

      console.log("📱 Showing dashboard for:", student.name);
    }
  }

  async showAdminDashboard(admin) {
    if (window.videoPlayer?.closeVideo) {
      try {
        await window.videoPlayer.closeVideo({ silentStop: true });
      } catch (error) {
        console.warn("⚠️ Error closing video before admin view:", error);
      }
    }

    if (this.loginScreen && this.dashboardScreen && this.adminScreen) {
      this.loginScreen.classList.add("hidden");
      this.dashboardScreen.classList.add("hidden");
      this.adminScreen.classList.remove("hidden");

      // Update admin navigation
      this.updateAdminNavigation(admin);

      // Load admin dashboard data
      window.admin?.loadAdminDashboard();

      console.log("🔧 Showing admin dashboard for:", admin.name);
    }
  }

  updateNavigation(student) {
    const nameEl = document.getElementById("nav-student-name");
    if (nameEl) nameEl.textContent = student.name;
  }

  updateAdminNavigation(admin) {
    const nameEl = document.getElementById("nav-admin-name");
    if (nameEl) nameEl.textContent = admin.name;
  }

  setLoading(loading) {
    const loginBtn = document.getElementById("login-btn");
    const loginBtnText = document.getElementById("login-btn-text");
    const loginSpinner = document.getElementById("login-spinner");

    if (loginBtn && loginBtnText && loginSpinner) {
      if (loading) {
        loginBtn.disabled = true;
        loginBtnText.textContent = "Logging in...";
        loginSpinner.classList.remove("hidden");
      } else {
        loginBtn.disabled = false;
        loginBtnText.textContent = "Continue to Course";
        loginSpinner.classList.add("hidden");
      }
    }
  }

  showMessage(message, type = "info") {
    const messageEl = document.getElementById("login-message");
    const messageTextEl = document.getElementById("login-message-text");

    if (messageEl && messageTextEl) {
      messageTextEl.textContent = message;
      messageEl.className = "rounded-md p-4";

      // Apply styling based on type
      switch (type) {
        case "success":
          messageEl.classList.add("bg-green-50", "border", "border-green-200");
          messageTextEl.className = "text-sm text-green-700";
          break;
        case "error":
          messageEl.classList.add("bg-red-50", "border", "border-red-200");
          messageTextEl.className = "text-sm text-red-700";
          break;
        case "info":
        default:
          messageEl.classList.add("bg-blue-50", "border", "border-blue-200");
          messageTextEl.className = "text-sm text-blue-700";
          break;
      }

      messageEl.classList.remove("hidden");

      // Auto-hide success and info messages
      if (type === "success" || type === "info") {
        setTimeout(() => this.clearMessage(), 3000);
      }
    }
  }

  clearMessage() {
    const messageEl = document.getElementById("login-message");
    if (messageEl) {
      messageEl.classList.add("hidden");
      messageEl.className = "hidden";
    }
  }

  // Public methods for external use
  isLoggedIn() {
    return window.api.isLoggedIn();
  }

  getCurrentStudent() {
    return window.api.getCurrentStudent();
  }

  requireAuth(callback) {
    if (this.isLoggedIn()) {
      callback();
    } else {
      this.showLogin();
    }
  }
}

// Create global auth manager instance
window.auth = new AuthManager();

// Utility functions for other modules
window.requireAuth = (callback) => window.auth.requireAuth(callback);
window.getCurrentStudent = () => window.auth.getCurrentStudent();
