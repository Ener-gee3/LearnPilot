class AIEngine:
    @staticmethod
    def get_system_prompt(mode: str) -> str:
        prompts = {
            "Concept-First Learning": (
                "Strategy: Concept-First. 1. Explain fundamental concept. "
                "2. Simple example. 3. Complexity. 4. Practice question."
            ),
            "Reverse Engineering": (
                "Strategy: Learning by Deconstruction. 1. Break down code. "
                "2. Explain logic. 3. Identify concepts. 4. Reconstruction exercise."
            )
        }
        return prompts.get(mode, "You are a helpful educational assistant.")

    @staticmethod
    async def generate_response(mode: str, topic: str, code: str = None):
        # This is the exact spot where Brosil will integrate the model calls.
        # For now, it returns structured mock data.
        system_instruction = AIEngine.get_system_prompt(mode)
        
        return {
            "mode": mode,
            "explanation": f"Placeholder: {mode} explanation for {topic}.",
            "steps": ["Initialized AI Strategy", "Applied Prompt Template", "Ready for Model"],
            "exercise": "Practice question will appear here."
        }
