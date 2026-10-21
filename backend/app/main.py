from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.graph import create_agent
from utils.case_store import list_complaints, get_complaint, get_case_events, get_batch_signals, init_case_store
import os
import fitz

agent = create_agent()

app = FastAPI()


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


# Temporary memory storage
# Later we move this to database (Mission 4)
conversation_memory = {"demo-user": {"complaint_data": {}, "chat_history": []}}


@app.on_event("startup")
def startup_case_store():
    init_case_store()


@app.get("/complaints")
def complaint_register(
    limit: int = Query(50, ge=1, le=200),
    severity: str | None = None,
    status: str | None = None,
    batch_number: str | None = None,
):
    """List saved cases for a review queue; filters are optional."""
    return {
        "cases": list_complaints(
            limit=limit,
            severity=severity,
            status=status,
            batch_number=batch_number,
        )
    }


@app.get("/complaints/{complaint_id}/events")
def complaint_events(complaint_id: str):
    """Return create/update history for a single complaint case."""
    case = get_complaint(complaint_id)
    if case is None:
        return JSONResponse(status_code=404, content={"error": "Complaint case not found"})
    return {"events": get_case_events(complaint_id)}


@app.get("/complaints/{complaint_id}")
def complaint_detail(complaint_id: str):
    case = get_complaint(complaint_id)
    if case is None:
        return JSONResponse(status_code=404, content={"error": "Complaint case not found"})
    return {"case": case}


@app.get("/analytics/batch-signals")
def batch_signals(
    days: int = Query(30, ge=1, le=365),
    min_reports: int = Query(2, ge=2, le=100),
):
    """Return repeat product/batch patterns for qualified human review."""
    return {
        "window_days": days,
        "signals": get_batch_signals(days=days, min_reports=min_reports),
        "note": (
            "Signals show repeated reports, not confirmed defects or causality. "
            "Verify product/batch identity and investigate using approved procedures."
        ),
    }


@app.get("/")
def home():
    return {"message": "Welcome to AI Complaint Management System 🚀"}


@app.get("/files")
async def get_files():
    files = [
        f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))
    ]
    return {"files": files}


@app.get("/files/{filename}")
def get_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    return FileResponse(path=file_path, media_type="application/pdf")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400, content={"error": "Only PDF files are supported"}
        )

    safe_name = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    return {"message": f"{safe_name} uploaded successfully", "filename": safe_name}


@app.get("/extract/{filename}")
def extract_pdf(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "File not found"})
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as exc:
        return JSONResponse(
            status_code=500, content={"error": f"Failed to read PDF: {exc}"}
        )
    return {"text": text}


@app.post("/chat")
def chat(request: ChatRequest):

    user_id = "demo-user"

    memory = conversation_memory[user_id]

    result = agent.invoke(
        {
            "message": request.message,
            "complaint_data": memory["complaint_data"],
            "response": "",
            "chat_history": memory["chat_history"],
        },
        config={"configurable": {"thread_id": user_id}},
    )

    conversation_memory[user_id]["complaint_data"] = result.get(
        "complaint_data", memory["complaint_data"]
    )

    conversation_memory[user_id]["chat_history"].append(
        {"user": request.message, "ai": result.get("response", "")}
    )

    return {
        "reply": result.get("response", ""),
        "complaint": result.get("complaint_data", {}),
    }
