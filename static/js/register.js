const form      = document.getElementById("register-form");
const errorMsg  = document.getElementById("error-msg");
const submitBtn = document.getElementById("submit-btn");

form.addEventListener("submit", async function(event) {
  event.preventDefault();

  submitBtn.disabled = true;
  submitBtn.textContent = "Wird geladen...";
  errorMsg.classList.add("hidden");

  const username         = document.getElementById("username").value;
  const password         = document.getElementById("password").value;
  const confirm_password = document.getElementById("confirm_password").value;

  const response = await fetch("/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, confirm_password })
  });

  const data = await response.json();

  if (data.ok) {
    window.location.href = data.redirect;
  } else {
    errorMsg.textContent = data.error;
    errorMsg.classList.remove("hidden");
    submitBtn.disabled = false;
    submitBtn.textContent = "Konto erstellen";
  }
});
