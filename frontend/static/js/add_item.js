const form = document.getElementById("addItemForm");
const message = document.getElementById("message");

const sellerId = localStorage.getItem("userId");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!sellerId) {
    message.textContent = "Please log in before posting an item.";
    setTimeout(() => {
      window.location.href = "/login";
    }, 1200);
    return;
  }

  const formData = new FormData();

  formData.append("title", document.getElementById("title").value);
  formData.append("description", document.getElementById("description").value);
  formData.append("category", document.getElementById("category").value);
  formData.append("item_condition", document.getElementById("itemCondition").value);
  formData.append("price", document.getElementById("price").value);
  formData.append("seller_id", sellerId);

  const image = document.getElementById("image").files[0];

  if (image) {
    formData.append("image", image);
  }

  const response = await fetch("/api/items", {
    method: "POST",
    body: formData
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