# Contributing to Grocy Amazon AutoBuy

Vielen Dank für dein Interesse an diesem Projekt! 🎉

## Wie du beitragen kannst

### 🐛 Bugs melden

1. Prüfe zuerst, ob der Bug bereits gemeldet wurde
2. Erstelle ein neues Issue mit:
   - Klare Beschreibung des Problems
   - Schritte zur Reproduktion
   - Erwartetes vs. tatsächliches Verhalten
   - Logs (mit `--verbose` Flag)
   - Deine Konfiguration (ohne sensible Daten!)

### 💡 Feature-Vorschläge

1. Erstelle ein Issue mit dem Label "enhancement"
2. Beschreibe das Feature und den Nutzen
3. Gerne auch Implementierungsvorschläge

### 🔧 Code beitragen

1. **Fork** das Repository
2. **Clone** deinen Fork: `git clone https://github.com/DEIN-USERNAME/Grocy_Amazon_AutoBuy.git`
3. **Branch** erstellen: `git checkout -b feature/mein-feature`
4. **Entwicklungsumgebung** einrichten:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[dev]"
   ```
5. **Änderungen** machen
6. **Tests** schreiben und ausführen: `pytest`
7. **Linting**: `ruff check src/`
8. **Commit**: `git commit -am 'Beschreibung der Änderung'`
9. **Push**: `git push origin feature/mein-feature`
10. **Pull Request** erstellen

## Code-Richtlinien

- Python 3.10+ Syntax
- Type Hints verwenden
- Docstrings für Funktionen und Klassen
- Tests für neue Funktionen
- Ruff für Linting
- Black für Formatierung (optional)

## Projekt-Struktur

```
Grocy_Amazon_AutoBuy/
├── src/grocy_amazon_autobuy/
│   ├── __init__.py          # Package init
│   ├── config.py             # Konfiguration
│   ├── models.py             # Datenmodelle
│   ├── grocy_client.py       # Grocy API
│   ├── homeassistant_client.py  # Home Assistant API
│   ├── order_service.py      # Bestelllogik
│   └── main.py               # Entry Point
├── tests/                    # Tests
├── homeassistant/           # HA Integration
└── ...
```

## Fragen?

Erstelle ein Issue oder kontaktiere die Maintainer!
