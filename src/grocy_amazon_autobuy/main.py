"""
Hauptmodul - Scheduler und Entry Point für Grocy Amazon AutoBuy.
"""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

import schedule

from .config import Settings, load_settings
from .grocy_client import GrocyClient, GrocyAPIError
from .homeassistant_client import HomeAssistantClient, HomeAssistantError
from .order_service import OrderService

# Logging Setup
logger = logging.getLogger("grocy_amazon_autobuy")


def setup_logging(log_level: str, log_file: Optional[str] = None):
    """
    Konfiguriert das Logging.
    
    Args:
        log_level: Log Level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optionaler Pfad zur Log-Datei
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    
    # File Handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Requests Logger reduzieren
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


class GrocyAutoOrderDaemon:
    """Daemon für automatische Bestandsprüfung und Bestellung."""

    def __init__(self, settings: Settings):
        """
        Initialisiert den Daemon.
        
        Args:
            settings: Konfiguration
        """
        self.settings = settings
        self.running = False
        
        # Clients initialisieren
        self.grocy = GrocyClient(settings.grocy)
        self.hass = HomeAssistantClient(settings.homeassistant)
        self.order_service = OrderService(
            hass_client=self.hass,
            order_settings=settings.order,
            history_file=Path("data/order_history.json")
        )

    def check_connections(self) -> bool:
        """
        Prüft alle Verbindungen.
        
        Returns:
            True wenn alle Verbindungen OK
        """
        logger.info("Prüfe Verbindungen...")
        
        # Grocy
        if not self.grocy.test_connection():
            logger.error("Grocy Verbindung fehlgeschlagen!")
            return False
        
        # Home Assistant
        if not self.hass.test_connection():
            logger.error("Home Assistant Verbindung fehlgeschlagen!")
            return False
        
        # Alexa verfügbar?
        if self.settings.order.mode == "voice_command":
            if not self.hass.check_alexa_available():
                logger.warning("Alexa Media Player nicht verfügbar")
        elif self.settings.order.mode == "shopping_list":
            if not self.hass.check_shopping_list_available():
                logger.warning("Alexa Shopping List nicht verfügbar")
        
        logger.info("Alle Verbindungen OK")
        return True

    def check_and_order(self):
        """
        Hauptlogik: Prüft Bestände und löst Bestellungen aus.
        """
        logger.info("=== Starte Bestandsprüfung ===")
        
        try:
            # Hole Produkte unter Mindestbestand
            products = self.grocy.get_products_below_min_stock()
            
            if not products:
                logger.info("Keine Produkte unter Mindestbestand gefunden")
                return
            
            logger.info(f"{len(products)} Produkt(e) unter Mindestbestand gefunden")
            
            # Verarbeite Bestellungen
            orders = self.order_service.process_products(products)
            
            # Zusammenfassung
            successful = [o for o in orders if o.status.value in ("added_to_list", "voice_ordered")]
            failed = [o for o in orders if o.status.value == "failed"]
            skipped = [o for o in orders if o.status.value == "skipped"]
            
            logger.info(
                f"Bestellungen: {len(successful)} erfolgreich, "
                f"{len(failed)} fehlgeschlagen, {len(skipped)} übersprungen"
            )
            
        except GrocyAPIError as e:
            logger.error(f"Grocy API Fehler: {e}")
        except HomeAssistantError as e:
            logger.error(f"Home Assistant Fehler: {e}")
        except Exception as e:
            logger.exception(f"Unerwarteter Fehler: {e}")

    def run_once(self):
        """Führt eine einzelne Prüfung durch."""
        if not self.check_connections():
            sys.exit(1)
        
        self.check_and_order()

    def run_daemon(self):
        """Startet den Daemon mit Scheduler."""
        if not self.check_connections():
            sys.exit(1)
        
        interval = self.settings.order.check_interval_minutes
        logger.info(f"Starte Daemon - Prüfintervall: {interval} Minuten")
        
        # Signal Handler für sauberes Beenden
        def signal_handler(signum, frame):
            logger.info("Signal empfangen, beende...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Scheduler konfigurieren
        schedule.every(interval).minutes.do(self.check_and_order)
        
        # Erste Prüfung sofort
        self.check_and_order()
        
        # Hauptschleife
        self.running = True
        while self.running:
            schedule.run_pending()
            time.sleep(10)
        
        logger.info("Daemon beendet")

    def get_status(self) -> dict:
        """
        Gibt den aktuellen Status zurück.
        
        Returns:
            Status Dictionary
        """
        return {
            "daemon_running": self.running,
            "grocy_connected": self.grocy.test_connection(),
            "hass_connected": self.hass.test_connection(),
            "order_status": self.order_service.get_status_summary(),
            "settings": {
                "mode": self.settings.order.mode,
                "dry_run": self.settings.order.dry_run,
                "interval_minutes": self.settings.order.check_interval_minutes,
            }
        }


def main():
    """Haupteinstiegspunkt."""
    parser = argparse.ArgumentParser(
        description="Grocy Amazon AutoBuy - Automatische Nachbestellung via Alexa",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  grocy-autobuy --check          Einmalige Bestandsprüfung
  grocy-autobuy --daemon         Daemon-Modus mit Scheduler
  grocy-autobuy --status         Status anzeigen
  grocy-autobuy --test           Verbindungstest
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        default=Path("config.yaml"),
        help="Pfad zur Konfigurationsdatei (Standard: config.yaml)"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Einmalige Bestandsprüfung durchführen"
    )
    
    parser.add_argument(
        "--daemon", "-d",
        action="store_true",
        help="Als Daemon mit Scheduler laufen"
    )
    
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Nur Verbindungen testen"
    )
    
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Status anzeigen"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Testmodus - keine echten Bestellungen"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Debug-Ausgabe aktivieren"
    )
    
    args = parser.parse_args()
    
    # Lade Konfiguration
    config_path = args.config if args.config.exists() else None
    settings = load_settings(config_path)
    
    # Override: Dry Run
    if args.dry_run:
        settings.order.dry_run = True
    
    # Override: Log Level
    if args.verbose:
        settings.log_level = "DEBUG"
    
    # Logging Setup
    setup_logging(settings.log_level, settings.log_file)
    
    # Banner
    logger.info("=" * 50)
    logger.info("  Grocy Amazon AutoBuy")
    logger.info(f"  Modus: {settings.order.mode}")
    logger.info(f"  Dry Run: {settings.order.dry_run}")
    logger.info("=" * 50)
    
    # Daemon erstellen
    daemon = GrocyAutoOrderDaemon(settings)
    
    # Aktion ausführen
    if args.test:
        success = daemon.check_connections()
        sys.exit(0 if success else 1)
    
    elif args.status:
        import json
        status = daemon.get_status()
        print(json.dumps(status, indent=2, default=str))
    
    elif args.daemon:
        daemon.run_daemon()
    
    else:
        # Standard: Einmalige Prüfung
        daemon.run_once()


if __name__ == "__main__":
    main()
