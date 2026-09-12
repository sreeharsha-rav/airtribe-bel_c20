"""Instruction text for tools.py's generate_interview_questions -- appended
after the per-call candidate/resume/must-have context, which stays dynamic
and inline (there's nothing reusable to extract there).
"""

INTERVIEW_QUESTIONS_INSTRUCTIONS = (
    "Draft 4-6 targeted interview questions that probe this candidate's gaps against the "
    "must-have requirements and verify specific claims in their resume. Ground every question "
    "in a detail from the resume text above -- do not ask generic questions."
)
