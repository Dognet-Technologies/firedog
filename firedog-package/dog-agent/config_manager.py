"""
Config Manager per Dog Agent
Gestisce caricamento e salvataggio configurazione JSON
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """Gestisce configurazione agent"""

    def __init__(self, config_path='/etc/dog-agent/agent.conf'):
        self.config_path = Path(config_path)
        self.config = {}
        self.load()

    def load(self):
        """Carica configurazione da file JSON"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return True
        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return False

    def save(self):
        """Salva configurazione su file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def get(self, key, default=None):
        """Ottiene valore config con dot notation (es: 'server.url')"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key, value):
        """Imposta valore config con dot notation"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def update(self, new_config: dict):
        """Aggiorna configurazione con nuovo dict"""
        self.config.update(new_config)
        self.save()
