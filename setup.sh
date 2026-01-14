#!/bin/bash

# ============================================
# Grocy Amazon AutoBuy - Interaktives Setup
# ============================================
# Dieses Script führt dich durch die komplette
# Installation und Konfiguration.
# ============================================

set -e

# Farben für bessere Lesbarkeit
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Banner
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║   🛒 Grocy Amazon AutoBuy - Setup                         ║"
echo "║                                                           ║"
echo "║   Automatische Amazon-Nachbestellung via Alexa            ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Hilfsfunktionen
print_step() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}▶ $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✖ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✔ $1${NC}"
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    
    if [[ "$default" == "y" ]]; then
        prompt="$prompt [J/n]: "
    else
        prompt="$prompt [j/N]: "
    fi
    
    read -p "$prompt" answer
    answer=${answer:-$default}
    
    [[ "$answer" =~ ^[JjYy]$ ]]
}

ask_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [[ -n "$default" ]]; then
        read -p "$prompt [$default]: " input
        input=${input:-$default}
    else
        read -p "$prompt: " input
    fi
    
    eval "$var_name='$input'"
}

ask_password() {
    local prompt="$1"
    local var_name="$2"
    
    read -sp "$prompt: " input
    echo ""
    eval "$var_name='$input'"
}

# Docker Compose Befehl ermitteln
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE=""
    fi
}

# ============================================
# Schritt 1: System-Voraussetzungen prüfen
# ============================================
print_step "Schritt 1/6: System-Voraussetzungen prüfen"

NEED_INSTALL=()

# Git prüfen
if command -v git &> /dev/null; then
    print_success "Git ist installiert: $(git --version)"
else
    print_warning "Git ist nicht installiert"
    NEED_INSTALL+=("git")
fi

# Docker prüfen
if command -v docker &> /dev/null; then
    print_success "Docker ist installiert: $(docker --version)"
else
    print_warning "Docker ist nicht installiert"
    NEED_INSTALL+=("docker.io")
fi

# Docker Compose prüfen
detect_docker_compose
if [[ -n "$DOCKER_COMPOSE" ]]; then
    print_success "Docker Compose gefunden: $DOCKER_COMPOSE"
else
    print_warning "Docker Compose ist nicht installiert"
    NEED_INSTALL+=("docker-compose")
fi

