"""
Test script for the database module.
"""

import logging

from src.data.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_database_connection():
    """Test the database connection module"""
    logger.info("Testing database connection...")

    # Get database connection
    db = get_db()

    # Try to connect
    if db.connect():
        logger.info("Connected using: %s", db.connection_type)

        # Try a simple query
        try:
            # Query the database
            results = db.query("assets", limit=5)

            if results:
                logger.info("Successfully queried database! Found %s records.", len(results))
                logger.info("Sample data: %s", results[:2])
            else:
                logger.warning("Query returned no results. This might be normal for a new database.")

            # Close the connection
            db.close()
            return True

        except Exception:
            logger.exception("Query failed")
            return False
    else:
        logger.error("Failed to connect to database.")
        return False


if __name__ == "__main__":
    success = test_database_connection()

    if success:
        logger.info("✅ Database module test completed!")
    else:
        logger.error("❌ Database module test failed!")
