#!/usr/bin/env python3
"""Test-Skript für Telegram-Verbindung."""
from grocy_amazon_autobuy.telegram_client import TelegramClient
from grocy_amazon_autobuy.config import TelegramSettings

settings = TelegramSettings(
    enabled=True,
    bot_token='8580748565:AAGsbO8aZ1nbEagF0oJmxp6gNAyJJKCJk0g',
    chat_id='16193482'
)

client = TelegramClient(settings)
print("Test Telegram Verbindung...")

if client.test_connection():
    print("✓ Telegram Verbindung OK!")
    
    # Sende Test-Nachricht mit klickbarem Link
    test_url = "https://www.amazon.de/gp/aws/cart/add.html?ASIN.1=B07D1X2H4K&Quantity.1=2"
    
    success = client.send_order_notification(
        product_name="Test-Produkt (Küchenrolle)",
        quantity=2,
        asin="B07D1X2H4K",
        current_stock=1,
        min_stock=3,
        unit="Packung",
        cart_url=test_url
    )
    
    if success:
        print("✓ Test-Nachricht gesendet!")
    else:
        print("✗ Nachricht senden fehlgeschlagen!")
else:
    print("✗ Telegram Verbindung fehlgeschlagen!")
