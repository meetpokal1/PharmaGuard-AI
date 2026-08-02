from groq import Groq
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


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

    text = text.strip()

    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return text


def detect_intent(message):

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": message},
        ],
    )

    result = response.choices[0].message.content.strip().upper()

    if "COMPLAINT" in result:
        return "COMPLAINT"

    return "CHAT"


def generate_chat_reply(message):

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
    )

    return response.choices[0].message.content.strip()


def ask_ai(prompt, previous_data=None):

    if previous_data is None:
        previous_data = {}

    intent = detect_intent(prompt)

    # Normal conversation

    if intent == "CHAT":

        return json.dumps({"type": "chat", "reply": generate_chat_reply(prompt)})

    # Complaint extraction

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
    )

    return strip_code_fences(response.choices[0].message.content or "")
