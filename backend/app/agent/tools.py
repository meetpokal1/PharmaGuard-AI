from ai_service import ask_ai, COMPLAINT_SCHEMA_KEYS
from utils.complaint_id import generate_complaint_id
from utils.case_store import save_complaint, get_batch_signals
import json

CRITICAL_KEYWORDS = [
    "death",
    "died",
    "life threatening",
    "life-threatening",
    "serious reaction",
    "contamination",
    "contaminated",
    "sterility",
    "non-sterile",
    "hospitalized",
    "hospitalised",
    "anaphylaxis",
    "severe side effect",
    "severe allergic reaction",
    "wrong medicine administered",
    "wrong drug administered",
]

MAJOR_KEYWORDS = [
    "wrong label",
    "wrong strength",
    "wrong batch",
    "batch mismatch",
    "damaged",
    "defect",
    "defective",
    "discoloration",
    "discoloured",
    "discolored",
    "quality issue",
    "broken",
    "leaking",
    "leakage",
    "missing tablets",
    "expired",
    "regulatory concern",
]

# Everything else (typos, documentation requests, suggestions, general
# feedback) defaults to Minor - matches the Mission spec's "no direct
# patient safety impact" bucket.


def classify_severity(complaint_data: dict) -> dict:
    """Keyword-classify severity from the single 'complaint' field (the
    only free-text field the LLM is asked to populate). Critical keywords
    are checked first so a complaint that mentions both a quality defect
    AND a safety issue is correctly escalated to Critical."""

    text = str(complaint_data.get("complaint", "")).lower()

    for word in CRITICAL_KEYWORDS:
        if word in text:
            return {
                "level": "Critical",
                "reason": "Patient safety risk.",
                "risk_level": "High",
                "recommended_action": "Escalate immediately to QA/Pharmacovigilance for urgent investigation.",
            }

    for word in MAJOR_KEYWORDS:
        if word in text:
            return {
                "level": "Major",
                "reason": "Potential product quality impact.",
                "risk_level": "Medium",
                "recommended_action": "Route to QA for batch investigation and root-cause analysis.",
            }

    return {
        "level": "Minor",
        "reason": "No direct patient safety impact.",
        "risk_level": "Low",
        "recommended_action": "Log for documentation review; no urgent action required.",
    }


def log_complaint_tool(state):

    message = state["message"]

    previous_data = state.get("complaint_data", {}) or {}

    # complaint_data must exist on every path, not just the JSONDecodeError
    # branch - previously this only got defined inside `except`, which
    # meant every successful AI call crashed with a NameError.
    complaint_data = previous_data.copy()

    reply = ask_ai(message, previous_data)

    try:
        new_data = json.loads(reply)
    except json.JSONDecodeError:
        new_data = {}

    if isinstance(new_data, dict):
        for key in COMPLAINT_SCHEMA_KEYS:
            value = new_data.get(key)
            if value not in ("", None):
                complaint_data[key] = value

                # Do not create complaint records from vague messages
    complaint_text = complaint_data.get("complaint", "").strip()

    if len(complaint_text) < 15:

        return {
            "message": message,
            "complaint_data": complaint_data,
            "response": (
                "I can help you create a complaint case. "
                "Please provide more details about the issue, "
                "such as product name, batch number, or what happened."
            ),
            "chat_history": state.get("chat_history", []),
        }

    # Ensure every schema field exists even if never set, so the frontend
    # never has to guard against missing keys.
    for key in COMPLAINT_SCHEMA_KEYS:
        complaint_data.setdefault(key, "")
    missing_fields = []

    required_fields = ["product_name", "complaint"]

    for field in required_fields:
        if not complaint_data.get(field):
            missing_fields.append(field)

    if missing_fields:

        return {
            "message": message,
            "complaint_data": complaint_data,
            "response": (
                "I have noted your complaint. "
                "Could you please provide more details so I can create the complaint case?\n\n"
                "Please provide:\n"
                "- Product name\n"
                "- Batch number (if available)\n"
                "- What happened with the product\n"
                "- Any patient safety concern"
            ),
            "chat_history": state.get("chat_history", []),
        }

    if "complaint_id" not in complaint_data:
        complaint_data["complaint_id"] = generate_complaint_id()

    if "status" not in complaint_data:
        complaint_data["status"] = "Under Investigation"

    if "department" not in complaint_data:
        complaint_data["department"] = "QA Investigation"

    severity_result = classify_severity(complaint_data)

    complaint_data["severity"] = severity_result["level"]
    complaint_data["severity_reason"] = severity_result["reason"]
    complaint_data["risk_level"] = severity_result["risk_level"]
    complaint_data["recommended_action"] = severity_result["recommended_action"]

    # Persist the case once its required details are present. Corrections reuse
    # the existing complaint ID and create an audit event only when fields change.
    saved_case = save_complaint(complaint_data)
    complaint_data["created_at"] = saved_case["created_at"]
    complaint_data["updated_at"] = saved_case["updated_at"]

    signal_match = None
    batch_key = str(complaint_data.get("batch_number") or "").strip().casefold()
    product_key = str(complaint_data.get("product_name") or "").strip().casefold()
    if batch_key:
        for signal in get_batch_signals(days=30, min_reports=2):
            if signal.get("batch_key") == batch_key and signal.get("product_key") == product_key:
                signal_match = signal
                break

    if signal_match:
        complaint_data["batch_signal"] = {
            "report_count": signal_match["report_count"],
            "critical_count": signal_match["critical_count"],
            "review_note": signal_match["review_note"],
        }

    product = complaint_data.get("product_name") or "the product"

    ai_reply = (
        f"Thank you for providing the details.\n\n"
        f"Complaint ID: {complaint_data['complaint_id']}\n"
        f"Product: {product}\n"
        f"Severity: {complaint_data['severity']} (Risk: {complaint_data['risk_level']})\n"
        f"Status: {complaint_data['status']}\n"
        f"Department: {complaint_data['department']}\n\n"
        f"Reason: {complaint_data['severity_reason']}\n"
        f"Recommended action: {complaint_data['recommended_action']}\n\n"
        + (
            f"Potential repeat-batch signal: {signal_match['report_count']} reports for "
            f"this product/batch were recorded in the last 30 days. Verify the source cases; "
            f"this signal does not confirm a defect.\n\n"
            if signal_match else ""
        )
        + "Your complaint has been recorded successfully."
    )

    return {
        "message": message,
        "complaint_data": complaint_data,
        "response": ai_reply,
        "chat_history": state.get("chat_history", []),
    }
