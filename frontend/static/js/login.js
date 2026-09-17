const form = document.getElementById("loginForm");
const message = document.getElementById("message");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const data = {
    email: document.getElementById("email").value,
    password: document.getElementById("password").value
  };

  const response = await fetch("/api/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(data)
  });

  const result = await response.json();

  if (response.ok) {
    localStorage.setItem("userId", result.user.id);
    localStorage.setItem("userName", result.user.name);

    message.textContent = "Login successful!";
    window.location.href = "/";
  } else {
    message.textContent = result.error || "Login failed.";
  }
});