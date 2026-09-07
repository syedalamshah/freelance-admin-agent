from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from strands import Agent


MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


class PaymentRecord(BaseModel):
    """Structured data extracted from one freelance payment email."""

    document_type: Literal["invoice", "payment_confirmation"] = Field(
        description="Whether the email is an invoice sent by the freelancer or a payment confirmation received by the freelancer"
    )
    invoice_number: str | None = Field(
        description="The invoice number mentioned in the email, without a leading #, or null when it is not stated"
    )
    client_name: str | None = Field(
        description="The client or company name, or null when it is not stated"
    )
    amount: float | None = Field(
        description="The primary invoice or payment amount, or null when it is not stated"
    )
    currency: str | None = Field(
        description="The currency code or symbol associated with the primary amount, or null when it is not stated"
    )
    sent_date: str | None = Field(
        description="The actual date the invoice was sent or payment was made in ISO format YYYY-MM-DD, or null when it cannot be determined"
    )
    due_days: int | None = Field(
        description="For invoices only, the number of days until payment is due; null for payment confirmations or when not stated"
    )
    notes: str | None = Field(
        description="Fees, delays, or other payment-specific notes; null for invoices or when no such notes are mentioned"
    )


SYSTEM_PROMPT = """
You are a freelance payment tracker. Analyze exactly one plain-text email and return
only the requested structured record.

Classify the email as:
- invoice: an invoice or billing request sent by the freelancer to a client.
- payment_confirmation: a message confirming that money was sent to the freelancer.

Extract the invoice number, primary client name, amount, currency, sent_date, and
due_days from the email. Preserve the invoice number as a string and remove a
leading '#'. sent_date is the actual date the invoice was sent or the payment was
made, in ISO format YYYY-MM-DD. If no year is given, assume 2026. Convert relative
dates to ISO format using sent_date as the reference when the reference is
available. Do not confuse due-date language such as "within 7 days of this email"
with sent_date: put 7 in due_days and keep sent_date as the actual invoice date, or
null if that date cannot be determined. due_days is for invoices only and must be
null for payment confirmations. For payment confirmations, include concise notes
about fees, delays, deductions, or other payment issues when they are mentioned.
Use null when a value is not stated or cannot be determined. Do not invent missing
facts.
""".strip()


agent = Agent(
    model=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
    structured_output_model=PaymentRecord,
    callback_handler=None,
)


def extract_payment_record(file_path: str | Path) -> dict:
    """Read an email file and return its extracted payment record as a dictionary."""
    email_path = Path(file_path)
    email_text = email_path.read_text(encoding="utf-8")

    prompt = f"""Extract the payment record from this email.

--- EMAIL START ---
{email_text}
--- EMAIL END ---
"""
    result = agent(prompt)
    return result.structured_output.model_dump()


if __name__ == "__main__":
    sample_dir = Path(__file__).parent / "sample_data"
    for email_file in ["email1.txt", "email2.txt", "email3.txt"]:
        print(f"\n--- {email_file} ---")
        print(extract_payment_record(sample_dir / email_file))