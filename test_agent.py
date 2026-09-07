from pathlib import Path

from agent_core import extract_payment_record
from tracker import add_record, get_status


if __name__ == "__main__":
    sample_dir = Path(__file__).parent / "sample_data"
    for email_file in ["email1.txt", "email1b.txt", "email2.txt", "email3.txt"]:
        add_record(extract_payment_record(sample_dir / email_file))

    print(f"Status for invoice 003: {get_status('003')}")
    print(f"Status for invoice 004: {get_status('004')}")