# Installation falls nötig
if [[ ${#NEED_INSTALL[@]} -gt 0 ]]; then
    echo ""
    print_info "Folgende Pakete müssen installiert werden: ${NEED_INSTALL[*]}"
    
    if ask_yes_no "Sollen die fehlenden Pakete jetzt installiert werden?"; then
        echo ""
        print_info "Installiere Pakete..."
        sudo apt update
        sudo apt install -y "${NEED_INSTALL[@]}"
        
        # Docker Gruppe
        if [[ " ${NEED_INSTALL[*]} " =~ " docker.io " ]]; then
            print_info "Füge Benutzer zur Docker-Gruppe hinzu..."
            sudo usermod -aG docker "$USER"
            print_warning "Du musst dich neu einloggen oder 'newgrp docker' ausführen!"
        fi
        
        # Nochmal prüfen
        detect_docker_compose
        print_success "Installation abgeschlossen!"
    else
        print_error "Ohne diese Pakete kann das Setup nicht fortgesetzt werden."
        exit 1
    fi
fi

# ============================================
# Schritt 2: Grocy Konfiguration
# ============================================
print_step "Schritt 2/6: Grocy Konfiguration"

print_info "Du findest den API-Key in Grocy unter:"
print_info "Einstellungen → API-Schlüssel verwalten → Neuen Schlüssel erstellen"
echo ""

ask_input "Grocy URL (z.B. http://192.168.1.100:9283)" "http://localhost:9283" GROCY_URL
ask_input "Grocy API-Key" "" GROCY_API_KEY

if [[ -z "$GROCY_API_KEY" ]]; then
    print_error "API-Key ist erforderlich!"
    exit 1
fi

# Benutzerdefinierte Felder
echo ""
print_info "In Grocy müssen zwei benutzerdefinierte Felder für Produkte existieren."
print_info "Standard: 'Amazon_ASIN' und 'Amazon_bestelleinheiten'"
echo ""

if ask_yes_no "Verwendest du die Standard-Feldnamen?" "y"; then
    GROCY_ASIN_FIELD="Amazon_ASIN"
    GROCY_ORDER_UNITS_FIELD="Amazon_bestelleinheiten"
else
    ask_input "Name des ASIN-Feldes" "Amazon_ASIN" GROCY_ASIN_FIELD
    ask_input "Name des Bestelleinheiten-Feldes" "Amazon_bestelleinheiten" GROCY_ORDER_UNITS_FIELD
fi

print_success "Grocy Konfiguration abgeschlossen!"

# ============================================
# Schritt 3: Home Assistant Konfiguration
# ============================================
print_step "Schritt 3/6: Home Assistant Konfiguration"

print_info "Du findest den Token in Home Assistant unter:"
print_info "Profil (unten links) → Langlebige Zugriffstokens → Token erstellen"
echo ""

ask_input "Home Assistant URL (z.B. http://192.168.1.100:8123)" "http://homeassistant.local:8123" HASS_URL
ask_password "Home Assistant Token (wird nicht angezeigt)" HASS_TOKEN

if [[ -z "$HASS_TOKEN" ]]; then
    print_error "Token ist erforderlich!"
    exit 1
fi

# Alexa Entities
echo ""
print_info "Alexa Media Player Entity IDs findest du in Home Assistant unter:"
print_info "Entwicklerwerkzeuge → Zustände → Nach 'media_player.echo' suchen"
echo ""

ask_input "Alexa Media Player Entity ID" "media_player.echo_dot" HASS_ALEXA_ENTITY_ID
ask_input "Alexa Shopping List Entity ID" "todo.alexa_shopping_list" HASS_SHOPPING_LIST_ENTITY

print_success "Home Assistant Konfiguration abgeschlossen!"

# ============================================
# Schritt 4: Bestellmodus wählen
# ============================================
print_step "Schritt 4/6: Bestellmodus wählen"

echo -e "${CYAN}Verfügbare Modi:${NC}"
echo ""
echo "  1) voice_order    - Vollautomatisch! Alexa bestellt direkt bei Amazon"
echo "                      (Erfordert: Spracheinkauf in Alexa App aktiviert)"
echo ""
echo "  2) shopping_list  - Fügt Artikel zur Alexa Einkaufsliste hinzu"
echo "                      (Du sagst dann 'Alexa, bestelle meine Einkaufsliste')"
echo ""
echo "  3) notify_only    - Nur Benachrichtigungen, keine automatische Bestellung"
echo "                      (Für Tests oder manuelle Kontrolle)"
echo ""

while true; do
    read -p "Wähle einen Modus (1/2/3) [1]: " mode_choice
    mode_choice=${mode_choice:-1}
    
    case $mode_choice in
        1) ORDER_MODE="voice_order"; break ;;
        2) ORDER_MODE="shopping_list"; break ;;
        3) ORDER_MODE="notify_only"; break ;;
        *) print_error "Ungültige Auswahl, bitte 1, 2 oder 3 eingeben." ;;
    esac
done

print_success "Modus gewählt: $ORDER_MODE"

# Weitere Einstellungen
echo ""
ask_input "Prüfintervall in Minuten" "60" ORDER_CHECK_INTERVAL
ask_input "Maximale Bestellungen pro Tag" "10" ORDER_MAX_PER_DAY

# Dry Run?
echo ""
if ask_yes_no "Testmodus aktivieren (keine echten Bestellungen)?" "y"; then
    ORDER_DRY_RUN="true"
    print_info "Testmodus aktiviert - keine echten Bestellungen!"
else
    ORDER_DRY_RUN="false"
    print_warning "ACHTUNG: Echte Bestellungen werden ausgeführt!"
fi

# Benachrichtigungen
echo ""
if ask_yes_no "Benachrichtigungen bei Bestellungen aktivieren?" "y"; then
    ORDER_NOTIFY="true"
    ask_input "Notification Service" "notify.persistent_notification" ORDER_NOTIFICATION_SERVICE
else
    ORDER_NOTIFY="false"
    ORDER_NOTIFICATION_SERVICE="notify.persistent_notification"
fi

# ============================================
# Schritt 5: Konfiguration speichern
# ============================================
print_step "Schritt 5/6: Konfiguration speichern"

