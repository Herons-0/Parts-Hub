"""CLI entry point to (re)build the product catalog from all vendors.

Usage (from the project root):
    python -m scripts.ingest

Run it once before starting the server, and re-run periodically (e.g. a daily cron
or Windows Task Scheduler job) to refresh prices and stock.
"""
from app.scrapers.runner import ingest_all

if __name__ == "__main__":
    ingest_all()
