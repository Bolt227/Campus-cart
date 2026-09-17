const itemsContainer = document.getElementById("itemsContainer");
const userId = localStorage.getItem("userId");

if (!userId) {
  window.location.href = "/login";
}

async function loadMyItems() {
  const response = await fetch(`/api/users/${userId}/items`);
  const items = await response.json();

  if (items.length === 0) {
    itemsContainer.innerHTML = "<p>You have not posted any items yet.</p>";
    return;
  }

  itemsContainer.innerHTML = items.map(item => `
    <article class="item-card">
      <p class="category">${item.category}</p>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
      <p>Condition: ${item.item_condition}</p>
      <p class="price">₹${item.price}</p>
      <p>Status: <strong>${item.status}</strong></p>

      ${item.status === "available"
        ? `<button onclick="markAsSold(${item.id})">Mark as Sold</button>`
        : ""}
    </article>
  `).join("");
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

loadMyItems();