// ── Vom Server eingesetzte Werte (siehe chat.html) ────────
const ME = window.SERVUS.me;
const MY_NAME = window.SERVUS.myName;

const socket = io();

// Höchstlänge einer angezeigten Nachrichten-Vorschau in den Anfragen.
const PREVIEW_MAX = 64;
// Höchstlänge der letzten-Nachricht-Vorschau in der Chat-Sidebar.
const SIDEBAR_PREVIEW_MAX = 15;
// Client-seitiges Ratelimit (spiegelt den Server: 5 Nachrichten / 5 s).
const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW = 5000;
const sendTimes = [];   // Zeitstempel der zuletzt gesendeten Nachrichten

// Aktueller Chat + Caches
let activeChatId = null;
const chatsById = {};    // chat_id → Chat-Objekt (id, display_name, members, is_group)
let allUsers = [];       // alle anderen Nutzer (für Kontaktliste)
let friends = [];        // akzeptierte Freunde (für die Gruppen-Mitglieder-Picker)
const unreadByChat = {}; // chat_id → Anzahl ungelesener Nachrichten

const chatListEl     = document.getElementById("chat-list");
const searchInputEl  = document.getElementById("search-input");
const searchResultsEl = document.getElementById("search-results");
const requestsListEl = document.getElementById("requests-list");
const requestsBadge  = document.getElementById("requests-badge");
const friendsListEl  = document.getElementById("friends-list");
const messagesEl   = document.getElementById("messages");
const placeholder  = document.getElementById("chat-placeholder");
const chatView     = document.getElementById("chat-view");
const peerNameEl   = document.getElementById("peer-name");
const peerSubEl    = document.getElementById("peer-sub");
const peerAvatarEl = document.getElementById("peer-avatar");
const msgInput     = document.getElementById("msg-input");
const sendBtn      = document.getElementById("send-btn");
const fileInput    = document.getElementById("file-input");
const attachBtn    = document.getElementById("attach-btn");
const filePreview  = document.getElementById("file-preview");

let selectedFile = null;
if (attachBtn) {
  attachBtn.addEventListener("click", () => fileInput.click());
}
if (fileInput) {
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      selectedFile = file;
      filePreview.innerHTML = `<span>📎 ${escapeHtml(file.name)}</span> <button class="icon-btn" style="font-size: 0.8rem; padding: 2px;" onclick="clearFile()">✕</button>`;
      filePreview.classList.remove("hidden");
    }
  });
}
window.clearFile = function() {
  selectedFile = null;
  if (fileInput) fileInput.value = "";
  if (filePreview) {
    filePreview.innerHTML = "";
    filePreview.classList.add("hidden");
  }
}

// ── Eigenes Profil anzeigen ───────────────────────────────
document.getElementById("me-name").textContent = MY_NAME;
document.getElementById("me-avatar").textContent = MY_NAME.charAt(0);

async function loadMe() {
  const res = await fetch("/api/me");
  const me = await res.json();
  document.getElementById("me-level").textContent =
    `Level ${me.level} · ${me.xp} XP`;
}

// ── Alle Nutzer laden (für die Kontaktliste) ─
async function loadUsers() {
  const res = await fetch("/api/users");
  allUsers = await res.json();
}

// ── Freunde laden (für die Gruppen-Mitglieder-Picker) ─
async function loadFriends() {
  const res = await fetch("/api/friends");
  friends = await res.json();
  renderFriendsList();
}

// Rendert die „Freunde"-Sektion in der Sidebar mit Entfernen-Button je Freund.
function renderFriendsList() {
  if (!friendsListEl) return;

  if (friends.length === 0) {
    friendsListEl.innerHTML = `<div class="empty-list">Noch keine Freunde.</div>`;
    return;
  }

  friendsListEl.innerHTML = friends.map(f => `
    <div class="friend-row" data-id="${f.id}">
      <div class="avatar">${escapeHtml(f.username.charAt(0))}</div>
      <div class="friend-row-name">${escapeHtml(f.username)}</div>
      <button class="btn-remove" data-id="${f.id}" data-name="${escapeHtml(f.username)}" title="Freundschaft beenden">✕</button>
    </div>
  `).join("");

  friendsListEl.querySelectorAll(".btn-remove").forEach(btn => {
    btn.addEventListener("click", () => openRemoveFriendModal(Number(btn.dataset.id), btn.dataset.name));
  });
}

