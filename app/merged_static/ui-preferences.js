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
    document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
      button.setAttribute("aria-expanded", String(!collapsed));
      button.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
      button.setAttribute("title", collapsed ? "Expand sidebar" : "Collapse sidebar");
      const label = button.querySelector("[data-sidebar-label]");
      if (label) label.textContent = collapsed ? "Expand" : "Collapse";
    });
  };

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
    });
  });
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      setSidebarCollapsed(!document.documentElement.classList.contains("sidebar-collapsed"));
    });
  });

  setTheme(document.documentElement.dataset.theme || "dark", false);
  setSidebarCollapsed(document.documentElement.classList.contains("sidebar-collapsed"), false);

  window.addEventListener("storage", (event) => {
    if (event.key === THEME_KEY) setTheme(event.newValue || "dark", false);
    if (event.key === SIDEBAR_KEY) setSidebarCollapsed(event.newValue === "true", false);
  });
})();
