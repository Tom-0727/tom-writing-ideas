"""Writing Platform — FastAPI backend for Ideas + Drafts collaboration."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
DRAFTS_DIR = DATA_DIR / "drafts"
DRAFTS_INDEX = DATA_DIR / "drafts-index.json"

DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Tom Writing Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Draft helpers ──────────────────────────────────────────────

def _load_index() -> list[dict]:
    if DRAFTS_INDEX.exists():
        return json.loads(DRAFTS_INDEX.read_text(encoding="utf-8"))
    return []


def _save_index(index: list[dict]):
    DRAFTS_INDEX.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _draft_path(draft_id: str) -> Path:
    return DRAFTS_DIR / f"{draft_id}.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Pydantic models ───────────────────────────────────────────

class DraftCreate(BaseModel):
    title: str
    content: str = ""
    status: str = "draft"  # draft | review | approved | published


class DraftUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


# ── API: Drafts ────────────────────────────────────────────────

@app.get("/api/drafts")
def list_drafts():
    index = _load_index()
    return {"drafts": index}


@app.post("/api/drafts")
def create_draft(body: DraftCreate):
    draft_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    now = _now_iso()
    meta = {
        "id": draft_id,
        "title": body.title,
        "status": body.status,
        "created_at": now,
        "updated_at": now,
    }
    # Save content
    _draft_path(draft_id).write_text(body.content, encoding="utf-8")
    # Update index
    index = _load_index()
    index.insert(0, meta)
    _save_index(index)
    return meta


@app.get("/api/drafts/{draft_id}")
def get_draft(draft_id: str):
    index = _load_index()
    meta = next((d for d in index if d["id"] == draft_id), None)
    if not meta:
        raise HTTPException(404, "Draft not found")
    path = _draft_path(draft_id)
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    return {**meta, "content": content}


@app.put("/api/drafts/{draft_id}")
def update_draft(draft_id: str, body: DraftUpdate):
    index = _load_index()
    meta = next((d for d in index if d["id"] == draft_id), None)
    if not meta:
        raise HTTPException(404, "Draft not found")
    if body.title is not None:
        meta["title"] = body.title
    if body.status is not None:
        meta["status"] = body.status
    if body.content is not None:
        _draft_path(draft_id).write_text(body.content, encoding="utf-8")
    meta["updated_at"] = _now_iso()
    _save_index(index)
    return meta


@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str):
    index = _load_index()
    new_index = [d for d in index if d["id"] != draft_id]
    if len(new_index) == len(index):
        raise HTTPException(404, "Draft not found")
    _save_index(new_index)
    path = _draft_path(draft_id)
    if path.exists():
        path.unlink()
    return {"ok": True}


# ── API: Ideas ─────────────────────────────────────────────────

@app.get("/api/ideas")
def get_ideas():
    ideas_file = DATA_DIR / "ideas.json"
    if ideas_file.exists():
        return json.loads(ideas_file.read_text(encoding="utf-8"))
    return {"ideas": [], "dates": []}


# ── Frontend ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_index():
    return (APP_DIR / "platform.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
