# Database Integration

This project uses Supabase as the database provider. The integration supports both the Supabase API client and direct PostgreSQL connections.

## Configuration

Add the following environment variables to your `.env` file:

```
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-key

# Direct PostgreSQL Connection (Optional)
DATABASE_URL=postgresql://postgres.your-project-id:your-password@aws-1-us-east-1.pooler.supabase.com:6543/postgres
```

## Usage

The database module provides a simple interface for connecting to and querying the database:

```python
from src.data.database import get_db

# Get database connection
db = get_db()

# Connect to the database
db.connect()

# Query data
assets = db.query("assets", limit=10)
print(assets)

# Close connection when done
db.close()
```

## Connection Methods

The database module will attempt to connect using the Supabase client first, and fall back to a direct PostgreSQL connection if that fails.

### Supabase Client

The Supabase client provides a high-level API for interacting with your Supabase database, including:

- Authentication
- Storage
- Realtime subscriptions
- Database queries with Row Level Security

### Direct PostgreSQL Connection

The direct PostgreSQL connection provides lower-level access to the database using the `psycopg2` library.

## Required Dependencies

Install the required dependencies:

```bash
pip install supabase psycopg2-binary python-dotenv
```

## Database Schema

The database schema will be automatically created when you first connect to the database. The schema includes the following tables:

- `assets`: Stores information about financial assets
- `relationships`: Stores relationships between assets
- `metrics`: Stores metrics for assets
- `users`: Stores user information

## Testing

You can test the database connection using the provided test scripts:

```bash
python test_db_module.py
```
