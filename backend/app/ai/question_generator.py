
import json
import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def generate_interview_questions(
    role: str,
    experience: str,
    interview_type: str,
    difficulty: str,
    question_count: int,
    skills: list[str] | None = None,
) -> list[str]:
    """Generate role-specific interview questions with Gemini."""

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from backend/.env")

    client = genai.Client(api_key=api_key)

    skills_text = ", ".join(skills or []) or "No additional skills specified"

    prompt = f"""
You are an experienced technical interviewer for NexHire.

Generate exactly {question_count} distinct interview questions.

Candidate profile:
- Target role: {role}
- Experience level: {experience}
- Interview type: {interview_type}
- Difficulty: {difficulty}
- Skills to focus on: {skills_text}

Requirements:
1. Match every question to the target role and experience level.
2. Easy: fundamentals and straightforward explanations.
3. Medium: practical applications, problem-solving, and examples.
4. Hard: advanced concepts, trade-offs, and deeper reasoning.
5. Technical interviews must focus on relevant technical knowledge.
6. HR interviews must focus on behavioral, motivation, and communication.
7. Mixed interviews must include both technical and HR questions.
8. Avoid duplicate questions and generic questions unrelated to the role.
9. Questions must be clear and suitable for a spoken mock interview.
10. Return exactly {question_count} questions.

Return only valid JSON in this format:
{{
  "questions": [
    "First interview question",
    "Second interview question"
  ]
}}
"""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
        },
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    data = json.loads(response.text)
    questions = data.get("questions")

    if not isinstance(questions, list):
        raise RuntimeError("Gemini returned an invalid question list.")

    questions = [
        question.strip()
        for question in questions
        if isinstance(question, str) and question.strip()
    ]

    if len(questions) != question_count:
        raise RuntimeError(
            f"Expected {question_count} questions, "
            f"but Gemini returned {len(questions)}."
        )

    return questions
