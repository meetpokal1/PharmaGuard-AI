from groq import Groq
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()


def get_groq_client():
    """Lazily initialize the Groq client if an API key is configured."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not api_key.strip():
        return None
    try:
        return Groq(api_key=api_key.strip())
    except Exception:
        return None


COMPLAINT_SCHEMA_KEYS = [
    "customer_name",
    "product_name",
    "product_strength",
    "batch_number",
    "manufacturing_date",
    "expiry_date",
    "affected_quantity",
    "complaint",
]


INTENT_PROMPT = """
You are an intent classifier for PharmaGuard AI.

Your job is to decide whether the user wants to create/update a pharmaceutical complaint or just chat.

Return ONLY one word:

COMPLAINT
or
CHAT


Choose COMPLAINT ONLY when the user provides actual complaint details.

COMPLAINT examples:

- Apollo Pharmacy reported damaged Amoxicillin capsules.
- Patient received the wrong medicine.
- The product packaging was broken.
- Batch number ABC123 has contamination.
- The medicine has expired.
- Tablets have discoloration.
- Wrong strength was printed on the label.
- Customer reported allergic reaction after using the medicine.


Choose CHAT when the user is only starting a conversation, asking for help, or has not provided enough details.

CHAT examples:

- Hello
- Hi
- Hii
- Hey
- What can you do?
- Who are you?
- Thank you
- I need help
- I have an issue
- I have a problem
- Something is wrong
- Can you help me?
- Tell me about this system


Important rules:

1. "I have an issue" alone is NOT a complaint.
2. "I have a problem" alone is NOT a complaint.
3. Ask for complaint details before creating a complaint.
4. Only select COMPLAINT when there is information about:
   - product
   - medicine
   - batch
   - quality issue
   - patient impact
   - packaging issue
   - safety concern
   - specific complaint description
"""

SYSTEM_PROMPT_TEMPLATE = """
You are PharmaGuard AI, a pharmaceutical complaint extraction engine.

Your job is to extract complaint information only when the user provides a valid pharmaceutical complaint.
- If the message does not contain a real complaint, keep all fields empty.
- Do not create a complaint record from greetings, questions, or vague statements.
Previous complaint data:

{previous_json}


Rules:

- Update existing information if user provides corrections.
- If user says "sorry, actually X", update only that field.
- Do not create a new complaint for corrections.
- Do not invent information.
- Do not guess product names.
- Do not guess batch numbers.
- Do not create severity or complaint IDs.
- Only extract information available in the user's message.
- Missing fields must remain empty strings.


The complaint field should contain the complete description of the issue.


Return ONLY valid JSON.

Schema:

{{
"customer_name":"",
"product_name":"",
"product_strength":"",
"batch_number":"",
"manufacturing_date":"",
"expiry_date":"",
"affected_quantity":"",
"complaint":""
}}
"""


def strip_code_fences(text):
    text = (text or "").strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def detect_intent(message: str) -> str:
    """Classify message as COMPLAINT or CHAT, using Groq when available with rule-based fallback."""
    client = get_groq_client()
    if client:
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": INTENT_PROMPT},
                    {"role": "user", "content": message},
                ],
                timeout=15.0,
            )
            result = (response.choices[0].message.content or "").strip().upper()
            if "COMPLAINT" in result:
                return "COMPLAINT"
            return "CHAT"
        except Exception:
            # Fall back gracefully to heuristic intent detection
            pass

    lower = (message or "").lower()
    complaint_signals = [
        "damaged", "defect", "broken", "leaking", "leakage", "discolor", "discolour",
        "contamination", "contaminated", "sterile", "sterility", "reaction", "hospital",
        "adverse", "batch", "expired", "capsule", "tablet", "vial", "dosage", "strength",
        "wrong medicine", "wrong drug", "packaging", "mg", "ml", "pharma", "recall",
        "unsealed", "foreign matter", "glass", "particulate"
    ]
    if any(sig in lower for sig in complaint_signals):
        return "COMPLAINT"

    return "CHAT"


def generate_chat_reply(message: str) -> str:
    """Generate conversational assistance, falling back to deterministic response if API is unreachable."""
    client = get_groq_client()
    if client:
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": """
You are PharmaGuard AI.

