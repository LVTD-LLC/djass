export function initMessages(root = document) {
  root.querySelectorAll("[data-message-item]").forEach((item, index) => {
    window.setTimeout(() => {
      item.classList.remove("opacity-0", "translate-x-full");
      startTimer(item);
    }, index * 100);
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-message-dismiss]");
    if (!button) {
      return;
    }

    const item = button.closest("[data-message-item]");
    if (item) {
      hideMessage(item);
    }
  });
}

export function showMessage(message, type = "error") {
  const container = document.querySelector("[data-messages-container]") || createMessagesContainer();
  const item = buildMessageElement(message, type);

  container.appendChild(item);
  window.setTimeout(() => {
    item.classList.remove("opacity-0", "translate-x-full");
    startTimer(item);
  }, 100);
}

function createMessagesContainer() {
  const container = document.createElement("div");
  container.dataset.messagesContainer = "";
  container.className = "fixed right-4 top-4 z-50 space-y-3";
  document.body.appendChild(container);
  return container;
}

function buildMessageElement(message, type) {
  const isError = type === "error";
  const item = document.createElement("div");
  item.dataset.messageItem = "";
  item.className = `dj-alert ${isError ? "dj-alert-danger" : "dj-alert-success"} max-w-sm translate-x-full opacity-0 shadow-lg transition-all duration-300 ease-in-out`;

  item.innerHTML = `
    <div class="flex items-start">
      <div class="mr-3 flex-shrink-0">
        <svg class="h-5 w-5" viewBox="0 0 24 24">
          <circle class="text-[var(--dj-border-strong)]" stroke-width="2" stroke="currentColor" fill="transparent" r="10" cx="12" cy="12"></circle>
          <circle class="${isError ? "text-[var(--dj-danger)]" : "text-[var(--dj-success)]"}" stroke-width="2" stroke="currentColor" fill="transparent" r="10" cx="12" cy="12" data-timer-circle></circle>
        </svg>
      </div>
      <div class="flex-grow">
        <p class="text-sm text-[var(--dj-heading)]"></p>
      </div>
      <div class="ml-3 flex-shrink-0">
        <button data-message-dismiss type="button" class="dj-icon-button h-6 w-6" aria-label="Dismiss">
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
          </svg>
        </button>
      </div>
    </div>
  `;
  item.querySelector("p").textContent = message;
  return item;
}

function startTimer(item) {
  const timerCircle = item.querySelector("[data-timer-circle]");
  if (!timerCircle) {
    return;
  }

  const radius = 10;
  const circumference = 2 * Math.PI * radius;
  timerCircle.style.strokeDasharray = `${circumference} ${circumference}`;
  timerCircle.style.strokeDashoffset = circumference;

  let progress = 0;
  const interval = window.setInterval(() => {
    if (progress >= 100) {
      window.clearInterval(interval);
      hideMessage(item);
      return;
    }

    progress += 1;
    timerCircle.style.strokeDashoffset = circumference - (progress / 100) * circumference;
  }, 50);
}

function hideMessage(item) {
  item.classList.add("opacity-0", "translate-x-full");
  window.setTimeout(() => item.remove(), 300);
}
