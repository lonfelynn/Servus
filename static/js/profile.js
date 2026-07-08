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
const accentPreview       = document.getElementById("accent-preview");
const settingsCloseBtn    = document.getElementById("settings-close-btn");
const settingsBtn         = document.getElementById("settings-btn");

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
function openSettingsModal() {
  const currentTheme  = localStorage.getItem('servus-theme')  || 'dark';
  const currentAccent = localStorage.getItem('servus-accent') || '#5c6fff';

  themeSelect.value = currentTheme;
  accentColorPicker.value = currentAccent;
  accentPreview.style.backgroundColor = currentAccent;

  settingsModal.classList.remove("hidden");
}

function closeSettingsModal() {
  settingsModal.classList.add("hidden");
}

// Theme wechseln
themeSelect.addEventListener("change", (e) => {
  applyTheme(e.target.value);
});

// Akzentfarbe wechseln
accentColorPicker.addEventListener("input", (e) => {
  const color = e.target.value;
  applyAccent(color);
  accentPreview.style.backgroundColor = color;
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