# .env Datei erstellen
cat > .env << EOF
# ============================================
# Grocy Amazon AutoBuy - Konfiguration
# Erstellt am: $(date)
# ============================================

# ---- Grocy ----
GROCY_URL=$GROCY_URL
GROCY_API_KEY=$GROCY_API_KEY
GROCY_ASIN_FIELD=$GROCY_ASIN_FIELD
GROCY_ORDER_UNITS_FIELD=$GROCY_ORDER_UNITS_FIELD

# ---- Home Assistant ----
HASS_URL=$HASS_URL
HASS_TOKEN=$HASS_TOKEN
HASS_ALEXA_ENTITY_ID=$HASS_ALEXA_ENTITY_ID
HASS_USE_SHOPPING_LIST=true
HASS_SHOPPING_LIST_ENTITY=$HASS_SHOPPING_LIST_ENTITY

# ---- Bestellung ----
ORDER_MODE=$ORDER_MODE
ORDER_CHECK_INTERVAL=$ORDER_CHECK_INTERVAL
ORDER_MAX_PER_DAY=$ORDER_MAX_PER_DAY
ORDER_DRY_RUN=$ORDER_DRY_RUN
ORDER_NOTIFY=$ORDER_NOTIFY
ORDER_NOTIFICATION_SERVICE=$ORDER_NOTIFICATION_SERVICE

# ---- Logging ----
LOG_LEVEL=INFO
EOF

print_success ".env Datei erstellt!"

# Berechtigungen setzen (Token schützen)
chmod 600 .env
print_info ".env Datei-Berechtigungen auf 600 gesetzt (nur Besitzer kann lesen)"

# ============================================
# Schritt 6: Container starten
# ============================================
print_step "Schritt 6/6: Container starten"

# Docker Compose nochmal erkennen (falls gerade installiert)
detect_docker_compose

if [[ -z "$DOCKER_COMPOSE" ]]; then
    print_error "Docker Compose konnte nicht gefunden werden!"
    print_info "Versuche 'newgrp docker' und starte das Setup erneut."
    exit 1
fi

print_info "Verwende: $DOCKER_COMPOSE"
echo ""

if ask_yes_no "Container jetzt bauen und starten?" "y"; then
    echo ""
    print_info "Baue Container... (kann beim ersten Mal etwas dauern)"
    $DOCKER_COMPOSE build
    
    echo ""
    print_info "Starte Container..."
    $DOCKER_COMPOSE up -d
    
    echo ""
    print_success "Container gestartet!"
    
    # Status anzeigen
    echo ""
    print_info "Container Status:"
    $DOCKER_COMPOSE ps
else
    print_info "Du kannst den Container später mit '$DOCKER_COMPOSE up -d' starten."
fi

# ============================================
# Fertig!
# ============================================
echo ""
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║   ✅ Setup abgeschlossen!                                 ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}Nächste Schritte:${NC}"
echo ""
echo "  1. Logs prüfen:"
echo "     $DOCKER_COMPOSE logs -f"
echo ""
echo "  2. Verbindungen testen:"
echo "     $DOCKER_COMPOSE exec grocy-autobuy grocy-autobuy --test"
echo ""
echo "  3. Testlauf durchführen:"
echo "     $DOCKER_COMPOSE exec grocy-autobuy grocy-autobuy --check --dry-run"
echo ""

if [[ "$ORDER_DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}⚠ HINWEIS: Der Testmodus ist aktiviert!${NC}"
    echo "  Um echte Bestellungen zu aktivieren:"
    echo "  1. nano .env"
    echo "  2. ORDER_DRY_RUN=false setzen"
    echo "  3. $DOCKER_COMPOSE restart"
    echo ""
fi

echo -e "${CYAN}Wichtige Befehle:${NC}"
echo ""
echo "  $DOCKER_COMPOSE logs -f      # Logs anzeigen"
echo "  $DOCKER_COMPOSE restart      # Neustarten"
echo "  $DOCKER_COMPOSE stop         # Stoppen"
echo "  $DOCKER_COMPOSE down         # Beenden und entfernen"
echo ""

print_info "Dokumentation: https://github.com/freezweb/Grocy_Amazon_AutoBuy"
echo ""
