const form = document.getElementById("registerForm");
const message = document.getElementById("message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const submitButton = form.querySelector("button[type='submit']");
  message.classList.remove("ok");
  message.textContent = "";
  if (submitButton) submitButton.disabled = true;

  const data = {
    name: document.getElementById("name").value,
    email: document.getElementById("email").value,
    password: document.getElementById("password").value
  };

  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(data)
    });

    const result = await response.json().catch(() => ({}));

    if (response.ok) {
      message.textContent = "Account created. Redirecting to login...";
      message.classList.add("ok");

      setTimeout(() => {
        window.location.href = "/login";
      }, 1000);
    } else {
      message.textContent = result.error || "Registration failed.";
      if (submitButton) submitButton.disabled = false;
    }
  } catch (error) {
    console.error("Registration error:", error);
    message.textContent = "Could not reach the server. Please try again.";
    if (submitButton) submitButton.disabled = false;
  }
});
