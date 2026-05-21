import { copyText } from "./clipboard.js";

export function initCopyButtons(root = document) {
  initExplicitCopyButtons(root);
  initLegacyClipboardControllers(root);
}

function initExplicitCopyButtons(root) {
  root.querySelectorAll("[data-copy-button]").forEach((button) => {
    if (button.dataset.copyBound === "true") {
      return;
    }

    button.dataset.copyBound = "true";
    button.addEventListener("click", async () => {
      const sourceSelector = button.dataset.copySource;
      const source = sourceSelector ? document.querySelector(sourceSelector) : null;
      const label = button.querySelector("[data-copy-label]") || button;
      const original = label.textContent;
      const text = source?.value || source?.textContent || "";
      const copied = await copyText(text);

      label.textContent = copied ? "Copied" : "Copy failed";
      window.clearTimeout(Number(button.dataset.resetTimer));
      button.dataset.resetTimer = window.setTimeout(() => {
        label.textContent = original;
      }, 1600);
    });
  });
}

function initLegacyClipboardControllers(root) {
  root.querySelectorAll('[data-controller~="clipboard"]').forEach((controller) => {
    if (controller.dataset.clipboardBound === "true") {
      return;
    }

    controller.dataset.clipboardBound = "true";
    const source = controller.querySelector('[data-clipboard-target~="source"]');
    const status = controller.querySelector('[data-clipboard-target~="status"]');

    controller.querySelectorAll('[data-action*="clipboard#copy"]').forEach((button) => {
      button.addEventListener("click", async () => {
        const value = source?.value || source?.textContent || "";
        const copied = await copyText(value);
        if (!status) {
          return;
        }

        status.textContent = copied ? "Copied" : "Copy failed";
        window.clearTimeout(Number(status.dataset.resetTimer));
        status.dataset.resetTimer = window.setTimeout(() => {
          status.textContent = "";
        }, 1600);
      });
    });
  });
}