// ── Freund entfernen (Bestätigungs-Modal) ──────────────────
const removeFriendModal = document.getElementById("remove-friend-modal");
const removeFriendText  = document.getElementById("remove-friend-text");
let pendingRemoveFriendId = null;

function openRemoveFriendModal(friendId, friendName) {
  pendingRemoveFriendId = friendId;
  removeFriendText.textContent =
    `Möchtest du die Freundschaft mit ${friendName} wirklich beenden?`;
  removeFriendModal.classList.remove("hidden");
}

function closeRemoveFriendModal() {
  pendingRemoveFriendId = null;
  removeFriendModal.classList.add("hidden");
}

document.getElementById("remove-friend-cancel-btn")
  .addEventListener("click", closeRemoveFriendModal);

document.getElementById("remove-friend-confirm-btn")
  .addEventListener("click", async () => {
    if (pendingRemoveFriendId === null) return;
    const res = await fetch(`/api/friends/${pendingRemoveFriendId}`, { method: "DELETE" });
    const data = await res.json();
    closeRemoveFriendModal();
    if (!data.ok) {
      alert(data.error || "Freundschaft konnte nicht beendet werden.");
      return;
    }
    await loadFriends();   // Freundesliste neu rendern
    await loadChats();     // ein gemeinsamer 1:1-Chat verschwindet ggf.
    if (searchInputEl.value.trim()) runSearch();   // Status in der Suche aktualisieren
  });

removeFriendModal.addEventListener("click", (e) => {
  if (e.target === removeFriendModal) closeRemoveFriendModal();
});

// Unterzeile eines Chat-Eintrags: gekürzte letzte Nachricht, sonst Fallback.
function chatSubline(chat) {
  if (chat.last_message) return truncate(chat.last_message, SIDEBAR_PREVIEW_MAX);
  return chat.is_group ? chat.members.length + " Mitglieder" : "Direktnachricht";
}

// Aktualisiert die letzte-Nachricht-Vorschau eines Chats in der Sidebar.
function updateChatPreview(chatId, content) {
  const chat = chatsById[chatId];
  if (chat) chat.last_message = content;
  const subEl = chatListEl.querySelector(`.user-item[data-id="${chatId}"] .user-sub`);
  if (subEl && chat) subEl.textContent = chatSubline(chat);
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
          <div class="user-sub">${escapeHtml(chatSubline(c))}</div>
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

  // Öffnen markiert den Chat immer als gelesen (force), auch wenn der lokale
  // Zähler noch nicht geladen ist (z.B. frischer Chat nach Anfrage-Annahme).
  markChatRead(chatId, true);
  if (window.showChatMobile) window.showChatMobile();
}

