from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time

from ai_engine import AIEngine
from logger_util import SystemMonitor
from history_service import HistoryService
from features import (
    generate_more_context,
    generate_quiz,
    generate_exercises,
    fetch_related_links,
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LearningRequest(BaseModel):
    topic: str
    mode: str
    code_snippet: Optional[str] = None
    pdf_id: Optional[str] = None
    chapter_ref: Optional[str] = None

class MoreContextRequest(BaseModel):
    topic: str
    mode: str
    already_covered: List[str] = []
    rag_context: str = ""

class ContextRequest(BaseModel):
    topic: str
    all_contexts: List[str] = []
    num_questions: Optional[int] = 4

class RelatedLinksRequest(BaseModel):
    topic: str

@app.get("/health")
async def health_check():
    return {"status": "online"}

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/history")
async def get_history():
    return HistoryService.get_history()

@app.get("/files")
async def get_files():
    return []

@app.post("/generate")
async def generate(request: LearningRequest):
    start_time = time.time()
    SystemMonitor.log_request(request.mode, request.topic)

    result = await AIEngine.generate_response(
        request.mode,
        request.topic,
        request.code_snippet,
    )

    HistoryService.save_session(request.mode, request.topic, result)
    SystemMonitor.log_performance(start_time)
    return result

@app.post("/more-context")
async def more_context(request: MoreContextRequest):
    return await generate_more_context(
        topic=request.topic,
        mode=request.mode,
        already_covered=request.already_covered,
        rag_context=request.rag_context,
    )

@app.post("/quiz")
async def quiz(request: ContextRequest):
    questions = await generate_quiz(request.topic, request.all_contexts)
    return {"questions": questions}

@app.post("/exercises")
async def exercises(request: ContextRequest):
    exercises = await generate_exercises(
        request.topic,
        request.all_contexts,
        request.num_questions or 4,
    )
    return {"exercises": exercises}

@app.post("/related-links")
async def related_links(request: RelatedLinksRequest):
    links = await fetch_related_links(request.topic)
    return {"links": links}

app.mount("/static", StaticFiles(directory="static"), name="static")
