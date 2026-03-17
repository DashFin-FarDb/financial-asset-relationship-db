"""Test script for the database module."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.data.database import create_engine_from_url, create_session_factory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_database_connection() -> None:
    """Test connectivity using current database module API."""
    logger.info("Testing database connection...")
    engine = create_engine_from_url()
    session_factory = create_session_factory(engine)
    backend = engine.url.get_backend_name()

    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
            logger.info("Connected using backend: %s", backend)
            table_rows = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 5")
            ).all()
            if table_rows:
                sample_tables = [row[0] for row in table_rows]
                logger.info(
                    "Successfully queried database! Found %s table(s).",
                    len(sample_tables),
                )
                logger.info("Sample tables: %s", sample_tables[:2])
            else:
                logger.warning("Query returned no table rows. This may be normal for a new database.")
    except SQLAlchemyError:
        logger.exception("Database query failed")
        raise


if __name__ == "__main__":
    try:
        test_database_connection()
        logger.info("✅ Database module test completed!")
    except Exception:  # noqa: BLE001
        logger.error("❌ Database module test failed!")
