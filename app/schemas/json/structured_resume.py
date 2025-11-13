SCHEMA = {
    "UUID": "string",
    "personal_data": {
        "first_name": "string",
        "last_name": "string",
        "email": "string",
        "phone": "string",
        "linkedin": "string",
        "portfolio": "string",
        "location": {"city": "string", "country": "string"},
    },
    "experiences": [
        {
            "job_title": "string",
            "company": "string",
            "location": "string",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD or Present",
            "description": ["string", "..."],
            "technologiesUsed": ["string", "..."],
        }
    ],
    "projects": [
        {
            "project_name": "string",
            "description": "string",
            "technologies_used": ["string", "..."],
            "link": "string",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
        }
    ],
    "skills": [{"category": "string", "skill_name": "string"}],
    "research_work": [
        {
            "title": "string | null",
            "publication": "string | null",
            "date": "YYYY-MM-DD | null",
            "link": "string | null",
            "description": "string | null",
        }
    ],
    "achievements": ["string", "..."],
    "education": [
        {
            "institution": "string",
            "degree": "string",
            "field_of_study": "string | null",
            "start_date": "YYYY-MM-DD",
            "end_date": "YYYY-MM-DD",
            "grade": "string",
            "description": "string",
        }
    ],
    "extracted_keywords": ["string", "..."],
}
