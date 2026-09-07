import json

from strands import Agent

from agent_core import MODEL_ID


FOLLOWUP_SYSTEM_PROMPT = """
You draft short, professional follow-up messages to freelance clients about invoices.
Return only the message text, with no subject line, analysis, labels, or quotation marks.
Use a warm, concise, natural tone and assume the client is acting in good faith.
Do not sound accusatory, threatening, or overly formal.

For a pending invoice, write a gentle, friendly reminder asking about the invoice status.
For a short payment, thank the client for the payment, explain that the amount received
is less than the invoiced amount, and ask whether they could send the remaining balance.
A bank fee or processing deduction may explain the difference, so phrase this as a
polite check rather than an accusation.
For a full payment that arrived late, write a light, friendly check-in rather than a
strict reminder, since the delay may simply have been a review or processing delay.
Include the invoice number and relevant amounts when they are available.
""".strip()


followup_agent = Agent(
    model=MODEL_ID,
    system_prompt=FOLLOWUP_SYSTEM_PROMPT,
    callback_handler=None,
)


def draft_followup(status: dict) -> str | None:
    """Draft a client follow-up message based on an invoice status."""
    invoice_status = status.get("status")
    if invoice_status == "paid_full_on_time":
        return None

    if invoice_status == "pending":
        request = (
            "Draft a gentle reminder asking the client for an update on the pending invoice. "
            "Assume it has been a while since the invoice was sent."
        )
    elif invoice_status in {"paid_short_on_time", "paid_short_late"}:
        request = (
            "Draft a polite message thanking the client for the payment, noting that the "
            "amount received does not match the invoiced amount, and asking whether they "
            "could send the remaining balance. Mention that a bank or processing fee may "
            "explain the difference."
        )
    elif invoice_status == "paid_full_late":
        request = (
            "Draft a light, friendly check-in about the late full payment. Do not make it "
            "sound like a strict reminder or complaint."
        )
    else:
        raise ValueError(f"Unsupported invoice status: {invoice_status!r}")

    prompt = f"""{request}

Invoice status data:
{json.dumps(status, sort_keys=True)}
"""
    return str(followup_agent(prompt)).strip()


if __name__ == "__main__":
    from tracker import get_status

    for invoice_number in ("003", "004"):
        status = get_status(invoice_number)
        message = draft_followup(status)
        print(f"Follow-up for invoice {invoice_number}:")
        print(message if message is not None else "No follow-up needed")
