document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("public-nav-toggle");
  const nav = document.getElementById("public-nav");
  if (!toggle || !nav) return;

  toggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });
});
