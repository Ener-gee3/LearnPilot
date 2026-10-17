from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi import FastAPI, File, UploadFile, HTTPException, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Literal
import time
import asyncio

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
from auth_service import resolve_user_id, resolve_user_from_headers
from rate_limit_service import check_rate_limit, RateLimitError
from metrics_service import record_request, snapshot as metrics_snapshot
from cache_service import get_cache, set_cache
from telemetry_service import record_usage, usage_summary
from learning_service import (
    get_or_create_profile,
    update_profile,
    record_progress,
    progress_summary,
    recommend_next_topic,
    bridge_lesson,
    schedule_flashcards,
    due_reviews,
    build_goal_plan,
)
from ecosystem_service import (
    add_course_doc,
    list_course_docs,
    search_course_docs,
    export_markdown_pack,
    export_lms_payload,
)
from background_jobs import create_job, get_job, set_running, set_done, set_failed
from api_contracts import ok, err

app = FastAPI(title="LearnPilot")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def observability_and_limits(request: Request, call_next):
    start = time.perf_counter()
    path = request.url.path
    exempt = path in {"/health", "/", "/metrics"} or path.startswith("/static")

    try:
        user_id = resolve_user_from_headers(request.headers)
    except HTTPException as e:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request(path, latency_ms, is_error=True)
        return JSONResponse(status_code=e.status_code, content=err("AUTH_REQUIRED", "Authentication required", e.detail))

    request.state.user_id = user_id

    if not exempt:
        try:
            check_rate_limit(user_id)
        except RateLimitError as e:
            latency_ms = (time.perf_counter() - start) * 1000
            record_request(path, latency_ms, is_error=True)
            return JSONResponse(status_code=429, content=err("RATE_LIMIT", str(e)))

    from fastapi.responses import JSONResponse
    try:
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000
        record_request(path, latency_ms, is_error=response.status_code >= 400)
        return response
    except Exception as ex:
        latency_ms = (time.perf_counter() - start) * 1000
        record_request(path, latency_ms, is_error=True)
        return JSONResponse(status_code=500, content=err("INTERNAL_ERROR", "Unexpected server error", str(ex)))


# ── Static files & index ──────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "online"}


@app.get("/metrics")
async def metrics():
    return ok(metrics_snapshot())


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
    topic: str = Field(min_length=2, max_length=200)
    mode: str
    code_snippet: Optional[str] = Field(default=None, max_length=10000)


class LearningResponse(BaseModel):
    mode: str
    explanation: str
    real_world_application: str
    resources: List[Dict[str, str]]
    quiz: Optional[QuizModel] = None
    steps: List[str]
    image_url: Optional[str] = None


class MoreContextRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    mode: str
    already_covered: List[str] = []
    rag_context: str = ""


class QuizRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    all_contexts: List[str]
    num_questions: int = Field(default=5, ge=1, le=20)


class ExerciseRequest(BaseModel):
    topic: str
    all_contexts: List[str]
    num_questions: int = 4


class RelatedLinksRequest(BaseModel):
    topic: str


class PlanRequest(BaseModel):
    pdf_id: str
    chapter_ref: str


class GenerateChunkRequest(BaseModel):
    topic: str
    mode: str
    pdf_id: str
    page_start: int
    page_end: int
    chunk_title: str
    chunk_index: int = 0
    total_chunks: int = 1


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


class FocusRequest(BaseModel):
    primary_goal: Literal["better learning outcomes", "better reliability", "broader adoption"]


class ProfileUpdateRequest(BaseModel):
    persona: Optional[Literal["beginner", "interview-prep", "exam-prep"]] = None
    target_exam_date: Optional[str] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=240)
    preferred_mode: Optional[str] = None
    primary_goal: Optional[str] = None
    weak_topics: Optional[List[str]] = None


class ProgressRecordRequest(BaseModel):
    topic: str
    score: float = Field(ge=0.0, le=1.0)
    source: str = Field(default="quiz", max_length=40)


class FeedbackRecommendationRequest(BaseModel):
    topic: str
    graded_results: List[Dict]


class BridgeRequest(BaseModel):
    topic: str


class CourseDocRequest(BaseModel):
    course_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=40000)


class CourseSearchRequest(BaseModel):
    course_id: str
    query: str


class AsyncExamRequest(BaseModel):
    topic: str
    all_contexts: List[str]


# ── Core endpoints ────────────────────────────────────────────────────────────

