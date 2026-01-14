"""
Telegram Bot Client mit interaktiven Buttons.

Features:
- Klickbare Amazon Warenkorb-Links
- Inline Keyboard Buttons (Bestellt, Geliefert)
- Nachrichten aktualisieren (Bestand ändern)
- Nachrichten löschen (nach Lieferung)
- Callback Query Handling
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import requests

from .config import TelegramSettings

logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Fehler bei Telegram API Aufrufen."""
    pass


@dataclass
class TrackedMessage:
    """Informationen über eine gesendete Telegram-Nachricht."""
    message_id: int
    chat_id: str
    product_id: int
    product_name: str
    asin: str
    quantity: int
    unit: str
    cart_url: str
    current_stock: float
    min_stock: float
    created_at: datetime = field(default_factory=datetime.now)
    ordered: bool = False
    ordered_at: Optional[datetime] = None
    delivered: bool = False
    delivered_at: Optional[datetime] = None


class TelegramClient:
    """Client für die Telegram Bot API mit interaktiven Features."""

    # Callback Data Prefixes
    CALLBACK_ORDERED = "ordered:"
    CALLBACK_DELIVERED = "delivered:"
    CALLBACK_CANCEL = "cancel:"

    def __init__(self, settings: TelegramSettings, data_dir: Path = None):
        """
        Initialisiert den Telegram Client.
        
        Args:
            settings: Telegram Konfiguration
            data_dir: Verzeichnis für persistente Daten
        """
        self.enabled = settings.enabled
        self.bot_token = settings.bot_token
        self.chat_id = settings.chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Tracking der gesendeten Nachrichten
        self.data_dir = data_dir or Path("data")
        self.messages_file = self.data_dir / "telegram_messages.json"
        self.tracked_messages: dict[str, TrackedMessage] = {}  # asin -> TrackedMessage
        
        # Polling für Callbacks
        self._polling_thread: Optional[threading.Thread] = None
        self._polling_active = False
        self._last_update_id = 0
        
        # Callbacks für externe Aktionen
        self.on_ordered_callback: Optional[Callable[[str, int], None]] = None
        self.on_delivered_callback: Optional[Callable[[str, int], None]] = None
        
        # Lade gespeicherte Nachrichten
        self._load_tracked_messages()

    def _load_tracked_messages(self):
        """Lädt gespeicherte Nachrichten aus Datei."""
        if self.messages_file.exists():
            try:
                with open(self.messages_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for asin, msg_data in data.items():
                        # Konvertiere datetime strings zurück
                        msg_data["created_at"] = datetime.fromisoformat(msg_data["created_at"])
                        if msg_data.get("ordered_at"):
                            msg_data["ordered_at"] = datetime.fromisoformat(msg_data["ordered_at"])
                        if msg_data.get("delivered_at"):
                            msg_data["delivered_at"] = datetime.fromisoformat(msg_data["delivered_at"])
                        self.tracked_messages[asin] = TrackedMessage(**msg_data)
                logger.info(f"Geladene Telegram-Nachrichten: {len(self.tracked_messages)}")
            except Exception as e:
                logger.error(f"Fehler beim Laden der Telegram-Nachrichten: {e}")

    def _save_tracked_messages(self):
        """Speichert Nachrichten in Datei."""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            for asin, msg in self.tracked_messages.items():
                msg_dict = {
                    "message_id": msg.message_id,
                    "chat_id": msg.chat_id,
                    "product_id": msg.product_id,
                    "product_name": msg.product_name,
                    "asin": msg.asin,
                    "quantity": msg.quantity,
                    "unit": msg.unit,
                    "cart_url": msg.cart_url,
                    "current_stock": msg.current_stock,
                    "min_stock": msg.min_stock,
                    "created_at": msg.created_at.isoformat(),
                    "ordered": msg.ordered,
                    "ordered_at": msg.ordered_at.isoformat() if msg.ordered_at else None,
                    "delivered": msg.delivered,
                    "delivered_at": msg.delivered_at.isoformat() if msg.delivered_at else None,
                }
                data[asin] = msg_dict
            
            with open(self.messages_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Telegram-Nachrichten: {e}")

    def _create_inline_keyboard(self, asin: str, ordered: bool = False) -> dict:
        """
        Erstellt Inline Keyboard Buttons.
        
        Args:
            asin: Amazon ASIN für Callback
            ordered: Ob bereits bestellt wurde
            
        Returns:
            Inline Keyboard Markup
        """
        if ordered:
            # Nach Bestellung: Geliefert-Button
            buttons = [[
                {"text": "✅ Bestellt", "callback_data": "noop"},
                {"text": "📦 Geliefert", "callback_data": f"{self.CALLBACK_DELIVERED}{asin}"}
            ]]
        else:
            # Vor Bestellung: Bestellt-Button
            buttons = [[
                {"text": "🛒 Bestellt", "callback_data": f"{self.CALLBACK_ORDERED}{asin}"},
                {"text": "❌ Abbrechen", "callback_data": f"{self.CALLBACK_CANCEL}{asin}"}
            ]]
        
        return {"inline_keyboard": buttons}

    def _format_order_message(
        self,
        product_name: str,
        quantity: int,
        asin: str,
        current_stock: float,
        min_stock: float,
        unit: str,
        cart_url: str,
        ordered: bool = False,
        ordered_at: Optional[datetime] = None
    ) -> str:
        """Formatiert die Bestell-Nachricht."""
        status = ""
        if ordered:
            status = f"\n\n✅ <i>Bestellt am {ordered_at.strftime('%d.%m.%Y %H:%M') if ordered_at else 'unbekannt'}</i>"
        
        return (
            f"🛒 <b>Amazon Nachbestellung</b>\n\n"
            f"<b>{product_name}</b>\n"
            f"Menge: {quantity}x {unit}\n"
            f"ASIN: <code>{asin}</code>\n\n"
            f"📊 Bestand: <b>{current_stock}/{min_stock}</b> {unit}"
            f"{status}\n\n"
            f"👉 <a href=\"{cart_url}\">In den Warenkorb legen</a>"
        )

    def send_message(
        self, 
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
        reply_markup: dict = None
    ) -> Optional[int]:
        """
        Sendet eine Nachricht über Telegram.
        
        Args:
            text: Nachrichtentext (kann HTML enthalten)
            parse_mode: Parse-Modus (HTML oder Markdown)
            disable_web_page_preview: Link-Vorschau deaktivieren
            reply_markup: Inline Keyboard Markup
            
        Returns:
            Message ID wenn erfolgreich, None sonst
        """
        if not self.enabled:
            logger.debug("Telegram deaktiviert, überspringe Nachricht")
            return None
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram nicht konfiguriert (Token oder Chat ID fehlt)")
            return None
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }
            
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get("ok"):
                message_id = result.get("result", {}).get("message_id")
                logger.info(f"Telegram Nachricht gesendet (ID: {message_id})")
                return message_id
            else:
                logger.error(f"Telegram Fehler: {result.get('description')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram API Fehler: {e}")
            return None

    def edit_message(
        self,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict = None
    ) -> bool:
        """
        Bearbeitet eine bestehende Nachricht.
        
        Args:
            message_id: ID der zu bearbeitenden Nachricht
            text: Neuer Nachrichtentext
            parse_mode: Parse-Modus
            reply_markup: Neues Inline Keyboard
            
        Returns:
            True wenn erfolgreich
        """
        if not self.enabled:
            return True
        
        try:
            url = f"{self.base_url}/editMessageText"
            payload = {
                "chat_id": self.chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            if reply_markup:
                payload["reply_markup"] = reply_markup
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"Telegram Nachricht aktualisiert (ID: {message_id})")
                return True
            else:
                # Ignoriere "message is not modified" Fehler
                if "message is not modified" in result.get("description", ""):
                    return True
                logger.error(f"Telegram Edit Fehler: {result.get('description')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram Edit API Fehler: {e}")
            return False

    def delete_message(self, message_id: int) -> bool:
        """
        Löscht eine Nachricht.
        
        Args:
            message_id: ID der zu löschenden Nachricht
            
        Returns:
            True wenn erfolgreich
        """
        if not self.enabled:
            return True
        
        try:
            url = f"{self.base_url}/deleteMessage"
            payload = {
                "chat_id": self.chat_id,
                "message_id": message_id
            }
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"Telegram Nachricht gelöscht (ID: {message_id})")
                return True
            else:
                logger.error(f"Telegram Delete Fehler: {result.get('description')}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram Delete API Fehler: {e}")
            return False

    def answer_callback_query(self, callback_query_id: str, text: str = None) -> bool:
        """
        Beantwortet einen Callback Query (Button-Klick).
        
        Args:
            callback_query_id: ID des Callback Query
            text: Optionale Antwort-Nachricht (Toast)
            
        Returns:
            True wenn erfolgreich
        """
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            payload = {"callback_query_id": callback_query_id}
            if text:
                payload["text"] = text
            
            response = requests.post(url, json=payload, timeout=10)
            return response.json().get("ok", False)
        except Exception as e:
            logger.error(f"Callback Answer Fehler: {e}")
            return False

    def send_order_notification(
        self,
        product_name: str,
        product_id: int,
        quantity: int,
        asin: str,
        current_stock: float,
        min_stock: float,
        unit: str,
        cart_url: str
    ) -> bool:
        """
        Sendet eine Bestell-Benachrichtigung mit interaktiven Buttons.
        
        Args:
            product_name: Produktname
            product_id: Grocy Produkt-ID
            quantity: Bestellmenge
            asin: Amazon ASIN
            current_stock: Aktueller Bestand
            min_stock: Mindestbestand
            unit: Einheit
            cart_url: Amazon Warenkorb URL
            
        Returns:
            True wenn erfolgreich
        """
        # Prüfe ob bereits eine Nachricht für dieses Produkt existiert
        if asin in self.tracked_messages:
            existing = self.tracked_messages[asin]
            # Wenn bereits bestellt und noch nicht geliefert, nur Bestand aktualisieren
            if existing.ordered and not existing.delivered:
                return self.update_stock(asin, current_stock)
            # Wenn noch nicht bestellt, aktualisiere die bestehende Nachricht
            elif not existing.ordered:
                existing.current_stock = current_stock
                existing.quantity = quantity
                self._update_message_content(asin)
                return True
        
        # Neue Nachricht mit Buttons senden
        message_text = self._format_order_message(
            product_name=product_name,
            quantity=quantity,
            asin=asin,
            current_stock=current_stock,
            min_stock=min_stock,
            unit=unit,
            cart_url=cart_url
        )
        
        reply_markup = self._create_inline_keyboard(asin, ordered=False)
        message_id = self.send_message(message_text, reply_markup=reply_markup)
        
        if message_id:
            # Tracke die Nachricht
            self.tracked_messages[asin] = TrackedMessage(
                message_id=message_id,
                chat_id=self.chat_id,
                product_id=product_id,
                product_name=product_name,
                asin=asin,
                quantity=quantity,
                unit=unit,
                cart_url=cart_url,
                current_stock=current_stock,
                min_stock=min_stock
            )
            self._save_tracked_messages()
            return True
        
        return False

    def update_stock(self, asin: str, new_stock: float) -> bool:
        """
        Aktualisiert den angezeigten Bestand in einer Nachricht.
        
        Args:
            asin: Amazon ASIN des Produkts
            new_stock: Neuer Bestandswert
            
        Returns:
            True wenn erfolgreich
        """
        if asin not in self.tracked_messages:
            logger.warning(f"Keine Nachricht für ASIN {asin} gefunden")
            return False
        
        msg = self.tracked_messages[asin]
        
        # Nur aktualisieren wenn sich der Bestand geändert hat
        if msg.current_stock == new_stock:
            return True
        
        msg.current_stock = new_stock
        self._save_tracked_messages()
        
        return self._update_message_content(asin)

    def _update_message_content(self, asin: str) -> bool:
        """Aktualisiert den Inhalt einer Nachricht."""
        if asin not in self.tracked_messages:
            return False
        
        msg = self.tracked_messages[asin]
        
        message_text = self._format_order_message(
            product_name=msg.product_name,
            quantity=msg.quantity,
            asin=msg.asin,
            current_stock=msg.current_stock,
            min_stock=msg.min_stock,
            unit=msg.unit,
            cart_url=msg.cart_url,
            ordered=msg.ordered,
            ordered_at=msg.ordered_at
        )
        
        reply_markup = self._create_inline_keyboard(asin, ordered=msg.ordered)
        
        return self.edit_message(
            message_id=msg.message_id,
            text=message_text,
            reply_markup=reply_markup
        )

    def mark_as_ordered(self, asin: str) -> bool:
        """
        Markiert ein Produkt als bestellt.
        
        Args:
            asin: Amazon ASIN
            
        Returns:
            True wenn erfolgreich
        """
        if asin not in self.tracked_messages:
            logger.warning(f"Keine Nachricht für ASIN {asin} gefunden")
            return False
        
        msg = self.tracked_messages[asin]
        msg.ordered = True
        msg.ordered_at = datetime.now()
        self._save_tracked_messages()
        
        # Aktualisiere Nachricht mit neuem Status und Buttons
        success = self._update_message_content(asin)
        
        # Callback aufrufen
        if success and self.on_ordered_callback:
            try:
                self.on_ordered_callback(asin, msg.product_id)
            except Exception as e:
                logger.error(f"Ordered Callback Fehler: {e}")
        
        return success

    def mark_as_delivered(self, asin: str) -> bool:
        """
        Markiert ein Produkt als geliefert und löscht die Nachricht.
        
        Args:
            asin: Amazon ASIN
            
        Returns:
            True wenn erfolgreich
        """
        if asin not in self.tracked_messages:
            logger.warning(f"Keine Nachricht für ASIN {asin} gefunden")
            return False
        
        msg = self.tracked_messages[asin]
        msg.delivered = True
        msg.delivered_at = datetime.now()
        
        # Sende Bestätigung
        self.send_message(
            f"📦 <b>{msg.product_name}</b> wurde als geliefert markiert!\n"
            f"Menge: {msg.quantity}x {msg.unit}"
        )
        
        # Lösche die ursprüngliche Bestellnachricht
        self.delete_message(msg.message_id)
        
        # Callback aufrufen
        if self.on_delivered_callback:
            try:
                self.on_delivered_callback(asin, msg.product_id)
            except Exception as e:
                logger.error(f"Delivered Callback Fehler: {e}")
        
        # Entferne aus Tracking
        del self.tracked_messages[asin]
        self._save_tracked_messages()
        
        return True

    def cancel_order(self, asin: str) -> bool:
        """
        Bricht eine Bestellung ab und löscht die Nachricht.
        
        Args:
            asin: Amazon ASIN
            
        Returns:
            True wenn erfolgreich
        """
        if asin not in self.tracked_messages:
            return False
        
        msg = self.tracked_messages[asin]
        
        # Lösche die Nachricht
        self.delete_message(msg.message_id)
        
        # Entferne aus Tracking
        del self.tracked_messages[asin]
        self._save_tracked_messages()
        
        logger.info(f"Bestellung abgebrochen: {msg.product_name}")
        return True

    def _process_callback(self, callback_query: dict):
        """Verarbeitet einen Button-Klick (Callback Query)."""
        callback_id = callback_query.get("id")
        data = callback_query.get("data", "")
        
        logger.debug(f"Callback erhalten: {data}")
        
        if data.startswith(self.CALLBACK_ORDERED):
            asin = data[len(self.CALLBACK_ORDERED):]
            if self.mark_as_ordered(asin):
                self.answer_callback_query(callback_id, "✅ Als bestellt markiert!")
            else:
                self.answer_callback_query(callback_id, "❌ Fehler!")
        
        elif data.startswith(self.CALLBACK_DELIVERED):
            asin = data[len(self.CALLBACK_DELIVERED):]
            if self.mark_as_delivered(asin):
                self.answer_callback_query(callback_id, "📦 Als geliefert markiert!")
            else:
                self.answer_callback_query(callback_id, "❌ Fehler!")
        
        elif data.startswith(self.CALLBACK_CANCEL):
            asin = data[len(self.CALLBACK_CANCEL):]
            if self.cancel_order(asin):
                self.answer_callback_query(callback_id, "❌ Bestellung abgebrochen")
            else:
                self.answer_callback_query(callback_id, "❌ Fehler!")
        
        elif data == "noop":
            self.answer_callback_query(callback_id)

    def start_polling(self):
        """Startet das Polling für Callback Queries."""
        if self._polling_active:
            return
        
        if not self.enabled:
            logger.debug("Telegram deaktiviert, kein Polling")
            return
        
        self._polling_active = True
        self._polling_thread = threading.Thread(target=self._polling_loop, daemon=True)
        self._polling_thread.start()
        logger.info("Telegram Callback Polling gestartet")

    def stop_polling(self):
        """Stoppt das Polling."""
        self._polling_active = False
        if self._polling_thread:
            self._polling_thread.join(timeout=5)
        logger.info("Telegram Callback Polling gestoppt")

    def _polling_loop(self):
        """Polling Loop für Updates."""
        while self._polling_active:
            try:
                url = f"{self.base_url}/getUpdates"
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": 30,
                    "allowed_updates": ["callback_query"]
                }
                
                response = requests.get(url, params=params, timeout=35)
                result = response.json()
                
                if result.get("ok"):
                    for update in result.get("result", []):
                        self._last_update_id = update.get("update_id", self._last_update_id)
                        
                        callback_query = update.get("callback_query")
                        if callback_query:
                            self._process_callback(callback_query)
                
            except requests.exceptions.Timeout:
                # Normal bei Long Polling
                pass
            except Exception as e:
                logger.error(f"Polling Fehler: {e}")
                time.sleep(5)

    def send_test_message(self) -> bool:
        """Sendet eine Test-Nachricht."""
        message_id = self.send_message(
            "✅ <b>Grocy Amazon AutoBuy</b>\n\n"
            "Telegram-Verbindung erfolgreich!\n"
            "Buttons und Callbacks aktiviert.",
            reply_markup={
                "inline_keyboard": [[
                    {"text": "✅ Test OK", "callback_data": "noop"}
                ]]
            }
        )
        return message_id is not None

    def test_connection(self) -> bool:
        """Testet die Verbindung zu Telegram."""
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

    def get_pending_orders(self) -> list[TrackedMessage]:
        """Gibt alle offenen Bestellungen zurück."""
        return [msg for msg in self.tracked_messages.values() if msg.ordered and not msg.delivered]

    def get_unordered(self) -> list[TrackedMessage]:
        """Gibt alle noch nicht bestellten Produkte zurück."""
        return [msg for msg in self.tracked_messages.values() if not msg.ordered]
