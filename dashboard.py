import tempfile
from pathlib import Path

import streamlit as st

from agent_core import extract_payment_record
from followup import draft_followup
from tracker import add_record, get_status, list_invoice_numbers


STATUS_MARKERS = {
    "paid_full_on_time": "🟢",
    "paid_full_late": "🟡",
    "pending": "🟡",
    "paid_short_late": "🔴",
    "paid_short_on_time": "🔴",
}


st.set_page_config(
    page_title="Freelance Admin Agent",
    page_icon="💼",
    layout="wide",
)


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


def _render_summary_metrics(statuses: list[dict]) -> None:
    total_invoices = len(statuses)
    overdue_or_short = sum(
        status["status"].endswith("_late")
        or status["status"].startswith("paid_short")
        for status in statuses
    )
    pending = sum(status["status"] == "pending" for status in statuses)
    outstanding = sum(
        max((status["expected_amount"] or 0) - (status["received_amount"] or 0), 0)
        for status in statuses
    )

    total_card, issue_card, pending_card, outstanding_card = st.columns(4)
    total_card.metric("📄 Invoices tracked", total_invoices)
    issue_card.metric("⚠️ Overdue / short", overdue_or_short)
    pending_card.metric("🕒 Pending", pending)
    outstanding_card.metric("💰 Amount outstanding", f"${outstanding:,.2f}")


def _render_status_table(statuses: list[dict]) -> None:
    table_rows = [
        {
            "Invoice": status["invoice_number"],
            "Client": status["client_name"] or "",
            "Expected": status["expected_amount"] or 0,
            "Received": status["received_amount"] or 0,
            "Status": f"{STATUS_MARKERS.get(status['status'], '⚪')} {status['status']}",
            "Timeliness": status["timeliness"],
        }
        for status in statuses
    ]
    st.dataframe(
        table_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Invoice": st.column_config.TextColumn("Invoice", width="small"),
            "Client": st.column_config.TextColumn("Client"),
            "Expected": st.column_config.NumberColumn(
                "Expected", format="$%.2f", width="small"
            ),
            "Received": st.column_config.NumberColumn(
                "Received", format="$%.2f", width="small"
            ),
            "Status": st.column_config.TextColumn(
                "Status",
                help="Green: paid in full on time; yellow: pending or late; red: short payment.",
            ),
            "Timeliness": st.column_config.TextColumn("Timeliness", width="small"),
        },
    )


def main() -> None:
    st.title("Freelance Admin Agent")
    st.caption("Paste an invoice or payment email to update your tracker.")

    st.sidebar.header("📄 Process Email")
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

    st.subheader("📊 Invoice Status")
    statuses = [get_status(number) for number in list_invoice_numbers()]
    if not statuses:
        st.info("No invoices have been tracked yet.")
        return

    _render_summary_metrics(statuses)
    _render_status_table(statuses)

    st.subheader("💬 Follow-ups")
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