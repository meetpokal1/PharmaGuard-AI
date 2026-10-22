from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent.graph import create_agent
from utils.case_store import list_complaints, get_complaint, get_case_events, get_batch_signals, get_case_summary, init_case_store
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import pymupdf as fitz

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    init_case_store()
    yield

agent = create_agent()

app = FastAPI(title="PharmaGuard AI API", version="1.1.0", lifespan=lifespan)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ResetRequest(BaseModel):
    session_id: str = "demo-user"


# In-memory session store (keyed by session_id)
conversation_memory: dict[str, dict] = {
    "demo-user": {"complaint_data": {}, "chat_history": []}
}


def get_safe_file_path(filename: str) -> Path | None:
    """Validate filename against path traversal and return resolved Path if within UPLOAD_DIR."""
    if not filename or "\0" in filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    clean_name = os.path.basename(filename)
    target = (Path(UPLOAD_DIR) / clean_name).resolve()
    base = Path(UPLOAD_DIR).resolve()
    try:
        if not target.is_relative_to(base) or not target.exists() or not target.is_file():
            return None
    except (ValueError, RuntimeError):
        return None
    return target


@app.get("/")
def home():
    return {
        "service": "PharmaGuard AI",
        "status": "online",
        "version": "1.1.0",
        "message": "Welcome to AI Complaint Management System 🚀"
    }


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


@app.get("/analytics/summary")
def complaint_summary():
    """Return live dashboard counts from the persisted complaint register."""
    return get_case_summary()


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


@app.get("/files")
async def get_files():
    base = Path(UPLOAD_DIR).resolve()
    files = [
        f for f in os.listdir(UPLOAD_DIR)
        if (base / f).is_file() and f.lower().endswith(".pdf")
    ]
    return {"files": sorted(files)}


@app.get("/files/{filename}")
def get_file(filename: str):
    safe_path = get_safe_file_path(filename)
    if safe_path is None:
        return JSONResponse(status_code=404, content={"error": "File not found or invalid path"})
    return FileResponse(path=str(safe_path), media_type="application/pdf")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    raw_filename = file.filename or ""
    if not raw_filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400, content={"error": "Only PDF files are supported"}
        )

    # Read with 10MB limit enforcement
    contents = await file.read(MAX_FILE_SIZE + 1)
    if len(contents) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=413, content={"error": f"File size exceeds maximum limit of {MAX_FILE_SIZE // (1024 * 1024)}MB"}
        )

    # Magic byte validation for PDF (%PDF-)
    if not contents.startswith(b"%PDF-"):
        return JSONResponse(
            status_code=400, content={"error": "Invalid file content: not a valid PDF document"}
        )

    # Sanitize filename strictly
    base_name = os.path.basename(raw_filename)
    clean_name = re.sub(r'[^a-zA-Z0-9_\-. ()]', '_', base_name).strip()
    if not clean_name or not clean_name.lower().endswith(".pdf"):
        clean_name = f"complaint_{int(datetime.now(timezone.utc).timestamp())}.pdf"

    dest_path = (Path(UPLOAD_DIR) / clean_name).resolve()
    base_upload_dir = Path(UPLOAD_DIR).resolve()

    if not dest_path.is_relative_to(base_upload_dir):
        return JSONResponse(
            status_code=400, content={"error": "Path traversal attempt detected"}
        )

    with open(dest_path, "wb") as f:
        f.write(contents)

    return {"message": f"{clean_name} uploaded successfully", "filename": clean_name}


@app.get("/extract/{filename}")
def extract_pdf(filename: str):
    safe_path = get_safe_file_path(filename)
    if safe_path is None:
        return JSONResponse(status_code=404, content={"error": "File not found or invalid path"})

    try:
        doc = fitz.open(str(safe_path))
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
    user_id = (request.session_id or "demo-user").strip()

    if user_id not in conversation_memory:
        conversation_memory[user_id] = {"complaint_data": {}, "chat_history": []}

    memory = conversation_memory[user_id]

    try:
        result = agent.invoke(
            {
                "message": request.message,
                "complaint_data": memory["complaint_data"],
                "response": "",
                "chat_history": memory["chat_history"],
            },
            config={"configurable": {"thread_id": user_id}},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent execution failed: {exc}", "reply": "An error occurred while processing your request.", "complaint": memory["complaint_data"]}
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


@app.post("/chat/reset")
def reset_chat(request: ResetRequest | None = None):
    user_id = (request.session_id if request and request.session_id else "demo-user").strip()
    conversation_memory[user_id] = {"complaint_data": {}, "chat_history": []}
    return {"message": "Chat session reset successfully", "session_id": user_id}
