const itemsContainer = document.getElementById("itemsContainer");
const userId = localStorage.getItem("userId");

if (!userId) {
  redirectToLogin();
}

function renderListing(item) {
  const imageSrc = safeImageSrc(item.image_path);
  const image = imageSrc
    ? `<img class="item-image" src="${escapeHtml(imageSrc)}" alt="${escapeHtml(item.title)}" loading="lazy">`
    : `<div class="no-image">No image available</div>`;

  const status = String(item.status || "available").toLowerCase();
  const isAvailable = status === "available";
  const isPending = status === "pending";
  const badgeClass = isAvailable ? "available" : isPending ? "pending" : "sold";

  return `
    <article class="item-card">
      <div class="card-media">
        ${image}
        <span class="badge ${badgeClass}">${escapeHtml(status)}</span>
      </div>
      <div class="card-body">
        <p class="category">${escapeHtml(item.category)} · ${escapeHtml(item.item_condition)}</p>
        <h3>${escapeHtml(item.title)}</h3>
        <p class="card-desc">${escapeHtml(item.description)}</p>
        <div class="card-footer">
          <span class="price">₹${escapeHtml(item.price)}</span>
          <a class="btn btn-ghost btn-sm" href="/item/${Number(item.id)}">View</a>
        </div>
        <div class="card-actions">
          ${isPending
            ? `<span class="muted">Payment in progress</span>`
            : `<a class="btn btn-ghost btn-sm" href="/edit-item/${Number(item.id)}">Edit</a>
               ${isAvailable ? `<button class="btn-success btn-sm" onclick="markAsSold(${Number(item.id)})">Mark as sold</button>` : ""}
               <button class="btn-danger btn-sm" onclick="deleteItem(${Number(item.id)})">Delete</button>`}
        </div>
      </div>
    </article>
  `;
}

async function loadMyItems() {
  try {
    const response = await fetch(`/api/users/${encodeURIComponent(userId)}/items`, {
      credentials: "same-origin"
    });

    if (response.status === 401 || response.status === 403) {
      redirectToLogin();
      return;
    }

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

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

    itemsContainer.innerHTML = items.map(renderListing).join("");
  } catch (error) {
    console.error("Could not load listings:", error);
    itemsContainer.innerHTML = `
      <div class="empty-state">
        <span class="emoji">⚠️</span>
        <h3>Could not load your listings</h3>
        <p>Please refresh the page and try again.</p>
      </div>`;
  }
}

async function markAsSold(itemId) {
  try {
    const response = await fetch(`/api/items/${itemId}/sold`, {
      method: "PATCH",
      credentials: "same-origin"
    });

    if (response.status === 401) {
      redirectToLogin();
      return;
    }

    if (response.ok) {
      loadMyItems();
    } else {
      const result = await response.json().catch(() => ({}));
      alert(result.error || "Could not mark the item as sold.");
    }
  } catch (error) {
    console.error("Mark as sold error:", error);
    alert("Could not reach the server. Please try again.");
  }
}

async function deleteItem(itemId) {
  if (!confirm("Are you sure you want to delete this item?")) {
    return;
  }

  try {
    const response = await fetch(`/api/items/${itemId}`, {
      method: "DELETE",
      credentials: "same-origin"
    });

    if (response.status === 401) {
      redirectToLogin();
      return;
    }

    if (response.ok) {
      loadMyItems();
    } else {
      const result = await response.json().catch(() => ({}));
      alert(result.error || "Could not delete item.");
    }
  } catch (error) {
    console.error("Delete item error:", error);
    alert("Could not reach the server. Please try again.");
  }
}

loadMyItems();