// ── Eine Nachricht rendern ────────────────────────────────
function renderMessage(msg) {
  const mine = msg.sender_id === ME;
  const chat = chatsById[msg.chat_id];
  const showSender = !mine && chat && chat.is_group;

  const row = document.createElement("div");
  row.className = `row ${mine ? "sent" : "received"}`;
  // data-Attribute ermöglichen gezielte DOM-Lookups bei edit/delete-Events.
  row.dataset.id     = msg.id;
  row.dataset.chatId = msg.chat_id;

  const bubbleClass = "bubble";
  let bubbleContent = "";
  
  if (!msg.is_deleted) {
    bubbleContent = escapeHtml(msg.content);
    if (msg.file_url) {
      const br = msg.content ? "<br>" : "";
      if (msg.file_type === "image") {
         bubbleContent += `${br}<img src="${escapeHtml(msg.file_url)}" alt="Attachment" style="max-width: 100%; border-radius: 8px; margin-top: 5px;">`;
      } else if (msg.file_type === "video") {
         bubbleContent += `${br}<video src="${escapeHtml(msg.file_url)}" controls style="max-width: 100%; border-radius: 8px; margin-top: 5px;"></video>`;
      } else {
         bubbleContent += `${br}<a href="${escapeHtml(msg.file_url)}" target="_blank" style="color: inherit; text-decoration: underline;">📎 ${escapeHtml(msg.file_name || "Download")}</a>`;
      }
    }
  }
  let readStatusHtml = "";
  if (mine && !msg.is_deleted) {
      if (msg.read_count >= msg.expected_read_count && msg.expected_read_count > 0) {
          readStatusHtml = `<span class="read-status" style="margin-left: 5px; font-size: 0.8rem; color: #4CAF50;">✓✓</span>`;
      } else {
          readStatusHtml = `<span class="read-status" style="margin-left: 5px; font-size: 0.8rem; opacity: 0.6;">✓</span>`;
      }
  }
  
  
  row.innerHTML = `
    ${showSender ? `<div class="sender">${escapeHtml(msg.sender_name || "")}</div>` : ""}
    ${msg.is_deleted ? `<div class="edited-marker">(gelöscht)</div>` : `<div class="${bubbleClass}">${bubbleContent}</div>`}
    ${(!msg.is_deleted && msg.edited_at) ? `<div class="edited-marker">(bearbeitet)</div>` : ""}
    <div class="time">${formatTime(msg.sent_at)}${readStatusHtml}</div>
    ${(mine && !msg.is_deleted) ? `
    <div class="msg-actions">
      <button class="msg-btn msg-edit-btn"   title="Bearbeiten">✎</button>
      <button class="msg-btn msg-delete-btn" title="Löschen">✕</button>
    </div>` : ""}
  `;

  if (mine && !msg.is_deleted)  {
    row.querySelector(".msg-edit-btn").addEventListener("click", () => {
      // Bereits im Bearbeitungsmodus → nichts tun.
      if (row.querySelector(".edit-input")) return;
      // textContent der Bubble ist der unescapte Original-Text.
      const currentContent = row.querySelector(".bubble").textContent;
      startEditMessage(msg.id, msg.chat_id, currentContent, row);
    });

    row.querySelector(".msg-delete-btn").addEventListener("click", () => {
      deleteMessage(msg.id, msg.chat_id);
    });
  }

  messagesEl.appendChild(row);
}

// ── Nachricht senden ──────────────────────────────────────
// Prüft das clientseitige Ratelimit (gleitendes Fenster). Bei Überschreitung
// bleibt der Text erhalten und es wird ein Hinweis angezeigt.
function canSendNow() {
  const now = Date.now();
  while (sendTimes.length && now - sendTimes[0] > RATE_LIMIT_WINDOW) sendTimes.shift();
  if (sendTimes.length >= RATE_LIMIT_MAX) return false;
  sendTimes.push(now);
  return true;
}

async function sendMessage() {
  const text = msgInput.value.trim();
  if (!text && !selectedFile) return;
  if (activeChatId === null) return;
  if (!canSendNow()) {
    showRateNotice();
    return;   // Text bleibt im Eingabefeld erhalten
  }
  let file_url = null;
  let file_type = null;
  let file_name = null;
  
  if (selectedFile) {
    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (data.ok) {
        file_url = data.file_url;
        file_type = data.file_type;
        file_name = data.file_name;
      } else {
        alert(data.error || "Upload fehlgeschlagen.");
        return;
      }
    } catch (e) {
      alert("Upload fehlgeschlagen.");
      return;
    }
  }
  socket.emit("send_message", { 
    chat_id: activeChatId, 
    content: text,
    file_url: file_url,
    file_type: file_type,
    file_name: file_name
  });
  msgInput.value = "";
  msgInput.style.height = "auto";
  clearFile();
  msgInput.focus();
}

// Blendet kurz einen Hinweis ein, wenn zu schnell gesendet wird.
let rateNoticeTimer = null;
function showRateNotice(text = "Du sendest zu schnell. Bitte warte kurz.") {
  const el = document.getElementById("rate-notice");
  if (!el) return;
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(rateNoticeTimer);
  rateNoticeTimer = setTimeout(() => el.classList.add("hidden"), 2500);
}

