const itemsContainer = document.getElementById("itemsContainer");
const userId = localStorage.getItem("userId");

if (!userId) {
  window.location.href = "/login";
}

async function loadMyItems() {
  const response = await fetch(`/api/users/${userId}/items`);
  const items = await response.json();

  if (items.length === 0) {
    itemsContainer.innerHTML = `
      <div class="empty-state">
        <span class="emoji">📦</span>
        <h3>Nothing posted yet</h3>
        <p>List your first item and reach students across campus.</p>
        <a class="btn btn-sm" href="/add-item">Post an item</a>
      </div>`;
    return;
  }

  itemsContainer.innerHTML = items.map(item => {
    const image = item.image_path
      ? `<img class="item-image" src="${escapeHtml(item.image_path)}" alt="${escapeHtml(item.title)}" loading="lazy">`
      : `<div class="no-image">No image available</div>`;
    const sold = item.status !== "available";

    return `
      <article class="item-card">
        <div class="card-media">
          ${image}
          <span class="badge ${sold ? "sold" : "available"}">${escapeHtml(item.status)}</span>
        </div>
        <div class="card-body">
          <p class="category">${escapeHtml(item.category)} · ${escapeHtml(item.item_condition)}</p>
          <h3>${escapeHtml(item.title)}</h3>
          <p class="card-desc">${escapeHtml(item.description)}</p>
          <div class="card-footer">
            <span class="price">₹${escapeHtml(item.price)}</span>
            <a class="btn btn-ghost btn-sm" href="/item/${item.id}">View</a>
          </div>
          <div class="card-actions">
            <a class="btn btn-ghost btn-sm" href="/edit-item/${item.id}">Edit</a>
            ${!sold ? `<button class="btn-success btn-sm" onclick="markAsSold(${item.id})">Mark as sold</button>` : ""}
            <button class="btn-danger btn-sm" onclick="deleteItem(${item.id})">Delete</button>
          </div>
        </div>
      </article>
    `;
  }).join("");
}

async function markAsSold(itemId) {
  const response = await fetch(`/api/items/${itemId}/sold`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      seller_id: Number(userId)
    })
  });

  if (response.ok) {
    loadMyItems();
  }
}

async function deleteItem(itemId) {
  const shouldDelete = confirm("Are you sure you want to delete this item?");

  if (!shouldDelete) {
    return;
  }

  const response = await fetch(`/api/items/${itemId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      seller_id: Number(userId)
    })
  });

  const result = await response.json();

  if (response.ok) {
    loadMyItems();
  } else {
    alert(result.error || "Could not delete item.");
  }
}

loadMyItems();
