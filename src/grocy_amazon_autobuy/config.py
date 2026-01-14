"""
Konfigurationsmanagement für Grocy Amazon AutoBuy.

Unterstützt Konfiguration via Umgebungsvariablen, .env Datei oder config.yaml.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GrocySettings(BaseSettings):
    """Grocy API Konfiguration."""

    url: str = Field(
        default="http://localhost:9283",
        description="Grocy Server URL",
        alias="GROCY_URL",
    )
    api_key: str = Field(
        default="",
        description="Grocy API Schlüssel",
        alias="GROCY_API_KEY",
    )
    
    # Benutzerdefinierte Felder für Amazon-Daten
    asin_field: str = Field(
        default="Amazon_ASIN",
        description="Name des benutzerdefinierten Feldes für Amazon ASIN",
        alias="GROCY_ASIN_FIELD",
    )
    order_units_field: str = Field(
        default="Amazon_bestelleinheiten",
        description="Name des benutzerdefinierten Feldes für Bestelleinheiten pro Paket",
        alias="GROCY_ORDER_UNITS_FIELD",
    )

    model_config = SettingsConfigDict(
        env_prefix="GROCY_",
        extra="ignore",
    )


class HomeAssistantSettings(BaseSettings):
    """Home Assistant Konfiguration."""

    url: str = Field(
        default="http://homeassistant.local:8123",
        description="Home Assistant URL",
        alias="HASS_URL",
    )
    token: str = Field(
        default="",
        description="Home Assistant Long-Lived Access Token",
        alias="HASS_TOKEN",
    )
    
    # Alexa Media Player Konfiguration
    alexa_entity_id: str = Field(
        default="media_player.echo_dot",
        description="Entity ID des Alexa-Geräts für Sprachbefehle",
        alias="HASS_ALEXA_ENTITY_ID",
    )
    
    # Alexa Shopping List Konfiguration (Alternative)
    use_shopping_list: bool = Field(
        default=True,
        description="Shopping List statt direkter Sprachbefehl verwenden",
        alias="HASS_USE_SHOPPING_LIST",
    )
    shopping_list_entity: str = Field(
        default="todo.alexa_shopping_list",
        description="Entity ID der Alexa Shopping Liste",
        alias="HASS_SHOPPING_LIST_ENTITY",
    )

    model_config = SettingsConfigDict(
        env_prefix="HASS_",
        extra="ignore",
    )


class OrderSettings(BaseSettings):
    """Bestellungs-Konfiguration."""

    # Bestellmodus
    mode: str = Field(
        default="shopping_list",
        description="Bestellmodus: 'shopping_list', 'voice_command', oder 'notify_only'",
        alias="ORDER_MODE",
    )
    
    # Zeitplanung
    check_interval_minutes: int = Field(
        default=60,
        description="Prüfintervall in Minuten",
        alias="ORDER_CHECK_INTERVAL",
    )
    
    # Sicherheitseinstellungen
    max_orders_per_day: int = Field(
        default=10,
        description="Maximale Anzahl Bestellungen pro Tag",
        alias="ORDER_MAX_PER_DAY",
    )
    require_confirmation: bool = Field(
        default=False,
        description="Bestätigung vor Bestellung erforderlich",
        alias="ORDER_REQUIRE_CONFIRMATION",
    )
    dry_run: bool = Field(
        default=True,
        description="Testmodus - keine echten Bestellungen",
        alias="ORDER_DRY_RUN",
    )
    
    # Benachrichtigungen
    notify_on_order: bool = Field(
        default=True,
        description="Benachrichtigung bei Bestellung senden",
        alias="ORDER_NOTIFY",
    )
    notification_service: str = Field(
        default="notify.persistent_notification",
        description="Home Assistant Notification Service",
        alias="ORDER_NOTIFICATION_SERVICE",
    )

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        valid_modes = ["voice_order", "shopping_list", "notify_only"]
        # Alias für Rückwärtskompatibilität
        if v == "voice_command":
            v = "voice_order"
        if v not in valid_modes:
            raise ValueError(f"Ungültiger Modus. Erlaubt: {valid_modes}")
        return v

    model_config = SettingsConfigDict(
        env_prefix="ORDER_",
        extra="ignore",
    )


class Settings(BaseSettings):
    """Hauptkonfiguration - kombiniert alle Einstellungen."""

    grocy: GrocySettings = Field(default_factory=GrocySettings)
    homeassistant: HomeAssistantSettings = Field(default_factory=HomeAssistantSettings)
    order: OrderSettings = Field(default_factory=OrderSettings)
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Log Level (DEBUG, INFO, WARNING, ERROR)",
        alias="LOG_LEVEL",
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Pfad zur Log-Datei (optional)",
        alias="LOG_FILE",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """
    Lädt die Konfiguration aus verschiedenen Quellen.
    
    Priorität:
    1. Umgebungsvariablen
    2. .env Datei
    3. config.yaml (wenn angegeben)
    4. Standardwerte
    """
    import yaml
    
    settings_dict = {}
    
    # Lade config.yaml wenn vorhanden
    if config_path and config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                settings_dict = yaml_config
    
    # Erstelle Settings (Umgebungsvariablen überschreiben YAML)
    return Settings(
        grocy=GrocySettings(**settings_dict.get("grocy", {})),
        homeassistant=HomeAssistantSettings(**settings_dict.get("homeassistant", {})),
        order=OrderSettings(**settings_dict.get("order", {})),
    )