// Server-seitige Ablehnung (falls der Client umgangen wurde).
socket.on("rate_limited", (data) => showRateNotice(data && data.error));

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
  updateChatPreview(msg.chat_id, msg.content);   // Sidebar-Vorschau aktuell halten
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
  loadNotifications();   // z.B. Intro-Nachricht nach angenommener Anfrage
  if (data.chat_id === activeChatId) refreshActiveHeader();
});

// ── Freundschafts-Events (Echtzeit) ───────────────────────
socket.on("friend_request", () => loadRequests());
socket.on("friend_update", () => {
  loadRequests();
  loadFriends();   // Freundesliste für die Gruppen-Picker aktuell halten
  if (searchInputEl.value.trim()) runSearch();   // Status in der Suche aktualisieren
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
  groupPicker.innerHTML = friends.map(u => `
    <label class="picker-item">
      <input type="checkbox" value="${u.id}">
      <span>${escapeHtml(u.username)}</span>
    </label>
  `).join("") || `<div class="empty-list">Du hast noch keine Freunde zum Hinzufügen.</div>`;
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
  if (!data.ok) {
    alert(data.error || "Gruppe konnte nicht erstellt werden.");
    return;
  }

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

// Arbeitskopie der Änderungen, solange das Modal offen ist. Erst beim
// Speichern werden sie an den Server gesendet; „Abbrechen“ verwirft sie.
let manageDraft = null;

document.getElementById("chat-settings-btn").addEventListener("click", openManageModal);
document.getElementById("manage-cancel-btn").addEventListener("click", () => {
  manageDraft = null;               // Änderungen verwerfen — nichts wurde committet
  manageModal.classList.add("hidden");
});

function openManageModal() {
  const chat = chatsById[activeChatId];
  if (!chat) return;
  manageDraft = { members: chat.members.map(m => ({ id: m.id, username: m.username })) };
  renameInput.value = chat.name || "";
  renderManageMembers();
  manageModal.classList.remove("hidden");
}

function renderManageMembers() {
  const members = manageDraft.members;
  const memberIds = new Set(members.map(m => m.id));

  memberListEl.innerHTML = members.map(m => `
    <div class="member-row">
      <span>${escapeHtml(m.username)}${m.id === ME ? " (du)" : ""}</span>
      <button class="btn-remove" data-id="${m.id}" title="Entfernen">✕</button>
    </div>
  `).join("");

  memberListEl.querySelectorAll(".btn-remove").forEach(btn => {
    btn.addEventListener("click", () => removeMember(Number(btn.dataset.id)));
  });

  // Freunde, die noch nicht Mitglied sind, zum Hinzufügen anbieten
  const addable = friends.filter(u => !memberIds.has(u.id));
  addPickerEl.innerHTML = addable.map(u => `
    <button class="btn-add" data-id="${u.id}">＋ ${escapeHtml(u.username)}</button>
  `).join("") || `<div class="empty-list">Alle deine Freunde sind bereits dabei.</div>`;

  addPickerEl.querySelectorAll(".btn-add").forEach(btn => {
    btn.addEventListener("click", () => addMember(Number(btn.dataset.id)));
  });
}

document.getElementById("manage-save-btn").addEventListener("click", async () => {
  const chatId = activeChatId;
  if (chatId === null || !manageDraft) return;
  const chat = chatsById[chatId];
  if (!chat) return;

  const origIds  = new Set(chat.members.map(m => m.id));
  const draftIds = new Set(manageDraft.members.map(m => m.id));
  const tasks = [];

  // Name, falls geändert.
  const newName = renameInput.value.trim();
  if (newName !== (chat.name || "")) {
    tasks.push(fetch(`/api/chats/${chatId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName }),
    }));
  }
  // Neu hinzugefügte Mitglieder.
  for (const m of manageDraft.members) {
    if (!origIds.has(m.id)) {
      tasks.push(fetch(`/api/chats/${chatId}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: m.id }),
      }));
    }
  }
  // Entfernte Mitglieder (sich selbst wird separat über den ✕-Button behandelt).
  for (const m of chat.members) {
    if (m.id !== ME && !draftIds.has(m.id)) {
      tasks.push(fetch(`/api/chats/${chatId}/members/${m.id}`, { method: "DELETE" }));
    }
  }

  await Promise.all(tasks);
  // Der Server sendet chat_updated → Liste + Header aktualisieren sich.
  manageDraft = null;
  manageModal.classList.add("hidden");
});