@app.get("/history")
async def get_history(request: Request):
    return HistoryService.get_history(request.state.user_id)


@app.post("/generate")
async def generate(request: LearningRequest, req: Request):
    start_time = time.time()
    user_id = req.state.user_id
    cache_key = f"gen:{user_id}:{request.mode}:{request.topic}:{request.code_snippet or ''}"

    cached = get_cache(cache_key)
    if cached:
        record_usage(user_id=user_id, endpoint="/generate", latency_ms=(time.time() - start_time) * 1000, cache_hit=True)
        return cached

    SystemMonitor.log_request(request.mode, request.topic)
    result = await AIEngine.generate_response(request.mode, request.topic, request.code_snippet)
    HistoryService.save_session(request.mode, request.topic, result, user_id=user_id)

    set_cache(cache_key, result, ttl_seconds=1800)
    latency_ms = (time.time() - start_time) * 1000
    record_usage(user_id=user_id, endpoint="/generate", latency_ms=latency_ms, cache_hit=False)
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


def _process_upload_job(job_id: str, file_content: bytes, file_name: str):
    try:
        set_running(job_id)
        result = asyncio.run(save_pdf(file_content, file_name))
        set_done(job_id, result)
    except Exception as e:
        set_failed(job_id, str(e))


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    info = await save_pdf(content, file.filename)
    return {
        "success": True,
        "file_id": info["id"],
        "id": info["id"],
        "name": info["name"],
        "pages": info["pages"],
    }


