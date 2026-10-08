const itemContainer = document.getElementById("itemContainer");
const itemId = window.location.pathname.split("/").pop();

async function loadItemDetails() {
  const response = await fetch(`/api/items/${itemId}`);

  if (!response.ok) {
    itemContainer.innerHTML = "<p>Item not found.</p>";
    return;
  }

  const item = await response.json();

  const image = item.image_path
    ? `<img class="item-image" src="${item.image_path}" alt="${item.title}">`
    : `<div class="no-image">No image available</div>`;

  itemContainer.innerHTML = `
    ${image}
    <p class="category">${item.category}</p>
    <h2>${item.title}</h2>
    <p>${item.description}</p>
    <p><strong>Condition:</strong> ${item.item_condition}</p>
    <p class="price">₹${item.price}</p>
    <hr>
    <h3>Seller Details</h3>
    <p><strong>Name:</strong> ${item.seller_name}</p>
    <p><strong>Email:</strong> ${item.seller_email}</p>
  `;
}

loadItemDetails();