function addMember(userId) {
  if (manageDraft.members.some(m => m.id === userId)) return;
  const friend = friends.find(u => u.id === userId);
  if (!friend) return;
  manageDraft.members.push({ id: friend.id, username: friend.username });
  renderManageMembers();
}

function removeMember(userId) {
  // Sich selbst zu entfernen bedeutet den Chat zu verlassen — das ist eine
  // destruktive Aktion und wird sofort (mit Bestätigung) ausgeführt.
  if (userId === ME) {
    const chat = chatsById[activeChatId];
    const label = chat && chat.is_group ? "diese Gruppe" : "diesen Chat";
    if (!confirm(`Möchtest du ${label} wirklich verlassen?`)) return;
    fetch(`/api/chats/${activeChatId}/members/${ME}`, { method: "DELETE" });
    // Chat wird über chat_removed geschlossen.
    manageDraft = null;
    manageModal.classList.add("hidden");
    return;
  }
  // Andere Mitglieder nur im Entwurf entfernen — wird beim Speichern übernommen.
  manageDraft.members = manageDraft.members.filter(m => m.id !== userId);
  renderManageMembers();
}

// ════════════════════════════════════════════════════════════
// ── Nutzersuche ────────────────────────────────────────────
// ════════════════════════════════════════════════════════════
let searchTimer = null;

searchInputEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 250);   // Debounce
});

async function runSearch() {
  const q = searchInputEl.value.trim();
  if (!q) {
    searchResultsEl.innerHTML = "";
    return;
  }
  const res = await fetch(`/api/users/search?q=${encodeURIComponent(q)}`);
  if (!res.ok) return;
  const users = await res.json();

  if (users.length === 0) {
    searchResultsEl.innerHTML = `<div class="empty-list">Keine Treffer.</div>`;
    return;
  }

  searchResultsEl.innerHTML = users.map(u => `
    <div class="user-item" data-id="${u.id}" data-name="${escapeHtml(u.username)}">
      <div class="avatar">${escapeHtml(u.username.charAt(0))}</div>
      <div class="user-info">
        <div class="user-name">${escapeHtml(u.username)}</div>
        <div class="user-sub">Level ${u.level} · ${u.mutual_friends} gemeinsame Freunde</div>
      </div>
      ${searchActionHtml(u)}
    </div>
  `).join("");

  searchResultsEl.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = Number(btn.dataset.id);
      const name = btn.dataset.name;
      if (btn.dataset.action === "request") openRequestModal(id, name);
      else if (btn.dataset.action === "open") startDirectChat(id);
    });
  });
}

// Aktions-Button je nach Freundschaftsstatus
function searchActionHtml(u) {
  switch (u.status) {
    case "friends":
      return `<button class="btn-action" data-action="open" data-id="${u.id}">Nachricht</button>`;
    case "pending_outgoing":
      return `<span class="status-tag">Angefragt</span>`;
    case "pending_incoming":
      return `<span class="status-tag">Antwortet unten</span>`;
    default:
      return `<button class="btn-action" data-action="request" data-id="${u.id}" data-name="${escapeHtml(u.username)}">Anfrage</button>`;
  }
}

// ── Modal: Freundschaftsanfrage senden ────────────────────
const requestModal   = document.getElementById("request-modal");
const requestMsgEl   = document.getElementById("request-message");
const requestSubEl   = document.getElementById("request-modal-sub");
const requestCountEl = document.getElementById("request-charcount");
let requestTargetId  = null;

