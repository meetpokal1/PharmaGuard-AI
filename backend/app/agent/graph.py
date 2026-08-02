from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import ComplaintState
from agent.tools import log_complaint_tool

from ai_service import detect_intent, generate_chat_reply


def receive_message(state: ComplaintState):

    return state


def route_message(state: ComplaintState):

    intent = detect_intent(state["message"])

    return {"intent": intent}


def chat_response(state: ComplaintState):

    reply = generate_chat_reply(state["message"])

    return {"response": reply, "complaint_data": state.get("complaint_data", {})}


def complaint_route(state):

    if state.get("intent") == "CHAT":

        return "chat_reply"

    return "log_complaint"


def create_agent():

    graph = StateGraph(ComplaintState)

    graph.add_node("receive_message", receive_message)

    graph.add_node("route_message", route_message)

    graph.add_node("chat_reply", chat_response)

    graph.add_node("log_complaint", log_complaint_tool)

    graph.set_entry_point("receive_message")

    graph.add_edge("receive_message", "route_message")

    graph.add_conditional_edges(
        "route_message",
        complaint_route,
        {"chat_reply": "chat_reply", "log_complaint": "log_complaint"},
    )

    graph.add_edge("chat_reply", END)

    graph.add_edge("log_complaint", END)

    memory = MemorySaver()

    return graph.compile(checkpointer=memory)
