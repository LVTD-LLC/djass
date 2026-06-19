import { copyText } from "./clipboard.js";

export function initDocsEnhancements(root = document) {
  root.querySelectorAll("[data-docs-page]").forEach((page) => enhanceDocsPage(page));
  root.querySelectorAll('[data-controller~="toc"]').forEach((page) => enhanceDocsPage(page));
}

function enhanceDocsPage(page) {
  addCodeCopyButtons(page);
  buildTableOfContents(page);
}

function addCodeCopyButtons(page) {
  const content = docsContent(page);
  if (!content) {
    return;
  }

  content.querySelectorAll("pre").forEach((block) => {
    if (block.dataset.copyEnhanced === "true") {
      return;
    }

    const code = block.querySelector("code");
    if (!code) {
      return;
    }

    block.dataset.copyEnhanced = "true";
    const wrapper = document.createElement("div");
    wrapper.className = "group relative my-6";
    block.parentNode.insertBefore(wrapper, block);
    wrapper.appendChild(block);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "dj-code-copy-button";
    button.textContent = "Copy";
    button.addEventListener("click", () => copyCode(code.textContent, button));
    wrapper.appendChild(button);
  });
}

async function copyCode(text, button) {
  const copied = await copyText(text);
  const original = button.dataset.originalLabel || button.textContent;
  button.dataset.originalLabel = original;
  button.textContent = copied ? "Copied" : "Copy failed";
  window.clearTimeout(Number(button.dataset.resetTimer));
  button.dataset.resetTimer = window.setTimeout(() => {
    button.textContent = original;
  }, 1600);
}

function buildTableOfContents(page) {
  const content = docsContent(page);
  const list = page.querySelector("[data-toc-list], [data-toc-target~='list']");
  const sidebar = page.querySelector("[data-toc-sidebar], [data-toc-target~='sidebar']");

  if (!content || !list || list.dataset.tocBuilt === "true") {
    return;
  }

  const headings = Array.from(content.querySelectorAll("h2"));
  if (headings.length === 0) {
    if (sidebar) {
      sidebar.hidden = true;
      sidebar.style.display = "none";
    }
    return;
  }

  list.dataset.tocBuilt = "true";
  list.replaceChildren();
  headings.forEach((heading) => {
    const headingText = heading.textContent.trim();
    const headingId = heading.id || slugify(headingText);
    heading.id = headingId;

    const listItem = document.createElement("li");
    const link = document.createElement("a");
    link.href = `#${headingId}`;
    link.textContent = headingText;
    link.dataset.tocLink = "";
    link.dataset.section = headingId;
    link.className = "dj-toc-link";
    link.addEventListener("click", (event) => {
      event.preventDefault();
      scrollToSection(headingId);
      updateActiveLink(page, headingId);
    });

    listItem.appendChild(link);
    list.appendChild(listItem);
  });

  const highlightCurrentSection = () => {
    const scrollPosition = window.scrollY + 100;
    const current = headings.reduce((currentId, heading) => {
      if (scrollPosition >= heading.offsetTop) {
        return heading.id;
      }
      return currentId;
    }, "");

    if (current) {
      updateActiveLink(page, current);
    }
  };

  highlightCurrentSection();
  window.addEventListener("scroll", highlightCurrentSection, { passive: true });
}

function docsContent(page) {
  return page.querySelector("[data-toc-content], [data-toc-target~='content'], .docs-code-blocks");
}

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .trim();
}

function scrollToSection(sectionId) {
  const section = document.getElementById(sectionId);
  if (!section) {
    return;
  }

  const offsetPosition = section.getBoundingClientRect().top + window.pageYOffset - 80;
  window.scrollTo({ top: offsetPosition, behavior: "smooth" });
}

function updateActiveLink(page, activeSectionId) {
  page.querySelectorAll("[data-toc-link]").forEach((link) => {
    const isActive = link.dataset.section === activeSectionId;
    link.classList.toggle("dj-toc-link-active", isActive);
  });
}
