import { initCopyButtons } from "./modules/copy.js";
import { initDocsEnhancements } from "./modules/docs.js";
import { initMessages, showMessage } from "./modules/messages.js";
import { initTheme } from "./modules/theme.js";
import { initUserSettingsCache } from "./modules/user-settings.js";

window.appMessages = { show: showMessage };

window.submitFeedback = async function submitFeedback(feedback) {
  const value = feedback.trim();
  if (!value) {
    return false;
  }

  const response = await fetch("/api/submit-feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ feedback: value, page: window.location.pathname }),
  });

  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }

  if (!response.ok || data.status === false) {
    throw new Error(data.message || "Failed to submit feedback. Please try again later.");
  }

  showMessage(data.message || "Feedback submitted successfully", "success");
  return true;
};

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initMessages();
  initCopyButtons();
  initDocsEnhancements();
  initUserSettingsCache();
  initLegacyDropdowns();
  initDeleteAccountControls();
  initLegacyFeedbackControls();
});

function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(";") : [];

  for (const cookie of cookies) {
    const [key, ...valueParts] = cookie.trim().split("=");
    if (key === name) {
      return decodeURIComponent(valueParts.join("="));
    }
  }

  return "";
}

function initLegacyDropdowns(root = document) {
  root.querySelectorAll('[data-controller~="dropdown"]').forEach((controller) => {
    if (controller.dataset.dropdownBound === "true") {
      return;
    }

    controller.dataset.dropdownBound = "true";
    const menu = controller.querySelector('[data-dropdown-target~="menu"]');
    const button = controller.querySelector('[data-action*="dropdown#toggle"]');
    if (!menu || !button) {
      return;
    }

    const hide = () => menu.classList.add("hidden");
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      menu.classList.toggle("hidden");
    });
    document.addEventListener("click", (event) => {
      if (!controller.contains(event.target)) {
        hide();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        hide();
      }
    });
  });
}

function initDeleteAccountControls(root = document) {
  root.querySelectorAll('[data-controller~="delete-account"]').forEach((controller) => {
    if (controller.dataset.deleteAccountBound === "true") {
      return;
    }

    controller.dataset.deleteAccountBound = "true";
    const modal = controller.querySelector('[data-delete-account-target~="modal"]');
    const confirmation = controller.querySelector('[data-delete-account-target~="confirmation"]');
    const submit = controller.querySelector('[data-delete-account-target~="submit"]');
    if (!modal) {
      return;
    }

    const open = () => {
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      if (confirmation) {
        confirmation.value = "";
        confirmation.focus();
      }
      updateDeleteSubmit(confirmation, submit);
    };
    const close = () => {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    };

    controller.querySelectorAll('[data-action*="delete-account#open"]').forEach((button) => {
      button.addEventListener("click", open);
    });
    controller.querySelectorAll('[data-action*="delete-account#close"]').forEach((button) => {
      button.addEventListener("click", close);
    });
    confirmation?.addEventListener("input", () => updateDeleteSubmit(confirmation, submit));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        close();
      }
    });
  });
}

function updateDeleteSubmit(confirmation, submit) {
  if (!confirmation || !submit) {
    return;
  }
  submit.disabled = confirmation.value !== "DELETE";
}

function initLegacyFeedbackControls(root = document) {
  root.querySelectorAll('[data-controller~="feedback"]').forEach((controller) => {
    if (controller.dataset.feedbackBound === "true") {
      return;
    }

    controller.dataset.feedbackBound = "true";
    const overlay = controller.querySelector('[data-feedback-target~="overlay"]');
    const formContainer = controller.querySelector('[data-feedback-target~="formContainer"]');
    const input = controller.querySelector('[data-feedback-target~="feedbackInput"]');
    const form = controller.querySelector("form");
    let open = false;

    const show = () => {
      if (!overlay || !formContainer || !input) {
        return;
      }
      overlay.classList.remove("pointer-events-none", "opacity-0");
      overlay.classList.add("pointer-events-auto", "opacity-100");
      window.setTimeout(() => {
        formContainer.classList.remove("scale-95");
        formContainer.classList.add("scale-100");
        input.focus();
      }, 10);
      open = true;
    };
    const hide = () => {
      if (!overlay || !formContainer) {
        return;
      }
      formContainer.classList.remove("scale-100");
      formContainer.classList.add("scale-95");
      window.setTimeout(() => {
        overlay.classList.remove("pointer-events-auto", "opacity-100");
        overlay.classList.add("pointer-events-none", "opacity-0");
      }, 100);
      open = false;
    };

    controller.querySelectorAll('[data-action*="feedback#toggleFeedback"]').forEach((button) => {
      button.addEventListener("click", () => (open ? hide() : show()));
    });
    controller.querySelectorAll('[data-action*="feedback#closeFeedback"]').forEach((button) => {
      button.addEventListener("click", hide);
    });
    overlay?.addEventListener("click", (event) => {
      if (event.target === overlay) {
        hide();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && open) {
        hide();
      }
    });
    form?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitButton = form.querySelector('button[type="submit"]');
      const originalButtonText = submitButton?.textContent || "Send Feedback";
      try {
        if (submitButton) {
          submitButton.disabled = true;
          submitButton.textContent = "Submitting...";
        }
        await window.submitFeedback(input?.value || "");
        if (input) {
          input.value = "";
        }
        hide();
      } catch (error) {
        showMessage(error.message || "Failed to submit feedback. Please try again later.", "error");
      } finally {
        if (submitButton) {
          submitButton.disabled = false;
          submitButton.textContent = originalButtonText;
        }
      }
    });
  });
}
