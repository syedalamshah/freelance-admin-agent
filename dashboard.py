import html
import tempfile
from pathlib import Path

import streamlit as st

from agent_core import extract_payment_record
from followup import draft_followup
from tracker import add_record, get_status, list_invoice_numbers


STATUS_COLORS = {
    "paid_full_on_time": "#d1fae5",
    "paid_full_late": "#fef3c7",
    "pending": "#fef3c7",
    "paid_short_late": "#fee2e2",
    "paid_short_on_time": "#fee2e2",
}


def _process_email(email_text: str) -> dict:
    """Persist pasted email text temporarily, extract it, and track the record."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".txt",
            delete=False,
        ) as temporary_file:
            temporary_file.write(email_text)
            temporary_path = Path(temporary_file.name)

        record = extract_payment_record(temporary_path)
        add_record(record)
        return record
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _render_status_table(statuses: list[dict]) -> None:
    rows = []
    for status in statuses:
        invoice_number = html.escape(str(status["invoice_number"]))
        client_name = html.escape(str(status["client_name"] or ""))
        status_value = status["status"]
        background = STATUS_COLORS.get(status_value, "#e5e7eb")
        status_badge = (
            f'<span style="background:{background}; padding:0.2rem 0.45rem; '
            f'border-radius:0.3rem;">{html.escape(status_value)}</span>'
        )
        rows.append(
            f"<tr><td>{invoice_number}</td><td>{client_name}</td>"
            f"<td>{status['expected_amount'] or 0:.2f}</td>"
            f"<td>{status['received_amount'] or 0:.2f}</td>"
            f"<td>{status_badge}</td><td>{html.escape(status['timeliness'])}</td></tr>"
        )

    table = """<table style="width:100%; border-collapse:collapse;">
<thead><tr><th>Invoice</th><th>Client</th><th>Expected</th>
<th>Received</th><th>Status</th><th>Timeliness</th></tr></thead>
<tbody>{}</tbody></table>""".format("".join(rows))
    st.markdown(table, unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Freelance Admin Agent", page_icon="$", layout="wide")
    st.title("Freelance Admin Agent")
    st.caption("Paste an invoice or payment email to update your tracker.")

    st.sidebar.header("Process Email")
    email_text = st.sidebar.text_area(
        "Email text",
        height=260,
        placeholder="Paste the email text here...",
    )
    if st.sidebar.button("Process Email", type="primary", use_container_width=True):
        if not email_text.strip():
            st.sidebar.warning("Paste an email before processing.")
        else:
            with st.spinner("Extracting and saving email..."):
                record = _process_email(email_text)
            st.session_state["last_processed_record"] = record
            st.rerun()

    if "last_processed_record" in st.session_state:
        record = st.session_state["last_processed_record"]
        st.sidebar.success(
            f"Saved {record.get('document_type', 'record')} "
            f"{record.get('invoice_number') or '(no invoice number)'}"
        )

    st.subheader("Invoice Status")
    statuses = [get_status(number) for number in list_invoice_numbers()]
    if not statuses:
        st.info("No invoices have been tracked yet.")
        return

    _render_status_table(statuses)

    st.subheader("Follow-ups")
    followup_count = 0
    for status in statuses:
        invoice_number = status["invoice_number"]
        draft_key = f"draft_{invoice_number}_{status['status']}"
        if draft_key not in st.session_state:
            st.session_state[draft_key] = draft_followup(status)
        message = st.session_state[draft_key]
        if message is None:
            continue

        followup_count += 1
        with st.expander(f"Invoice {invoice_number} - {status['status']}"):
            st.text_area("Draft message", key=draft_key, height=140)
            approve, edit, reject = st.columns(3)
            if approve.button("Approve", key=f"approve_{invoice_number}"):
                st.success("Follow-up approved. Sending is not connected yet.")
            if edit.button("Edit", key=f"edit_{invoice_number}"):
                st.info("Edit the message above, then copy it when ready.")
            if reject.button("Reject", key=f"reject_{invoice_number}"):
                st.info("Follow-up rejected.")

    if followup_count == 0:
        st.success("No follow-ups are needed right now.")


if __name__ == "__main__":
    main()