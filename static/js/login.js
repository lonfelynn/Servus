const form      = document.getElementById("login-form");
const errorMsg  = document.getElementById("error-msg");
const submitBtn = document.getElementById("submit-btn");

form.addEventListener("submit", async function(event) {
  // Verhindert das normale Absenden des Formulars (kein Neuladen)
  event.preventDefault();

  // Button deaktivieren damit man nicht doppelt klickt
  submitBtn.disabled = true;
  submitBtn.textContent = "Wird geladen...";
  errorMsg.classList.add("hidden");

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  // Daten als JSON ans Backend schicken
  const response = await fetch("/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password })
  });

  const data = await response.json();

  if (data.ok) {
    // Erfolg → zur Zielseite weiterleiten
    window.location.href = data.redirect;
  } else {
    // Fehler → Meldung anzeigen
    errorMsg.textContent = data.error;
    errorMsg.classList.remove("hidden");
    submitBtn.disabled = false;
    submitBtn.textContent = "Anmelden";
  }
});
