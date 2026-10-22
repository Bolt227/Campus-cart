/* Shared helpers + navbar, loaded on every page before the page's own script. */

// Escape text for safe use in HTML content AND inside quoted attributes.
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, function (character) {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    };

    return replacements[character];
  });
}

// Allow only local upload paths or https image URLs.
function safeImageSrc(path) {
  const value = String(path || "").trim();

  if (!value) return "";
  if (value.startsWith("/") && !value.startsWith("//")) return value;
  if (/^https:\/\//i.test(value)) return value;

  return "";
}

// Forget the browser-side login info (the server session is separate).
function clearLocalLogin() {
  localStorage.removeItem("userId");
  localStorage.removeItem("userName");
}

// If the server says we are not logged in, clean up and go to the login page.
function redirectToLogin() {
  clearLocalLogin();
  window.location.href = "/login";
}

function renderNavbar() {
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
      clearLocalLogin();
      window.location.href = "/login";
    });
  }
}

// Keep the navbar in sync with the real server session, so an expired
// session does not leave the browser thinking it is still logged in.
async function syncLoginState() {
  try {
    const response = await fetch("/api/me", { credentials: "same-origin" });

    if (response.ok) {
      const { user } = await response.json();
      const changed =
        localStorage.getItem("userId") !== String(user.id) ||
        localStorage.getItem("userName") !== user.name;

      localStorage.setItem("userId", user.id);
      localStorage.setItem("userName", user.name);
      if (changed) renderNavbar();
    } else if (response.status === 401 && localStorage.getItem("userId")) {
      clearLocalLogin();
      renderNavbar();
    }
  } catch (error) {
    // Offline or server down: keep whatever the navbar already shows.
    console.error("Could not check login state:", error);
  }
}

renderNavbar();
syncLoginState();
