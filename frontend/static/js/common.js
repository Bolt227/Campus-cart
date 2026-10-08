/* Shared helpers + navbar, loaded on every page before the page's own script. */

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = text == null ? "" : String(text);
  return element.innerHTML;
}

(function renderNavbar() {
  const mount = document.getElementById("navbar");
  if (!mount) return;

  const loggedInId = localStorage.getItem("userId");
  const loggedInName = localStorage.getItem("userName");
  const isLoggedIn = Boolean(loggedInId && loggedInName);
  const path = window.location.pathname;

  const links = [
    { href: "/", label: "Browse", match: p => p === "/" || p.startsWith("/item/") },
    { href: "/add-item", label: "Sell an Item", match: p => p === "/add-item" },
    { href: "/my-listings", label: "My Listings", match: p => p === "/my-listings" || p.startsWith("/edit-item/") }
  ];

  const linkHtml = links
    .map(l => `<a href="${l.href}" class="${l.match(path) ? "active" : ""}">${l.label}</a>`)
    .join("");

  const authHtml = isLoggedIn
    ? `<span class="nav-user">Hi, <strong>${escapeHtml(loggedInName)}</strong></span>
       <button id="logoutButton" type="button" class="btn-ghost btn-sm">Logout</button>`
    : `<a href="/login" class="btn btn-ghost btn-sm">Login</a>
       <a href="/register" class="btn btn-sm">Register</a>`;

  mount.className = "navbar";
  mount.innerHTML = `
    <div class="nav-inner">
      <a href="/" class="brand"><span class="brand-mark">🛒</span>Campus Cart</a>
      <nav class="nav-links">${linkHtml}</nav>
      <div class="nav-auth">${authHtml}</div>
    </div>
  `;

  const logoutButton = document.getElementById("logoutButton");
  if (logoutButton) {
    logoutButton.addEventListener("click", async () => {
      try {
        await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
      } catch (error) {
        console.error("Could not clear the server session:", error);
      }
      localStorage.removeItem("userId");
      localStorage.removeItem("userName");
      window.location.href = "/login";
    });
  }
})();
