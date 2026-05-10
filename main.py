from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI()

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
        "You are an AI educational assistant. Follow the Concept-First Learning strategy: "
        "1. Explain the basic, fundamental concept of the topic provided. "
        "2. Provide a simple, clear example. "
        "3. Gradually introduce more complex ideas related to the topic. "
        "4. End with a short practice question to reinforce learning."
    ),
    "Reverse Engineering": (
        "You are an AI educational assistant. Follow the Learning by Deconstruction (LbD) strategy: "
        "1. Start with the complete solution or code snippet provided. "
        "2. Break it down step-by-step into smaller components. "
        "3. Explain the logic behind each component and how it fits the whole. "
        "4. Identify the underlying concepts used. "
        "5. End with a reconstruction exercise for the student."
    )
}

@app.post("/generate", response_model=LearningResponse)
async def generate(request: LearningRequest):
    system_instruction = PROMPTS.get(request.mode, "You are a helpful educational assistant.")
    user_input = f"Topic: {request.topic}"
    if request.code_snippet:
        user_input += f"\nCode/Solution: {request.code_snippet}"

    print(f"--- DEBUG ---")
    print(f"Mode Selected: {request.mode}")
    print(f"System Prompt: {system_instruction}")

    return {
        "mode": request.mode,
        "explanation": f"Placeholder for {request.topic} using {request.mode}",
        "steps": ["Step 1: Analyzed", "Step 2: Logic Ready", "Step 3: Integration Ready"],
        "exercise": "Check terminal for prompt output."
    }
