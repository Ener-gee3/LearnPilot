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

## Frontend Integration (Example for Kashi/Priyanshu)
To fetch data from this API in the frontend:
```javascript
const response = await fetch('http://127.0.0.1:8000/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        topic: "Your Topic Here",
        mode: "Concept-First Learning", // or "Reverse Engineering"
        code_snippet: null // Optional
    })
});
const data = await response.json();
console.log(data);
```
