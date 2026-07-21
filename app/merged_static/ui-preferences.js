(() => {
  const THEME_KEY = "ui_theme";
  const SIDEBAR_KEY = "sidebar_collapsed";
  const nativeFetch = window.fetch.bind(window);
  let refreshPromise = null;

  const refreshAccessToken = async () => {
    const refreshToken = localStorage.getItem("mentor_refresh_token");
    if (!refreshToken) return false;
    if (!refreshPromise) {
      refreshPromise = nativeFetch("/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).then(async (response) => {
        if (!response.ok) return false;
        const tokens = await response.json();
        localStorage.setItem("mentor_access_token", tokens.access_token);
        localStorage.setItem("mentor_refresh_token", tokens.refresh_token);
        return true;
      }).catch(() => false).finally(() => { refreshPromise = null; });
    }
    return refreshPromise;
  };

  window.fetch = async (input, init = {}) => {
    const headers = new Headers(init.headers || {});
    const authenticated = headers.has("Authorization");
    if (authenticated) {
      const accessToken = localStorage.getItem("mentor_access_token");
      if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    }
    const options = { ...init, headers };
    let response = await nativeFetch(input, options);
    if (authenticated && response.status === 401 && await refreshAccessToken()) {
      headers.set("Authorization", `Bearer ${localStorage.getItem("mentor_access_token")}`);
      response = await nativeFetch(input, options);
    }
    return response;
  };

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
