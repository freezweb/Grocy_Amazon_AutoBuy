"""
Amazon Order Service - Orchestriert die Bestellungen über verschiedene Kanäle.

Unterstützte Bestellmodi:
1. cart_link - Sendet Benachrichtigung mit direktem Amazon-Warenkorb-Link (EMPFOHLEN)
2. shopping_list - Fügt Artikel zur Alexa Einkaufsliste hinzu
3. voice_command - Sendet Sprachbefehle an Alexa (eingeschränkt)
4. notify_only - Nur Benachrichtigungen, keine automatische Bestellung
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import OrderSettings, TelegramSettings
from .homeassistant_client import HomeAssistantClient, HomeAssistantError
from .telegram_client import TelegramClient
from .models import OrderHistory, OrderRequest, OrderStatus, Product

logger = logging.getLogger(__name__)


class OrderService:
    """Service für die Verwaltung und Ausführung von Amazon-Bestellungen."""

    def __init__(
        self,
        hass_client: HomeAssistantClient,
        order_settings: OrderSettings,
        history_file: Optional[Path] = None,
        telegram_client: Optional[TelegramClient] = None
    ):
        """
        Initialisiert den Order Service.
        
        Args:
            hass_client: Home Assistant Client
            order_settings: Bestellungs-Konfiguration
            history_file: Pfad zur History-Datei (optional)
            telegram_client: Telegram Client für Benachrichtigungen (optional)
        """
        self.hass = hass_client
        self.settings = order_settings
        self.history_file = history_file or Path("order_history.json")
        self.history = self._load_history()
        self.telegram = telegram_client

    def _load_history(self) -> OrderHistory:
        """Lädt den Bestellverlauf aus der Datei."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    history = OrderHistory()
                    
                    # Lade ausstehende Lieferungen (WICHTIG für Duplikatschutz!)
                    history.pending_deliveries = data.get("pending_deliveries", {})
                    
                    logger.info(
                        f"History geladen: {len(history.pending_deliveries)} ausstehende Lieferungen"
                    )
                    return history
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Konnte History nicht laden: {e}")
        return OrderHistory()

    def _save_history(self):
        """Speichert den Bestellverlauf."""
        try:
            # Stelle sicher, dass das Verzeichnis existiert
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "orders": [
                    {
                        "asin": o.asin,
                        "product_name": o.product.name,
                        "quantity": o.quantity,
                        "status": o.status.value,
                        "created_at": o.created_at.isoformat(),
                        "processed_at": o.processed_at.isoformat() if o.processed_at else None,
                        "error_message": o.error_message,
                    }
                    for o in self.history.orders[-100:]  # Letzte 100 behalten
                ],
                # WICHTIG: Speichere ausstehende Lieferungen
                "pending_deliveries": self.history.pending_deliveries,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.debug(
                f"History gespeichert: {len(self.history.pending_deliveries)} ausstehende Lieferungen"
            )
        except IOError as e:
            logger.error(f"Konnte History nicht speichern: {e}")

    def can_place_order(self, product: Product) -> tuple[bool, str]:
        """
        Prüft ob eine Bestellung aufgegeben werden kann.
        
        Sicherheitsprüfungen:
        1. Tageslimit nicht überschritten
        2. Keine ausstehende Lieferung (Bestand muss erst steigen)
        3. Produkt hat gültige ASIN
        
        Args:
            product: Das zu bestellende Produkt
            
        Returns:
            Tuple (erlaubt, grund)
        """
        # Prüfe Tageslimit
        orders_today = self.history.count_orders_today()
        if orders_today >= self.settings.max_orders_per_day:
            return False, f"Tageslimit erreicht ({orders_today}/{self.settings.max_orders_per_day})"
        
        # WICHTIG: Prüfe ob Lieferung noch aussteht
        # Erst wieder bestellen wenn Bestand in Grocy gestiegen ist (= Lieferung eingebucht)
        if self.history.is_delivery_pending(product.amazon_asin, product.stock_amount):
            return False, (
                f"Lieferung noch ausstehend (bestellt bei Bestand {self.history.pending_deliveries.get(product.amazon_asin, '?')}, "
                f"aktuell {product.stock_amount}). Erst nach Wareneingang erneut bestellen."
            )
        
        # Prüfe ASIN
        if not product.amazon_asin:
            return False, "Keine Amazon ASIN hinterlegt"
        
        return True, "OK"

    def create_shopping_list_item(self, product: Product) -> str:
        """
        Erstellt einen Einkaufslisten-Eintrag für Alexa.
        
        Das Format ist so gestaltet, dass Alexa den Artikel
        bei Amazon finden kann.
        
        Args:
            product: Das Produkt
            
        Returns:
            Formatierter Einkaufslisten-Text
        """
        # Format: "Produktname (ASIN: xyz)" oder nur Produktname
        # Alexa versteht natürliche Sprache besser
        if product.packages_to_order > 1:
            return f"{product.packages_to_order}x {product.name}"
        return product.name

    def process_order(self, product: Product) -> OrderRequest:
        """
        Verarbeitet eine Bestellung für ein Produkt.
        
        Args:
            product: Das zu bestellende Produkt
            
        Returns:
            OrderRequest mit Status
        """
        order = OrderRequest(
            product=product,
            quantity=product.packages_to_order,
            asin=product.amazon_asin
        )
        
        # Prüfe ob Bestellung erlaubt
        can_order, reason = self.can_place_order(product)
        if not can_order:
            logger.warning(f"Bestellung nicht möglich: {reason}")
            order.status = OrderStatus.SKIPPED
            order.error_message = reason
            return order
        
        # Dry Run Modus
        if self.settings.dry_run:
            logger.info(f"[DRY RUN] Würde bestellen: {product.get_order_description()}")
            order.status = OrderStatus.PENDING
            order.error_message = "Dry Run - keine echte Bestellung"
            self._notify_order(order, dry_run=True)
            return order
        
        # Führe Bestellung basierend auf Modus aus
        try:
            success = False
            
            if self.settings.mode == "cart_link":
                # Neuer Modus: Direkte Warenkorb-Links
                success = True
                order.status = OrderStatus.PENDING
                order.error_message = "Warenkorb-Link gesendet"
            
            elif self.settings.mode == "voice_order":
                success = self._order_via_voice(product)
                if success:
                    order.status = OrderStatus.VOICE_ORDERED
                    
            elif self.settings.mode == "shopping_list":
                success = self._order_via_shopping_list(product)
                if success:
                    order.status = OrderStatus.ADDED_TO_LIST
                    
            elif self.settings.mode == "notify_only":
                success = True
                order.status = OrderStatus.PENDING
                order.error_message = "Nur Benachrichtigung (notify_only Modus)"
            
            if success:
                order.mark_success()
                
                # WICHTIG: Markiere als "Lieferung ausstehend"
                # Verhindert erneute Bestellung bis Wareneingang in Grocy gebucht
                self.history.mark_pending_delivery(
                    asin=product.amazon_asin,
                    stock_at_order=product.stock_amount
                )
                logger.info(
                    f"ASIN {product.amazon_asin} als 'Lieferung ausstehend' markiert "
                    f"(Bestand bei Bestellung: {product.stock_amount})"
                )
                
                self.history.add_order(order)
                self._save_history()
                self._notify_order(order)
            else:
                order.mark_failed("Bestellung fehlgeschlagen")
                self._notify_order(order, failed=True)
                
        except Exception as e:
            logger.exception(f"Fehler bei Bestellung: {e}")
            order.mark_failed(str(e))
            self._notify_order(order, failed=True)
        
        return order

    def _order_via_shopping_list(self, product: Product) -> bool:
        """
        Fügt Produkt zur Alexa Einkaufsliste hinzu.
        
        Args:
            product: Das Produkt
            
        Returns:
            True wenn erfolgreich
        """
        item_text = self.create_shopping_list_item(product)
        logger.info(f"Füge zur Alexa Einkaufsliste hinzu: {item_text}")
        
        return self.hass.add_to_alexa_shopping_list(item_text)

    def _order_via_voice(self, product: Product) -> bool:
        """
        Bestellt via Alexa Sprachbefehl.
        
        VORAUSSETZUNG: In der Alexa App muss aktiviert sein:
        - Einstellungen → Konto → Spracheinkauf: AN
        - Bestätigungscode: AUS (oder 1-Click Bestellung aktiviert)
        
        Args:
            product: Das zu bestellende Produkt
            
        Returns:
            True wenn Befehl gesendet wurde
        """
        # Methode 1: Direkte ASIN-Bestellung (präziser)
        if product.amazon_asin and len(product.amazon_asin) == 10:
            logger.info(f"Versuche ASIN-Bestellung: {product.amazon_asin}")
            success = self.hass.order_by_asin(product.amazon_asin)
            if success:
                return True
        
        # Methode 2: Bestellung per Produktname
        logger.info(f"Versuche Namens-Bestellung: {product.name}")
        return self.hass.send_alexa_order_command(
            product_name=product.name,
            quantity=product.packages_to_order
        )

    def _create_amazon_cart_url(self, asin: str, quantity: int = 1) -> str:
        """
        Erstellt eine Amazon-URL, die das Produkt direkt zum Warenkorb hinzufügt.
        
        Args:
            asin: Amazon ASIN
            quantity: Anzahl
            
        Returns:
            URL zum Hinzufügen in den Warenkorb
        """
        # Amazon Cart Add URL - funktioniert für amazon.de
        # Format: https://www.amazon.de/gp/aws/cart/add.html?ASIN.1=XXX&Quantity.1=Y
        base_url = "https://www.amazon.de/gp/aws/cart/add.html"
        return f"{base_url}?ASIN.1={asin}&Quantity.1={quantity}"

    def _notify_order(
        self, 
        order: OrderRequest, 
        dry_run: bool = False,
        failed: bool = False
    ):
        """
        Sendet Benachrichtigung über Bestellung.
        
        Args:
            order: Die Bestellung
            dry_run: Ob es ein Dry Run war
            failed: Ob die Bestellung fehlgeschlagen ist
        """
        if not self.settings.notify_on_order:
            return
        
        product = order.product
        
        # Amazon Warenkorb-Link erstellen
        cart_url = self._create_amazon_cart_url(product.amazon_asin, order.quantity)
        
        if failed:
            title = "❌ Bestellung fehlgeschlagen"
            message = (
                f"Konnte {product.name} nicht bestellen.\n"
                f"Fehler: {order.error_message}"
            )
        elif dry_run:
            title = "🧪 Bestellung (Testmodus)"
            message = (
                f"Würde bestellen: {product.get_order_description()}\n"
                f"ASIN: {product.amazon_asin}\n"
                f"Bestand: {product.stock_amount}/{product.stock_min_amount} {product.qu_name}\n"
                f"Warenkorb-Link: {cart_url}"
            )
        else:
            title = "🛒 Amazon Bestellung"
            if self.settings.mode == "cart_link":
                message = (
                    f"Produkt unter Mindestbestand!\n"
                    f"{product.get_order_description()}\n\n"
                    f"👉 In den Warenkorb: {cart_url}"
                )
            elif self.settings.mode == "shopping_list":
                message = (
                    f"Zur Alexa Einkaufsliste hinzugefügt:\n"
                    f"{product.get_order_description()}\n"
                    f"Bestand: {product.stock_amount}/{product.stock_min_amount} {product.qu_name}"
                )
            else:
                message = (
                    f"Bestellung ausgelöst:\n"
                    f"{product.get_order_description()}\n"
                    f"ASIN: {product.amazon_asin}"
                )
        
        # Home Assistant Benachrichtigung
        try:
            self.hass.send_notification(
                title=title,
                message=message,
                service=self.settings.notification_service
            )
        except HomeAssistantError as e:
            logger.error(f"Home Assistant Benachrichtigung fehlgeschlagen: {e}")
        
        # Telegram Benachrichtigung (mit klickbarem Link und Buttons)
        if self.telegram and not failed:
            try:
                self.telegram.send_order_notification(
                    product_name=product.name,
                    product_id=product.id,
                    quantity=order.quantity,
                    asin=product.amazon_asin,
                    current_stock=product.stock_amount,
                    min_stock=product.stock_min_amount,
                    unit=product.amazon_order_unit or product.qu_name,
                    cart_url=cart_url
                )
            except Exception as e:
                logger.error(f"Telegram Benachrichtigung fehlgeschlagen: {e}")

    def process_products(self, products: list[Product]) -> list[OrderRequest]:
        """
        Verarbeitet eine Liste von Produkten.
        
        Args:
            products: Liste der zu bestellenden Produkte
            
        Returns:
            Liste der Bestellanfragen
        """
        orders = []
        
        for product in products:
            if not product.needs_reorder:
                continue
            
            logger.info(f"Verarbeite: {product.name} (ASIN: {product.amazon_asin})")
            order = self.process_order(product)
            orders.append(order)
        
        return orders

    def update_telegram_stocks(self, products: list[Product]):
        """
        Aktualisiert die Bestandsanzeige in Telegram für alle getrackten Produkte.
        
        Args:
            products: Liste aller Produkte mit aktuellem Bestand
        """
        if not self.telegram:
            return
        
        # Erstelle ein Mapping von ASIN zu aktuellem Bestand
        stock_by_asin = {
            p.amazon_asin: p.stock_amount 
            for p in products 
            if p.amazon_asin
        }
        
        # Aktualisiere alle getrackten Nachrichten
        for asin in list(self.telegram.tracked_messages.keys()):
            if asin in stock_by_asin:
                new_stock = stock_by_asin[asin]
                self.telegram.update_stock(asin, new_stock)

    def get_status_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung des aktuellen Status zurück.
        
        Returns:
            Status-Dictionary
        """
        orders_today = self.history.get_orders_today()
        
        return {
            "mode": self.settings.mode,
            "dry_run": self.settings.dry_run,
            "orders_today": len(orders_today),
            "max_orders_per_day": self.settings.max_orders_per_day,
            "successful_today": len([o for o in orders_today if o.status in (
                OrderStatus.ADDED_TO_LIST, 
                OrderStatus.VOICE_ORDERED,
                OrderStatus.CONFIRMED
            )]),
            "failed_today": len([o for o in orders_today if o.status == OrderStatus.FAILED]),
        }
