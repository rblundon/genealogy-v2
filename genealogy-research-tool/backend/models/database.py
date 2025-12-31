from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL from environment
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MARIADB_USER')}:"
    f"{os.getenv('MARIADB_PASSWORD')}@"
    f"{os.getenv('MARIADB_HOST')}:"
    f"{os.getenv('MARIADB_PORT', '3306')}/"
    f"{os.getenv('MARIADB_DATABASE')}"
    f"?charset=utf8mb4"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=os.getenv('ENVIRONMENT') == 'development'
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
