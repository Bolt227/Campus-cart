const itemsContainer = document.getElementById("itemsContainer");
const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");
const searchButton = document.getElementById("searchButton");

function escapeHtml(text) {
  const element = document.createElement("div");
  element.textContent = text;
  return element.innerHTML;
}

async function loadItems() {
  const search = searchInput.value.trim();
  const category = categoryFilter.value;

  const parameters = new URLSearchParams();

  if (search) parameters.append("search", search);
  if (category) parameters.append("category", category);

  itemsContainer.innerHTML = "<p>Loading items...</p>";

  try {
    const response = await fetch(`/api/items?${parameters}`);
    const items = await response.json();

    if (items.length === 0) {
      itemsContainer.innerHTML = "<p>No available items found.</p>";
      return;
    }

    itemsContainer.innerHTML = items.map(item => `
      <article class="item-card">
        <p class="category">${escapeHtml(item.category)}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.description)}</p>
        <p>Condition: ${escapeHtml(item.item_condition)}</p>
        <p class="price">₹${item.price}</p>
        <a href="/item/${item.id}">View Details</a>
      </article>
    `).join("");

  } catch (error) {
    itemsContainer.innerHTML = "<p>Could not load items. Ensure the backend is running.</p>";
  }
}

searchButton.addEventListener("click", loadItems);
categoryFilter.addEventListener("change", loadItems);

loadItems();