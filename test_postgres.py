import logging
import os

import psycopg2
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_postgres_connection():
    """Test direct PostgreSQL connection to Supabase"""

    # Load environment variables
    load_dotenv()

    # Get database URL from environment variables
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.error("Missing DATABASE_URL environment variable")
        return False

    # Check if [YOUR-PASSWORD] placeholder is still in the connection string
    if "[YOUR-PASSWORD]" in database_url:
        logger.error("Please replace [YOUR-PASSWORD] with your actual database password in .env file")
        return False

    try:
        # Connect to the database
        conn = psycopg2.connect(database_url)

        # Create a cursor
        cur = conn.cursor()

        # Execute a simple query
        cur.execute("SELECT current_database(), current_user, version();")

        # Fetch the result
        result = cur.fetchone()

        # Close cursor and connection
        cur.close()
        conn.close()

        logger.info("Successfully connected to PostgreSQL database: %s", result[0])
        logger.info("Connected as user: %s", result[1])
        logger.info("PostgreSQL version: %s", result[2])

        return True

    except Exception as e:
        logger.exception("Failed to connect to PostgreSQL database")
        return False


if __name__ == "__main__":
    logger.info("Testing PostgreSQL connection...")
    success = test_postgres_connection()

    if success:
        logger.info("✅ PostgreSQL connection test passed!")
    else:
        logger.error("❌ PostgreSQL connection test failed!")
