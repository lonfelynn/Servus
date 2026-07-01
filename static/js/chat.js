// ── Vom Server eingesetzte Werte (siehe chat.html) ────────
const ME = window.SERVUS.me;
const MY_NAME = window.SERVUS.myName;

const socket = io();

// Aktueller Chat + Caches
let activeChatId = null;
const chatsById = {};    // chat_id → Chat-Objekt (id, display_name, members, is_group)
let allUsers = [];       // alle anderen Nutzer (für Kontaktliste + Mitglieder-Picker)
const unreadByChat = {}; // chat_id → Anzahl ungelesener Nachrichten

const userListEl   = document.getElementById("user-list");
const chatListEl   = document.getElementById("chat-list");
const messagesEl   = document.getElementById("messages");
const placeholder  = document.getElementById("chat-placeholder");
const chatView     = document.getElementById("chat-view");
const peerNameEl   = document.getElementById("peer-name");
const peerSubEl    = document.getElementById("peer-sub");
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

// ── Kontaktliste laden (Einstieg für neue 1-zu-1-Chats) ───
async function loadUsers() {
  const res = await fetch("/api/users");
  allUsers = await res.json();

  userListEl.innerHTML = allUsers.map(u => `
    <div class="user-item" data-id="${u.id}">
      <div class="avatar">${escapeHtml(u.username.charAt(0))}</div>
      <div class="user-info">
        <div class="user-name">${escapeHtml(u.username)}</div>
        <div class="user-sub">Level ${u.level}</div>
      </div>
    </div>
  `).join("") || `<div class="empty-list">Keine weiteren Nutzer.</div>`;

  userListEl.querySelectorAll(".user-item").forEach(item => {
    item.addEventListener("click", () => startDirectChat(Number(item.dataset.id)));
  });
}

// ── Chat-Liste laden ──────────────────────────────────────
async function loadChats(selectId = null) {
  const res = await fetch("/api/chats");
  const chats = await res.json();

  for (const key in chatsById) delete chatsById[key];
  chats.forEach(c => { chatsById[c.id] = c; });

  if (chats.length === 0) {
    chatListEl.innerHTML = `<div class="empty-list">Noch keine Chats.</div>`;
  } else {
    chatListEl.innerHTML = chats.map(c => `
      <div class="user-item ${c.id === activeChatId ? "active" : ""}" data-id="${c.id}">
        <div class="avatar">${escapeHtml(c.display_name.charAt(0))}</div>
        <div class="user-info">
          <div class="user-name">${escapeHtml(c.display_name)}</div>
          <div class="user-sub">${c.is_group ? c.members.length + " Mitglieder" : "Direktnachricht"}</div>
        </div>
        <div class="notif-badge hidden" id="badge-${c.id}"></div>
      </div>
    `).join("");

    chatListEl.querySelectorAll(".user-item").forEach(item => {
      item.addEventListener("click", () => openChat(Number(item.dataset.id)));
    });
  }

  applyBadges();   // Badge-Elemente wurden neu gerendert → Zähler wieder setzen
  if (selectId !== null && chatsById[selectId]) openChat(selectId);
}

// ── Neuen 1-zu-1-Chat mit einem Nutzer starten ────────────
async function startDirectChat(userId) {
  const res = await fetch("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_ids: [userId] }),
  });
  const data = await res.json();
  if (!data.ok) return;
  socket.emit("join_chat", { chat_id: data.chat.id });
  await loadChats();
  openChat(data.chat.id);
}

// ── Chat öffnen ───────────────────────────────────────────
async function openChat(chatId) {
  const chat = chatsById[chatId];
  if (!chat) return;
  activeChatId = chatId;

  chatListEl.querySelectorAll(".user-item").forEach(el =>
    el.classList.toggle("active", Number(el.dataset.id) === chatId));

  placeholder.classList.add("hidden");
  chatView.classList.remove("hidden");
  peerNameEl.textContent = chat.display_name;
  peerAvatarEl.textContent = chat.display_name.charAt(0);
  peerSubEl.textContent = chat.is_group
    ? chat.members.map(m => m.username).join(", ")
    : "Direktnachricht";

  const res = await fetch(`/api/chats/${chatId}/messages`);
  const messages = await res.json();
  messagesEl.innerHTML = "";
  messages.forEach(renderMessage);
  scrollToBottom();
  msgInput.focus();

  markChatRead(chatId);
  if (window.showChatMobile) window.showChatMobile();
}