You assist pharmaceutical teams in managing complaints.

You can:
- Analyze complaints
- Extract information
- Review uploaded PDFs
- Explain severity
- Help update complaint details

Rules:
- Reply naturally.
- Do not create fake complaint records.
- Do not generate complaint IDs.
- Do not assign severity without complaint details.
- If message is unclear, ask the user for complaint details.
""",
                    },
                    {"role": "user", "content": message},
                ],
                timeout=15.0,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception:
            pass

    return (
        "Hello! I am PharmaGuard AI, your assistant for logging and triaging pharmaceutical quality and adverse event complaints. "
        "You can describe a product defect (e.g. broken seals, discoloration, or adverse reactions) with the product name and batch number, "
        "or upload a complaint PDF document for automated extraction."
    )


def ask_ai(prompt: str, previous_data: dict | None = None) -> str:
    """Extract complaint fields into JSON, falling back to rule-based parser if LLM is offline."""
    if previous_data is None:
        previous_data = {}

    intent = detect_intent(prompt)
    if intent == "CHAT":
        return json.dumps({"type": "chat", "reply": generate_chat_reply(prompt)})

    client = get_groq_client()
    if client:
        try:
            editable_previous = {
                key: previous_data.get(key, "") for key in COMPLAINT_SCHEMA_KEYS
            }
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                previous_json=json.dumps(editable_previous)
            )
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                timeout=20.0,
            )
            return strip_code_fences(response.choices[0].message.content or "")
        except Exception:
            pass

    # Deterministic rule-based extraction fallback
    extracted = {key: previous_data.get(key, "") for key in COMPLAINT_SCHEMA_KEYS}

    # Extract batch number (e.g. "batch: ABC-123", "Batch Number BATCH-7", "batch #XYZ")
    batch_match = re.search(r'(?:batch(?:\s*(?:no|number|#))?[:\s]+)([A-Za-z0-9\-]+)', prompt, re.IGNORECASE)
    if batch_match:
        extracted["batch_number"] = batch_match.group(1).strip()

    # Extract strength (e.g. "500 mg", "10 ml", "250mg")
    strength_match = re.search(r'(\d+\s*(?:mg|ml|mcg|g))\b', prompt, re.IGNORECASE)
    if strength_match:
        extracted["product_strength"] = strength_match.group(1).strip()

    # Extract customer
    customer_match = re.search(r'(?:customer|pharmacy|hospital|clinic|reported by)[:\s]+([^,\n.]+)', prompt, re.IGNORECASE)
    if customer_match:
        extracted["customer_name"] = customer_match.group(1).strip()

    # Extract product name
    COMMON_MEDICINES = [
        "Amoxicillin", "Paracetamol", "Ibuprofen", "Metformin", "Atorvastatin",
        "Azithromycin", "Omeprazole", "Ciprofloxacin", "Cough Syrup", "PainRelief",
        "Insulin", "Aspirin", "Lisinopril", "Losartan", "Cetirizine"
    ]
    for candidate in COMMON_MEDICINES:
        if re.search(r'\b' + re.escape(candidate) + r'\b', prompt, re.IGNORECASE):
            extracted["product_name"] = candidate
            break

    if not extracted.get("product_name"):
        med_form_match = re.search(
            r'\b([A-Za-z]{3,25})\s+(?:\d+\s*(?:mg|ml|mcg|g)\s+)?(?:tablets|capsules|syrup|suspension|injection|drops|ointment|cream|solution)\b',
            prompt,
            re.IGNORECASE
        )
        if med_form_match:
            extracted["product_name"] = med_form_match.group(1).capitalize()

    if not extracted.get("product_name"):
        product_match = re.search(r'(?:product|medicine|drug)[:\s]+([^,\n.]+)', prompt, re.IGNORECASE)
        if product_match:
            extracted["product_name"] = product_match.group(1).strip()

    # Description
    extracted["complaint"] = prompt.strip()

    return json.dumps(extracted)
