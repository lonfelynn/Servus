// ════════════════════════════════════════════════════════════
// ── Ende-zu-Ende-Verschlüsselung (E2EE) ────────────────────
// ════════════════════════════════════════════════════════════
// Alles hier läuft ausschließlich im Browser. Der Server bekommt nur
// Chiffretext und verpackte Schlüssel zu sehen — er kann keine Nachricht lesen.
//
// Schlüssel-Modell
//   1. Jeder Nutzer hat ein RSA-OAEP-2048-Schlüsselpaar. Der öffentliche
//      Schlüssel liegt im Klartext auf dem Server, der private nur AES-GCM-
//      verpackt mit einem aus dem Passwort abgeleiteten Schlüssel (PBKDF2).
//   2. Jeder Chat hat einen AES-GCM-256-Schlüssel. Der liegt einmal pro
//      Mitglied mit dessen öffentlichem Schlüssel verpackt in `chat_keys`.
//   3. Nachrichten werden mit dem Chatschlüssel verschlüsselt und als
//      "enc:v1:" + base64(IV ‖ Chiffretext) gespeichert.
//
// Bewusste Grenzen (siehe README):
//   • Passwort vergessen = Verlauf unwiederbringlich weg. Es gibt niemanden,
//     der den privaten Schlüssel sonst entpacken könnte — das ist der Punkt.
//   • Ein Chat behält seinen Schlüssel dauerhaft: keine Forward Secrecy, und
//     ein neu hinzugefügtes Mitglied kann auch ältere Nachrichten lesen.
//   • Datei-Uploads liegen weiterhin im Klartext in static/uploads.