// ── Eine Nachricht rendern ────────────────────────────────
function renderMessage(msg) {
  const mine = msg.sender_id === ME;
  const chat = chatsById[msg.chat_id];
  const showSender = !mine && chat && chat.is_group;

  const row = document.createElement("div");
  row.className = `row ${mine ? "sent" : "received"}`;
  row.innerHTML = `
    ${showSender ? `<div class="sender">${escapeHtml(msg.sender_name || "")}</div>` : ""}
    <div class="bubble">${escapeHtml(msg.content)}</div>
    <div class="time">${formatTime(msg.sent_at)}</div>
  `;
  messagesEl.appendChild(row);
}

// ── Nachricht senden ──────────────────────────────────────
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || activeChatId === null) return;
  socket.emit("send_message", { chat_id: activeChatId, content: text });
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
  if (msg.chat_id === activeChatId) {
    renderMessage(msg);
    scrollToBottom();
    // Offener Chat → in DB als gelesen markieren (force, da der lokale Zähler
    // schon 0 ist, der Server aber trotzdem eine ungelesen-Zeile anlegt).
    if (msg.sender_id !== ME) markChatRead(msg.chat_id, true);
  } else if (msg.sender_id !== ME) {
    // Geschlossener Chat → ungelesen-Zähler erhöhen + Item aufleuchten.
    unreadByChat[msg.chat_id] = (unreadByChat[msg.chat_id] || 0) + 1;
    updateChatBadge(msg.chat_id);
    flashChatItem(msg.chat_id);
  }
  if (msg.sender_id === ME) loadMe();   // XP/Level aktualisieren
});

// ── Chat-Änderungen (erstellt / umbenannt / Mitglied dazu) ─
socket.on("chat_updated", async (data) => {
  socket.emit("join_chat", { chat_id: data.chat_id });
  await loadChats();
  if (data.chat_id === activeChatId) refreshActiveHeader();
});

socket.on("chat_removed", (data) => {
  socket.emit("leave_chat", { chat_id: data.chat_id });
  if (data.chat_id === activeChatId) {
    activeChatId = null;
    chatView.classList.add("hidden");
    placeholder.classList.remove("hidden");
  }
  loadChats();
});

function refreshActiveHeader() {
  const chat = chatsById[activeChatId];
  if (!chat) return;
  peerNameEl.textContent = chat.display_name;
  peerAvatarEl.textContent = chat.display_name.charAt(0);
  peerSubEl.textContent = chat.is_group
    ? chat.members.map(m => m.username).join(", ")
    : "Direktnachricht";
}

// ── Abmelden ──────────────────────────────────────────────
document.getElementById("logout-btn").addEventListener("click", async () => {
  const res = await fetch("/logout");
  const data = await res.json();
  window.location.href = data.redirect || "/login";
});

// ════════════════════════════════════════════════════════════
// ── Modal: Neue Gruppe ─────────────────────────────────────
// ════════════════════════════════════════════════════════════
const groupModal    = document.getElementById("group-modal");
const groupPicker   = document.getElementById("group-member-picker");
const groupNameIn   = document.getElementById("group-name-input");

document.getElementById("new-group-btn").addEventListener("click", () => {
  groupNameIn.value = "";
  groupPicker.innerHTML = allUsers.map(u => `
    <label class="picker-item">
      <input type="checkbox" value="${u.id}">
      <span>${escapeHtml(u.username)}</span>
    </label>
  `).join("") || `<div class="empty-list">Keine anderen Nutzer.</div>`;
  groupModal.classList.remove("hidden");
});

document.getElementById("group-cancel-btn").addEventListener("click", () => {
  groupModal.classList.add("hidden");
});

document.getElementById("group-create-btn").addEventListener("click", async () => {
  const ids = [...groupPicker.querySelectorAll("input:checked")].map(c => Number(c.value));
  if (ids.length === 0) return;

  const res = await fetch("/api/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_ids: ids, name: groupNameIn.value.trim() }),
  });
  const data = await res.json();
  if (!data.ok) return;

  groupModal.classList.add("hidden");
  socket.emit("join_chat", { chat_id: data.chat.id });
  await loadChats();
  openChat(data.chat.id);
});

// ════════════════════════════════════════════════════════════
// ── Modal: Chat verwalten (umbenennen / Mitglieder) ────────
// ════════════════════════════════════════════════════════════
const manageModal  = document.getElementById("manage-modal");
const renameInput  = document.getElementById("rename-input");
const memberListEl = document.getElementById("manage-member-list");
const addPickerEl  = document.getElementById("manage-add-picker");

