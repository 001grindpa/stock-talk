/**
 * Stocktalk Feedback Floating Control
 * Draggable button, expand/collapse panel, client-side validation, and API integration.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "stocktalk.feedback.pos";
  const DRAG_THRESHOLD = 5; // px

  function initFeedback() {
    if (document.getElementById("feedback-widget-root")) {
      return;
    }

    // Create container
    const root = document.createElement("div");
    root.id = "feedback-widget-root";
    root.className = "feedback-widget-root";

    root.innerHTML = `
      <div id="feedback-panel" class="feedback-panel" role="dialog" aria-modal="false" aria-labelledby="feedback-panel-title" hidden>
        <div class="feedback-panel-header">
          <div class="feedback-header-title-wrap">
            <svg class="feedback-header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
            </svg>
            <h3 id="feedback-panel-title">Send Feedback</h3>
          </div>
          <button id="feedback-close-btn" type="button" class="feedback-close-btn" aria-label="Close feedback panel" title="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <form id="feedback-form" class="feedback-form" novalidate>
          <div class="feedback-form-alert" id="feedback-form-alert" hidden></div>

          <div class="feedback-field">
            <label for="feedback-email" class="feedback-label">
              Email <span class="feedback-required" aria-hidden="true">*</span>
            </label>
            <input
              type="email"
              id="feedback-email"
              name="email"
              class="feedback-input"
              placeholder="you@domain.com"
              maxlength="254"
              required
              autocomplete="email"
            />
            <span class="feedback-inline-error" id="feedback-email-error" aria-live="polite"></span>
          </div>

          <div class="feedback-field">
            <label for="feedback-handle" class="feedback-label">
              X Handle <span class="feedback-optional">(optional)</span>
            </label>
            <input
              type="text"
              id="feedback-handle"
              name="handle"
              class="feedback-input"
              placeholder="@username"
              maxlength="50"
              autocomplete="off"
              spellcheck="false"
            />
            <span class="feedback-inline-error" id="feedback-handle-error" aria-live="polite"></span>
          </div>

          <div class="feedback-field">
            <div class="feedback-label-row">
              <label for="feedback-message" class="feedback-label">
                Feedback / Complaint / Issue <span class="feedback-required" aria-hidden="true">*</span>
              </label>
              <span class="feedback-char-count" id="feedback-char-count">0 / 2000</span>
            </div>
            <textarea
              id="feedback-message"
              name="message"
              class="feedback-textarea"
              placeholder="Share your thoughts, suggestions, or issues (10–2000 chars)..."
              rows="4"
              minlength="10"
              maxlength="2000"
              required
            ></textarea>
            <span class="feedback-inline-error" id="feedback-message-error" aria-live="polite"></span>
          </div>

          <button id="feedback-submit-btn" type="submit" class="feedback-submit-btn">
            <span class="feedback-btn-text">Submit Feedback</span>
            <span class="feedback-btn-spinner" aria-hidden="true" hidden></span>
          </button>
        </form>
      </div>

      <button
        id="feedback-fab-btn"
        type="button"
        class="feedback-fab-btn"
        aria-label="Send feedback"
        aria-haspopup="dialog"
        aria-expanded="false"
        title="Send feedback"
      >
        <span class="feedback-fab-icon-wrap" aria-hidden="true">
          <svg class="feedback-fab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <svg class="feedback-fab-success-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" hidden>
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
        </span>
      </button>

      <div id="feedback-toast" class="feedback-toast" role="status" aria-live="polite" hidden>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="feedback-toast-icon">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        <span>Feedback sent! Thank you.</span>
      </div>
    `;

    document.body.appendChild(root);

    const fabBtn = document.getElementById("feedback-fab-btn");
    const panel = document.getElementById("feedback-panel");
    const closeBtn = document.getElementById("feedback-close-btn");
    const form = document.getElementById("feedback-form");
    const emailInput = document.getElementById("feedback-email");
    const handleInput = document.getElementById("feedback-handle");
    const messageInput = document.getElementById("feedback-message");
    const charCount = document.getElementById("feedback-char-count");
    const submitBtn = document.getElementById("feedback-submit-btn");
    const formAlert = document.getElementById("feedback-form-alert");
    const toast = document.getElementById("feedback-toast");

    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let initialLeft = 0;
    let initialTop = 0;
    let hasMoved = false;

    // Position calculation and persistence
    function clampPosition(left, top) {
      const btnSize = 48;
      const margin = 12;
      const maxLeft = Math.max(margin, window.innerWidth - btnSize - margin);
      const maxTop = Math.max(margin, window.innerHeight - btnSize - margin);
      const clampedLeft = Math.min(Math.max(margin, left), maxLeft);
      const clampedTop = Math.min(Math.max(margin, top), maxTop);
      return { left: clampedLeft, top: clampedTop };
    }

    function applySavedPosition() {
      const saved = localStorage.getItem(STORAGE_KEY);
      let left, top;
      const btnSize = 48;
      const defaultRight = 24;
      const defaultBottom = 128;

      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          left = parsed.left;
          top = parsed.top;
        } catch (e) {
          left = window.innerWidth - btnSize - defaultRight;
          top = window.innerHeight - btnSize - defaultBottom;
        }
      } else {
        left = window.innerWidth - btnSize - defaultRight;
        top = window.innerHeight - btnSize - defaultBottom;
      }

      const clamped = clampPosition(left, top);
      fabBtn.style.left = `${clamped.left}px`;
      fabBtn.style.top = `${clamped.top}px`;
      fabBtn.style.bottom = "auto";
      fabBtn.style.right = "auto";
    }

    applySavedPosition();

    window.addEventListener("resize", () => {
      const rect = fabBtn.getBoundingClientRect();
      const clamped = clampPosition(rect.left, rect.top);
      fabBtn.style.left = `${clamped.left}px`;
      fabBtn.style.top = `${clamped.top}px`;
      if (isPanelOpen()) {
        positionPanel();
      }
    });

    // Drag handling via pointer events
    fabBtn.addEventListener("pointerdown", (e) => {
      // Only main click (mouse left button or touch)
      if (e.button !== 0 && e.pointerType === "mouse") return;
      isDragging = true;
      hasMoved = false;
      dragStartX = e.clientX;
      dragStartY = e.clientY;

      const rect = fabBtn.getBoundingClientRect();
      initialLeft = rect.left;
      initialTop = rect.top;

      try {
        fabBtn.setPointerCapture(e.pointerId);
      } catch (err) {}
    });

    fabBtn.addEventListener("pointermove", (e) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      const dist = Math.hypot(dx, dy);

      if (dist > DRAG_THRESHOLD) {
        hasMoved = true;
        fabBtn.classList.add("is-dragging");
        const rawLeft = initialLeft + dx;
        const rawTop = initialTop + dy;
        const clamped = clampPosition(rawLeft, rawTop);
        fabBtn.style.left = `${clamped.left}px`;
        fabBtn.style.top = `${clamped.top}px`;

        if (isPanelOpen()) {
          positionPanel();
        }
      }
    });

    function endDrag(e) {
      if (!isDragging) return;
      isDragging = false;
      fabBtn.classList.remove("is-dragging");

      try {
        fabBtn.releasePointerCapture(e.pointerId);
      } catch (err) {}

      if (hasMoved) {
        const rect = fabBtn.getBoundingClientRect();
        const clamped = clampPosition(rect.left, rect.top);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(clamped));
      } else {
        togglePanel();
      }
      hasMoved = false;
    }

    fabBtn.addEventListener("pointerup", endDrag);
    fabBtn.addEventListener("pointercancel", endDrag);

    // Panel open/close and positioning
    function isPanelOpen() {
      return !panel.hidden;
    }

    function positionPanel() {
      const btnRect = fabBtn.getBoundingClientRect();
      const panelWidth = Math.min(window.innerWidth - 24, 340);
      const margin = 12;

      // Vertical positioning: default above the button; if not enough space, place below
      const spaceAbove = btnRect.top;
      const panelHeightEstimate = 420;
      let top;
      if (spaceAbove >= panelHeightEstimate || spaceAbove >= window.innerHeight / 2) {
        top = Math.max(margin, btnRect.top - panelHeightEstimate - 8);
      } else {
        top = Math.min(window.innerHeight - panelHeightEstimate - margin, btnRect.bottom + 8);
      }

      // Horizontal positioning: align with right edge of button or clamp
      let left = btnRect.right - panelWidth;
      if (left < margin) left = margin;
      if (left + panelWidth > window.innerWidth - margin) {
        left = window.innerWidth - panelWidth - margin;
      }

      panel.style.top = `${top}px`;
      panel.style.left = `${left}px`;
      panel.style.width = `${panelWidth}px`;
    }

    function openPanel() {
      panel.hidden = false;
      fabBtn.setAttribute("aria-expanded", "true");
      positionPanel();
      clearErrors();
      setTimeout(() => emailInput.focus(), 50);
    }

    function closePanel() {
      panel.hidden = true;
      fabBtn.setAttribute("aria-expanded", "false");
      clearErrors();
    }

    function togglePanel() {
      if (isPanelOpen()) {
        closePanel();
      } else {
        openPanel();
      }
    }

    closeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      closePanel();
    });

    // Close on click outside
    document.addEventListener("pointerdown", (e) => {
      if (!isPanelOpen()) return;
      if (!root.contains(e.target)) {
        closePanel();
      }
    });

    // Close on Escape
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isPanelOpen()) {
        closePanel();
      }
    });

    // Character counter
    messageInput.addEventListener("input", () => {
      const len = messageInput.value.length;
      charCount.textContent = `${len} / 2000`;
      if (len < 10 && len > 0) {
        charCount.classList.add("is-under");
        charCount.classList.remove("is-max");
      } else if (len >= 1950) {
        charCount.classList.remove("is-under");
        charCount.classList.add("is-max");
      } else {
        charCount.classList.remove("is-under", "is-max");
      }
      clearFieldError("message");
    });

    emailInput.addEventListener("input", () => clearFieldError("email"));
    handleInput.addEventListener("input", () => clearFieldError("handle"));

    function clearFieldError(field) {
      const errEl = document.getElementById(`feedback-${field}-error`);
      if (errEl) errEl.textContent = "";
      const inputEl = document.getElementById(`feedback-${field}`);
      if (inputEl) inputEl.classList.remove("input-error");
    }

    function showFieldError(field, msg) {
      const errEl = document.getElementById(`feedback-${field}-error`);
      if (errEl) errEl.textContent = msg;
      const inputEl = document.getElementById(`feedback-${field}`);
      if (inputEl) {
        inputEl.classList.add("input-error");
        inputEl.focus();
      }
    }

    function clearErrors() {
      clearFieldError("email");
      clearFieldError("handle");
      clearFieldError("message");
      if (formAlert) {
        formAlert.hidden = true;
        formAlert.textContent = "";
        formAlert.className = "feedback-form-alert";
      }
    }

    function showFormAlert(msg, isSuccess = false) {
      if (!formAlert) return;
      formAlert.hidden = false;
      formAlert.textContent = msg;
      formAlert.className = `feedback-form-alert ${isSuccess ? "alert-success" : "alert-error"}`;
    }

    function showToast(msg) {
      if (!toast) return;
      const span = toast.querySelector("span");
      if (span) span.textContent = msg || "Feedback sent! Thank you.";
      toast.hidden = false;
      toast.classList.add("is-visible");

      // Animate FAB icon to checkmark
      const defaultIcon = fabBtn.querySelector(".feedback-fab-icon");
      const successIcon = fabBtn.querySelector(".feedback-fab-success-icon");
      if (defaultIcon && successIcon) {
        defaultIcon.hidden = true;
        successIcon.hidden = false;
        fabBtn.classList.add("is-success");
      }

      setTimeout(() => {
        toast.classList.remove("is-visible");
        setTimeout(() => {
          toast.hidden = true;
          if (defaultIcon && successIcon) {
            defaultIcon.hidden = false;
            successIcon.hidden = true;
            fabBtn.classList.remove("is-success");
          }
        }, 300);
      }, 3500);
    }

    // Client-side validation & submit
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearErrors();

      const emailVal = emailInput.value.trim();
      let handleVal = handleInput.value.trim();
      const messageVal = messageInput.value.trim();

      // Validate email
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailVal) {
        showFieldError("email", "Email is required.");
        return;
      }
      if (!emailRegex.test(emailVal) || emailVal.length > 254) {
        showFieldError("email", "Please enter a valid email address.");
        return;
      }

      // Normalize handle
      if (handleVal) {
        handleVal = "@" + handleVal.replace(/^@+/, "");
      }

      // Validate message
      if (!messageVal) {
        showFieldError("message", "Message is required.");
        return;
      }
      if (messageVal.length < 10) {
        showFieldError("message", "Message must be at least 10 characters.");
        return;
      }
      if (messageVal.length > 2000) {
        showFieldError("message", "Message must not exceed 2000 characters.");
        return;
      }

      // In-flight state
      setSubmitting(true);

      try {
        const response = await fetch("/api/feedback", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: emailVal,
            handle: handleVal,
            message: messageVal,
          }),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          const errMsg = data.error || `Server responded with ${response.status}`;
          showFormAlert(errMsg);
          setSubmitting(false);
          return;
        }

        // Success: collapse panel, reset form, show toast
        setSubmitting(false);
        form.reset();
        charCount.textContent = "0 / 2000";
        closePanel();
        showToast(data.message || "Feedback sent! Thank you.");
      } catch (err) {
        showFormAlert("Network error. Please check your connection and try again.");
        setSubmitting(false);
      }
    });

    function setSubmitting(isSubmitting) {
      submitBtn.disabled = isSubmitting;
      emailInput.disabled = isSubmitting;
      handleInput.disabled = isSubmitting;
      messageInput.disabled = isSubmitting;

      const btnText = submitBtn.querySelector(".feedback-btn-text");
      const btnSpinner = submitBtn.querySelector(".feedback-btn-spinner");

      if (isSubmitting) {
        submitBtn.classList.add("is-loading");
        if (btnText) btnText.textContent = "Sending...";
        if (btnSpinner) btnSpinner.hidden = false;
      } else {
        submitBtn.classList.remove("is-loading");
        if (btnText) btnText.textContent = "Submit Feedback";
        if (btnSpinner) btnSpinner.hidden = true;
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFeedback);
  } else {
    initFeedback();
  }
})();