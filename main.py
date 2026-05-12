from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from ai_engine import AIEngine
from logger_util import SystemMonitor
from history_service import HistoryService

app = FastAPI()

@app.get("/health")
@app.get("/files")
async def get_files():
    return []

async def health_check():
    return {"status": "online"}
@app.get('/')
async def read_index():
    return FileResponse('static/index.html')

app.mount('/static', StaticFiles(directory='static'), name='static')

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

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
    real_world: str
    resources: List[Dict[str, str]]
    quiz: Optional[QuizModel] = None
    steps: List[str]
    image_url: Optional[str] = None

@app.get("/history")
async def get_history():
    return HistoryService.get_history()

@app.post("/generate", response_model=LearningResponse)
async def generate(request: LearningRequest):
    start_time = time.time()
    SystemMonitor.log_request(request.mode, request.topic)
    result = await AIEngine.generate_response(request.mode, request.topic, request.code_snippet)
    HistoryService.save_session(request.mode, request.topic, result)
    SystemMonitor.log_performance(start_time)
    return result
