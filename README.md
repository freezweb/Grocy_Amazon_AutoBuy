# 🛒 Grocy Amazon AutoBuy

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Automatische Amazon-Nachbestellung basierend auf Grocy Mindestbeständen via Home Assistant & Alexa**

Dieses Projekt verbindet dein [Grocy](https://grocy.info/) Vorratsverwaltungssystem mit Amazon über [Home Assistant](https://www.home-assistant.io/) und Alexa. Wenn Produkte unter den Mindestbestand fallen, werden sie automatisch zur Alexa Einkaufsliste hinzugefügt oder per Sprachbefehl nachbestellt.

> 💡 **Erinnerst du dich an die Amazon Dash Buttons?** Dieses Projekt bringt automatische Nachbestellung zurück - aber intelligenter!

## ✨ Features

- 🔄 **Automatische Bestandsüberwachung** - Prüft regelmäßig Grocy nach Produkten unter Mindestbestand
- 📦 **Amazon ASIN Unterstützung** - Hinterlege ASINs direkt in Grocy
- 📦 **Bestelleinheiten** - Berücksichtigt Packungsgrößen (z.B. 20 Nudeln pro Paket)
- 📝 **Alexa Shopping List** - Fügt Artikel zur Einkaufsliste hinzu
- 🗣️ **Sprachbefehle** - Optional: Direktbestellung per Alexa
- 🏠 **Home Assistant Integration** - Vollständige Integration mit HA
- 🐳 **Docker Support** - Einfache Bereitstellung
- 🔒 **Sicherheitsfunktionen** - Tageslimits, Dry-Run Modus, Duplikatsprüfung

## 📋 Voraussetzungen

- **Grocy** - Installiert und konfiguriert
- **Home Assistant** - Mit Alexa Media Player Integration
- **Amazon Echo** - Für Alexa Shopping List
- **Python 3.10+** - Für lokale Installation

## 🚀 Schnellstart

### 1. Grocy konfigurieren

Erstelle zwei benutzerdefinierte Felder in Grocy:

1. Gehe zu **Einstellungen** → **Benutzerdefinierte Felder** → **Produkte**
2. Erstelle folgende Felder:

| Feld | Typ | Name |
|------|-----|------|
| Amazon_ASIN | Text | Amazon ASIN |
| Amazon_bestelleinheiten | Zahl | Amazon Bestelleinheiten |

Dann bei jedem Amazon-Produkt:
- **Amazon_ASIN**: Die 10-stellige Amazon Artikelnummer (z.B. `B08N5WRWNW`)
- **Amazon_bestelleinheiten**: Anzahl Einheiten pro Paket (z.B. `20` für 20er-Pack Nudeln)

### 2. Home Assistant vorbereiten

#### Alexa Media Player Integration installieren

1. Installiere [HACS](https://hacs.xyz/) falls noch nicht vorhanden
2. Installiere "Alexa Media Player" über HACS
3. Konfiguriere die Integration mit deinem Amazon-Konto
4. Aktiviere die Shopping List Funktion

Nach der Konfiguration solltest du folgende Entities haben:
- `media_player.echo_xxx` - Dein Echo Gerät
- `todo.alexa_shopping_list` - Alexa Einkaufsliste

#### Long-Lived Access Token erstellen

1. Öffne Home Assistant → **Profil** (unten links)
2. Scrolle zu "**Langlebige Zugriffstokens**"
3. Erstelle einen neuen Token und speichere ihn sicher

### 3. Installation

#### 🚀 Schnell-Installation (empfohlen für Anfänger)

Ein interaktives Setup-Script führt dich durch die komplette Installation:

```bash
# Nur diesen einen Befehl ausführen - der Rest wird interaktiv abgefragt!
curl -fsSL https://raw.githubusercontent.com/freezweb/Grocy_Amazon_AutoBuy/main/setup.sh | bash
```

Oder wenn du das Repository bereits geklont hast:

```bash
cd Grocy_Amazon_AutoBuy
chmod +x setup.sh
./setup.sh
```

Das Setup-Script:
- ✅ Installiert fehlende Pakete (git, docker, docker-compose)
- ✅ Erkennt automatisch `docker-compose` vs `docker compose`
- ✅ Fragt alle Konfigurationswerte interaktiv ab
- ✅ Erstellt die `.env` Datei automatisch
- ✅ Baut und startet den Container

---

#### Option A: Docker auf frischem Linux-Server (manuell)

Wenn du einen frischen Debian/Ubuntu-Server hast, installiere zuerst die Voraussetzungen:

```bash
# System aktualisieren
sudo apt update && sudo apt upgrade -y

# Git und Docker installieren
sudo apt install -y git docker.io docker-compose

# Docker ohne sudo nutzen (nach diesem Befehl neu einloggen oder 'newgrp docker' ausführen)
sudo usermod -aG docker $USER
newgrp docker

# Prüfen ob alles funktioniert
docker --version
docker-compose --version  # Sollte "docker-compose version 1.x.x" zeigen
git --version
```

> **Hinweis:** Je nach System heißt der Befehl `docker-compose` (mit Bindestrich, ältere Version) oder `docker compose` (mit Leerzeichen, neuere Version). Diese Anleitung verwendet `docker-compose`.

Dann das Projekt installieren:

```bash
# Repository klonen
git clone https://github.com/freezweb/Grocy_Amazon_AutoBuy.git
cd Grocy_Amazon_AutoBuy

# Konfiguration erstellen
cp .env.example .env
nano .env  # Werte anpassen (siehe Abschnitt Konfiguration)

# Container bauen und starten
docker-compose up -d

# Logs prüfen (Strg+C zum Beenden)
docker-compose logs -f

# Status prüfen
docker-compose ps
```

**Nützliche Docker-Befehle:**
```bash
docker-compose stop      # Stoppen
docker-compose start     # Starten
docker-compose restart   # Neustarten
docker-compose down      # Komplett beenden
docker-compose pull      # Update holen
docker-compose up -d     # Nach Update neu starten
```

#### Option B: Docker (wenn Git & Docker bereits installiert)

```bash
# Repository klonen
git clone https://github.com/freezweb/Grocy_Amazon_AutoBuy.git
cd Grocy_Amazon_AutoBuy

# Konfiguration erstellen
cp .env.example .env
nano .env  # Werte anpassen

# Starten
docker-compose up -d

# Logs prüfen
docker-compose logs -f
```

#### Option C: Lokale Python-Installation (ohne Docker)

```bash
# Repository klonen
git clone https://github.com/freezweb/Grocy_Amazon_AutoBuy.git
cd Grocy_Amazon_AutoBuy

# Virtuelle Umgebung erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Installieren
pip install -e .

# Konfiguration erstellen
cp .env.example .env
# .env Datei anpassen

# Testen
grocy-autobuy --test

# Einmal ausführen
grocy-autobuy --check --dry-run

# Als Daemon starten
grocy-autobuy --daemon
```

### 4. Konfiguration

Kopiere `.env.example` nach `.env` und passe die Werte an:

```env
# Grocy
GROCY_URL=http://deine-grocy-url:9283
GROCY_API_KEY=dein_api_key

# Home Assistant
HASS_URL=http://homeassistant.local:8123
HASS_TOKEN=dein_token

# Bestellung
ORDER_MODE=voice_order   # Vollautomatisch!
ORDER_DRY_RUN=true  # Auf false für echte Bestellungen!
```

Alternativ: Verwende `config.yaml` (siehe `config.example.yaml`).

## 📖 Verwendung

### Kommandozeile

```bash
# Verbindungen testen
grocy-autobuy --test

# Einmalige Prüfung (Dry Run)
grocy-autobuy --check --dry-run

# Einmalige Prüfung (Echt)
grocy-autobuy --check

# Daemon-Modus (läuft kontinuierlich)
grocy-autobuy --daemon

# Status anzeigen
grocy-autobuy --status

# Mit eigener Config
grocy-autobuy --config /pfad/zu/config.yaml --check
```

### Bestellmodi

| Modus | Beschreibung | Automatisch? |
|-------|--------------|--------------|
| `voice_order` | Direkte Bestellung via Alexa | ✅ **Vollautomatisch** |
| `shopping_list` | Fügt zur Alexa Einkaufsliste hinzu | ⚡ Halb-automatisch |
| `notify_only` | Nur Benachrichtigungen | ❌ Manuell |

### 🤖 Vollautomatische Bestellung einrichten (voice_order)

Für **komplett automatische** Bestellungen ohne Sprachbefehl:

1. **Alexa App öffnen** → Einstellungen → Konto → **Spracheinkauf**
2. **Spracheinkauf aktivieren** (AN)
3. **Sprachcode/Bestätigungscode deaktivieren** 
4. Optional: **1-Click Bestellung** bei Amazon aktivieren

Dann in der Konfiguration:
```env
ORDER_MODE=voice_order
```

> ⚠️ **Sicherheitshinweis:** Ohne Bestätigungscode kann jeder mit Zugang zu deinem Echo bestellen. Überlege ob du ein tägliches Limit setzt (`ORDER_MAX_PER_DAY`).

## 🔧 Home Assistant Automation

Für noch mehr Automatisierung kannst du HA-Automationen erstellen:

```yaml
automation:
  - alias: "Grocy AutoBuy - Tägliche Prüfung"
    trigger:
      - platform: time
        at: "10:00:00"
    action:
      - service: shell_command.grocy_autobuy
      
shell_command:
  grocy_autobuy: "docker exec grocy-autobuy grocy-autobuy --check"
```

Weitere Beispiele findest du in [`homeassistant/automations.yaml`](homeassistant/automations.yaml).

## 📊 Wie die Bestelllogik funktioniert

1. **Bestandsprüfung**: Holt alle Produkte aus Grocy, die unter dem Mindestbestand sind
2. **Filter**: Nur Produkte mit hinterlegter Amazon ASIN werden berücksichtigt
3. **Mengenberechnung**: 
   - Fehlende Menge = Mindestbestand - Aktueller Bestand
   - Benötigte Pakete = Fehlende Menge ÷ Bestelleinheiten (aufgerundet)
4. **Sicherheitsprüfungen**:
   - ⚠️ **Lieferung ausstehend?** Erst wieder bestellen wenn Bestand in Grocy gestiegen ist!
   - Tageslimit nicht überschritten?
5. **Bestellung**:
   - **voice_order**: Alexa bestellt direkt bei Amazon ✅
   - **shopping_list**: Zur Einkaufsliste hinzufügen
6. **Benachrichtigung**: Optional via Home Assistant

### Beispiel

| Produkt | Bestand | Mindestbestand | Bestelleinheiten | Aktion |
|---------|---------|----------------|------------------|--------|
| Nudeln | 5 | 10 | 20 | 1 Paket bestellen |
| Reis | 2 | 5 | 10 | 1 Paket bestellen |
| Tomaten | 3 | 8 | 1 | 5 Stück bestellen |
| Milch | 2 | 4 | - | ⏭️ Übersprungen (keine ASIN) |

## 🐛 Fehlerbehebung

### "Grocy Verbindung fehlgeschlagen"
- Prüfe `GROCY_URL` - ist die URL erreichbar?
- Prüfe `GROCY_API_KEY` - ist der API-Key korrekt?
- Test: `curl -H "GROCY-API-KEY: xxx" http://grocy-url/api/system/info`

### "Home Assistant Verbindung fehlgeschlagen"
- Prüfe `HASS_URL` - ist Home Assistant erreichbar?
- Prüfe `HASS_TOKEN` - ist der Token noch gültig?
- Test: `curl -H "Authorization: Bearer xxx" http://hass-url/api/`

### "Alexa Shopping List nicht verfügbar"
- Ist Alexa Media Player in HA installiert?
- Ist die Shopping List aktiviert?
- Prüfe die Entity ID: `todo.alexa_shopping_list`

### Bestellungen werden nicht ausgeführt
- Ist `ORDER_DRY_RUN=false` gesetzt?
- Ist das Tageslimit erreicht? (`ORDER_MAX_PER_DAY`)
- **Lieferung noch ausstehend?** Prüfe `data/order_history.json` → `pending_deliveries`
  - Das System bestellt erst erneut wenn der Bestand in Grocy **gestiegen** ist (= Lieferung eingebucht)
  - Buche den Wareneingang in Grocy ein, dann wird automatisch wieder bestellt falls nötig

## 🤝 Beitragen

Beiträge sind willkommen! 

1. Fork das Repository
2. Erstelle einen Feature Branch (`git checkout -b feature/MeinFeature`)
3. Committe deine Änderungen (`git commit -am 'Neues Feature'`)
4. Push zum Branch (`git push origin feature/MeinFeature`)
5. Erstelle einen Pull Request

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE)

## 🙏 Danksagungen

- [Grocy](https://grocy.info/) - Fantastische Vorratsverwaltung
- [Home Assistant](https://www.home-assistant.io/) - Smart Home Zentrale
- [Alexa Media Player](https://github.com/custom-components/alexa_media_player) - HA Integration

---

**⚠️ Disclaimer:** Dieses Projekt ist nicht mit Amazon, Grocy oder Home Assistant affiliiert. Automatische Bestellungen erfolgen auf eigene Verantwortung. Teste immer zuerst mit `ORDER_DRY_RUN=true`!
