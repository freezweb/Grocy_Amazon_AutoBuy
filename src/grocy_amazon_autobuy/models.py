"""
Datenmodelle für Grocy Amazon AutoBuy.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    """Status einer Bestellung."""
    
    PENDING = "pending"
    ADDED_TO_LIST = "added_to_list"
    VOICE_ORDERED = "voice_ordered"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Product:
    """Ein Grocy-Produkt mit Amazon-Daten."""
    
    id: int
    name: str
    
    # Bestandsinformationen
    stock_amount: float
    stock_min_amount: float
    qu_id_stock: int
    qu_name: Optional[str] = None
    
    # Amazon-spezifische Daten
    amazon_asin: Optional[str] = None
    amazon_order_units: int = 1  # Anzahl Einheiten pro Amazon-Paket
    
    # Berechnete Felder
    missing_amount: float = field(init=False)
    packages_to_order: int = field(init=False)
    
    def __post_init__(self):
        """Berechne fehlende Menge und benötigte Pakete."""
        self.missing_amount = max(0, self.stock_min_amount - self.stock_amount)
        
        if self.missing_amount > 0 and self.amazon_order_units > 0:
            # Aufrunden zur nächsten vollen Paketanzahl
            self.packages_to_order = max(
                1, 
                int((self.missing_amount + self.amazon_order_units - 1) // self.amazon_order_units)
            )
        else:
            self.packages_to_order = 0
    
    @property
    def needs_reorder(self) -> bool:
        """Prüft ob eine Nachbestellung nötig ist."""
        return (
            self.missing_amount > 0 
            and self.amazon_asin is not None 
            and self.amazon_asin.strip() != ""
        )
    
    def get_order_description(self) -> str:
        """Erstellt eine Bestellbeschreibung für Alexa."""
        if self.packages_to_order == 1:
            return f"{self.name}"
        else:
            return f"{self.packages_to_order}x {self.name}"


@dataclass
class OrderRequest:
    """Eine Bestellanfrage."""
    
    product: Product
    quantity: int
    asin: str
    
    created_at: datetime = field(default_factory=datetime.now)
    status: OrderStatus = OrderStatus.PENDING
    
    # Tracking
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    
    def mark_success(self, order_id: Optional[str] = None):
        """Markiert die Bestellung als erfolgreich."""
        self.status = OrderStatus.ADDED_TO_LIST
        self.order_id = order_id
        self.processed_at = datetime.now()
    
    def mark_failed(self, error: str):
        """Markiert die Bestellung als fehlgeschlagen."""
        self.status = OrderStatus.FAILED
        self.error_message = error
        self.processed_at = datetime.now()


@dataclass
class OrderHistory:
    """Verlauf der Bestellungen für Rate-Limiting und Duplikatschutz."""
    
    orders: list[OrderRequest] = field(default_factory=list)
    
    # Ausstehende Bestellungen: ASIN -> Bestand zum Zeitpunkt der Bestellung
    # Verhindert erneute Bestellung bis Lieferung eingetroffen (Bestand erhöht)
    pending_deliveries: dict[str, float] = field(default_factory=dict)
    
    def add_order(self, order: OrderRequest):
        """Fügt eine Bestellung zum Verlauf hinzu."""
        self.orders.append(order)
    
    def get_orders_today(self) -> list[OrderRequest]:
        """Gibt alle Bestellungen von heute zurück."""
        today = datetime.now().date()
        return [o for o in self.orders if o.created_at.date() == today]
    
    def count_orders_today(self) -> int:
        """Zählt die Bestellungen von heute."""
        return len(self.get_orders_today())
    
    def was_ordered_recently(self, asin: str, hours: int = 24) -> bool:
        """Prüft ob ein Produkt kürzlich bestellt wurde."""
        cutoff = datetime.now().timestamp() - (hours * 3600)
        return any(
            o.asin == asin and o.created_at.timestamp() > cutoff
            for o in self.orders
            if o.status in (OrderStatus.ADDED_TO_LIST, OrderStatus.VOICE_ORDERED, OrderStatus.CONFIRMED)
        )
    
    def mark_pending_delivery(self, asin: str, stock_at_order: float):
        """
        Markiert eine ASIN als "Lieferung ausstehend".
        
        Speichert den Bestand zum Zeitpunkt der Bestellung.
        Erst wenn der Bestand in Grocy höher ist, gilt die Lieferung als eingetroffen.
        
        Args:
            asin: Amazon ASIN
            stock_at_order: Aktueller Bestand zum Zeitpunkt der Bestellung
        """
        self.pending_deliveries[asin] = stock_at_order
    
    def is_delivery_pending(self, asin: str, current_stock: float) -> bool:
        """
        Prüft ob eine Lieferung noch aussteht.
        
        Eine Lieferung gilt als "ausstehend" wenn:
        - Die ASIN als pending markiert ist UND
        - Der aktuelle Bestand nicht höher ist als bei der Bestellung
        
        Wenn der Bestand gestiegen ist, wurde die Lieferung eingebucht
        und die ASIN wird automatisch aus pending entfernt.
        
        Args:
            asin: Amazon ASIN
            current_stock: Aktueller Bestand in Grocy
            
        Returns:
            True wenn Lieferung noch aussteht (nicht erneut bestellen!)
        """
        if asin not in self.pending_deliveries:
            return False
        
        stock_at_order = self.pending_deliveries[asin]
        
        # Bestand ist gestiegen = Lieferung eingetroffen und eingebucht
        if current_stock > stock_at_order:
            del self.pending_deliveries[asin]
            return False
        
        # Bestand gleich oder niedriger = Lieferung noch ausstehend
        return True
    
    def clear_pending_delivery(self, asin: str):
        """Entfernt eine ASIN aus den ausstehenden Lieferungen."""
        if asin in self.pending_deliveries:
            del self.pending_deliveries[asin]
