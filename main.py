import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from ai_engine import AIEngine
from logger_util import SystemMonitor
from history_service import HistoryService

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QuizModel(BaseModel):
    question: str
    options: List[str]
    correct_answer: str

class LearningResponse(BaseModel):
    mode: str
    explanation: str
    real_world_application: str
    resources: List[Dict[str, str]]
    quiz: Optional[QuizModel] = None
    image_url: Optional[str] = None
    steps: List[str]

@app.get("/history")
async def get_history():
    return HistoryService.get_history()

@app.post("/generate", response_model=LearningResponse)
async def generate(request: LearningRequest):
    start_time = time.time()
    SystemMonitor.log_request(request.mode, request.topic)
    result = await AIEngine.generate_response(request.mode, request.topic)
    HistoryService.save_session(request.mode, request.topic, result)
    SystemMonitor.log_performance(start_time)
    return result
