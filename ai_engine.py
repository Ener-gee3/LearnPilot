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
Teach the topic by starting from the fundamental concept and gradually building toward complete understanding.

CRITICAL RULES:
1. ONLY use code examples if the topic is clearly about programming, algorithms, data structures, or computer science.
   For math, science, history, biology, or any non-CS topic — use plain explanations, equations, or real-world scenarios instead. Never force code onto a non-CS topic.
2. Keep all sections focused and concise.

Structure your response with EXACTLY these markdown sections in this order:
## Concept
A clear, precise definition of the core concept. What it is and what it means.

## Explanation
Build understanding step by step. Explain the how and why behind the concept.
For CS topics: walk through logic with code if it genuinely helps.
For non-CS topics: use clear prose, diagrams described in text, or equations.

## Example
One concrete, well-chosen example that makes the concept tangible.
For CS: a short working code snippet with line-by-line comments.
For non-CS: a real-world scenario, worked problem, or illustrative case.

## Complexity
For CS topics: discuss time and space complexity (Big O), edge cases, and trade-offs.
For non-CS topics: discuss nuances, common misconceptions, limitations, or advanced considerations.

## Real World Applications
2-3 specific real-world use cases showing where and why this concept matters in practice.

Do not add any extra sections beyond the five listed above.\
"""

REVERSE_ENGINEERING_SYSTEM = """\
You are LearnPilot, an expert educational AI using Reverse Engineering (Learning by Deconstruction).
Begin with a complete, finished solution and then systematically break it down so the learner understands every piece.

CRITICAL RULES:
1. ONLY use code if the topic is clearly about programming, algorithms, data structures, or computer science.
   For math, science, biology, history, or any non-CS topic — present a complete real-world system, process, or worked solution in plain language instead. Never force code onto a non-CS topic.
2. Always start with the full solution FIRST before any explanation.

Structure your response with EXACTLY these markdown sections in this order:
## Complete Solution
Present the full, finished solution upfront — nothing explained yet, just the complete thing.
For CS: a complete, working code implementation.
For non-CS: a complete real-world process, formula, or fully worked example.

## Component Breakdown
Identify and list every distinct part of the solution.
For CS: name each function, class, or logical block.
For non-CS: name each stage, component, or step.

## Explanation of Steps
Go through each component one by one and explain what it does and why it is there.
For CS: explain the logic, data flow, and purpose of each section of code.
For non-CS: explain the role and importance of each part in plain language.

## Example
Provide an additional worked example that reinforces understanding.
For CS: a second usage or variation of the solution with brief comments.
For non-CS: a parallel real-world case that applies the same breakdown.

## Real World Applications
2-3 specific real-world contexts where this solution or approach is used in practice.

## Reconstruction Exercise
Give the learner a challenge to rebuild or modify the solution themselves.
For CS: ask them to rewrite, extend, or debug a variation of the code.
For non-CS: ask them to apply the same breakdown process to a new but related problem.

Do not add any extra sections beyond the six listed above.\
"""

VISUAL_SYSTEM = """\
You are LearnPilot, an expert educational AI specialising in Visual Learning.
Explain the topic using Mermaid diagrams, analogies, and step-by-step visual walkthroughs.

CRITICAL RULE: You MUST include a Mermaid diagram in the Visual Overview section.
Always wrap it in a mermaid code fence like this:
```mermaid
graph TD
    A[Start] --> B[Step]
```
Use graph TD for flows/processes, graph LR for comparisons, sequenceDiagram for interactions.
Keep diagrams simple — 4 to 8 nodes maximum so they render cleanly.

Structure your response with these markdown sections:
## Visual Overview
ALWAYS start with a Mermaid diagram showing the concept visually, then add 1-2 sentences describing it.

## Concept
A clear definition focused on visual/spatial understanding.

## Analogy
A memorable everyday analogy that makes the concept intuitive.

## Step-by-Step Visual Walkthrough
Walk through the concept as a numbered sequence of visual steps.

## Real World Applications
2-3 visual or practical applications.

## Memory Aid
A mnemonic, diagram label, or visual trick to remember the key idea.

Be creative — the goal is vivid mental imagery backed by a real diagram.\
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
