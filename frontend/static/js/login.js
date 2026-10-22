const form = document.getElementById("loginForm");
const message = document.getElementById("message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector("button[type='submit']");
  message.classList.remove("ok");
  message.textContent = "";
  if (submitButton) submitButton.disabled = true;

  const data = {
    email: document.getElementById("email").value,
    password: document.getElementById("password").value
  };

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(data)
    });

    const result = await response.json().catch(() => ({}));

    if (response.ok) {
      localStorage.setItem("userId", result.user.id);
      localStorage.setItem("userName", result.user.name);

      message.textContent = "Login successful!";
      message.classList.add("ok");
      window.location.href = "/";
    } else {
      message.textContent = result.error || "Login failed.";
      if (submitButton) submitButton.disabled = false;
    }
  } catch (error) {
    console.error("Login error:", error);
    message.textContent = "Could not reach the server. Please try again.";
    if (submitButton) submitButton.disabled = false;
  }
});
