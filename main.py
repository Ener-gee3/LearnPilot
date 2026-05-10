from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

# Enable CORS so the frontend can talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
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

PROMPTS = {
    "Concept-First Learning": (
        "Explain basic concepts, provide examples, and end with a practice question."
    ),
    "Reverse Engineering": (
        "Deconstruct provided code, explain logic, and suggest reconstruction exercises."
    )
}

@app.post("/generate", response_model=LearningResponse)
async def generate(request: LearningRequest):
    print(f"--- LOG: Request for {request.topic} using {request.mode} ---")
    return {
        "mode": request.mode,
        "explanation": f"This is a placeholder for {request.topic}. Ready for model integration.",
        "steps": ["Step 1: Receive request", "Step 2: Apply logic", "Step 3: Response generated"],
        "exercise": "Check terminal for successful connection."
    }