function openRequestModal(userId, userName) {
  requestTargetId = userId;
  requestSubEl.textContent = `An ${userName}`;
  requestMsgEl.value = "";
  requestCountEl.textContent = "0 / 2048";
  requestModal.classList.remove("hidden");
  requestMsgEl.focus();
}

requestMsgEl.addEventListener("input", () => {
  requestCountEl.textContent = `${requestMsgEl.value.length} / 2048`;
});

document.getElementById("request-cancel-btn").addEventListener("click", () => {
  requestModal.classList.add("hidden");
});

document.getElementById("request-send-btn").addEventListener("click", async () => {
  if (requestTargetId === null) return;
  const res = await fetch("/api/friends/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: requestTargetId, message: requestMsgEl.value.trim() }),
  });
  const data = await res.json();
  if (!data.ok) {
    alert(data.error || "Anfrage konnte nicht gesendet werden.");
    return;
  }
  requestModal.classList.add("hidden");
  runSearch();   // Status → „Angefragt"
});

// ════════════════════════════════════════════════════════════
// ── Freundschaftsanfragen (eingehend) ──────────────────────
// ════════════════════════════════════════════════════════════
async function loadRequests() {
  const res = await fetch("/api/friends/requests");
  if (!res.ok) return;
  const requests = await res.json();

  if (requests.length === 0) {
    requestsListEl.innerHTML = "";
    requestsBadge.classList.add("hidden");
  } else {
    requestsBadge.textContent = requests.length > 99 ? "99+" : String(requests.length);
    requestsBadge.classList.remove("hidden");

    requestsListEl.innerHTML = requests.map(r => `
      <div class="request-card" data-id="${r.id}">
        <div class="request-top">
          <div class="avatar">${escapeHtml(r.requester_name.charAt(0))}</div>
          <div class="user-info">
            <div class="user-name">${escapeHtml(r.requester_name)}</div>
            <div class="user-sub">${r.mutual_friends} gemeinsame Freunde</div>
          </div>
        </div>
        ${r.intro_message ? `<div class="request-message">${escapeHtml(truncate(r.intro_message))}</div>` : ""}
        <div class="request-actions">
          <button class="btn-action btn-accept" data-accept="${r.id}">Annehmen</button>
          <button class="btn-action btn-decline" data-decline="${r.id}">Ablehnen</button>
        </div>
      </div>
    `).join("");

    requestsListEl.querySelectorAll("[data-accept]").forEach(btn =>
      btn.addEventListener("click", () => acceptRequest(Number(btn.dataset.accept))));
    requestsListEl.querySelectorAll("[data-decline]").forEach(btn =>
      btn.addEventListener("click", () => declineRequest(Number(btn.dataset.decline))));
  }
}

async function acceptRequest(requestId) {
  const res = await fetch(`/api/friends/requests/${requestId}/accept`, { method: "POST" });
  const data = await res.json();
  if (!data.ok) return;
  await loadRequests();
  await loadFriends();   // neuer Freund erscheint sofort in der Freundesliste
  if (data.chat) {
    socket.emit("join_chat", { chat_id: data.chat.id });
    await loadChats();
    openChat(data.chat.id);
  }
}

async function declineRequest(requestId) {
  await fetch(`/api/friends/requests/${requestId}/decline`, { method: "POST" });
  loadRequests();
}

// ── Hilfsfunktionen ───────────────────────────────────────
function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function formatTime(iso) {
  let [hours, minutes] = iso.slice(11, 16).split(":");

  hours = (parseInt(hours, 10) + 2) % 24;

  return `${String(hours).padStart(2, "0")}:${minutes}`;
}

