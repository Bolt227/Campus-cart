const form = document.getElementById("editItemForm");
const message = document.getElementById("message");

const userId = localStorage.getItem("userId");
const itemId = window.location.pathname.split("/").filter(Boolean).pop();

if (!userId) {
  redirectToLogin();
}

async function loadItem() {
  try {
    const response = await fetch(`/api/items/${encodeURIComponent(itemId)}`, {
      credentials: "same-origin"
    });

    if (!response.ok) {
      message.textContent = "Item not found.";
      form.querySelector("button[type='submit']").disabled = true;
      return;
    }

    const item = await response.json();

    if (Number(item.seller_id) !== Number(userId)) {
      message.textContent = "You can edit only your own items.";
      form.querySelector("button[type='submit']").disabled = true;
      return;
    }

    document.getElementById("title").value = item.title;
    document.getElementById("description").value = item.description;
    document.getElementById("category").value = item.category;
    document.getElementById("itemCondition").value = item.item_condition;
    document.getElementById("price").value = item.price;
  } catch (error) {
    console.error("Could not load item:", error);
    message.textContent = "Could not load the item. Please try again.";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector("button[type='submit']");
  message.classList.remove("ok");
  message.textContent = "";
  if (submitButton) submitButton.disabled = true;

  // The server checks ownership from the session, not from the request body.
  const data = {
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    category: document.getElementById("category").value,
    item_condition: document.getElementById("itemCondition").value,
    price: document.getElementById("price").value
  };

  try {
    const response = await fetch(`/api/items/${encodeURIComponent(itemId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(data)
    });

    if (response.status === 401) {
      redirectToLogin();
      return;
    }

    const result = await response.json().catch(() => ({}));

    if (response.ok) {
      message.textContent = "Item updated successfully!";
      message.classList.add("ok");

      setTimeout(() => {
        window.location.href = "/my-listings";
      }, 1000);
    } else {
      message.textContent = result.error || "Could not update item.";
      if (submitButton) submitButton.disabled = false;
    }
  } catch (error) {
    console.error("Update item error:", error);
    message.textContent = "Could not reach the server. Please try again.";
    if (submitButton) submitButton.disabled = false;
  }
});

loadItem();
