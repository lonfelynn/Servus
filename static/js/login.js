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
    // Der Login ist der einzige Moment, in dem der Browser das Passwort hat —
    // also hier den privaten E2EE-Schlüssel anlegen (erster Login) bzw.
    // entpacken und lokal ablegen. Danach ist das Passwort wieder weg.
    try {
      await E2EE.unlock(data.user_id, password);
    } catch (err) {
      errorMsg.textContent = E2EE.available
        ? "Verschlüsselung konnte nicht eingerichtet werden. Bitte erneut versuchen."
        : "Verschlüsselung braucht HTTPS (oder localhost). Bitte über eine sichere Verbindung anmelden.";
      errorMsg.classList.remove("hidden");
      submitBtn.disabled = false;
      submitBtn.textContent = "Anmelden";
      return;
    }
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
