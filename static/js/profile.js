// profile.js – Profil- und Einstellungs-Modal-Verwaltung

// Profil-Modal
const profileModal        = document.getElementById("profile-modal");
const profileAvatarEl     = document.getElementById("profile-avatar");
const profileStatusInput  = document.getElementById("profile-status-input");
const profilePresenceInput = document.getElementById("profile-presence-input");
const uploadAvatarBtn     = document.getElementById("upload-avatar-btn");
const profileImageInput   = document.getElementById("profile-image-input");
const profileSaveBtn      = document.getElementById("profile-save-btn");
const profileCancelBtn    = document.getElementById("profile-cancel-btn");
const meAvatarEl          = document.getElementById("me-avatar");

// Einstellungs-Modal
const settingsModal       = document.getElementById("settings-modal");
const themeSelect         = document.getElementById("theme-select");
const accentColorPicker   = document.getElementById("accent-color-picker");
const settingsCloseBtn    = document.getElementById("settings-close-btn");
const settingsBtn         = document.getElementById("settings-btn");
const themeCards          = document.getElementById("theme-cards");
const accentSwatches      = document.getElementById("accent-swatches");
const modeSection         = document.getElementById("mode-section");
const accentSection       = document.getElementById("accent-section");
const settingsLockedNote  = document.getElementById("settings-locked-note");
const themeCardNormal     = document.getElementById("theme-card-normal");
const themeNormalLock     = document.getElementById("theme-normal-lock");
const themeNormalPrice    = document.getElementById("theme-normal-price");
const themeUnlockBox      = document.getElementById("theme-unlock-box");
const themeUnlockBtn      = document.getElementById("theme-unlock-btn");
const themeUnlockCostEl   = document.getElementById("theme-unlock-cost");

// Zwischengespeicherte Profildaten
let profileData = {
  avatar_url: null,
  status_text: "",
  presence: "online",
};

// Profildaten vom Server laden
async function loadProfileData() {
  try {
    const res = await fetch("/api/me");
    const data = await res.json();
    profileData = {
      avatar_url: data.avatar_url || null,
      status_text: data.status_text || "",
      presence: data.presence || "online",
    };
    updateProfileUI();
    // Server ist die verbindliche Quelle für App-Theme + Freischaltung.
    if (typeof syncThemeState === "function") syncThemeState(data);
    refreshSettingsUI();
  } catch (e) {
    console.error("Profildaten konnten nicht geladen werden:", e);
  }
}

function updateProfileUI() {
  profileStatusInput.value = profileData.status_text;
  profilePresenceInput.value = profileData.presence;

  if (profileData.avatar_url) {
    profileAvatarEl.style.backgroundImage = `url(${profileData.avatar_url})`;
    profileAvatarEl.style.backgroundSize = "cover";
    profileAvatarEl.textContent = "";
    meAvatarEl.style.backgroundImage = `url(${profileData.avatar_url})`;
    meAvatarEl.style.backgroundSize = "cover";
    meAvatarEl.textContent = "";
  } else {
    profileAvatarEl.style.backgroundImage = "";
    profileAvatarEl.textContent = window.SERVUS.myName.charAt(0);
    meAvatarEl.style.backgroundImage = "";
    meAvatarEl.textContent = window.SERVUS.myName.charAt(0);
  }
}

// Profil-Modal öffnen
function openProfileModal() {
  loadProfileData();
  updateProfileUI();
  profileModal.classList.remove("hidden");
}

// Profil-Modal schließen
function closeProfileModal() {
  profileModal.classList.add("hidden");
}

// Avatar hochladen
uploadAvatarBtn.addEventListener("click", () => {
  profileImageInput.click();
});

profileImageInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;

  // Das Bild wird als Data-URL gespeichert (kein Cloud-Storage im Schulprojekt).
  const reader = new FileReader();
  reader.onload = (event) => {
    profileData.avatar_url = event.target.result;
    updateProfileUI();
  };
  reader.readAsDataURL(file);
});

// Profil speichern
profileSaveBtn.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status_text: profileStatusInput.value.trim(),
        presence: profilePresenceInput.value,
        avatar_url: profileData.avatar_url,
      }),
    });

    if (res.ok) {
      closeProfileModal();
      loadProfileData();
    } else {
      alert("Fehler beim Speichern des Profils");
    }
  } catch (e) {
    console.error("Profil konnte nicht gespeichert werden:", e);
    alert("Fehler beim Speichern des Profils");
  }
});

profileCancelBtn.addEventListener("click", closeProfileModal);

// Klick auf den eigenen Avatar öffnet das Profil-Modal
meAvatarEl.addEventListener("click", openProfileModal);

