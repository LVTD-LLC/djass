const STORAGE_KEY = "theme";

export function initTheme(root = document) {
  applyTheme(currentTheme());
  const buttons = [
    ...root.querySelectorAll("[data-theme-toggle]"),
    ...root.querySelectorAll('[data-controller~="theme"]'),
  ];

  buttons.forEach((button) => {
    if (button.dataset.themeBound === "true") {
      updateButton(button);
      return;
    }

    button.dataset.themeBound = "true";
    updateButton(button);
    button.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
      buttons.forEach(updateButton);
    });
  });
}

function preferredTheme() {
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

function currentTheme() {
  return localStorage.getItem(STORAGE_KEY) || preferredTheme();
}

function applyTheme(theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

function updateButton(button) {
  const theme = currentTheme();
  button.querySelectorAll("[data-theme-icon]").forEach((icon) => {
    icon.classList.toggle("hidden", icon.dataset.themeIcon !== theme);
  });
  button.querySelectorAll('[data-theme-target~="iconLight"]').forEach((icon) => {
    icon.classList.toggle("hidden", theme !== "light");
  });
  button.querySelectorAll('[data-theme-target~="iconDark"]').forEach((icon) => {
    icon.classList.toggle("hidden", theme !== "dark");
  });

  const label = button.querySelector("[data-theme-label], [data-theme-target~='label']");
  if (label) {
    label.textContent = theme === "dark" ? "Dark" : "Light";
  }

  button.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
}
