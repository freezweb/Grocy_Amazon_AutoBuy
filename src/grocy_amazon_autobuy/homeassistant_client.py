"""
Home Assistant Client für die Integration mit Alexa und Benachrichtigungen.

Unterstützt:
- Alexa Media Player (Sprachbefehle)
- Alexa Shopping List (über Home Assistant Todo)
- Benachrichtigungen
"""

import logging
from typing import Any, Optional

import requests

from .config import HomeAssistantSettings

logger = logging.getLogger(__name__)


class HomeAssistantError(Exception):
    """Fehler bei Home Assistant API Aufrufen."""
    pass


class HomeAssistantClient:
    """Client für die Home Assistant REST API."""

    def __init__(self, settings: HomeAssistantSettings):
        """
        Initialisiert den Home Assistant Client.
        
        Args:
            settings: Home Assistant Konfiguration
        """
        self.base_url = settings.url.rstrip("/")
        self.token = settings.token
        self.alexa_entity_id = settings.alexa_entity_id
        self.use_shopping_list = settings.use_shopping_list
        self.shopping_list_entity = settings.shopping_list_entity
        
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        **kwargs
    ) -> Any:
        """
        Führt einen API-Request aus.
        
        Args:
            method: HTTP Methode
            endpoint: API Endpunkt
            **kwargs: Weitere requests Parameter
            
        Returns:
            JSON Response
        """
        url = f"{self.base_url}/api{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return None
            
        except requests.exceptions.ConnectionError as e:
            raise HomeAssistantError(f"Verbindung zu Home Assistant fehlgeschlagen: {e}")
        except requests.exceptions.HTTPError as e:
            raise HomeAssistantError(f"Home Assistant API Fehler: {e}")
        except requests.exceptions.Timeout:
            raise HomeAssistantError("Home Assistant Timeout")

    def test_connection(self) -> bool:
        """
        Testet die Verbindung zu Home Assistant.
        
        Returns:
            True wenn Verbindung erfolgreich
        """
        try:
            result = self._request("GET", "/")
            logger.info(f"Home Assistant Verbindung erfolgreich: {result.get('message', 'OK')}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Home Assistant Verbindungstest fehlgeschlagen: {e}")
            return False

    def call_service(
        self, 
        domain: str, 
        service: str, 
        data: Optional[dict] = None,
        target: Optional[dict] = None
    ) -> Any:
        """
        Ruft einen Home Assistant Service auf.
        
        Args:
            domain: Service Domain (z.B. 'notify', 'media_player')
            service: Service Name (z.B. 'alexa_media')
            data: Service Daten
            target: Target Entity IDs
            
        Returns:
            API Response
        """
        payload = {}
        if data:
            payload.update(data)
        if target:
            payload["target"] = target
        
        return self._request(
            "POST", 
            f"/services/{domain}/{service}",
            json=payload
        )

    def get_entity_state(self, entity_id: str) -> dict:
        """
        Ruft den State einer Entity ab.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity State Dict
        """
        return self._request("GET", f"/states/{entity_id}")

    def check_alexa_available(self) -> bool:
        """
        Prüft ob Alexa Media Player verfügbar ist.
        
        Returns:
            True wenn verfügbar
        """
        try:
            state = self.get_entity_state(self.alexa_entity_id)
            is_available = state.get("state") not in ("unavailable", "unknown")
            logger.debug(f"Alexa Entity {self.alexa_entity_id}: {state.get('state')}")
            return is_available
        except HomeAssistantError:
            return False

    def check_shopping_list_available(self) -> bool:
        """
        Prüft ob die Alexa Shopping List Entity verfügbar ist.
        
        Returns:
            True wenn verfügbar
        """
        try:
            state = self.get_entity_state(self.shopping_list_entity)
            is_available = state.get("state") not in ("unavailable", "unknown")
            logger.debug(f"Shopping List Entity {self.shopping_list_entity}: {state.get('state')}")
            return is_available
        except HomeAssistantError:
            return False

    def add_to_alexa_shopping_list(self, item: str) -> bool:
        """
        Fügt einen Artikel zur Alexa Einkaufsliste hinzu.
        
        Verwendet die Home Assistant Todo Integration.
        
        Args:
            item: Artikelname/Beschreibung
            
        Returns:
            True wenn erfolgreich
        """
        try:
            # Verwende todo.add_item Service
            self.call_service(
                domain="todo",
                service="add_item",
                target={"entity_id": self.shopping_list_entity},
                data={"item": item}
            )
            logger.info(f"Zur Alexa Einkaufsliste hinzugefügt: {item}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Hinzufügen zur Einkaufsliste: {e}")
            return False

    def send_alexa_voice_command(
        self, 
        message: str,
        entity_id: Optional[str] = None
    ) -> bool:
        """
        Sendet einen Sprachbefehl an Alexa.
        
        Verwendet Alexa Media Player Integration.
        Hinweis: Für Amazon-Bestellungen funktioniert dies nur eingeschränkt,
        da Amazon Voice Shopping Sicherheitsmechanismen hat.
        
        Args:
            message: Der Sprachbefehl
            entity_id: Optional abweichende Entity ID
            
        Returns:
            True wenn erfolgreich gesendet
        """
        target_entity = entity_id or self.alexa_entity_id
        
        try:
            # Alexa Media Player - notify Service für TTS/Routine
            self.call_service(
                domain="notify",
                service="alexa_media",
                data={
                    "message": message,
                    "target": target_entity,
                    "data": {
                        "type": "tts"  # Text-to-Speech
                    }
                }
            )
            logger.info(f"Alexa Sprachbefehl gesendet: {message}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Senden des Sprachbefehls: {e}")
            return False

    def send_alexa_order_command(
        self, 
        product_name: str,
        quantity: int = 1,
        entity_id: Optional[str] = None
    ) -> bool:
        """
        Sendet einen direkten Bestellbefehl an Alexa.
        
        WICHTIG: Für automatische Bestellungen muss in der Alexa App:
        1. Spracheinkauf aktiviert sein (Einstellungen → Konto → Spracheinkauf)
        2. Bestätigungscode deaktiviert sein ODER 1-Click aktiviert
        
        Args:
            product_name: Name des Produkts
            quantity: Anzahl (wird im Befehl verwendet)
            entity_id: Optional abweichende Entity ID
            
        Returns:
            True wenn Befehl gesendet wurde
        """
        target_entity = entity_id or self.alexa_entity_id
        
        # Natürlicher Bestellbefehl
        if quantity > 1:
            command = f"Bestelle {quantity} {product_name}"
        else:
            command = f"Bestelle {product_name}"
        
        try:
            # Verwende alexa_media notify Service für Sprachbefehle
            self.call_service(
                domain="notify",
                service="alexa_media",
                data={
                    "message": command,
                    "target": target_entity,
                    "data": {
                        "type": "announce"  # announce für Befehle
                    }
                }
            )
            logger.info(f"Alexa Bestellbefehl gesendet: {command}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Senden des Bestellbefehls: {e}")
            return False

    def order_by_asin(
        self, 
        asin: str,
        entity_id: Optional[str] = None
    ) -> bool:
        """
        Bestellt ein Produkt direkt über die ASIN.
        
        Verwendet den Alexa-Befehl "Bestelle ASIN [nummer]".
        
        Args:
            asin: Amazon ASIN (10-stellig)
            entity_id: Optional abweichende Entity ID
            
        Returns:
            True wenn Befehl gesendet wurde
        """
        target_entity = entity_id or self.alexa_entity_id
        
        # ASIN-basierter Bestellbefehl
        command = f"Bestelle ASIN {asin}"
        
        try:
            # Verwende alexa_media notify Service für Sprachbefehle
            self.call_service(
                domain="notify",
                service="alexa_media",
                data={
                    "message": command,
                    "target": target_entity,
                    "data": {
                        "type": "announce"
                    }
                }
            )
            logger.info(f"Alexa ASIN-Bestellung gesendet: {asin}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim ASIN-Bestellbefehl: {e}")
            return False

    def trigger_alexa_routine(
        self, 
        routine_name: str,
        entity_id: Optional[str] = None
    ) -> bool:
        """
        Triggert eine Alexa Routine.
        
        Die Routine muss in der Alexa App konfiguriert sein.
        
        Args:
            routine_name: Name der Routine
            entity_id: Optional abweichende Entity ID
            
        Returns:
            True wenn erfolgreich
        """
        target_entity = entity_id or self.alexa_entity_id
        
        try:
            self.call_service(
                domain="media_player",
                service="play_media",
                target={"entity_id": target_entity},
                data={
                    "media_content_type": "routine",
                    "media_content_id": routine_name
                }
            )
            logger.info(f"Alexa Routine '{routine_name}' getriggert")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Triggern der Routine: {e}")
            return False

    def send_notification(
        self, 
        title: str,
        message: str,
        service: str = "persistent_notification"
    ) -> bool:
        """
        Sendet eine Benachrichtigung über Home Assistant.
        
        Args:
            title: Titel der Benachrichtigung
            message: Nachrichteninhalt
            service: Notification Service (z.B. 'persistent_notification', 'mobile_app_...')
            
        Returns:
            True wenn erfolgreich
        """
        try:
            # Parse service name (kann format "notify.xyz" oder nur "xyz" sein)
            if "." in service:
                domain, svc = service.split(".", 1)
            else:
                domain = "notify"
                svc = service
            
            self.call_service(
                domain=domain,
                service=svc,
                data={
                    "title": title,
                    "message": message,
                }
            )
            logger.debug(f"Benachrichtigung gesendet: {title}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Senden der Benachrichtigung: {e}")
            return False

    def send_alexa_announcement(
        self, 
        message: str,
        entity_id: Optional[str] = None
    ) -> bool:
        """
        Sendet eine Alexa Ankündigung (Announcement).
        
        Args:
            message: Die Ankündigung
            entity_id: Optional abweichende Entity ID
            
        Returns:
            True wenn erfolgreich
        """
        target_entity = entity_id or self.alexa_entity_id
        
        try:
            self.call_service(
                domain="notify",
                service="alexa_media",
                data={
                    "message": message,
                    "target": target_entity,
                    "data": {
                        "type": "announce"
                    }
                }
            )
            logger.info(f"Alexa Ankündigung gesendet: {message}")
            return True
        except HomeAssistantError as e:
            logger.error(f"Fehler beim Senden der Ankündigung: {e}")
            return False
