const itemsContainer = document.getElementById("itemsContainer");
const searchInput = document.getElementById("searchInput");
const categoryFilter = document.getElementById("categoryFilter");
const searchButton = document.getElementById("searchButton");

function renderItemCard(item) {
  const image = item.image_path
    ? `<img class="item-image" src="${escapeHtml(item.image_path)}" alt="${escapeHtml(item.title)}" loading="lazy">`
    : `<div class="no-image">No image available</div>`;

  return `
    <article class="item-card">
      <div class="card-media">
        ${image}
        <span class="badge condition">${escapeHtml(item.item_condition)}</span>
      </div>
      <div class="card-body">
        <p class="category">${escapeHtml(item.category)}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="card-desc">${escapeHtml(item.description)}</p>
        <div class="card-footer">
          <span class="price">₹${escapeHtml(item.price)}</span>
          <a class="btn btn-sm" href="/item/${item.id}">View Details</a>
        </div>
      </div>
    </article>
  `;
}

async function loadItems() {
  if (!itemsContainer || !searchInput || !categoryFilter) return;

  const search = searchInput.value.trim();
  const category = categoryFilter.value;
  const parameters = new URLSearchParams();

  if (search) parameters.append("search", search);
  if (category) parameters.append("category", category);

  itemsContainer.innerHTML = '<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>';

  try {
    const response = await fetch(`/api/items?${parameters}`);

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const items = await response.json();

    if (items.length === 0) {
      itemsContainer.innerHTML = `<div class="empty-state"><span class="emoji">🔍</span><h3>No items found</h3><p>Try a different search or category.</p></div>`;
      return;
    }

    itemsContainer.innerHTML = items.map(renderItemCard).join("");
  } catch (error) {
    itemsContainer.innerHTML =
      `<div class="empty-state"><span class="emoji">⚠️</span><h3>Could not load items</h3><p>Make sure the backend is running.</p></div>`;
    console.error("Could not load items:", error);
  }
}

if (searchButton) {
  searchButton.addEventListener("click", loadItems);
}

if (searchInput) {
  searchInput.addEventListener("keydown", event => {
    if (event.key === "Enter") loadItems();
  });
}

if (categoryFilter) {
  categoryFilter.addEventListener("change", loadItems);
}

loadItems();
