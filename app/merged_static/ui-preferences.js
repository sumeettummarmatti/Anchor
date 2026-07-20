(() => {
  const THEME_KEY = "ui_theme";
  const SIDEBAR_KEY = "sidebar_collapsed";

  const setTheme = (theme, persist = true) => {
    const nextTheme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    if (persist) localStorage.setItem(THEME_KEY, nextTheme);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const isLight = nextTheme === "light";
      button.textContent = isLight ? "☾" : "☀";
      button.setAttribute("aria-label", isLight ? "Use dark theme" : "Use light theme");
      button.setAttribute("title", isLight ? "Use dark theme" : "Use light theme");
      const label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = isLight ? "Dark" : "Light";
    });
  };

  const setSidebarCollapsed = (collapsed, persist = true) => {
    document.documentElement.classList.toggle("sidebar-collapsed", collapsed);
    if (persist) localStorage.setItem(SIDEBAR_KEY, String(collapsed));
  };

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
    });
  });
  setTheme(document.documentElement.dataset.theme || "dark", false);
  const hoverSidebar = window.matchMedia("(hover: hover)").matches;
  setSidebarCollapsed(hoverSidebar || document.documentElement.classList.contains("sidebar-collapsed"), false);

  if (hoverSidebar) {
    document.querySelectorAll(".sidebar").forEach((sidebar) => {
      sidebar.addEventListener("mouseenter", () => setSidebarCollapsed(false, false));
      sidebar.addEventListener("mouseleave", () => setSidebarCollapsed(true, false));
    });
  }

  window.addEventListener("storage", (event) => {
    if (event.key === THEME_KEY) setTheme(event.newValue || "dark", false);
    if (event.key === SIDEBAR_KEY) setSidebarCollapsed(event.newValue === "true", false);
  });
})();