document.getElementById("chat-settings-btn").addEventListener("click", openManageModal);
document.getElementById("manage-close-btn").addEventListener("click", () => {
  manageModal.classList.add("hidden");
});

function openManageModal() {
  const chat = chatsById[activeChatId];
  if (!chat) return;
  renameInput.value = chat.name || "";
  renderManageMembers(chat);
  manageModal.classList.remove("hidden");
}

function renderManageMembers(chat) {
  const memberIds = new Set(chat.members.map(m => m.id));

  memberListEl.innerHTML = chat.members.map(m => `
    <div class="member-row">
      <span>${escapeHtml(m.username)}${m.id === ME ? " (du)" : ""}</span>
      <button class="btn-remove" data-id="${m.id}" title="Entfernen">✕</button>
    </div>
  `).join("");

  memberListEl.querySelectorAll(".btn-remove").forEach(btn => {
    btn.addEventListener("click", () => removeMember(Number(btn.dataset.id)));
  });

  // Nutzer, die noch nicht Mitglied sind, zum Hinzufügen anbieten
  const addable = allUsers.filter(u => !memberIds.has(u.id));
  addPickerEl.innerHTML = addable.map(u => `
    <button class="btn-add" data-id="${u.id}">＋ ${escapeHtml(u.username)}</button>
  `).join("") || `<div class="empty-list">Alle Nutzer sind bereits dabei.</div>`;

  addPickerEl.querySelectorAll(".btn-add").forEach(btn => {
    btn.addEventListener("click", () => addMember(Number(btn.dataset.id)));
  });
}

document.getElementById("rename-btn").addEventListener("click", async () => {
  if (activeChatId === null) return;
  await fetch(`/api/chats/${activeChatId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: renameInput.value.trim() }),
  });
  // Der Server sendet chat_updated → Liste + Header aktualisieren sich.
});

async function addMember(userId) {
  const res = await fetch(`/api/chats/${activeChatId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  const data = await res.json();
  if (data.ok) {
    chatsById[data.chat.id] = data.chat;
    renderManageMembers(data.chat);
  }
}

async function removeMember(userId) {
  const chatId = activeChatId;
  await fetch(`/api/chats/${chatId}/members/${userId}`, { method: "DELETE" });
  // Sich selbst entfernt → Chat wird über chat_removed geschlossen.
  if (userId === ME) {
    manageModal.classList.add("hidden");
    return;
  }
  const chat = chatsById[chatId];
  if (chat) {
    chat.members = chat.members.filter(m => m.id !== userId);
    renderManageMembers(chat);
  }
}

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
// ── Benachrichtigungen (ungelesen-Badges pro Chat) ─────────
// ════════════════════════════════════════════════════════════
async function loadNotifications() {
  try {
    const res = await fetch("/api/notifications");
    if (!res.ok) return;
    const counts = await res.json();   // [{chat_id, count}]
    counts.forEach(c => { unreadByChat[c.chat_id] = c.count; });
    applyBadges();
  } catch (_) {
    // Benachrichtigungen sind nicht kritisch — stummes Fehlschlagen.
  }
}

// Setzt alle Badges gemäß unreadByChat (nach jedem Neu-Rendern der Liste).
function applyBadges() {
  Object.keys(chatsById).forEach(id => updateChatBadge(Number(id)));
}

function updateChatBadge(chatId) {
  const badge = document.getElementById(`badge-${chatId}`);
  if (!badge) return;
  const count = unreadByChat[chatId] || 0;
  if (count > 0) {
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

function flashChatItem(chatId) {
  const item = chatListEl.querySelector(`.user-item[data-id="${chatId}"]`);
  if (!item) return;
  item.classList.add("notif-flash");
  setTimeout(() => item.classList.remove("notif-flash"), 600);
}

async function markChatRead(chatId, force = false) {
  // Ohne force nur handeln, wenn lokal etwas ungelesen ist (spart Requests).
  // Mit force (Nachricht im offenen Chat) immer die DB aktualisieren.
  if (!force && !unreadByChat[chatId]) return;
  delete unreadByChat[chatId];
  updateChatBadge(chatId);
  try {
    await fetch(`/api/notifications/chat/${chatId}/read`, { method: "POST" });
  } catch (_) {
    // Badge wurde lokal bereits entfernt — stummes Fehlschlagen.
  }
}

// ── Start ─────────────────────────────────────────────────
async function init() {
  loadMe();
  await loadUsers();   // muss vor loadChats/Pickern stehen (allUsers befüllen)
  await loadChats();
  loadNotifications();
}

init();
