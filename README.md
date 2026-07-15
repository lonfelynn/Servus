<div align="center">

<img src="static/img/logo.png" height="120" alt="Servus Logo" style="margin-top: 1rem; border-radius: 0.5rem;">

# Servus

**Ein bayerisches Schulprojekt – endlich ein Messenger von Schülern für Schüler.**

Echtzeit-Chat mit Freunden, Gruppen, Datei-Anhängen, XP-System und einer ordentlichen Prise Bayern. 🥨

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-Echtzeit-010101?logo=socketdotio&logoColor=white)](https://socket.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

**➡️ [servus.klappstuhl.me](https://servus.klappstuhl.me)**

</div>

---

## Funktionen

### 💬 Chats & Nachrichten
- **1-zu-1- und Gruppenchats** – ein einheitliches Chat-Modell, bei dem jeder Chat (auch die Direktnachricht) einfach ein Chat mit Mitgliedern ist.
- **Echtzeit** über Socket.IO – Nachrichten erscheinen sofort bei allen Beteiligten.
- **Datei-Anhänge** – Bilder, Videos und beliebige Dateien direkt im Chat.
- **Bearbeiten & Löschen** von eigenen Nachrichten (Löschen als Soft-Delete).
- **Lesebestätigungen** und Ungelesen-Zähler pro Chat.
- **Verlauf** dauerhaft in PostgreSQL gespeichert.

### 🤝 Freunde
- **Nutzersuche** inklusive Anzeige gemeinsamer Freunde.
- **Freundschaftsanfragen** mit optionaler Vorstellungsnachricht.
- Direkt chatten und zu Gruppen hinzufügen kann man nur befreundete Nutzer.

### 🎨 Personalisierung
- **Profil** mit Avatar, Statustext und Präsenz (online / abwesend / beschäftigt / offline).
- **XP-/Level-System** – für jede gesendete Nachricht gibt es Erfahrungspunkte.
- **App-Themes** inklusive „Söder"-Theme mit Freischalt-Mechanik und Live-Zitaten.
- **Akzentfarbe** sowie Hell-/Dunkel-Modus.

### 🔒 Sicherheit
- Passwörter mit **bcrypt** gehasht.
- **Rate-Limiting** für Login / Registrierung und für das Senden von Nachrichten.
- Sichere Session-Cookies (`HttpOnly`, `SameSite=Strict`, optional `Secure`).
- Security-Header (Content-Security-Policy, `X-Frame-Options`, `nosniff`).

> Die gesamte Oberfläche ist auf **Deutsch**.

## Einrichtung

Die Abhängigkeiten werden mit [Poetry](https://python-poetry.org/) verwaltet (es gibt bewusst keine `requirements.txt`).

1. **Abhängigkeiten installieren**

   ```bash
   poetry install
   ```

2. **PostgreSQL einrichten**

   Stelle sicher, dass ein PostgreSQL-Server läuft, und lege eine leere
   Datenbank an, z. B.:

   ```sql
   CREATE ROLE servus WITH LOGIN PASSWORD 'dein_passwort';
   CREATE DATABASE servus OWNER servus;
   ```

3. **Umgebungsvariablen konfigurieren**

   Kopiere `.env.example` nach `.env` und trage deine Datenbank-Zugangsdaten
   sowie einen zufälligen `SECRET_KEY` ein (ohne den startet die App nicht):

   ```bash
   cp .env.example .env
   ```

4. **App starten**

   ```bash
   poetry run python app.py
   ```

   Beim Start öffnet die App den Connection-Pool und führt die
   Datenbank-Migrationen (`sql/*.sql`) automatisch aus, sodass die Tabellen
   beim ersten Start angelegt werden. Öffne anschließend
   <http://localhost:5000> im Browser.

### Alternativ: mit Docker

Ein `Dockerfile` liegt bei. Die Container-Variante verbindet sich mit einem
**externen** PostgreSQL-Server (setze `DB_HOST` etc. in der `.env`):

```bash
docker build -t servus .
docker run --env-file .env -p 5000:5000 servus
```

## Architektur

Server-gerenderte Jinja-Templates + Vanilla JS im Frontend; Flask-Blueprints
für die Routen, Socket.IO für die Echtzeit-Nachrichten und eine gepoolte
psycopg2-Schicht für PostgreSQL. Die Web-Schicht liegt im Paket `routes/`,
während die Infrastruktur (`app.py`, `models.py`, `database.py`, `extensions.py`)
im Projektwurzelverzeichnis bleibt.

### Datenbank

- **Connection-Pool** – die gesamte App teilt sich einen
  `ThreadedConnectionPool` (siehe `database.py`). Nutze ihn über den
  Context-Manager, der eine Verbindung ausleiht, bei Erfolg committet /
  bei einer Ausnahme zurückrollt und die Verbindung wieder an den Pool zurückgibt:

  ```python
  from database import get_connection

  with get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute("SELECT ... WHERE id = %s", (user_id,))
      rows = cursor.fetchall()
  ```

  Die Rows sind dict-artig (`row["username"]`), und Platzhalter sind `%s`
  (psycopg2), nicht `?`.

- **Migrationen** – jede `*.sql`-Datei im Ordner `sql/` wird genau einmal
  ausgeführt, in alphabetischer Reihenfolge, jede in ihrer eigenen Transaktion,
  und in der Tabelle `schema_migrations` vermerkt. Für eine Schema-Änderung
  legst du einfach eine neue, höher nummerierte Datei daneben (z. B. `sql/10.sql`)
  und startest die App neu – nur neue Dateien werden ausgeführt. SQL ist im
  PostgreSQL-Dialekt (`SERIAL` für Auto-Increment-PKs).

## Chat testen

Registriere zwei Konten (öffne für den zweiten Nutzer einen zweiten Browser
oder ein privates Fenster), schicke dem anderen eine Freundschaftsanfrage,
nimm sie an und schreibt euch Nachrichten hin und her – sie erscheinen in
Echtzeit. Für einen Gruppenchat lädst du weitere Freunde dazu ein.

## Projektstruktur

| Datei / Ordner        | Zweck                                                         |
| --------------------- | ------------------------------------------------------------- |
| `app.py`              | Einstiegspunkt: App-Setup, Konfiguration, Registrierung, Start |
| `extensions.py`       | Geteilte Instanzen (Rate-Limiter, Socket.IO), spät gebunden   |
| `database.py`         | PostgreSQL-Connection-Pool und Migrations-Runner              |
| `models.py`           | Sämtlicher SQL-Zugriff (Nutzer, Chats, Nachrichten, Freunde, XP) |
| `routes/`             | Die Web-Schicht (siehe unten)                                 |
| `templates/`          | Jinja-Templates (`login`, `register`, `chat`, `profile`)      |
| `static/`             | CSS, JS, Bilder und hochgeladene Anhänge (`uploads/`)         |
| `sql/`                | Nummerierte Migrationsdateien (`0.sql`, `1.sql`, …)           |
| `data/`               | Lokaler Snapshot der Söder-Zitate                             |
| `Dockerfile`          | Container-Build für den Produktivbetrieb                      |

### Das `routes/`-Paket

| Modul                  | Zweck                                                        |
| ---------------------- | ----------------------------------------------------------- |
| `routes/__init__.py`   | Bündelt die Blueprints und registriert die Socket.IO-Handler |
| `routes/auth.py`       | Registrierung / Login / Logout                              |
| `routes/views.py`      | Server-gerenderte Seiten (`/`, `/chat`)                     |
| `routes/profile.py`    | Profil, App-Theme und Nutzerverzeichnis (JSON-API)          |
| `routes/chats.py`      | Chats, Nachrichten, Uploads, Mitglieder, Benachrichtigungen |
| `routes/friends.py`    | Nutzersuche und Freundschaftsanfragen                       |
| `routes/sockets.py`    | Echtzeit-Handler (connect / join / leave / send) + Rate-Limit |
| `routes/helpers.py`    | `login_required`-Decorator und JSON-Serialisierer           |
| `routes/constants.py`  | Projektpfade und Größenlimits                                |
| `routes/soeder.py`     | Lädt und cached den Söder-Zitate-Snapshot                   |
