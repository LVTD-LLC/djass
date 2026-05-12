import { Controller } from "@hotwired/stimulus";

export default class extends Controller {
  static targets = ["source", "status"];

  async copy() {
    if (!this.hasSourceTarget) return;

    const value = this.sourceTarget.value || this.sourceTarget.textContent || "";
    if (!value.trim()) return;

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        this.sourceTarget.select();
        document.execCommand("copy");
        this.sourceTarget.blur();
      }

      this.showStatus("Copied");
    } catch (error) {
      console.error("Failed to copy API key:", error);
      this.showStatus("Copy failed — select and copy manually");
    }
  }

  showStatus(message) {
    if (!this.hasStatusTarget) return;

    this.statusTarget.textContent = message;

    window.clearTimeout(this.statusTimeout);
    this.statusTimeout = window.setTimeout(() => {
      this.statusTarget.textContent = "";
    }, 2500);
  }
}
