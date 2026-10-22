const form = document.getElementById("addItemForm");
const message = document.getElementById("message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector("button[type='submit']");
  message.classList.remove("ok");
  message.textContent = "";
  if (submitButton) submitButton.disabled = true;

  // The server knows who is logged in from the session cookie.
  const formData = new FormData();

  formData.append("title", document.getElementById("title").value);
  formData.append("description", document.getElementById("description").value);
  formData.append("category", document.getElementById("category").value);
  formData.append("item_condition", document.getElementById("itemCondition").value);
  formData.append("price", document.getElementById("price").value);

  const image = document.getElementById("image").files[0];
  if (image) {
    formData.append("image", image);
  }

  try {
    const response = await fetch("/api/items", {
      method: "POST",
      credentials: "same-origin",
      body: formData
    });

    if (response.status === 401) {
      message.textContent = "Please log in before posting an item.";
      setTimeout(redirectToLogin, 1200);
      return;
    }

    const result = await response.json().catch(() => ({}));

    if (response.ok) {
      message.textContent = "Item posted successfully!";
      message.classList.add("ok");
      form.reset();

      setTimeout(() => {
        window.location.href = "/";
      }, 1000);
    } else {
      message.textContent = result.error || "Could not post item.";
      if (submitButton) submitButton.disabled = false;
    }
  } catch (error) {
    console.error("Post item error:", error);
    message.textContent = "Could not reach the server. Please try again.";
    if (submitButton) submitButton.disabled = false;
  }
});
