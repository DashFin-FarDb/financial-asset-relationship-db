"""Local script to test Supabase and PostgreSQL connectivity."""

# mypy: disable-error-code=import-untyped
# pyright: reportMissingImports=false

import importlib
import os
import socket
from collections.abc import Callable
from typing import Any

import psycopg2  # pyright: ignore[reportMissingTypeStubs]
from dotenv import load_dotenv


def _load_supabase_client_factory() -> Callable[..., Any] | None:
    """Return the optional Supabase client factory when its API is available."""
    try:
        supabase_module = importlib.import_module("supabase")
    except ImportError:
        return None
    candidate = getattr(supabase_module, "create_client", None)
    return candidate if callable(candidate) else None


CREATE_SUPABASE_CLIENT = _load_supabase_client_factory()


def _create_configured_supabase_client(url: str | None, key: str | None) -> Any:
    """Create the optional client after validating its runtime boundary."""
    client_factory = CREATE_SUPABASE_CLIENT
    if client_factory is None:
        raise RuntimeError("optional Supabase client API is unavailable")
    missing_variables = tuple(name for name, value in (("SUPABASE_URL", url), ("SUPABASE_KEY", key)) if not value)
    if missing_variables:
        raise RuntimeError("missing required environment variables: " + ", ".join(missing_variables))
    return client_factory(url, key)


def _test_supabase_api(url: str | None, key: str | None) -> None:
    """Run the optional Supabase portion of the manual connectivity diagnostic."""
    try:
        print("\n--- Testing Supabase API Connection with New Credentials ---")
        supabase = _create_configured_supabase_client(url, key)
        print("✅ Supabase client initialized successfully!")

        try:
            print("Attempting to execute query via Supabase API...")
            response = supabase.table("transactions").select("*").limit(1).execute()
            print(f"✅ Query successful! Found {len(response.data)} records.")
            if response.data:
                print("Sample data:", response.data[0])
            else:
                print("No records found in the 'transactions' table.")

            print("\nTrying to list available tables...")
            response = supabase.rpc("get_tables").execute()
            if hasattr(response, "data") and response.data:
                print("Available tables:", response.data)
            else:
                print("Could not retrieve table list.")
        except socket.gaierror:
            print("⚠️ Network connection issue: Unable to reach Supabase API servers.")
            print("This is expected in test environments with network restrictions.")
        except (RuntimeError, ValueError, TypeError) as query_error:
            print(f"⚠️ Query error: {query_error}")
    except (RuntimeError, ValueError, TypeError, OSError) as error:
        print(f"❌ Failed to initialize Supabase client: {error}")


# Load environment variables from .env
load_dotenv()

# Get database connection details
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Path to SSL certificate
CERT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prod-ca-2021.crt",
)

print("Supabase URL:", SUPABASE_URL)
SUPABASE_KEY_PREVIEW = SUPABASE_KEY[:5] + "..." if SUPABASE_KEY else "Not found"
print("Supabase Key:", SUPABASE_KEY_PREVIEW)
print("Certificate path:", CERT_PATH)

_test_supabase_api(SUPABASE_URL, SUPABASE_KEY)

# Try direct PostgreSQL connection with SSL certificate
try:
    print("\n--- Testing Direct PostgreSQL Connection with SSL ---")

    # Use DATABASE_URL directly.
    # If migrating projects, replace the fragment accordingly.
    updated_db_url = DATABASE_URL

    # Parse connection parameters from DATABASE_URL.
    # Otherwise use individual parameters.
    if updated_db_url:
        print(f"Using connection string: {updated_db_url[:20]}...")

        if not os.path.exists(CERT_PATH):
            print(f"⚠️ Warning: Certificate file not found at {CERT_PATH}")
            print("Connection may fail if SSL is required.")

        # Add SSL parameters to connection
        DB_CONNECTION = psycopg2.connect(
            updated_db_url,
            sslmode="require",
            sslrootcert=CERT_PATH,
        )
    else:
        print("No DATABASE_URL found, using individual parameters")
        DB_CONNECTION = None

    if DB_CONNECTION:
        print("✅ PostgreSQL connection successful!")

        # Create a cursor to execute SQL queries
        cursor = DB_CONNECTION.cursor()

        # Example query
        print("Executing query...")
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("Current Time:", result)

        # Close the cursor and connection
        cursor.close()
        DB_CONNECTION.close()
        print("Connection closed.")

except psycopg2.Error as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")

print("\nConnection tests completed.")
