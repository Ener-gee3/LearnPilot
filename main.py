import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from ai_engine import AIEngine
from logger_util import SystemMonitor

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

class LearningResponse(BaseModel):
    mode: str
    explanation: str
    steps: List[str]
    exercise: str

@app.post("/generate", response_model=LearningResponse)
async def generate(request: LearningRequest):
    # Track the start time
    start_time = time.time()
    
    # Log the incoming request
    SystemMonitor.log_request(request.mode, request.topic)
    
    # Process request
    result = await AIEngine.generate_response(
        request.mode, 
        request.topic, 
        request.code_snippet
    )
    
    # Log performance before returning
    SystemMonitor.log_performance(start_time)
    
    return result
