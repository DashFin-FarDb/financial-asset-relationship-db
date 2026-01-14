import os
import socket

import psycopg2
from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables from .env
load_dotenv()

# Get database connection details
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Path to SSL certificate
CERT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prod-ca-2021.crt")

print("Supabase URL:", SUPABASE_URL)
print("Supabase Key:", SUPABASE_KEY[:5] + "..." if SUPABASE_KEY else "Not found")
print("Certificate path:", CERT_PATH)

# Try Supabase API connection
try:
    print("\n--- Testing Supabase API Connection with New Credentials ---")
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ Supabase client initialized successfully!")

    try:
        # Example query - fetch data
        print("Attempting to execute query via Supabase API...")
        response = supabase.table("transactions").select("*").limit(1).execute()
        print(f"✅ Query successful! Found {len(response.data)} records.")
        if response.data:
            print("Sample data:", response.data[0])
        else:
            print("No records found in the 'transactions' table.")

        # Try another table if assets doesn't exist
        print("\nTrying to list available tables...")
        response = supabase.rpc("get_tables").execute()
        if hasattr(response, "data") and response.data:
            print("Available tables:", response.data)
        else:
            print("Could not retrieve table list.")

    except socket.gaierror:
        print("⚠️ Network connection issue: Unable to reach Supabase API servers.")
        print("This is expected in test environments with network restrictions.")
    except Exception as query_error:
        print(f"⚠️ Query error: {query_error}")

except Exception as e:
    print(f"❌ Failed to initialize Supabase client: {e}")

# Try direct PostgreSQL connection with SSL certificate
try:
    print("\n--- Testing Direct PostgreSQL Connection with SSL ---")

    # Use DATABASE_URL directly; if migrating projects, replace the fragment accordingly
    updated_db_url = DATABASE_URL

    # Parse connection parameters from DATABASE_URL or use individual parameters
    if updated_db_url:
        print(f"Using connection string: {updated_db_url[:20]}...")

        # Add SSL parameters to connection
        connection = psycopg2.connect(updated_db_url, sslmode="require", sslrootcert=CERT_PATH)
    else:
        print("No DATABASE_URL found, using individual parameters")
        connection = None

    if connection:
        print("✅ PostgreSQL connection successful!")

        # Create a cursor to execute SQL queries
        cursor = connection.cursor()

        # Example query
        print("Executing query...")
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("Current Time:", result)

        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("Connection closed.")

except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")

print("\nConnection tests completed.")
