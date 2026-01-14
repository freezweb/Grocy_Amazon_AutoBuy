"""
Tests für die Datenmodelle.
"""

import pytest
from grocy_amazon_autobuy.models import Product, OrderRequest, OrderHistory, OrderStatus


class TestProduct:
    """Tests für das Product Model."""

    def test_product_needs_reorder_with_asin(self):
        """Produkt unter Mindestbestand mit ASIN braucht Nachbestellung."""
        product = Product(
            id=1,
            name="Test Nudeln",
            stock_amount=5,
            stock_min_amount=10,
            qu_id_stock=1,
            amazon_asin="B08N5WRWNW",
            amazon_order_units=20,
        )
        
        assert product.needs_reorder is True
        assert product.missing_amount == 5
        assert product.packages_to_order == 1

    def test_product_no_reorder_without_asin(self):
        """Produkt ohne ASIN braucht keine Nachbestellung."""
        product = Product(
            id=1,
            name="Test Produkt",
            stock_amount=5,
            stock_min_amount=10,
            qu_id_stock=1,
            amazon_asin=None,
        )
        
        assert product.needs_reorder is False

    def test_product_no_reorder_above_min_stock(self):
        """Produkt über Mindestbestand braucht keine Nachbestellung."""
        product = Product(
            id=1,
            name="Test Produkt",
            stock_amount=15,
            stock_min_amount=10,
            qu_id_stock=1,
            amazon_asin="B08N5WRWNW",
        )
        
        assert product.needs_reorder is False
        assert product.missing_amount == 0
        assert product.packages_to_order == 0

    def test_packages_calculation(self):
        """Berechnung der benötigten Pakete."""
        # 15 fehlen, 20 pro Paket = 1 Paket
        product = Product(
            id=1,
            name="Test",
            stock_amount=5,
            stock_min_amount=20,
            qu_id_stock=1,
            amazon_asin="B123",
            amazon_order_units=20,
        )
        assert product.packages_to_order == 1
        
        # 25 fehlen, 20 pro Paket = 2 Pakete
        product2 = Product(
            id=2,
            name="Test2",
            stock_amount=5,
            stock_min_amount=30,
            qu_id_stock=1,
            amazon_asin="B123",
            amazon_order_units=20,
        )
        assert product2.packages_to_order == 2

    def test_order_description(self):
        """Bestellbeschreibung für Alexa."""
        product = Product(
            id=1,
            name="Barilla Nudeln",
            stock_amount=0,
            stock_min_amount=40,
            qu_id_stock=1,
            amazon_asin="B123",
            amazon_order_units=20,
        )
        
        assert product.packages_to_order == 2
        assert "2x" in product.get_order_description()


class TestOrderHistory:
    """Tests für die Bestellhistorie."""

    def test_count_orders_today(self):
        """Zähle Bestellungen von heute."""
        history = OrderHistory()
        
        product = Product(
            id=1, name="Test", stock_amount=0, stock_min_amount=10,
            qu_id_stock=1, amazon_asin="B123"
        )
        
        order = OrderRequest(product=product, quantity=1, asin="B123")
        history.add_order(order)
        
        assert history.count_orders_today() == 1

    def test_was_ordered_recently(self):
        """Prüfe ob kürzlich bestellt."""
        history = OrderHistory()
        
        product = Product(
            id=1, name="Test", stock_amount=0, stock_min_amount=10,
            qu_id_stock=1, amazon_asin="B123"
        )
        
        order = OrderRequest(product=product, quantity=1, asin="B123")
        order.mark_success()
        history.add_order(order)
        
        assert history.was_ordered_recently("B123") is True
        assert history.was_ordered_recently("B456") is False