// Kürzt eine Zeichenkette für die Anzeige in Menüleisten (mit … am Ende).
function truncate(str, max = PREVIEW_MAX) {
  const s = String(str);
  return s.length > max ? s.slice(0, max) + "…" : s;
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

// ════════════════════════════════════════════════════════════
// ── Nachricht bearbeiten ───────────────────────────────────
// ════════════════════════════════════════════════════════════

function startEditMessage(msgId, chatId, currentContent, rowEl) {
  const bubble = rowEl.querySelector(".bubble");

  bubble.innerHTML = `
    <textarea class="edit-input" maxlength="2048" rows="1"></textarea>
    <div class="edit-actions">
      <button class="btn-edit-cancel">Abbrechen</button>
      <button class="btn-edit-save">Speichern</button>
    </div>
  `;

  const textarea = bubble.querySelector(".edit-input");
  textarea.value = currentContent;
  textarea.style.height = "auto";
  textarea.style.height = textarea.scrollHeight + "px";
  textarea.focus();
  textarea.setSelectionRange(textarea.value.length, textarea.value.length);

  textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
  });

  const cancel = () => {
    bubble.innerHTML = escapeHtml(currentContent);
  };

  bubble.querySelector(".btn-edit-cancel").addEventListener("click", cancel);

  const save = () => {
    const newContent = textarea.value.trim();
    if (!newContent) return;
    if (newContent === currentContent) { cancel(); return; }
    saveEditMessage(msgId, chatId, newContent, rowEl, currentContent);
  };

  bubble.querySelector(".btn-edit-save").addEventListener("click", save);

  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(); }
    if (e.key === "Escape") cancel();
  });
}

async function saveEditMessage(msgId, chatId, newContent, rowEl, originalContent) {
  try {
    const res = await fetch(`/api/chats/${chatId}/messages/${msgId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: newContent }),
    });
    const data = await res.json();
    if (!data.ok) {
      rowEl.querySelector(".bubble").innerHTML = escapeHtml(originalContent);
    }
    // Erfolgsfall: message_edited-Event vom Server aktualisiert den DOM.
  } catch (_) {
    rowEl.querySelector(".bubble").innerHTML = escapeHtml(originalContent);
  }
}

// ════════════════════════════════════════════════════════════
// ── Nachricht löschen ──────────────────────────────────────
// ════════════════════════════════════════════════════════════

async function deleteMessage(msgId, chatId) {
  if (!confirm("Nachricht wirklich löschen?")) return;
  try {
    await fetch(`/api/chats/${chatId}/messages/${msgId}`, { method: "DELETE" });
    // Erfolgsfall: message_deleted-Event vom Server entfernt die Zeile.
  } catch (_) {
    // Stummes Fehlschlagen — kein sichtbarer Effekt.
  }
}

// ─── Eingehende edit/delete-Events (Echtzeit) ─────────────

socket.on("message_edited", (msg) => {
  const row = messagesEl.querySelector(`.row[data-id="${msg.id}"]`);
  if (!row) return;

  row.querySelector(".bubble").innerHTML = escapeHtml(msg.content);

  // "(bearbeitet)"-Marker setzen oder aktualisieren.
  let marker = row.querySelector(".edited-marker");
  if (!marker) {
    marker = document.createElement("div");
    marker.className = "edited-marker";
    row.querySelector(".time").insertAdjacentElement("beforebegin", marker);
  }
  marker.textContent = "(bearbeitet)";
});

socket.on("message_deleted", (data) => {
  const row = messagesEl.querySelector(`.row[data-id="${data.message_id}"]`);
  if (row) {
    const bubble = row.querySelector(".bubble");
    if (bubble) bubble.remove();
    const actions = row.querySelector(".msg-actions");
    if (actions) actions.remove();
    let marker = row.querySelector(".edited-marker");
    if (marker) {
      marker.textContent = "(gelöscht)";
    } else {
      marker = document.createElement("div");
      marker.className = "edited-marker";
      marker.textContent = "(gelöscht)";
      row.querySelector(".time").insertAdjacentElement("beforebegin", marker);
    }
  }
});

socket.on("message_read", (data) => {
  if (data.chat_id === activeChatId) {
     messagesEl.querySelectorAll(".read-status").forEach(el => {
         el.textContent = "✓✓";
         el.style.color = "#4CAF50";
         el.style.opacity = "1";
     });
  }
});

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
  await loadFriends(); // Freunde für die Gruppen-Picker
  await loadChats();
  loadNotifications();
  loadRequests();
}

init();
