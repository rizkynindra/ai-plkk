document.querySelectorAll(".nav-toggle").forEach((button) => {
  button.addEventListener("click", () => {
    const bar = button.closest(".topbar-inner");
    const open = bar.classList.toggle("is-open");
    button.setAttribute("aria-expanded", open ? "true" : "false");
  });
});
