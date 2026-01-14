"""
Tests für den Grocy Client.
"""

import pytest
from unittest.mock import Mock, patch
from grocy_amazon_autobuy.grocy_client import GrocyClient, GrocyAPIError
from grocy_amazon_autobuy.config import GrocySettings


class TestGrocyClient:
    """Tests für den Grocy API Client."""

    @pytest.fixture
    def settings(self):
        """Test-Konfiguration."""
        return GrocySettings(
            url="http://localhost:9283",
            api_key="test_key",
            asin_field="Amazon_ASIN",
            order_units_field="Amazon_bestelleinheiten",
        )

    @pytest.fixture
    def client(self, settings):
        """Test-Client."""
        return GrocyClient(settings)

    @patch("requests.Session.request")
    def test_connection_success(self, mock_request, client):
        """Erfolgreicher Verbindungstest."""
        mock_request.return_value = Mock(
            status_code=200,
            content=b'{"grocy_version": "4.0.0"}',
            json=lambda: {"grocy_version": "4.0.0"}
        )
        
        assert client.test_connection() is True

    @patch("requests.Session.request")
    def test_connection_failure(self, mock_request, client):
        """Fehlgeschlagener Verbindungstest."""
        from requests.exceptions import ConnectionError
        mock_request.side_effect = ConnectionError("Connection refused")
        
        assert client.test_connection() is False

    @patch("requests.Session.request")
    def test_get_stock(self, mock_request, client):
        """Bestandsabfrage."""
        mock_response = Mock(
            status_code=200,
            content=b'[{"product": {"id": 1, "name": "Test"}, "amount": 5}]',
        )
        mock_response.json.return_value = [
            {"product": {"id": 1, "name": "Test"}, "amount": 5}
        ]
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response
        
        stock = client.get_stock()
        
        assert len(stock) == 1
        assert stock[0]["product"]["name"] == "Test"
