const itemsContainer = document.getElementById("itemsContainer");
const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");
const searchButton = document.getElementById("searchButton");
const userGreeting = document.getElementById("userGreeting");
const logoutButton = document.getElementById("logoutButton");

const userId = localStorage.getItem("userId");
const userName = localStorage.getItem("userName");

if (userId && userName && userGreeting && logoutButton) {
  userGreeting.textContent = `Hello, ${userName}!`;
  logoutButton.hidden = false;
}

if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      await fetch("/api/logout", {
        method: "POST",
        credentials: "same-origin"
      });
    } catch (error) {
      console.error("Could not clear the server session:", error);
    }

    localStorage.removeItem("userId");
    localStorage.removeItem("userName");
    window.location.href = "/login";
  });
}

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element.innerHTML;
}

async function loadItems() {
  if (!itemsContainer || !searchInput || !categoryFilter) return;

  const search = searchInput.value.trim();
  const category = categoryFilter.value;
  const parameters = new URLSearchParams();

  if (search) parameters.append("search", search);
  if (category) parameters.append("category", category);

  itemsContainer.innerHTML = "<p>Loading items...</p>";

  try {
    const response = await fetch(`/api/items?${parameters}`);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const items = await response.json();

    if (items.length === 0) {
      itemsContainer.innerHTML = "<p>No available items found.</p>";
      return;
    }

    itemsContainer.innerHTML = items.map(item => {
      const image = item.image_path
        ? `<img class="item-image" src="${item.image_path}" alt="${escapeHtml(item.title)}">`
        : `<div class="no-image">No image available</div>`;

      return `
        <article class="item-card">
          ${image}
          <p class="category">${escapeHtml(item.category)}</p>
          <h3>${escapeHtml(item.title)}</h3>
          <p>${escapeHtml(item.description)}</p>
          <p>Condition: ${escapeHtml(item.item_condition)}</p>
          <p class="price">₹${item.price}</p>
          <a href="/item/${item.id}">View Details</a>
        </article>
      `;
    }).join("");
  } catch (error) {
    itemsContainer.innerHTML =
      "<p>Could not load items. Ensure the backend is running.</p>";
    console.error("Could not load items:", error);
  }
}

if (searchButton) {
  searchButton.addEventListener("click", loadItems);
}

if (categoryFilter) {
  categoryFilter.addEventListener("change", loadItems);
}

loadItems();