# LearnPilot Backend
FastAPI implementation for AI-driven learning strategies.

## API Contract
- **Endpoint**: `POST /generate`
- **Payload**:
  ```json
  {
    "topic": "string",
    "mode": "Concept-First Learning" | "Reverse Engineering",
    "code_snippet": "optional string"
  }
  ```

## Quick Start
1. `source venv/Scripts/activate`
2. `pip install -r requirements.txt` (once generated)
3. `uvicorn main:app --reload`
