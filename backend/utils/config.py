"""Configuration management utilities."""
from sqlalchemy.orm import Session
from models import ConfigSettings
from typing import Any, Optional


class Config:
    """Helper class for accessing configuration settings"""

    @staticmethod
    def get(db: Session, key: str, default: Any = None) -> Any:
        """Get a configuration value by key"""
        setting = db.query(ConfigSettings).filter(
            ConfigSettings.setting_key == key
        ).first()
        
        if setting:
            return setting.get_typed_value()
        return default

    @staticmethod
    def set(db: Session, key: str, value: Any, setting_type: str, description: str = None) -> ConfigSettings:
        """Set a configuration value"""
        setting = db.query(ConfigSettings).filter(
            ConfigSettings.setting_key == key
        ).first()

        str_value = str(value)
        
        if setting:
            setting.setting_value = str_value
            setting.setting_type = setting_type
            if description:
                setting.description = description
        else:
            setting = ConfigSettings(
                setting_key=key,
                setting_value=str_value,
                setting_type=setting_type,
                description=description
            )
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        return setting

    @staticmethod
    def get_confidence_threshold_auto_store(db: Session) -> float:
        """Get the auto-store confidence threshold"""
        return Config.get(db, 'confidence_threshold_auto_store', 0.85)

    @staticmethod
    def get_confidence_threshold_review(db: Session) -> float:
        """Get the review confidence threshold"""
        return Config.get(db, 'confidence_threshold_review', 0.60)

    @staticmethod
    def get_always_review(db: Session) -> bool:
        """Check if always review is enabled"""
        return Config.get(db, 'always_review', False)

    @staticmethod
    def get_llm_provider(db: Session) -> str:
        """Get the default LLM provider"""
        return Config.get(db, 'llm_default_provider', 'openai')

    @staticmethod
    def get_llm_model(db: Session) -> str:
        """Get the default LLM model"""
        return Config.get(db, 'llm_default_model', 'gpt-4-turbo-preview')
