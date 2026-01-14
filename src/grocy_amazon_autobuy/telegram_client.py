"""
Telegram Bot Client für Benachrichtigungen.

Sendet klickbare Links direkt an Telegram.
"""

import logging
from typing import Optional

import requests

from .config import TelegramSettings

logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Fehler bei Telegram API Aufrufen."""
    pass


class TelegramClient:
    """Client für die Telegram Bot API."""

    def __init__(self, settings: TelegramSettings):
        """
        Initialisiert den Telegram Client.
        
        Args:
            settings: Telegram Konfiguration
        """
        self.enabled = settings.enabled
        self.bot_token = settings.bot_token
        self.chat_id = settings.chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(
        self, 
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False
    ) -> bool:
        """
        Sendet eine Nachricht über Telegram.
        
        Args:
            text: Nachrichtentext (kann HTML enthalten)
            parse_mode: Parse-Modus (HTML oder Markdown)
            disable_web_page_preview: Link-Vorschau deaktivieren
            
        Returns:
            True wenn erfolgreich
        """
        if not self.enabled:
            logger.debug("Telegram deaktiviert, überspringe Nachricht")
            return True
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram nicht konfiguriert (Token oder Chat ID fehlt)")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                logger.info("Telegram Nachricht gesendet")
                return True
            else:
                logger.error(f"Telegram Fehler: {result.get('description')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API Fehler: {e}")
            return False

    def send_order_notification(
        self,
        product_name: str,
        quantity: int,
        asin: str,
        current_stock: float,
        min_stock: float,
        unit: str,
        cart_url: str
    ) -> bool:
        """
        Sendet eine Bestell-Benachrichtigung mit klickbarem Link.
        
        Args:
            product_name: Produktname
            quantity: Bestellmenge
            asin: Amazon ASIN
            current_stock: Aktueller Bestand
            min_stock: Mindestbestand
            unit: Einheit
            cart_url: Amazon Warenkorb URL
            
        Returns:
            True wenn erfolgreich
        """
        # Formatiere HTML-Nachricht mit klickbarem Link
        message = (
            f"🛒 <b>Amazon Nachbestellung</b>\n\n"
            f"<b>{product_name}</b>\n"
            f"Menge: {quantity}x\n"
            f"ASIN: <code>{asin}</code>\n\n"
            f"📊 Bestand: {current_stock}/{min_stock} {unit}\n\n"
            f"👉 <a href=\"{cart_url}\">In den Warenkorb legen</a>"
        )
        
        return self.send_message(message)

    def send_test_message(self) -> bool:
        """
        Sendet eine Test-Nachricht.
        
        Returns:
            True wenn erfolgreich
        """
        return self.send_message(
            "✅ <b>Grocy Amazon AutoBuy</b>\n\n"
            "Telegram-Verbindung erfolgreich!"
        )

    def test_connection(self) -> bool:
        """
        Testet die Verbindung zu Telegram.
        
        Returns:
            True wenn Verbindung erfolgreich
        """
        if not self.enabled:
            logger.info("Telegram deaktiviert")
            return True
        
        if not self.bot_token:
            logger.warning("Telegram Bot Token nicht konfiguriert")
            return False
        
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                bot_name = result.get("result", {}).get("username", "Unknown")
                logger.info(f"Telegram Verbindung erfolgreich (Bot: @{bot_name})")
                return True
            else:
                logger.error(f"Telegram Verbindungstest fehlgeschlagen: {result.get('description')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram Verbindungstest fehlgeschlagen: {e}")
            return False
