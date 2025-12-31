from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Enum, Boolean
from sqlalchemy.sql import func
from .database import Base


class ConfigSettings(Base):
    """Application configuration settings"""
    __tablename__ = 'config_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=False)
    setting_type = Column(
        Enum('string', 'integer', 'float', 'boolean', 'json'),
        nullable=False
    )
    description = Column(Text)
    updated_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(),
                              onupdate=func.current_timestamp())

    def __repr__(self):
        return f"<ConfigSettings(key='{self.setting_key}', value='{self.setting_value}')>"

    def get_typed_value(self):
        """Return value with proper type conversion"""
        if self.setting_type == 'integer':
            return int(self.setting_value)
        elif self.setting_type == 'float':
            return float(self.setting_value)
        elif self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            return json.loads(self.setting_value)
        else:
            return self.setting_value


class AuditLog(Base):
    """Audit trail for all operations"""
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    user_action = Column(Boolean, default=False)
    details = Column(Text)  # JSON string
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action_type}', entity='{self.entity_type}')>"
