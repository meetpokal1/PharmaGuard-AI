from typing import TypedDict, List


class ComplaintState(TypedDict):

    message: str

    complaint_data: dict

    chat_history: List[dict]

    response: str

    intent: str
