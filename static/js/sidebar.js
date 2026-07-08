// sidebar.js – Seitenleisten-Navigation
// Blendet die Freundschaftsanfragen in eine eigene Seitenleiste aus/ein.
// Bewusst schlank gehalten: die Chat-Erstellung bleibt in chat.js (Button
// #new-group-btn), damit hier nichts doppelt verdrahtet wird.

const mainSidebar     = document.getElementById("sidebar");
const requestsSidebar = document.getElementById("requests-sidebar");
const requestsBtn     = document.getElementById("requests-btn");
const backToChatsBtn  = document.getElementById("back-to-chats-btn");

function showRequestsSidebar() {
  mainSidebar.classList.add("hidden");
  requestsSidebar.classList.remove("hidden");
  requestsSidebar.style.display = "flex";
}

function showChatsSidebar() {
  requestsSidebar.classList.add("hidden");
  requestsSidebar.style.display = "none";
  mainSidebar.classList.remove("hidden");
}

if (requestsBtn)    requestsBtn.addEventListener("click", showRequestsSidebar);
if (backToChatsBtn) backToChatsBtn.addEventListener("click", showChatsSidebar);
