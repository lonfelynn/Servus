# Servus

Ein bayerisches Schulprojekt. Endlich ein Messenger von Schülern für Schüler.

https://servus.klappstuhl.me

## Funktionen (Basis)

- Registrierung / Login / Logout (Passwörter mit bcrypt gehasht)
- Kontaktliste aller registrierten Nutzer
- 1-zu-1-Chat mit Echtzeit-Nachrichten über Socket.IO
- Nachrichtenverlauf in PostgreSQL gespeichert
- Einfaches XP-/Level-System (XP für jede gesendete Nachricht)

Die gesamte Oberfläche ist auf Deutsch.

## Einrichtung

Die Abhängigkeiten werden mit [Poetry](https://python-poetry.org/) verwaltet.

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

   Kopiere `.env.example` nach `.env` und trage deine Datenbank-Zugangsdaten ein:

   ```bash
   cp .env.example .env
   ```

4. **App starten**

   ```bash
   poetry run python app.py
   ```

   Beim Start öffnet die App einen Connection-Pool und führt die
   Datenbank-Migrationen (`sql/*.sql`) automatisch aus, sodass die Tabellen
   beim ersten Start angelegt werden. Öffne anschließend
   <http://localhost:5000> im Browser.

## Datenbank

- **Connection-Pool** – die gesamte App teilt sich einen
  `ThreadedConnectionPool` (siehe `database.py`). Nutze ihn über den
  Context-Manager, der eine Verbindung ausleiht und automatisch wieder an den
  Pool zurückgibt:

  ```python
  from database import get_connection

  with get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute("SELECT ...")
      rows = cursor.fetchall()
  ```

- **Migrationen** – jede `*.sql`-Datei im Ordner `sql/` wird genau einmal
  ausgeführt, in alphabetischer Reihenfolge, und in der Tabelle
  `schema_migrations` vermerkt. Für eine Schema-Änderung legst du einfach eine
  neue Datei daneben (z. B. `sql/1.sql`) und startest die App neu – nur neue
  Dateien werden ausgeführt.

## Chat testen

Registriere zwei Konten (öffne für den zweiten Nutzer einen zweiten Browser
oder ein privates Fenster), wähle dann in der Kontaktliste den anderen Nutzer
aus und schicke Nachrichten hin und her – sie erscheinen in Echtzeit.

## Projektstruktur

| Datei / Ordner       | Zweck                                                  |
| -------------------- | ------------------------------------------------------ |
| `app.py`             | Flask-App, Routen, JSON-API und Socket.IO-Handler      |
| `auth.py`            | Blueprint für Registrierung / Login / Logout           |
| `models.py`          | Datenbankzugriff (Nutzer, Nachrichten, XP)             |
| `database.py`        | PostgreSQL-Connection-Pool und Migrationen             |
| `templates/`         | `login.html`, `register.html`, `chat.html`             |
| `static/css/`        | Stylesheets (`style.css` für Auth, `chat.css`)         |
| `static/js/`         | Seiten-Skripte (`login.js`, `register.js`, `chat.js`)  |
