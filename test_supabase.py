import logging
import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_supabase_connection():
    """Test connection to Supabase database"""

    # Load environment variables
    load_dotenv()

    # Get Supabase credentials from environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        logger.error("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_KEY environment variables.")
        return False

    try:
        # Initialize Supabase client
        supabase: Client = create_client(supabase_url, supabase_key)

        # Test connection with a simple query
        response = supabase.table("assets").select("*").limit(5).execute()

        # Check if we got a response
        if response and hasattr(response, "data"):
            logger.info("Successfully connected to Supabase! Found %d records.", len(response.data))
            return True
        else:
            logger.error("Connection successful but no data returned.")
            return False

    except Exception:
        logger.exception("Failed to connect to Supabase")
        return False


if __name__ == "__main__":
    logger.info("Testing Supabase connection...")
    success = test_supabase_connection()

    if success:
        logger.info("✅ Supabase connection test passed!")
    else:
        logger.error("❌ Supabase connection test failed!")
