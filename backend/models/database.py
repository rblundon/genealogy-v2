"""Database configuration and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database connection string
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MARIADB_USER')}:"
    f"{os.getenv('MARIADB_PASSWORD')}@"
    f"{os.getenv('MARIADB_HOST')}:"
    f"{os.getenv('MARIADB_PORT', '3306')}/"
    f"{os.getenv('MARIADB_DATABASE')}"
    f"?charset=utf8mb4"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=os.getenv('ENVIRONMENT') == 'development'  # Log SQL in dev
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency for FastAPI endpoints
def get_db():
    """
    Database session dependency for FastAPI.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
