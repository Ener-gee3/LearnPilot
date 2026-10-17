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

## Expansion Features (v2)
- Learner profile and adaptive path APIs: `/v2/profile`, `/v2/progress`, `/v2/adaptive/{topic}`, `/v2/goal-plan`
- Spaced repetition scheduling integrated into `/flashcards` and due reviews at `/v2/reviews/due`
- Milestone focus tracking: `/v2/roadmap/focus`
- Bridge lessons and prerequisite support: `/v2/bridge/{topic}`
- Multi-document knowledge base and exports:
  - Add/list/search docs: `/v2/knowledge-base/docs`, `/v2/knowledge-base/search`
  - Export study packs: `/v2/integrations/export/markdown/{course_id}`, `/v2/integrations/export/lms/{course_id}`
- Background jobs for heavy tasks:
  - Async upload: `POST /upload-async`
  - Async exam generation: `POST /exam-async`
  - Poll job status: `GET /jobs/{job_id}`
- Observability and reliability:
  - Metrics dashboard endpoint: `/metrics`
  - Usage telemetry endpoint: `/v2/usage`
  - SQLite-backed history migration from `history.json` to `learnpilot.db`

## Testing
- Run tests with: `pytest`

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
