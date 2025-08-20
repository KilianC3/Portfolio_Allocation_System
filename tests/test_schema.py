from pathlib import Path
import re

def test_schema_contains_positions_and_ticker_guard():
    schema = Path('database/schema.sql').read_text()
    assert 'CREATE TABLE IF NOT EXISTS positions' in schema
    required = [
        'wiki_views',
        'google_trends',
        'reddit_mentions',
        'app_reviews',
        'gov_contracts',
        'analyst_ratings',
    ]
    for table in required:
        pattern = rf"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS ticker"
        assert re.search(pattern, schema)
