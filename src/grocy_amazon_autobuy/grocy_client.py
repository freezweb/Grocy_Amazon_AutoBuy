"""
Grocy API Client für Bestandsabfragen und Produktinformationen.
"""

import logging
from typing import Any, Optional

import requests

from .config import GrocySettings
from .models import Product

logger = logging.getLogger(__name__)


class GrocyAPIError(Exception):
    """Fehler bei Grocy API Aufrufen."""
    pass


class GrocyClient:
    """Client für die Grocy REST API."""

    def __init__(self, settings: GrocySettings):
        """
        Initialisiert den Grocy Client.
        
        Args:
            settings: Grocy Konfiguration mit URL und API-Key
        """
        self.base_url = settings.url.rstrip("/")
        self.api_key = settings.api_key
        self.asin_field = settings.asin_field
        self.order_units_field = settings.order_units_field
        
        self.session = requests.Session()
        self.session.headers.update({
            "GROCY-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
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
            endpoint: API Endpunkt (ohne Basis-URL)
            **kwargs: Weitere requests Parameter
            
        Returns:
            JSON Response
        """
        url = f"{self.base_url}/api{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.content:
                return response.json()
            return None
            
        except requests.exceptions.ConnectionError as e:
            raise GrocyAPIError(f"Verbindung zu Grocy fehlgeschlagen: {e}")
        except requests.exceptions.HTTPError as e:
            raise GrocyAPIError(f"Grocy API Fehler: {e}")
        except requests.exceptions.JSONDecodeError as e:
            raise GrocyAPIError(f"Ungültige JSON Antwort: {e}")

    def test_connection(self) -> bool:
        """
        Testet die Verbindung zur Grocy API.
        
        Returns:
            True wenn Verbindung erfolgreich
        """
        try:
            self._request("GET", "/system/info")
            logger.info("Grocy Verbindung erfolgreich")
            return True
        except GrocyAPIError as e:
            logger.error(f"Grocy Verbindungstest fehlgeschlagen: {e}")
            return False

    def get_all_products(self) -> list[dict]:
        """
        Ruft alle Produkte ab.
        
        Returns:
            Liste aller Produkte
        """
        return self._request("GET", "/objects/products") or []

    def get_stock(self) -> list[dict]:
        """
        Ruft den aktuellen Bestand ab.
        
        Returns:
            Liste aller Bestandseinträge
        """
        return self._request("GET", "/stock") or []

    def get_missing_products(self) -> list[dict]:
        """
        Ruft Produkte ab, die unter dem Mindestbestand sind.
        
        Returns:
            Liste der Produkte unter Mindestbestand
        """
        return self._request("GET", "/stock/volatile") or {}

    def get_product_userfields(self, product_id: int) -> dict:
        """
        Ruft benutzerdefinierte Felder für ein Produkt ab.
        
        Args:
            product_id: ID des Produkts
            
        Returns:
            Dict mit benutzerdefinierten Feldern
        """
        return self._request("GET", f"/userfields/products/{product_id}") or {}

    def get_quantity_units(self) -> dict[int, str]:
        """
        Ruft alle Mengeneinheiten ab.
        
        Returns:
            Dict mit QU-ID -> Name Mapping
        """
        units = self._request("GET", "/objects/quantity_units") or []
        return {u["id"]: u["name"] for u in units}

    def get_products_below_min_stock(self) -> list[Product]:
        """
        Ruft alle Produkte unter Mindestbestand mit Amazon-Daten ab.
        
        Dies ist die Hauptmethode für die Bestelllogik.
        
        Returns:
            Liste von Product-Objekten die nachbestellt werden müssen
        """
        products_needing_reorder = []
        
        # Hole Bestand und Mengeneinheiten
        stock_data = self.get_stock()
        quantity_units = self.get_quantity_units()
        
        logger.debug(f"Verarbeite {len(stock_data)} Bestandseinträge")
        
        for item in stock_data:
            product_info = item.get("product", {})
            product_id = product_info.get("id")
            
            if not product_id:
                continue
            
            # Prüfe ob unter Mindestbestand
            stock_amount = float(item.get("amount", 0))
            min_stock = float(product_info.get("min_stock_amount", 0))
            
            if stock_amount >= min_stock or min_stock <= 0:
                continue
            
            # Hole benutzerdefinierte Felder (Amazon ASIN, etc.)
            try:
                userfields = self.get_product_userfields(product_id)
            except GrocyAPIError:
                userfields = {}
            
            amazon_asin = userfields.get(self.asin_field)
            
            # Nur Produkte mit Amazon ASIN verarbeiten
            if not amazon_asin or not amazon_asin.strip():
                logger.debug(
                    f"Produkt '{product_info.get('name')}' ohne Amazon ASIN übersprungen"
                )
                continue
            
            # Bestelleinheiten (Standard: 1)
            try:
                order_units = int(userfields.get(self.order_units_field, 1))
            except (ValueError, TypeError):
                order_units = 1
            
            # QU Name
            qu_id = product_info.get("qu_id_stock", 1)
            qu_name = quantity_units.get(qu_id, "Stück")
            
            product = Product(
                id=product_id,
                name=product_info.get("name", f"Produkt {product_id}"),
                stock_amount=stock_amount,
                stock_min_amount=min_stock,
                qu_id_stock=qu_id,
                qu_name=qu_name,
                amazon_asin=amazon_asin.strip(),
                amazon_order_units=order_units,
            )
            
            if product.needs_reorder:
                logger.info(
                    f"Produkt '{product.name}' unter Mindestbestand: "
                    f"{stock_amount}/{min_stock} {qu_name} - "
                    f"{product.packages_to_order} Paket(e) benötigt (ASIN: {amazon_asin})"
                )
                products_needing_reorder.append(product)
        
        return products_needing_reorder

    def add_to_shopping_list(
        self, 
        product_id: int, 
        amount: float = 1.0,
        note: Optional[str] = None
    ) -> bool:
        """
        Fügt ein Produkt zur Grocy Einkaufsliste hinzu.
        
        Args:
            product_id: Produkt ID
            amount: Menge
            note: Optionale Notiz
            
        Returns:
            True wenn erfolgreich
        """
        data = {
            "product_id": product_id,
            "amount": amount,
        }
        if note:
            data["note"] = note
        
        try:
            self._request("POST", "/objects/shopping_list", json=data)
            return True
        except GrocyAPIError as e:
            logger.error(f"Fehler beim Hinzufügen zur Einkaufsliste: {e}")
            return False
