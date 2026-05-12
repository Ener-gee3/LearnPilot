import os, re, json, logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger       = logging.getLogger("LearnPilot")
MODEL_ID     = os.getenv("MODEL_ID", "llama-3.3-70b-versatile")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_client      = Groq(api_key=GROQ_API_KEY)

# ── Mode System Prompts ───────────────────────────────────────────────────────
# Imported by features.py so keep these at module level.

CONCEPT_FIRST_SYSTEM = """\
You are LearnPilot, an expert educational AI using Concept-First Learning.
Teach the topic by building from fundamentals to complex ideas.

Structure your response with these markdown sections:
## Concept
A clear, concise definition and explanation of the core concept.

## Why It Matters
Why this concept is important and where it fits in the bigger picture.

## Simple Example
A concrete, beginner-friendly example.

## Deeper Dive
More advanced aspects, edge cases, or nuances.

## Real World Applications
2-3 specific real-world use cases with brief explanations.

## Quick Review
3 bullet points summarising the key takeaways.

Keep explanations clear, accurate, and appropriately detailed for the topic complexity.\
"""

REVERSE_ENGINEERING_SYSTEM = """\
You are LearnPilot, an expert educational AI using Reverse Engineering (Learning by Deconstruction).
Start with a complete working solution and systematically break it down.

Structure your response with these markdown sections:
## Complete Solution
Present a full, working example or solution relevant to the topic.

## Component Breakdown
Identify and list each major component or step in the solution.

## Step-by-Step Explanation
Explain each component in detail — what it does and why it's there.

## Concept Connections
Link each component back to underlying theoretical concepts.

## Real World Applications
2-3 industries or domains where this solution pattern is used.

## Reconstruction Challenge
A brief exercise prompting the learner to recreate or modify the solution.

Keep code examples syntactically correct and explanations precise.\
"""

VISUAL_SYSTEM = """\
You are LearnPilot, an expert educational AI specialising in Visual Learning.
Explain the topic using diagrams described in plain text, analogies, and step-by-step visual walkthroughs.

Structure your response with these markdown sections:
## Visual Overview
Describe a diagram or mental model that captures the concept (use ASCII art or Mermaid if applicable).

## Concept
A clear definition focused on visual/spatial understanding.

## Analogy
A memorable everyday analogy that makes the concept intuitive.

## Step-by-Step Visual Walkthrough
Walk through the concept as a sequence of visual steps.

## Real World Applications
2-3 visual or practical applications.

## Memory Aid
A mnemonic, diagram label, or visual trick to remember the key idea.

Be creative and descriptive — the goal is vivid mental imagery.\
"""

_SYSTEMS = {
    "Concept-First Learning": CONCEPT_FIRST_SYSTEM,
    "Reverse Engineering":    REVERSE_ENGINEERING_SYSTEM,
    "Visual Learning":        VISUAL_SYSTEM,
}


class AIEngine:
    @staticmethod
    async def generate_response(mode: str, topic: str, code_snippet: str = None):
        system = _SYSTEMS.get(mode, CONCEPT_FIRST_SYSTEM)

        user_parts = [f"Topic: {topic}"]
        if code_snippet and code_snippet.strip():
            user_parts.append(f"\nCode/Example provided by the student:\n```\n{code_snippet.strip()}\n```")
        user_parts.append("\nGenerate a complete learning response following your structure exactly.")
        user_msg = "\n".join(user_parts)

        try:
            resp = _client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0.7,
                max_tokens=1200,
                top_p=0.9,
            )
            raw = resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"[AIEngine] LLM call failed: {e}")
            raw = f"## Concept\nAn error occurred while generating a response for '{topic}'. Please try again."

        # Parse real_world section out for the dedicated field
        rw_match = re.search(
            r"##\s+Real World Applications\s*\n(.*?)(?=\n##|\Z)", raw, re.DOTALL
        )
        real_world = rw_match.group(1).strip() if rw_match else ""

        # Parse steps from Quick Review / Step-by-Step section
        steps: list[str] = []
        steps_match = re.search(
            r"##\s+(?:Quick Review|Step-by-Step[^\n]*|Reconstruction Challenge)\s*\n(.*?)(?=\n##|\Z)",
            raw, re.DOTALL
        )
        if steps_match:
            for line in steps_match.group(1).splitlines():
                line = line.strip().lstrip("-•* ").strip()
                if line:
                    steps.append(line)
        if not steps:
            steps = ["Review the concept", "Try the example", "Apply to a new problem"]

        # Strip real_world from raw for clean rendering (shown separately in UI)
        raw_clean = re.sub(
            r"##\s+Real World Applications[\s\S]*?(?=\n##|\Z)", "", raw
        ).strip()

        return {
            # Fields required by LearningResponse pydantic model
            "mode":                   mode,
            "explanation":            raw,
            "real_world_application": real_world,
            "resources": [
                {"title": "Khan Academy", "url": f"https://www.khanacademy.org/search?referer=%2F&page_search_query={topic}"},
                {"title": "Wikipedia",    "url": f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"},
                {"title": "YouTube",      "url": f"https://www.youtube.com/results?search_query={topic}+explained"},
            ],
            "quiz":      None,
            "steps":     steps[:6],
            "image_url": None,
            # Extra fields used directly by frontend JS (not in pydantic model —
            # must be preserved by removing response_model= from /generate route)
            "raw":        raw,
            "raw_clean":  raw_clean,
            "real_world": real_world,
        }
