"""
features.py — LearnPilot Extended Features Engine v2
"""
import os, re, json, logging, urllib.request, urllib.parse
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger       = logging.getLogger("LearnPilot")
MODEL_ID     = os.getenv("MODEL_ID", "llama-3.1-8b-instant")  # Keep in sync with ai_engine.py
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client       = Groq(api_key=GROQ_API_KEY)

# Import mode system prompts from ai_engine
from ai_engine import CONCEPT_FIRST_SYSTEM, REVERSE_ENGINEERING_SYSTEM, VISUAL_SYSTEM

def _call_llm(system: str, user: str, max_tokens: int = 1500, temp: float = 0.7) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role":"system","content":system},{"role":"user","content":user}],
            temperature=temp, max_tokens=max_tokens, top_p=0.9,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"[Features] LLM call failed: {e}")
        return ""

def _extract_json(raw: str, kind: str = "array"):
    """
    Robustly extract a JSON array or object from LLM output.
    Handles: markdown fences, leading/trailing text, single-quoted JSON (rare),
    and common LLM errors like missing closing braces.
    kind = 'array' looks for [...], kind = 'object' looks for {...}
    """
    if not raw:
        return None
    # Strip markdown fences
    clean = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    # Try direct parse first
    try:
        return json.loads(clean)
    except Exception:
        pass
    # Try auto-repair: balance unmatched braces/brackets
    repaired = _repair_json(clean)
    if repaired:
        try:
            return json.loads(repaired)
        except Exception:
            pass
    # Search for the first complete [...] or {...} block
    pattern = r"\[.*?\]" if kind == "array" else r"\{.*?\}"
    m = re.search(pattern, clean, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    # Last resort: find outermost bracket pair
    open_char, close_char = ("[", "]") if kind == "array" else ("{", "}")
    start = clean.find(open_char)
    end   = clean.rfind(close_char)
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(clean[start:end+1])
        except Exception:
            pass
    return None


def _repair_json(s: str) -> str:
    """
    Repair common LLM JSON errors by iteratively inserting missing characters
    at parse-failure positions. Handles missing }, ], commas, and unterminated strings.
    Tries up to 10 fixes before giving up.
    """
    if not s:
        return None
    attempt = s
    for _ in range(20):
        try:
            json.loads(attempt)
            return attempt  # Valid!
        except json.JSONDecodeError as e:
            msg = e.msg
            pos = e.pos
            # Common error patterns we can fix
            if "Expecting ',' delimiter" in msg:
                # Missing comma OR missing closing brace before next element
                # Try inserting '}' first (more common when LLM forgets to close object)
                # If we're at a position where the previous chars look like end-of-value,
                # the issue is usually a missing }
                before = attempt[:pos].rstrip()
                if before.endswith(']') or before.endswith('}') or before.endswith('"'):
                    # Try inserting } first
                    candidate = attempt[:pos] + '}' + attempt[pos:]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        pass
                    # Try inserting ,
                    attempt = attempt[:pos] + ',' + attempt[pos:]
                    continue
                attempt = attempt[:pos] + ',' + attempt[pos:]
                continue
            elif "Expecting property name" in msg or "Expecting value" in msg:
                # Likely trailing comma or extra char — remove char before pos
                if pos > 0 and attempt[pos-1] in ',':
                    attempt = attempt[:pos-1] + attempt[pos:]
                    continue
                break
            elif "Unterminated string" in msg:
                # Close the string
                attempt = attempt[:pos] + '"' + attempt[pos:]
                continue
            elif "Expecting" in msg and "delimiter" in msg:
                attempt = attempt[:pos] + ',' + attempt[pos:]
                continue
            else:
                break
    # Final fallback: balance unclosed braces/brackets at the end
    open_curly  = attempt.count('{') - attempt.count('}')
    open_square = attempt.count('[') - attempt.count(']')
    if open_curly > 0 or open_square > 0:
        attempt = attempt.rstrip().rstrip(',')
        attempt += '}' * max(0, open_curly) + ']' * max(0, open_square)
        try:
            json.loads(attempt)
            return attempt
        except Exception:
            pass
    return None

ORDINALS = ["First","Second","Third","Fourth","Fifth","Sixth","Seventh","Eighth","Ninth","Tenth"]

def _ordinal(n: int) -> str:
    return ORDINALS[n] if n < len(ORDINALS) else f"#{n+1}"


# ══════════════════════════════════════════════════════════════════════════════
# MORE CONTEXT — uses exact same mode system prompt, covers different aspects
# ══════════════════════════════════════════════════════════════════════════════

async def generate_more_context(
    topic: str,
    mode: str,
    already_covered: list,
    context_index: int = 1,  # how many times user has clicked (0-based after first)
    rag_context: str = "",
) -> dict:
    """
    Generate additional content using the SAME mode structure.
    context_index determines the ordinal label (Second Concept, Third Concept, etc.)
    """
    # Pick correct system prompt
    system_map = {
        "Concept-First Learning":  CONCEPT_FIRST_SYSTEM,
        "Reverse Engineering":     REVERSE_ENGINEERING_SYSTEM,
        "Visual Learning":         VISUAL_SYSTEM,
    }
    system = system_map.get(mode, CONCEPT_FIRST_SYSTEM)

    # Summarize already covered to avoid repetition
    covered_aspects = []
    for resp in already_covered:
        headings = re.findall(r"##\s+(.+)", resp)
        # Extract concept titles from content — first non-header sentence per section
        concepts = re.findall(r"##\s+Concept\s*\n(.{0,120})", resp)
        covered_aspects.extend(concepts)

    covered_note = ""
    if covered_aspects:
        covered_note = (
            f"IMPORTANT: The learner has already studied these aspects:\n"
            f"{chr(10).join(f'- {a.strip()[:100]}' for a in covered_aspects[:5])}\n\n"
            f"Cover a DIFFERENT angle, subtopic, or deeper aspect of '{topic}'. "
            f"Do NOT repeat what was already covered above."
        )

    rag_block = f"Reference material:\n{rag_context}\n\n---\n\n" if rag_context else ""
    label     = _ordinal(context_index + 1)

    user = (
        f"{rag_block}"
        f"{covered_note}\n\n"
        f"Topic: {topic}\n"
        f"This is the {label} explanation for this topic. "
        f"Cover a genuinely different aspect than what was already shown. "
        f"Follow the learning structure exactly."
    )

    raw = _call_llm(system, user, max_tokens=900)

    # Extract concept title for the label
    concept_match = re.search(r"##\s+Concept\s*\n(.{10,100})", raw)
    concept_title = concept_match.group(1).strip()[:60] if concept_match else f"{label} Concept"

    # Parse real_world separately
    rw_match = re.search(r"##\s+Real World Applications\s*\n(.*?)(?=\n##|\Z)", raw, re.DOTALL)
    real_world = rw_match.group(1).strip() if rw_match else ""

    # Strip real_world from raw for frontend rendering (shown separately)
    raw_clean = re.sub(r"##\s+Real World Applications[\s\S]*?(?=\n##|\Z)", "", raw).strip()

    return {
        "raw":         raw,
        "raw_clean":   raw_clean,
        "real_world":  real_world,
        "label":       f"{label} Concept",
        "title":       concept_title,
        "mode":        mode,
    }


# ══════════════════════════════════════════════════════════════════════════════
# QUIZ — MCQ, as many questions as context allows
# ══════════════════════════════════════════════════════════════════════════════

async def generate_quiz(topic: str, all_contexts: list) -> list:
    combined = "\n\n---\n\n".join(all_contexts)
    char_count    = len(combined)
    # Cap questions at 5 — each MCQ takes ~180 tokens in JSON output.
    # 5 questions × 180 = 900 tokens output + 200 overhead = 1100 safe.
    # More contexts = more chars but we cap questions so JSON always fits.
    num_questions = max(3, min(5, char_count // 500))
    combined      = combined[:4000]  # cap input

    system = """You are a quiz generator for LearnPilot.
Generate multiple-choice questions based STRICTLY on the provided content.
Every question and correct answer MUST be directly derivable from the content.

Return ONLY valid JSON array, no markdown fences, no explanation:
[
  {
    "question": "Question text?",
    "options": ["A) Option one", "B) Option two", "C) Option three", "D) Option four"],
    "correct": "A",
    "explanation": "Why A is correct based on the content."
  }
]"""

    user = (
        f"Content:\n{combined}\n\n"
        f"Generate EXACTLY {num_questions} multiple-choice questions. "
        f"Mix easy, medium, and hard. Cover different parts of the content. "
        f"Return ONLY the JSON array. Do NOT add any text before or after the array."
    )

    # Scale max_tokens dynamically: 200 tokens per question + 300 buffer
    max_tok = min(2000, num_questions * 220 + 300)
    raw = _call_llm(system, user, max_tokens=max_tok, temp=0.3)
    q = _extract_json(raw, "array")
    if q:
        logger.info(f"[Quiz] {len(q)} questions for '{topic}'")
        return q
    logger.error(f"[Quiz] parse failed for '{topic}' — raw: {raw[:200]}")
    return []


# ══════════════════════════════════════════════════════════════════════════════
# EXERCISES — Open-ended, as many as context allows, with AI grading
# ══════════════════════════════════════════════════════════════════════════════

async def generate_exercises(topic: str, all_contexts: list) -> list:
    combined      = "\n\n---\n\n".join(all_contexts)
    char_count    = len(combined)
    # Cap at 4 — each exercise with sample_answer takes ~250 tokens in JSON.
    # 4 × 250 = 1000 + 300 overhead = 1300 safe.
    num_questions = max(2, min(4, char_count // 600))
    combined      = combined[:4000]

    system = """You are an exercise generator for LearnPilot.
Generate open-ended questions requiring the learner to think, apply, analyze, or calculate.
Base ALL questions strictly on the provided content.

Return ONLY valid JSON array:
[
  {
    "question": "Open-ended question?",
    "type": "apply|analyze|explain|calculate|compare",
    "hint": "Brief hint or empty string",
    "sample_answer": "Detailed model answer the learner can compare against."
  }
]"""

    user = (
        f"Content:\n{combined}\n\n"
        f"Generate EXACTLY {num_questions} open-ended questions. "
        f"Mix types. For math/physics include calculations with real numbers from the content. "
        f"Make sample answers thorough — 2-4 sentences each. "
        f"Return ONLY the JSON array. Do NOT add any text before or after the array."
    )

    max_tok = min(2000, num_questions * 280 + 300)
    raw = _call_llm(system, user, max_tokens=max_tok, temp=0.4)
    q = _extract_json(raw, "array")
    if q:
        logger.info(f"[Exercises] {len(q)} exercises for '{topic}'")
        return q
    logger.error(f"[Exercises] parse failed for '{topic}' — raw: {raw[:200]}")
    return []


async def grade_exercise(question: str, sample_answer: str, user_answer: str) -> dict:
    """
    AI grades the user's answer against the question and sample answer.
    Returns verdict: correct | partial | incorrect, plus explanation.
    """
    system = """You are a grading assistant for LearnPilot.
Evaluate the student's answer against the question and the model answer.
Be fair — partial credit for answers that show understanding but miss details.

Return ONLY valid JSON:
{
  "verdict": "correct|partial|incorrect",
  "score": "number 0-100",
  "feedback": "2-3 sentences explaining what was right, what was missing, and how to improve."
}"""

    user = (
        f"Question: {question}\n\n"
        f"Model answer: {sample_answer}\n\n"
        f"Student's answer: {user_answer}\n\n"
        f"Grade the student's answer. Return ONLY the JSON."
    )

    raw = _call_llm(system, user, max_tokens=300, temp=0.2)
    result = _extract_json(raw, "object")
    if result:
        return result
    logger.error(f"[Grade] parse failed — raw: {raw[:200]}")
    return {"verdict": "incorrect", "score": "0", "feedback": "Could not grade. Please try again."}


# ══════════════════════════════════════════════════════════════════════════════
# RELATED LINKS — always returns at least 3-4 links
# ══════════════════════════════════════════════════════════════════════════════

async def fetch_related_links(topic: str) -> list:
    links = []
    topic_lower = topic.lower()

    # 1. Wikipedia
    try:
        enc = urllib.parse.quote(topic)
        req = urllib.request.Request(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{enc}",
            headers={"User-Agent":"LearnPilot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode())
            if d.get("extract") and d.get("content_urls"):
                links.append({
                    "title":       d.get("title", topic),
                    "url":         d["content_urls"]["desktop"]["page"],
                    "description": d.get("extract","")[:200]+"...",
                    "source":      "Wikipedia", "icon": "📖",
                })
    except Exception as e:
        logger.warning(f"[Links] Wikipedia: {e}")

    # 2. DuckDuckGo
    try:
        enc = urllib.parse.quote(f"{topic} tutorial")
        req = urllib.request.Request(
            f"https://api.duckduckgo.com/?q={enc}&format=json&no_html=1&skip_disambig=1",
            headers={"User-Agent":"LearnPilot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            d = json.loads(r.read().decode())
            if d.get("AbstractURL") and d.get("AbstractText"):
                if not any(l["url"]==d["AbstractURL"] for l in links):
                    links.append({
                        "title":       d.get("Heading", topic),
                        "url":         d["AbstractURL"],
                        "description": d["AbstractText"][:200]+"...",
                        "source":      d.get("AbstractSource","Reference"), "icon":"🔗",
                    })
            for item in d.get("RelatedTopics",[])[:3]:
                if isinstance(item,dict) and item.get("FirstURL") and item.get("Text"):
                    links.append({
                        "title":       item["Text"][:60],
                        "url":         item["FirstURL"],
                        "description": item["Text"][:150],
                        "source":      "DuckDuckGo", "icon":"🔍",
                    })
    except Exception as e:
        logger.warning(f"[Links] DDG: {e}")

    # 3. Always add Khan Academy
    links.append({
        "title":       f"Khan Academy: {topic}",
        "url":         f"https://www.khanacademy.org/search?referer=%2F&page_search_query={urllib.parse.quote(topic)}",
        "description": "Free video lessons, worked examples, and practice exercises.",
        "source":      "Khan Academy", "icon":"🎓",
    })

    # 4. Subject-specific curated links
    cs_kw   = {"algorithm","programming","code","python","java","data structure","binary","sort","tree","graph","recursion","machine learning","pointer","hash"}
    math_kw = {"calculus","algebra","math","equation","theorem","statistics","probability","matrix","vector","physics","quantum","relativity"}
    bio_kw  = {"biology","cell","dna","gene","chemistry","photosynthesis","anatomy","evolution","ecology","medicine","respiration"}

    if any(k in topic_lower for k in cs_kw):
        links.append({"title":f"GeeksForGeeks: {topic}","url":f"https://www.geeksforgeeks.org/?s={urllib.parse.quote(topic)}","description":"In-depth CS tutorials, code examples, and practice problems.","source":"GeeksForGeeks","icon":"💻"})
        links.append({"title":f"W3Schools: {topic}","url":f"https://www.w3schools.com/search/searchresult.asp?q={urllib.parse.quote(topic)}","description":"Simple web-based coding tutorials and references.","source":"W3Schools","icon":"🌐"})

    elif any(k in topic_lower for k in math_kw):
        links.append({"title":f"MIT OpenCourseWare: {topic}","url":f"https://ocw.mit.edu/search/?q={urllib.parse.quote(topic)}","description":"Free MIT lecture notes, problem sets, and exams.","source":"MIT OCW","icon":"🏛️"})
        links.append({"title":f"Wolfram MathWorld: {topic}","url":f"https://mathworld.wolfram.com/search/?query={urllib.parse.quote(topic)}","description":"Comprehensive mathematics reference and explanations.","source":"MathWorld","icon":"🔢"})

    elif any(k in topic_lower for k in bio_kw):
        links.append({"title":f"NIH / PubMed: {topic}","url":f"https://www.ncbi.nlm.nih.gov/search/research-articles/?term={urllib.parse.quote(topic)}","description":"Peer-reviewed biology and medical research articles.","source":"NIH","icon":"🔬"})
        links.append({"title":f"Biology Online: {topic}","url":f"https://www.biologyonline.com/?s={urllib.parse.quote(topic)}","description":"Biology dictionary, tutorials, and resources.","source":"Biology Online","icon":"🧬"})

    else:
        links.append({"title":f"YouTube: {topic} explained","url":f"https://www.youtube.com/results?search_query={urllib.parse.quote(topic+' explained')}","description":"Video explanations and visual tutorials.","source":"YouTube","icon":"▶️"})
        links.append({"title":f"Britannica: {topic}","url":f"https://www.britannica.com/search?query={urllib.parse.quote(topic)}","description":"Encyclopaedia Britannica articles and references.","source":"Britannica","icon":"📚"})

    # Deduplicate, return at least 3, max 6
    seen, unique = set(), []
    for l in links:
        if l["url"] not in seen:
            seen.add(l["url"])
            unique.append(l)

    logger.info(f"[Links] {len(unique)} links for '{topic}'")
    return unique[:6]


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARIZE — short AI-generated summary for the summary panel
# ══════════════════════════════════════════════════════════════════════════════



async def generate_summary(raw_response, topic):
    content = raw_response[:2000]
    system = (
        'You are a summarizer for LearnPilot. '
        'Given a learning response, return ONLY valid JSON (no markdown): '
        '{"title": "2-5 word topic title", "summary": "2-3 sentence plain-language summary."}'
    )
    user = 'Topic: ' + topic + chr(10) + chr(10) + 'Content:' + chr(10) + content + chr(10) + chr(10) + 'Return ONLY JSON.'
    raw = _call_llm(system, user, max_tokens=400, temp=0.3)
    result = _extract_json(raw, "object")
    if result:
        return {"title": result.get("title", topic)[:60], "summary": result.get("summary", "")}
    logger.error("[Summary] parse failed — raw: " + raw[:200])
    return {}

# ══════════════════════════════════════════════════════════════════════════════
# EXAM / ASSESSMENT
# ══════════════════════════════════════════════════════════════════════════════

async def generate_exam(topic, all_contexts):
    """Generate a mixed-format exam paper from accumulated context.
    Per-session targets: ~30-40 marks. Multi-session totals scale naturally.
    Caps are tight so 3 sessions ≈ 100 marks, not 250+.
    """
    combined = "\n\n---\n\n".join(all_contexts)[:6000]
    cc = len(combined)
    # Full exam — max tokens set to 8000 so JSON never truncates
    n_mcq   = max(3, min(5,  cc // 700))
    n_tf    = max(2, min(4,  cc // 900))
    n_fib   = max(2, min(3,  cc // 1100))
    n_short = max(1, min(2,  cc // 1500))
    n_long  = 1

    system = (
        "You are an exam paper generator for LearnPilot. "
        "Create a formal mixed-format exam based STRICTLY on the provided content. "
        "\n\nCRITICAL RULES — VIOLATIONS WILL FAIL THE TASK:\n"
        "1. Every question MUST be answerable using ONLY the facts, definitions, examples, and "
        "concepts that appear LITERALLY in the provided content.\n"
        "2. DO NOT include questions about related topics, background knowledge, or general "
        "subject knowledge that isn't stated in the content.\n"
        "3. If you cannot find a specific fact, definition, or example in the content to base "
        "a question on, GENERATE FEWER QUESTIONS rather than make one up.\n"
        "4. For MCQ: the correct answer and ALL 3 distractor options must be plausible given "
        "the content — preferably with distractors also drawn from the content.\n"
        "5. For TF: the statement must be directly verifiable as true/false from the content.\n"
        "6. For FIB: the blanked word/phrase MUST appear verbatim in the content.\n"
        "7. For short/long answer: the model answer must be constructible from sentences in "
        "the content.\n"
        "8. If a topic is only briefly mentioned and you can't form a solid question from it, "
        "SKIP IT.\n\n"
        "Return ONLY valid JSON, no markdown fences. Structure:\n"
        '{"title":"Exam: <topic>","instructions":"Answer all sections.","sections":[\n'
        '  {"name":"Section A - Multiple Choice","type":"mcq","marks_each":2,"questions":[{"q":"Question?","options":["A) ...","B) ...","C) ...","D) ..."],"answer":"A","explanation":"Why A."}]},\n'
        '  {"name":"Section B - True or False","type":"tf","marks_each":1,"questions":[{"q":"Statement.","answer":"True","explanation":"Why."}]},\n'
        '  {"name":"Section C - Fill in the Blanks","type":"fib","marks_each":2,"questions":[{"q":"Sentence with ___ blank.","answer":"word","explanation":"From content."}]},\n'
        '  {"name":"Section D - Short Answer","type":"short","marks_each":5,"questions":[{"q":"Question?","answer":"Model answer.","marks":5}]},\n'
        '  {"name":"Section E - Long Answer","type":"long","marks_each":15,"questions":[{"q":"Detailed Q?","answer":"Detailed A.","marks":15}]}\n'
        ']}'
    )
    user = (
        "Content:\n" + combined + "\n\n"
        "Generate AT MOST: " + str(n_mcq) + " MCQ, " + str(n_tf) + " true/false, "
        + str(n_fib) + " fill-in-blanks (use ___ for the blank), "
        + str(n_short) + " short answer, " + str(n_long) + " long answer. "
        "It's better to generate FEWER questions than to invent questions from outside the content. "
        "EVERY question MUST be answerable from facts that appear LITERALLY in the content above. "
        "If the content is short or lacks enough material for some sections, return fewer questions in those sections. "
        "Return ONLY JSON."
    )
    raw = _call_llm(system, user, max_tokens=8000, temp=0.3)
    result = _extract_json(raw, "object")
    if result: return result
    logger.error(f"[ExamSections] parse failed — len={len(raw)} | first200: {raw[:200]} | last200: {raw[-200:]}")
    return {}



async def grade_exam(questions: list, answers: list) -> list:
    """
    Grade all exam answers in one LLM call.
    questions: [{q, answer (model), marks, type}]
    answers:   [{"user_answer": str}]
    Returns:   [{verdict, score, max_marks, feedback}]
    """
    pairs = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        pairs.append(
            "Q" + str(i+1) + " [" + str(q.get("marks",5)) + " marks]: " + q.get("q","") + "\n"
            "Model answer: " + q.get("answer","") + "\n"
            "Student answer: " + a.get("user_answer","(blank)")
        )

    system = (
        "You are an exam grader for LearnPilot. Grade each student answer fairly. "
        "Return ONLY a JSON array with one object per question:\n"
        '[{"score": number, "max_marks": number, "feedback": "1-2 sentences."}]'
    )
    user = "\n\n".join(pairs) + "\n\nGrade all answers. Return ONLY the JSON array."
    raw = _call_llm(system, user, max_tokens=800, temp=0.2)
    result = _extract_json(raw, "array")
    if result: return result
    logger.error("[ExamGrade] parse failed — raw: " + raw[:200])
    return []


# ══════════════════════════════════════════════════════════════════════════════
# FLASHCARDS
# ══════════════════════════════════════════════════════════════════════════════

async def generate_flashcards(topic: str, all_contexts: list) -> list:
    """
    Generate spaced-repetition flashcards from accumulated context.
    Returns [{front, back, difficulty}]
    """
    combined  = "\n\n---\n\n".join(all_contexts)[:4000]
    char_count = len(combined)
    n_cards   = max(5, min(20, char_count // 300))

    system = (
        "You are a flashcard generator for LearnPilot. "
        "Create flashcards for spaced repetition study. "
        "Front = concise question or term. Back = clear, complete answer. "
        "Return ONLY valid JSON array:\n"
        '[{"front":"Term or question?","back":"Answer or definition.","difficulty":"easy|medium|hard"}]'
    )
    user = (
        "Content:\n" + combined + "\n\n"
        "Generate " + str(n_cards) + " flashcards covering key terms, concepts, and facts. "
        "Mix difficulty levels. Return ONLY the JSON array."
    )
    raw = _call_llm(system, user, max_tokens=1000, temp=0.4)
    result = _extract_json(raw, "array")
    if result:
        logger.info("[Flashcards] " + str(len(result)) + " cards for '" + topic + "'")
        return result
    logger.error("[Flashcards] parse failed — raw: " + raw[:200])
    return []

# ══════════════════════════════════════════════════════════════════════════════
# ASK FOLLOW-UP
# ══════════════════════════════════════════════════════════════════════════════

async def ask_followup(topic: str, mode: str, context: str, question: str) -> str:
    """
    Answer a follow-up question in the context of what was already learned.
    Returns plain text answer.
    """
    system = (
        "You are LearnPilot, an educational AI. "
        "The student has been studying '" + topic + "' in " + mode + " mode. "
        "Answer their follow-up question concisely and clearly, "
        "using the context of what they already learned. "
        "2-4 paragraphs max. No section headers."
    )
    user = (
        "What the student already learned:\n" + context[:2000] + "\n\n"
        "Their follow-up question: " + question
    )
    return _call_llm(system, user, max_tokens=600, temp=0.6)
