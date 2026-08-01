document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("public-nav-toggle");
  const nav = document.getElementById("public-nav");
  if (!toggle || !nav) return;

  const DESKTOP_QUERY = "(min-width: 901px)";

  const openMenu = () => {
    nav.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
  };

  const closeMenu = () => {
    nav.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  };

  const isOpen = () => nav.classList.contains("is-open");

  toggle.addEventListener("click", () => {
    if (isOpen()) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  nav.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (link) {
      closeMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) {
      closeMenu();
      toggle.focus();
    }
  });

  const desktopMediaQuery = window.matchMedia
    ? window.matchMedia(DESKTOP_QUERY)
    : null;

  if (desktopMediaQuery) {
    const resetStaleMobileState = (event) => {
      if (event.matches) {
        closeMenu();
      }
    };

    if (typeof desktopMediaQuery.addEventListener === "function") {
      desktopMediaQuery.addEventListener("change", resetStaleMobileState);
    } else if (typeof desktopMediaQuery.addListener === "function") {
      // Safari < 14 fallback.
      desktopMediaQuery.addListener(resetStaleMobileState);
    }
  }
});
