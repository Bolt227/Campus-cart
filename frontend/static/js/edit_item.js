const form = document.getElementById("editItemForm");
const message = document.getElementById("message");

const userId = localStorage.getItem("userId");
const itemId = window.location.pathname.split("/").pop();

if (!userId) {
  window.location.href = "/login";
}

async function loadItem() {
  const response = await fetch(`/api/items/${itemId}`);

  if (!response.ok) {
    message.textContent = "Item not found.";
    return;
  }

  const item = await response.json();

  if (Number(item.seller_id) !== Number(userId)) {
    message.textContent = "You can edit only your own items.";
    return;
  }

  document.getElementById("title").value = item.title;
  document.getElementById("description").value = item.description;
  document.getElementById("category").value = item.category;
  document.getElementById("itemCondition").value = item.item_condition;
  document.getElementById("price").value = item.price;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const data = {
    seller_id: Number(userId),
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    category: document.getElementById("category").value,
    item_condition: document.getElementById("itemCondition").value,
    price: document.getElementById("price").value
  };

  const response = await fetch(`/api/items/${itemId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  });

  const result = await response.json();

  if (response.ok) {
    message.textContent = "Item updated successfully!";
    message.classList.add("ok");

    setTimeout(() => {
      window.location.href = "/my-listings";
    }, 1000);
  } else {
    message.textContent = result.error || "Could not update item.";
  }
});

loadItem();