const E2EE = (() => {
  const PREFIX = "enc:v1:";
  const PBKDF2_ROUNDS = 250000;
  const IV_BYTES = 12;              // von AES-GCM vorgegeben
  const DB_NAME = "servus-e2ee";
  const STORE = "keys";

  const subtle = window.crypto && window.crypto.subtle;

  // ── base64 ⇄ ArrayBuffer ────────────────────────────────
  const toB64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const fromB64 = (str) => Uint8Array.from(atob(str), (c) => c.charCodeAt(0));

  const enc = new TextEncoder();
  const dec = new TextDecoder();

  // ── IndexedDB: hält den entpackten privaten Schlüssel ────
  // Als nicht-exportierbares CryptoKey-Objekt, damit ihn kein Skript wieder
  // auslesen kann — benutzen ja, herauskopieren nein. Überlebt Reloads, sodass
  // das Passwort nur einmal pro Browser gebraucht wird.
  function openDb() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => req.result.createObjectStore(STORE);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function idb(mode, fn) {
    const db = await openDb();
    try {
      return await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, mode);
        const req = fn(tx.objectStore(STORE));
        let result;
        req.onsuccess = () => { result = req.result; };
        req.onerror = () => reject(req.error);
        // Erst auf `complete` warten, nicht schon auf `success`: der Request
        // meldet Erfolg, bevor die Transaktion committed ist. Nach dem Login
        // wird direkt weitergeleitet — würden wir dort schon weitermachen,
        // bräche die Navigation die offene Transaktion ab und der Schlüssel
        // wäre auf der Chat-Seite wieder weg (= Passwortabfrage bei jedem
        // Login, obwohl das Passwort gerade erst eingegeben wurde).
        tx.oncomplete = () => resolve(result);
        tx.onabort = () => reject(tx.error);
        tx.onerror = () => reject(tx.error);
      });
    } finally {
      db.close();
    }
  }

  // Pro Nutzer ein eigener Eintrag — sonst würde ein zweiter Login im selben
  // Browser den Schlüssel des ersten überschreiben.
  const privSlot = (userId) => `priv:${userId}`;

  const storePrivateKey = (userId, key) =>
    idb("readwrite", (s) => s.put(key, privSlot(userId)));
  const loadPrivateKey = (userId) =>
    idb("readonly", (s) => s.get(privSlot(userId)));
  const forgetPrivateKey = (userId) =>
    idb("readwrite", (s) => s.delete(privSlot(userId)));

  // ── Passwort → Wrapping-Key (PBKDF2) ────────────────────
  async function deriveWrapKey(password, salt) {
    const base = await subtle.importKey(
      "raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]
    );
    return subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: PBKDF2_ROUNDS, hash: "SHA-256" },
      base,
      { name: "AES-GCM", length: 256 },
      false,
      ["wrapKey", "unwrapKey"]
    );
  }

  const RSA_PARAMS = {
    name: "RSA-OAEP",
    modulusLength: 2048,
    publicExponent: new Uint8Array([1, 0, 1]),
    hash: "SHA-256",
  };

  // ── Schlüsselpaar erzeugen und ans Backend geben ────────
  // Der private Schlüssel verlässt den Browser nur verpackt: das Passwort geht
  // dabei nie mit, der Server bekommt Salt + verpackten Schlüssel und kann
  // damit ohne das Passwort nichts anfangen.
  async function createBundle(password) {
    const pair = await subtle.generateKey(RSA_PARAMS, true, ["wrapKey", "unwrapKey"]);
    const salt = window.crypto.getRandomValues(new Uint8Array(16));
    const iv = window.crypto.getRandomValues(new Uint8Array(IV_BYTES));
    const wrapKey = await deriveWrapKey(password, salt);

    const wrapped = await subtle.wrapKey("pkcs8", pair.privateKey, wrapKey, {
      name: "AES-GCM", iv,
    });
    const spki = await subtle.exportKey("spki", pair.publicKey);

    // IV vor den verpackten Schlüssel hängen, damit ein Feld reicht.
    const blob = new Uint8Array(iv.length + wrapped.byteLength);
    blob.set(iv, 0);
    blob.set(new Uint8Array(wrapped), iv.length);

    return {
      bundle: {
        public_key: toB64(spki),
        private_key: toB64(blob),
        key_salt: toB64(salt),
      },
      privateKey: pair.privateKey,
    };
  }

  async function unwrapBundle(bundle, password) {
    const salt = fromB64(bundle.key_salt);
    const blob = fromB64(bundle.private_key);
    const wrapKey = await deriveWrapKey(password, salt);
    // Nicht exportierbar: der Schlüssel darf benutzt, aber nie ausgelesen werden.
    return subtle.unwrapKey(
      "pkcs8",
      blob.slice(IV_BYTES),
      wrapKey,
      { name: "AES-GCM", iv: blob.slice(0, IV_BYTES) },
      RSA_PARAMS,
      false,
      ["unwrapKey"]
    );
  }

  // ── Login/Entsperren: Schlüssel holen oder anlegen ──────
  // Ein Aufruf deckt alle drei Fälle ab: erster Login nach der Umstellung
  // (noch kein Schlüssel), neuer Browser (Schlüssel da, aber lokal nicht) und
  // der Normalfall (schon entpackt im IndexedDB).
  async function unlock(userId, password) {
    if (!subtle) throw new Error("insecure-context");

    const existing = await loadPrivateKey(userId);
    if (existing) return existing;

    const res = await fetch("/api/keys");
    const bundle = await res.json();

    let privateKey;
    if (bundle && bundle.public_key) {
      privateKey = await unwrapBundle(bundle, password);   // wirft bei falschem Passwort
    } else {
      const created = await createBundle(password);
      const post = await fetch("/api/keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(created.bundle),
      });
      const data = await post.json();
      if (!data.ok) {
        // 409: ein paralleler Login war schneller. Dessen Schlüssel gilt —
        // den eigenen wegwerfen und den gespeicherten entpacken.
        const again = await (await fetch("/api/keys")).json();
        if (!again || !again.public_key) throw new Error("key-setup-failed");
        privateKey = await unwrapBundle(again, password);
      } else {
        privateKey = created.privateKey;
      }
    }

    await storePrivateKey(userId, privateKey);
    return privateKey;
  }

  // ── Chatschlüssel: erzeugen / verpacken / entpacken ─────
  const newChatKey = () =>
    subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);

  async function wrapChatKey(chatKey, publicKeyB64) {
    const pub = await subtle.importKey(
      "spki", fromB64(publicKeyB64), RSA_PARAMS, false, ["wrapKey"]
    );
    return toB64(await subtle.wrapKey("raw", chatKey, pub, { name: "RSA-OAEP" }));
  }

  const unwrapChatKey = (wrappedB64, privateKey) =>
    subtle.unwrapKey(
      "raw", fromB64(wrappedB64), privateKey, { name: "RSA-OAEP" },
      { name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]
    );

  // ── Nachrichten ─────────────────────────────────────────
  const isEncrypted = (text) => typeof text === "string" && text.startsWith(PREFIX);

  async function encryptMessage(chatKey, plaintext) {
    const iv = window.crypto.getRandomValues(new Uint8Array(IV_BYTES));
    const ct = await subtle.encrypt({ name: "AES-GCM", iv }, chatKey, enc.encode(plaintext));
    const blob = new Uint8Array(iv.length + ct.byteLength);
    blob.set(iv, 0);
    blob.set(new Uint8Array(ct), iv.length);
    return PREFIX + toB64(blob);
  }

  async function decryptMessage(chatKey, payload) {
    // Nachrichten von vor der Umstellung liegen im Klartext vor — durchreichen.
    if (!isEncrypted(payload)) return payload;
    const blob = fromB64(payload.slice(PREFIX.length));
    const plain = await subtle.decrypt(
      { name: "AES-GCM", iv: blob.slice(0, IV_BYTES) }, chatKey, blob.slice(IV_BYTES)
    );
    return dec.decode(plain);
  }

  return {
    available: !!subtle,
    isEncrypted,
    unlock,
    // Nur der lokal abgelegte Schlüssel, ohne Passwort. null → der Nutzer muss
    // entsperren (neuer Browser, Daten gelöscht).
    loadStored: (userId) => (subtle ? loadPrivateKey(userId) : Promise.resolve(null)),
    forgetPrivateKey,
    newChatKey,
    wrapChatKey,
    unwrapChatKey,
    encryptMessage,
    decryptMessage,
  };
})();
