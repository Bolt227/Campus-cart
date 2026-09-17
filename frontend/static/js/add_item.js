const form = document.getElementById("addItemForm");
const message = document.getElementById("message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const item = {
    title: document.getElementById("title").value,
    description: document.getElementById("description").value,
    category: document.getElementById("category").value,
    item_condition: document.getElementById("itemCondition").value,
    price: document.getElementById("price").value,
    seller_id: 1
  };

  const response = await fetch("/api/items", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(item)
  });

  const result = await response.json();

  if (response.ok) {
    message.textContent = "Item posted successfully!";
    form.reset();

    setTimeout(() => {
      window.location.href = "/";
    }, 1000);
  } else {
    message.textContent = result.error || "Could not post item.";
  }
});