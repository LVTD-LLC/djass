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
  initSecretRevealControls();
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

function setDisclosureState(button, menu, isOpen) {
  menu.hidden = !isOpen;
  menu.classList.toggle("hidden", !isOpen);
  button?.setAttribute("aria-expanded", String(isOpen));
}

function isOpenElement(element) {
  return element && !element.hidden && !element.classList.contains("hidden");
}

function focusableElements(container) {
  return Array.from(
    container.querySelectorAll(
      [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled]):not([type='hidden'])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "summary",
        "[tabindex]:not([tabindex='-1'])",
      ].join(",")
    )
  ).filter((element) => {
    const style = window.getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
  });
}

function trapFocus(container, event) {
  if (event.key !== "Tab") {
    return;
  }

  const focusable = focusableElements(container);
  if (focusable.length === 0) {
    event.preventDefault();
    return;
  }

  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
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

    setDisclosureState(button, menu, false);

    const hide = (restoreFocus = false) => {
      if (!isOpenElement(menu)) {
        return;
      }

      setDisclosureState(button, menu, false);
      if (restoreFocus) {
        button.focus();
      }
    };

    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setDisclosureState(button, menu, !isOpenElement(menu));
    });

    document.addEventListener("click", (event) => {
      if (!controller.contains(event.target)) {
        hide();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpenElement(menu)) {
        hide(true);
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

    let previouslyFocused = null;

    const open = (event) => {
      previouslyFocused = event.currentTarget;
      modal.classList.remove("hidden");
      modal.classList.add("flex");
      modal.setAttribute("aria-hidden", "false");
      window.requestAnimationFrame(() => {
        const first = confirmation || focusableElements(modal)[0];
        first?.focus();
      });
      if (confirmation) {
        confirmation.value = "";
      }
      updateDeleteSubmit(confirmation, submit);
    };

    const close = (restoreFocus = true) => {
      if (!isOpenElement(modal)) {
        return;
      }

      modal.classList.add("hidden");
      modal.classList.remove("flex");
      modal.setAttribute("aria-hidden", "true");
      if (restoreFocus) {
        previouslyFocused?.focus();
      }
    };

    controller.querySelectorAll('[data-action*="delete-account#open"]').forEach((button) => {
      button.addEventListener("click", open);
    });
    controller.querySelectorAll('[data-action*="delete-account#close"]').forEach((button) => {
      button.addEventListener("click", close);
    });
    confirmation?.addEventListener("input", () => updateDeleteSubmit(confirmation, submit));
    modal.addEventListener("keydown", (event) => trapFocus(modal, event));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpenElement(modal)) {
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

function initSecretRevealControls(root = document) {
  root.querySelectorAll('[data-controller~="secret-reveal"]').forEach((controller) => {
    if (controller.dataset.secretRevealBound === "true") {
      return;
    }

    controller.dataset.secretRevealBound = "true";
    const input = controller.querySelector('[data-secret-reveal-target~="input"]');
    const button = controller.querySelector('[data-secret-reveal-target~="toggle"]');
    if (!input || !button) {
      return;
    }

    const setVisible = (isVisible) => {
      input.type = isVisible ? "text" : "password";
      button.setAttribute("aria-pressed", String(isVisible));
      button.textContent = isVisible ? "Hide key" : "Show key";
    };

    setVisible(false);
    button.addEventListener("click", () => setVisible(input.type === "password"));
  });
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
    const toggleButton = controller.querySelector('[data-feedback-target~="toggleButton"]');
    const form = controller.querySelector("form");
    let open = false;
    let previouslyFocused = null;

    const show = (event) => {
      if (!overlay || !formContainer || !input) {
        return;
      }

      previouslyFocused = event?.currentTarget || document.activeElement;
      overlay.classList.remove("pointer-events-none", "opacity-0");
      overlay.classList.add("pointer-events-auto", "opacity-100");
      overlay.setAttribute("aria-hidden", "false");
      toggleButton?.setAttribute("aria-expanded", "true");
      window.setTimeout(() => {
        formContainer.classList.remove("scale-95");
        formContainer.classList.add("scale-100");
        input.focus();
      }, 10);
      open = true;
    };

    const hide = (restoreFocus = true) => {
      if (!overlay || !formContainer) {
        return;
      }

      formContainer.classList.remove("scale-100");
      formContainer.classList.add("scale-95");
      overlay.setAttribute("aria-hidden", "true");
      toggleButton?.setAttribute("aria-expanded", "false");
      window.setTimeout(() => {
        overlay.classList.remove("pointer-events-auto", "opacity-100");
        overlay.classList.add("pointer-events-none", "opacity-0");
      }, 100);
      open = false;
      if (restoreFocus) {
        previouslyFocused?.focus();
      }
    };

    controller.querySelectorAll('[data-action*="feedback#toggleFeedback"]').forEach((button) => {
      button.addEventListener("click", (event) => (open ? hide() : show(event)));
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
    formContainer?.addEventListener("keydown", (event) => trapFocus(formContainer, event));
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
