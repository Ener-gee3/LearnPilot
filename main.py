from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from ai_engine import AIEngine

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
    # This calls the modular engine we created
    result = await AIEngine.generate_response(
        request.mode, 
        request.topic, 
        request.code_snippet
    )
    return result
