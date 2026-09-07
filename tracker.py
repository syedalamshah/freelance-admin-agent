import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from agent_core import extract_payment_record


DATABASE_PATH = Path(__file__).with_name("tracker.db")


@contextmanager
def _connect():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS payment_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT NOT NULL,
                invoice_number TEXT,
                client_name TEXT,
                amount REAL,
                currency TEXT,
                sent_date TEXT,
                due_days INTEGER,
                notes TEXT
            )
            """
        )
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(payment_records)")
        }
        if "sent_date" not in columns:
            connection.execute("ALTER TABLE payment_records ADD COLUMN sent_date TEXT")
        if "due_days" not in columns:
            connection.execute("ALTER TABLE payment_records ADD COLUMN due_days INTEGER")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()


def add_record(record: dict) -> None:
    """Insert one extracted payment record into the SQLite tracker."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO payment_records (
                document_type, invoice_number, client_name, amount,
                currency, sent_date, due_days, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("document_type"),
                record.get("invoice_number"),
                record.get("client_name"),
                record.get("amount"),
                record.get("currency"),
                record.get("sent_date"),
                record.get("due_days"),
                record.get("notes"),
            ),
        )


def get_status(invoice_number: str) -> dict:
    """Return the payment status for an invoice and its matching payments."""
    with _connect() as connection:
        invoice = connection.execute(
            """
            SELECT invoice_number, client_name, amount, sent_date, due_days
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
                 SELECT COALESCE(SUM(amount), 0) AS received_amount,
                     MIN(sent_date) AS payment_sent_date
            FROM payment_records
            WHERE invoice_number = ? AND document_type = 'payment_confirmation'
            """,
            (invoice_number,),
        ).fetchone()

    expected_amount = invoice["amount"]
    received_amount = payment["received_amount"]
    if received_amount == 0:
        status = "pending"
    else:
        payment_sent_date = payment["payment_sent_date"]
        due_date = None
        if invoice["sent_date"] is not None and invoice["due_days"] is not None:
            due_date = date.fromisoformat(invoice["sent_date"]) + timedelta(
                days=invoice["due_days"]
            )

        if due_date is not None and payment_sent_date is not None:
            timeliness = (
                "on_time"
                if date.fromisoformat(payment_sent_date) <= due_date
                else "late"
            )
        else:
            timeliness = "not_applicable"

        amount_status = (
            "paid_full"
            if expected_amount is not None and received_amount >= expected_amount
            else "paid_short"
        )
        status = f"{amount_status}_{'late' if timeliness == 'late' else 'on_time'}"

    if status == "pending":
        timeliness = "not_applicable"

    return {
        "invoice_number": invoice["invoice_number"],
        "client_name": invoice["client_name"],
        "expected_amount": expected_amount,
        "received_amount": received_amount,
        "status": status,
        "timeliness": timeliness,
    }


if __name__ == "__main__":
    sample_dir = Path(__file__).parent / "sample_data"
    for email_file in ["email1.txt", "email1b.txt", "email2.txt", "email3.txt"]:
        record = extract_payment_record(sample_dir / email_file)
        add_record(record)
        print(f"Added {email_file}: {record}")

    print(f"Status for invoice 003: {get_status('003')}")
    print(f"Status for invoice 004: {get_status('004')}")