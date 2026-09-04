import sqlite3
from pathlib import Path

from agent_core import extract_payment_record


DATABASE_PATH = Path(__file__).with_name("tracker.db")


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_type TEXT NOT NULL,
            invoice_number TEXT,
            client_name TEXT,
            amount REAL,
            currency TEXT,
            date TEXT,
            notes TEXT
        )
        """
    )
    return connection


def add_record(record: dict) -> None:
    """Insert one extracted payment record into the SQLite tracker."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO payment_records (
                document_type, invoice_number, client_name, amount,
                currency, date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("document_type"),
                record.get("invoice_number"),
                record.get("client_name"),
                record.get("amount"),
                record.get("currency"),
                record.get("date"),
                record.get("notes"),
            ),
        )


def get_status(invoice_number: str) -> dict:
    """Return the payment status for an invoice and its matching payments."""
    with _connect() as connection:
        invoice = connection.execute(
            """
            SELECT invoice_number, client_name, amount
            FROM payment_records
            WHERE invoice_number = ? AND document_type = 'invoice'
            ORDER BY id
            LIMIT 1
            """,
            (invoice_number,),
        ).fetchone()

        if invoice is None:
            raise ValueError(f"Invoice {invoice_number!r} was not found")

        payment = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS received_amount
            FROM payment_records
            WHERE invoice_number = ? AND document_type = 'payment_confirmation'
            """,
            (invoice_number,),
        ).fetchone()

    expected_amount = invoice["amount"]
    received_amount = payment["received_amount"]
    if received_amount == 0:
        status = "pending"
    elif expected_amount is not None and received_amount >= expected_amount:
        status = "paid_full"
    else:
        status = "paid_short"

    return {
        "invoice_number": invoice["invoice_number"],
        "client_name": invoice["client_name"],
        "expected_amount": expected_amount,
        "received_amount": received_amount,
        "status": status,
    }


if __name__ == "__main__":
    sample_dir = Path(__file__).parent / "sample_data"
    for email_file in ["email1.txt", "email1b.txt", "email2.txt", "email3.txt"]:
        record = extract_payment_record(sample_dir / email_file)
        add_record(record)
        print(f"Added {email_file}: {record}")

    print(f"Status for invoice 003: {get_status('003')}")
    print(f"Status for invoice 004: {get_status('004')}")