@app.post("/upload-async")
async def upload_pdf_async(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    content = await file.read()
    job_id = create_job("pdf_upload")
    background_tasks.add_task(_process_upload_job, job_id, content, file.filename)
    return ok({"job_id": job_id, "status": "queued"}, "PDF processing started")


@app.get("/jobs/{job_id}")
async def get_async_job(job_id: str):
    data = get_job(job_id)
    if not data:
        raise HTTPException(status_code=404, detail=err("JOB_NOT_FOUND", "Job not found"))
    return ok(data)


@app.get("/files")
async def list_files():
    return get_uploaded_files()


@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    ok_delete = delete_pdf(file_id)
    if not ok_delete:
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
    rag_context = page_text[:3000] if page_text else ""

    result = await AIEngine.generate_response(
        mode=request.mode,
        topic=f"{request.topic} — {request.chunk_title}",
        code_snippet=None,
    )
    result["rag_context"] = rag_context
    result["chunk_title"] = request.chunk_title
    result["chunk_index"] = request.chunk_index
    result["total_chunks"] = request.total_chunks
    return result


# ── Grade / Flashcards / Followup / Exam / Exam-grade / Summarize endpoints ──

@app.post("/grade")
async def grade(request: GradeRequest, req: Request):
    result = await grade_exercise(
        question=request.question,
        sample_answer=request.sample_answer,
        user_answer=request.user_answer,
    )
    try:
        score = float(result.get("score", 0))
        max_marks = float(result.get("max_marks", 1))
        normalized = 0.0 if max_marks == 0 else min(max(score / max_marks, 0), 1)
        record_progress(req.state.user_id, "exercise", normalized, "exercise")
    except Exception:
        pass
    return result


@app.post("/flashcards")
async def flashcards(request: FlashcardsRequest, req: Request):
    cards = await generate_flashcards(request.topic, request.all_contexts)
    schedule = schedule_flashcards(req.state.user_id, request.topic, cards)
    return {"cards": cards, "scheduled_reviews": schedule}


@app.post("/exam")
async def exam(request: ExamRequest):
    result = await generate_exam(request.topic, request.all_contexts)
    return result


def _process_exam_job(job_id: str, topic: str, all_contexts: list):
    try:
        set_running(job_id)
        result = asyncio.run(generate_exam(topic, all_contexts))
        set_done(job_id, result)
    except Exception as e:
        set_failed(job_id, str(e))


@app.post("/exam-async")
async def exam_async(request: AsyncExamRequest, background_tasks: BackgroundTasks):
    job_id = create_job("exam_generation")
    background_tasks.add_task(_process_exam_job, job_id, request.topic, request.all_contexts)
    return ok({"job_id": job_id, "status": "queued"}, "Exam generation started")


@app.post("/exam-grade")
async def exam_grade(request: ExamGradeRequest, req: Request):
    results = await grade_exam(request.questions, request.answers)
    if results:
        aggregate = 0.0
        seen = 0
        for item in results:
            try:
                s = float(item.get("score", 0))
                m = float(item.get("max_marks", 1))
                aggregate += 0.0 if m == 0 else max(min(s / m, 1), 0)
                seen += 1
            except Exception:
                continue
        if seen:
            record_progress(req.state.user_id, "exam", aggregate / seen, "exam")
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


# ── Expansion v2 endpoints ────────────────────────────────────────────────────


@app.get("/v2/profile")
async def get_profile(user_id: str = Depends(resolve_user_id)):
    profile = get_or_create_profile(user_id)
    profile["weak_topics"] = [] if not profile.get("weak_topics_json") else __import__("json").loads(profile["weak_topics_json"])
    return ok(profile)


@app.post("/v2/profile")
async def save_profile(payload: ProfileUpdateRequest, user_id: str = Depends(resolve_user_id)):
    data = update_profile(user_id, payload.model_dump(exclude_none=True))
    return ok(data, "Profile updated")


@app.post("/v2/roadmap/focus")
async def set_focus(payload: FocusRequest, user_id: str = Depends(resolve_user_id)):
    data = update_profile(user_id, {"primary_goal": payload.primary_goal})
    return ok({"primary_goal": data["primary_goal"]}, "Milestone focus saved")


@app.post("/v2/progress")
async def save_progress(payload: ProgressRecordRequest, user_id: str = Depends(resolve_user_id)):
    record_progress(user_id, payload.topic, payload.score, payload.source)
    return ok({"recorded": True}, "Progress recorded")


@app.get("/v2/progress")
async def get_progress(user_id: str = Depends(resolve_user_id)):
    return ok(progress_summary(user_id))


@app.get("/v2/adaptive/{topic}")
async def adaptive(topic: str, user_id: str = Depends(resolve_user_id)):
    return ok(recommend_next_topic(user_id, topic))


@app.get("/v2/bridge/{topic}")
async def bridge(topic: str):
    return ok(bridge_lesson(topic))


@app.get("/v2/reviews/due")
async def reviews_due(user_id: str = Depends(resolve_user_id)):
    return ok({"reviews": due_reviews(user_id)})


@app.get("/v2/goal-plan")
async def goal_plan(user_id: str = Depends(resolve_user_id)):
    return ok(build_goal_plan(user_id))


@app.post("/v2/feedback/recommendations")
async def feedback_recommendations(payload: FeedbackRecommendationRequest, user_id: str = Depends(resolve_user_id)):
    weak_areas = []
    for item in payload.graded_results:
        score = float(item.get("score", 0))
        max_marks = float(item.get("max_marks", 1) or 1)
        if max_marks and score / max_marks < 0.6:
            weak_areas.append(item.get("feedback", "Review this item"))

    rec = recommend_next_topic(user_id, payload.topic)
    followup = [
        f"Revise: {w}" for w in weak_areas[:3]
    ] or [f"Try an {rec['recommended_difficulty']} practice set for {payload.topic}"]

    return ok(
        {
            "topic": payload.topic,
            "weak_feedback": weak_areas,
            "recommended_next_topic": rec["recommended_next_topic"],
            "recommended_actions": followup,
        }
    )


@app.post("/v2/knowledge-base/docs")
async def kb_add_doc(payload: CourseDocRequest, user_id: str = Depends(resolve_user_id)):
    doc_id = add_course_doc(user_id, payload.course_id, payload.title, payload.body)
    return ok({"doc_id": doc_id}, "Document added")


@app.get("/v2/knowledge-base/docs/{course_id}")
async def kb_list_docs(course_id: str, user_id: str = Depends(resolve_user_id)):
    return ok({"documents": list_course_docs(user_id, course_id)})


@app.post("/v2/knowledge-base/search")
async def kb_search(payload: CourseSearchRequest, user_id: str = Depends(resolve_user_id)):
    return ok({"results": search_course_docs(user_id, payload.course_id, payload.query)})


@app.get("/v2/integrations/export/markdown/{course_id}")
async def export_markdown(course_id: str, user_id: str = Depends(resolve_user_id)):
    return ok({"markdown": export_markdown_pack(user_id, course_id)})


@app.get("/v2/integrations/export/lms/{course_id}")
async def export_lms(course_id: str, user_id: str = Depends(resolve_user_id)):
    return ok(export_lms_payload(user_id, course_id))


@app.get("/v2/usage")
async def usage(user_id: str = Depends(resolve_user_id)):
    return ok(usage_summary(user_id))
