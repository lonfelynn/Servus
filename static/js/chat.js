// ── Vom Server eingesetzte Werte (siehe chat.html) ────────
const ME = window.SERVUS.me;
const MY_NAME = window.SERVUS.myName;

const socket = io();

let activePeerId = null;
let activePeerName = "";

const userListEl   = document.getElementById("user-list");
const messagesEl   = document.getElementById("messages");
const placeholder  = document.getElementById("chat-placeholder");
const chatView     = document.getElementById("chat-view");
const peerNameEl   = document.getElementById("peer-name");
const peerAvatarEl = document.getElementById("peer-avatar");
const msgInput     = document.getElementById("msg-input");
const sendBtn      = document.getElementById("send-btn");

// ── Eigenes Profil anzeigen ───────────────────────────────
document.getElementById("me-name").textContent = MY_NAME;
document.getElementById("me-avatar").textContent = MY_NAME.charAt(0);

async function loadMe() {
  const res = await fetch("/api/me");
  const me = await res.json();
  document.getElementById("me-level").textContent =
    `Level ${me.level} · ${me.xp} XP`;
}

// ── Kontaktliste laden ────────────────────────────────────
async function loadUsers() {
  const res = await fetch("/api/users");
  const users = await res.json();

  if (users.length === 0) {
    userListEl.innerHTML = users.map(u => `
  <div class="user-item" data-id="${u.id}" data-name="${escapeHtml(u.username)}">
    <div class="avatar">${escapeHtml(u.username.charAt(0))}</div>
    <div class="user-info">
      <div class="user-name">${escapeHtml(u.username)}</div>
      <div class="user-sub">Level ${u.level}</div>
    </div>
    <div class="notif-badge hidden" id="badge-${u.id}"></div>
  </div>
`).join("");
    return;
  }

  userListEl.innerHTML = users.map(u => `
    <div class="user-item" data-id="${u.id}" data-name="${escapeHtml(u.username)}">
      <div class="avatar">${escapeHtml(u.username.charAt(0))}</div>
      <div class="user-info">
        <div class="user-name">${escapeHtml(u.username)}</div>
        <div class="user-sub">Level ${u.level}</div>
      </div>
    </div>
  `).join("");

  userListEl.querySelectorAll(".user-item").forEach(item => {
    item.addEventListener("click", () => {
      selectPeer(Number(item.dataset.id), item.dataset.name, item);
    });
  });
}

// ── Kontakt auswählen ─────────────────────────────────────
async function selectPeer(peerId, peerName, itemEl) {
  activePeerId = peerId;
  activePeerName = peerName;

  userListEl.querySelectorAll(".user-item")
    .forEach(el => el.classList.remove("active"));
  if (itemEl) itemEl.classList.add("active");

  placeholder.classList.add("hidden");
  chatView.classList.remove("hidden");
  peerNameEl.textContent = peerName;
  peerAvatarEl.textContent = peerName.charAt(0);

  const res = await fetch(`/api/messages/${peerId}`);
  const messages = await res.json();
  messagesEl.innerHTML = "";
  messages.forEach(renderMessage);
  scrollToBottom();
  msgInput.focus();
  markNotificationsRead(peerId);
}

// ── Eine Nachricht rendern ────────────────────────────────
function renderMessage(msg) {
  const mine = msg.sender_id === ME;
  const row = document.createElement("div");
  row.className = `row ${mine ? "sent" : "received"}`;
  row.innerHTML = `
    <div class="bubble">${escapeHtml(msg.content)}</div>
    <div class="time">${formatTime(msg.sent_at)}</div>
  `;
  messagesEl.appendChild(row);
}

// ── Nachricht senden ──────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || activePeerId === null) return;
  socket.emit("send_message", { to: activePeerId, content: text });
  msgInput.value = "";
  msgInput.style.height = "auto";
  msgInput.focus();
}

sendBtn.addEventListener("click", sendMessage);

msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Textarea mitwachsen lassen
msgInput.addEventListener("input", () => {
  msgInput.style.height = "auto";
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + "px";
});

// ── Eingehende Nachrichten (Echtzeit) ─────────────────────
socket.on("new_message", (msg) => {
  const peerId = msg.sender_id === ME ? msg.receiver_id : msg.sender_id;
  if (peerId === activePeerId) {
    renderMessage(msg);
    scrollToBottom();
  }
  // XP/Level aktualisieren, wenn ich gesendet habe
  if (msg.sender_id === ME) loadMe();
});

// ── Abmelden ──────────────────────────────────────────────
document.getElementById("logout-btn").addEventListener("click", async () => {
  const res = await fetch("/logout");
  const data = await res.json();
  window.location.href = data.redirect || "/login";
});

// ── Hilfsfunktionen ───────────────────────────────────────
function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

// ════════════════════════════════════════════════════════════
// ── Benachrichtigungssystem ───────────────────────────────
// ════════════════════════════════════════════════════════════

// sender_id → Anzahl ungelesener Benachrichtigungen
const unreadCounts = {};

async function loadNotifications() {
  try {
    const res = await fetch("/api/notifications");
    if (!res.ok) return;
    const notifs = await res.json();

    notifs.forEach(n => {
      unreadCounts[n.sender_id] = (unreadCounts[n.sender_id] || 0) + 1;
    });

    Object.entries(unreadCounts).forEach(([id, count]) => {
      updateUserBadge(Number(id), count);
    });

    updateContactsTitle();
  } catch (_) {
    // Benachrichtigungen sind nicht kritisch — stummes Fehlschlagen
  }
}

function updateUserBadge(senderId, count) {
  const badge = document.getElementById(`badge-${senderId}`);
  if (!badge) return;

  if (count > 0) {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }

  updateContactsTitle();
}

function updateContactsTitle() {
  const total = Object.values(unreadCounts).reduce((sum, n) => sum + n, 0);
  const titleEl = document.querySelector(".list-title");
  if (titleEl) {
    titleEl.textContent = total > 0 ? `Kontakte (${total})` : "Kontakte";
  }
}

async function markNotificationsRead(peerId) {
  if (!unreadCounts[peerId]) return;

  try {
    await fetch(`/api/notifications/read-by-sender/${peerId}`, { method: "POST" });
  } catch (_) {
    // Stummes Fehlschlagen — Badge wird trotzdem lokal entfernt
  }

  delete unreadCounts[peerId];
  updateUserBadge(peerId, 0);
}

function flashUserItem(senderId) {
  const item = document.querySelector(`.user-item[data-id="${senderId}"]`);
  if (!item) return;
  item.classList.add("notif-flash");
  setTimeout(() => item.classList.remove("notif-flash"), 600);
}

socket.on("notification", (notif) => {
  if (notif.sender_id === activePeerId) {
    // Chat mit Absender ist offen → sofort als gelesen markieren
    markNotificationsRead(notif.sender_id);
  } else {
    // Chat geschlossen → Badge erhöhen + Item aufleuchten lassen
    unreadCounts[notif.sender_id] = (unreadCounts[notif.sender_id] || 0) + 1;
    updateUserBadge(notif.sender_id, unreadCounts[notif.sender_id]);
    flashUserItem(notif.sender_id);
  }
});

// ── Start ─────────────────────────────────────────────────
// loadUsers() muss awaited werden, damit die Badge-Elemente im DOM
// existieren, bevor loadNotifications() sie befüllt.
async function init() {
  loadMe();
  await loadUsers();
  loadNotifications();
}

init();
