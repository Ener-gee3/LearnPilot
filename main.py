from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import time

from ai_engine import AIEngine
from logger_util import SystemMonitor
from history_service import HistoryService
from features import (
    generate_more_context,
    generate_quiz,
    generate_exercises,
    fetch_related_links,
    grade_exercise,
    generate_flashcards,
    grade_exam,
    generate_exam,
    ask_followup,
    generate_summary,
)
from pdf_service import (
    get_uploaded_files,
    extract_pages,
    load_metadata,
    save_pdf,
    get_learning_plan,
    delete_pdf,
)
from rag_service import retrieve_context as fetch_rag_context

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Static files & index ──────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "online"}

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Pydantic models ───────────────────────────────────────────────────────────

class QuizModel(BaseModel):
    question: str
    options: List[str]
    correct_answer: str

class LearningRequest(BaseModel):
    topic: str
    mode: str
    code_snippet: Optional[str] = None

class LearningResponse(BaseModel):
    mode: str
    explanation: str
    real_world_application: str
    resources: List[Dict[str, str]]
    quiz: Optional[QuizModel] = None
    steps: List[str]
    image_url: Optional[str] = None

class MoreContextRequest(BaseModel):
    topic: str
    mode: str
    already_covered: List[str] = []
    rag_context: str = ""

class QuizRequest(BaseModel):
    topic: str
    all_contexts: List[str]
    num_questions: int = 5

class ExerciseRequest(BaseModel):
    topic: str
    all_contexts: List[str]
    num_questions: int = 4

class RelatedLinksRequest(BaseModel):
    topic: str

class PlanRequest(BaseModel):
    pdf_id: str
    chapter_ref: str  # e.g. "Chapter 3" or "3"

class GenerateChunkRequest(BaseModel):
    topic: str
    mode: str
    pdf_id: str
    page_start: int
    page_end: int
    chunk_title: str
    chunk_index: int = 0
    total_chunks: int = 1

# ── Core endpoints ────────────────────────────────────────────────────────────

@app.get("/history")
async def get_history():
    return HistoryService.get_history()

@app.post("/generate")
async def generate(request: LearningRequest):
    start_time = time.time()
    SystemMonitor.log_request(request.mode, request.topic)
    result = await AIEngine.generate_response(request.mode, request.topic, request.code_snippet)
    HistoryService.save_session(request.mode, request.topic, result)
    SystemMonitor.log_performance(start_time)
    return result

# ── Feature endpoints ─────────────────────────────────────────────────────────

@app.post("/more-context")
async def more_context(request: MoreContextRequest):
    context_index = len(request.already_covered)
    data = await generate_more_context(
        topic=request.topic,
        mode=request.mode,
        already_covered=request.already_covered,
        context_index=context_index,
        rag_context=request.rag_context,
    )
    return data

@app.post("/quiz")
async def quiz(request: QuizRequest):
    questions = await generate_quiz(request.topic, request.all_contexts)
    return {"questions": questions}

@app.post("/exercises")
async def exercises(request: ExerciseRequest):
    items = await generate_exercises(request.topic, request.all_contexts)
    return {"exercises": items}

@app.post("/related-links")
async def related_links(request: RelatedLinksRequest):
    links = await fetch_related_links(request.topic)
    return {"links": links}

# ── PDF / chunked learning endpoints ─────────────────────────────────────────

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    info    = await save_pdf(content, file.filename)
    # Frontend checks data.success and uses data.file_id
    return {
        "success": True,
        "file_id": info["id"],
        "id":      info["id"],
        "name":    info["name"],
        "pages":   info["pages"],
    }

@app.get("/files")
async def list_files():
    return get_uploaded_files()

@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    ok = delete_pdf(file_id)
    if not ok:
        raise HTTPException(status_code=404, detail="File not found.")
    return {"deleted": file_id}

@app.post("/plan")
async def build_plan(request: PlanRequest):
    subtopics = get_learning_plan(request.pdf_id, request.chapter_ref)
    if not subtopics:
        raise HTTPException(status_code=404, detail="PDF not found or no subtopics could be parsed.")
    return {"subtopics": subtopics}

@app.post("/generate-chunk")
async def generate_chunk(request: GenerateChunkRequest):
    meta = load_metadata()
    if request.pdf_id not in meta:
        raise HTTPException(status_code=404, detail="PDF not found.")
    from pathlib import Path
    pdf_path = Path(meta[request.pdf_id]["path"])

    page_text, _ = extract_pages(pdf_path, request.page_start, request.page_end)
    rag_context  = page_text[:3000] if page_text else ""

    result = await AIEngine.generate_response(
        mode=request.mode,
        topic=f"{request.topic} — {request.chunk_title}",
        code_snippet=None,
    )
    result["rag_context"]   = rag_context
    result["chunk_title"]   = request.chunk_title
    result["chunk_index"]   = request.chunk_index
    result["total_chunks"]  = request.total_chunks
    return result

# ── Grade / Flashcards / Followup / Exam / Exam-grade / Summarize endpoints ──

class GradeRequest(BaseModel):
    question: str
    sample_answer: str
    user_answer: str

class FlashcardsRequest(BaseModel):
    topic: str
    all_contexts: List[str]

class ExamRequest(BaseModel):
    topic: str
    all_contexts: List[str]

class ExamGradeRequest(BaseModel):
    questions: List[Dict]
    answers: List[Dict]

class FollowupRequest(BaseModel):
    topic: str
    mode: str
    context: str
    question: str

class SummarizeRequest(BaseModel):
    raw_response: str
    topic: str

@app.post("/grade")
async def grade(request: GradeRequest):
    result = await grade_exercise(
        question=request.question,
        sample_answer=request.sample_answer,
        user_answer=request.user_answer,
    )
    return result

@app.post("/flashcards")
async def flashcards(request: FlashcardsRequest):
    cards = await generate_flashcards(request.topic, request.all_contexts)
    return {"cards": cards}

@app.post("/exam")
async def exam(request: ExamRequest):
    result = await generate_exam(request.topic, request.all_contexts)
    return result

@app.post("/exam-grade")
async def exam_grade(request: ExamGradeRequest):
    results = await grade_exam(request.questions, request.answers)
    return {"results": results}

@app.post("/followup")
async def followup(request: FollowupRequest):
    answer = await ask_followup(
        topic=request.topic,
        mode=request.mode,
        context=request.context,
        question=request.question,
    )
    return {"answer": answer}

@app.post("/summarize")
async def summarize(request: SummarizeRequest):
    result = await generate_summary(request.raw_response, request.topic)
    return result
