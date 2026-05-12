import os
import re
import json
import logging
from groq import Groq
from dotenv import load_dotenv
from rag_service import retrieve_context

load_dotenv()

logger = logging.getLogger("LearnPilot")
MODEL_ID = os.getenv("MODEL_ID", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

CONCEPT_FIRST_SYSTEM = """
You are LearnPilot, an educational tutor.

Use this exact structure:

## Concept
Explain the core idea clearly.

## Why It Matters
Explain why the concept matters.

## Step-by-Step
Break it into clear steps.

## Example
Give one concrete example.

## Common Mistake
Explain one common mistake.

## Practice
Give one short practice question.
"""

REVERSE_ENGINEERING_SYSTEM = """
You are LearnPilot in Reverse Engineering mode.

Use this exact structure:

## Final Result
Start with what the learner should understand.

## Backward Breakdown
Work backward from the result.

## Key Mechanism
Explain the mechanism underneath.

## Example
Give one concrete example.

## Practice
Give one short practice question.
"""

VISUAL_SYSTEM = """
You are LearnPilot in Visual Learning mode.

Use this exact structure:

## Mental Picture
Describe the idea visually.

## Diagram Description
Describe what a diagram would show.

## Step-by-Step
Break it into visual steps.

## Example
Give one concrete example.

## Practice
Give one short practice question.
"""

class AIEngine:
    @staticmethod
    async def generate_response(mode: str, topic: str, code_snippet=None):
        system_map = {
            "Concept-First Learning": CONCEPT_FIRST_SYSTEM,
            "Reverse Engineering": REVERSE_ENGINEERING_SYSTEM,
            "Visual Learning": VISUAL_SYSTEM,
        }

        system = system_map.get(mode, CONCEPT_FIRST_SYSTEM)
        rag_context = await retrieve_context(topic, mode)

        user = f"""
Topic: {topic}

Reference context:
{rag_context if rag_context else "No external context found. Use reliable general knowledge."}

Code snippet:
{code_snippet if code_snippet else "None"}

Generate a useful learning response.
"""

        try:
            resp = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.6,
                max_tokens=1400,
                top_p=0.9,
            )
            raw = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"[AIEngine] LLM call failed: {e}")
            raw = f"## Concept\nI could not connect to the AI provider.\n\n## Practice\nTry again after checking the backend API key."

        real_world = ""
        practice = ""

        rw_match = re.search(r"##\s*Why It Matters\s*\n([\s\S]*?)(?=\n##|\Z)", raw)
        if rw_match:
            real_world = rw_match.group(1).strip()

        practice_match = re.search(r"##\s*Practice\s*\n([\s\S]*?)(?=\n##|\Z)", raw)
        if practice_match:
            practice = practice_match.group(1).strip()

        steps = []
        step_match = re.search(r"##\s*Step-by-Step\s*\n([\s\S]*?)(?=\n##|\Z)", raw)
        if step_match:
            lines = [x.strip("-• 1234567890. ") for x in step_match.group(1).splitlines() if x.strip()]
            steps = lines[:5]

        if not steps:
            steps = ["Understand the idea", "Study an example", "Try a practice question"]

        return {
            "mode": mode,
            "explanation": raw,
            "raw": raw,
            "real_world": real_world,
            "resources": [],
            "steps": steps,
            "exercise": practice,
            "image_url": None,
        }