// ── Einstellungs-Modal ──────────────────────────────────────
// Spiegelt die aktuelle Auswahl (Karten, Swatches) und schaltet Modus/Akzent
// aus, wenn ein Theme mit festem Farbschema (z.B. Söder) aktiv ist.
function refreshSettingsUI() {
  const appTheme = localStorage.getItem('servus-app-theme') || 'soeder';
  const mode     = localStorage.getItem('servus-theme')     || 'dark';
  const accent   = localStorage.getItem('servus-accent')    || '#5c6fff';
  const unlocked = isThemeUnlocked();
  const cost     = getThemeUnlockCost();

  // Theme-Karten markieren
  themeCards.querySelectorAll(".theme-card").forEach(card => {
    card.classList.toggle("selected", card.dataset.appTheme === appTheme);
  });

  // Normal-Theme sperren, bis freigekauft. Freikauf-Box entsprechend zeigen.
  themeCardNormal.classList.toggle("locked", !unlocked);
  themeNormalLock.classList.toggle("hidden", unlocked);
  themeUnlockBox.classList.toggle("hidden", unlocked);
  themeNormalPrice.textContent = cost + " Level";
  themeUnlockCostEl.textContent = cost + " Level";

  // Modus-Dropdown
  themeSelect.value = mode;

  // Akzent-Swatches + Custom-Picker
  accentColorPicker.value = accent;
  let matched = false;
  accentSwatches.querySelectorAll(".accent-swatch[data-color]").forEach(sw => {
    const on = sw.dataset.color.toLowerCase() === accent.toLowerCase();
    sw.classList.toggle("selected", on);
    if (on) matched = true;
  });
  // Eigene Farbe hervorheben, wenn sie keinem Preset entspricht.
  const custom = accentSwatches.querySelector(".accent-custom");
  custom.classList.toggle("selected", !matched);
  custom.style.setProperty("--sw", accent);

  // Bei festen Themes (Söder) Modus + Akzent deaktivieren.
  const locked = appTheme !== 'normal';
  modeSection.classList.toggle("section-disabled", locked);
  accentSection.classList.toggle("section-disabled", locked);
  settingsLockedNote.classList.toggle("hidden", !locked);
}

function openSettingsModal() {
  refreshSettingsUI();
  settingsModal.classList.remove("hidden");
}

function closeSettingsModal() {
  settingsModal.classList.add("hidden");
}

// App-Theme serverseitig merken (verbindliche Quelle, geräteübergreifend).
async function persistAppTheme(theme) {
  try {
    const res = await fetch("/api/theme", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme }),
    });
    return await res.json();
  } catch (_) {
    return { ok: false };
  }
}

// Theme-Karte wählen (Söder / Normal). Normal ist nur nach Freikauf möglich.
themeCards.addEventListener("click", async (e) => {
  const card = e.target.closest(".theme-card");
  if (!card) return;
  const theme = card.dataset.appTheme;

  if (theme === "normal" && !isThemeUnlocked()) {
    // Gesperrt → auf die Freikauf-Box aufmerksam machen statt zu wechseln.
    themeUnlockBox.classList.remove("hidden");
    themeUnlockBox.classList.add("nudge");
    setTimeout(() => themeUnlockBox.classList.remove("nudge"), 600);
    return;
  }

  applyAppTheme(theme);      // sofort visuell umschalten
  refreshSettingsUI();
  const res = await persistAppTheme(theme);
  if (!res.ok) {             // serverseitig doch gesperrt → zurück auf Söder
    applyAppTheme("soeder");
    refreshSettingsUI();
    alert(res.error || "Theme konnte nicht gesetzt werden.");
  }
});

// „Freikaufen": kostet Level, schaltet das Umschalten dauerhaft frei.
themeUnlockBtn.addEventListener("click", async () => {
  themeUnlockBtn.disabled = true;
  const original = themeUnlockBtn.textContent;
  themeUnlockBtn.textContent = "Wird freigeschaltet…";
  try {
    const res = await fetch("/api/theme/unlock", { method: "POST" });
    const data = await res.json();
    if (!data.ok) {
      alert(data.error || "Freikauf nicht möglich.");
      return;
    }
    // Dauerhaft freigeschaltet: Status cachen, auf Normal wechseln.
    localStorage.setItem("servus-theme-unlocked", "1");
    applyAppTheme("normal");
    if (typeof loadMe === "function") loadMe();   // Level/XP-Anzeige aktualisieren
    refreshSettingsUI();
  } finally {
    themeUnlockBtn.disabled = false;
    themeUnlockBtn.textContent = original;
  }
});

// Erscheinungsbild (Hell/Dunkel) wechseln
themeSelect.addEventListener("change", (e) => {
  applyTheme(e.target.value);
});

// Akzentfarbe über ein Preset-Swatch wählen
accentSwatches.addEventListener("click", (e) => {
  const sw = e.target.closest(".accent-swatch[data-color]");
  if (!sw) return;
  applyAccent(sw.dataset.color);
  refreshSettingsUI();
});

// Akzentfarbe frei wählen
accentColorPicker.addEventListener("input", (e) => {
  applyAccent(e.target.value);
  refreshSettingsUI();
});

settingsBtn.addEventListener("click", openSettingsModal);
settingsCloseBtn.addEventListener("click", closeSettingsModal);

// Modals schließen bei Klick auf den Hintergrund
profileModal.addEventListener("click", (e) => {
  if (e.target === profileModal) closeProfileModal();
});

settingsModal.addEventListener("click", (e) => {
  if (e.target === settingsModal) closeSettingsModal();
});

// Profil beim Start laden
loadProfileData();
