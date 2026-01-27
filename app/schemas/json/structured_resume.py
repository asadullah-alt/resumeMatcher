SCHEMA = {
    "UUID": "string",
    "summary": "string",
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
    "publications": [
        {
            "title": "string | null",
            "authors": ["string", "..."],
            "publication_venue": "string | null",
            "date": "YYYY-MM-DD | null",
            "link": "string | null",
            "description": "string | null",
        }
    ],
    "conferences_trainings_workshops": [
        {
            "type": "conference | training | workshop",
            "name": "string | null",
            "organizer": "string | null",
            "date": "YYYY-MM-DD | null",
            "location": "string | null",
            "description": "string | null",
            "certificate_link": "string | null",
        }
    ],
    "awards": [
        {
            "title": "string | null",
            "issuer": "string | null",
            "date": "YYYY-MM-DD | null",
            "description": "string | null",
        }
    ],
    "extracurricular_activities": [
        {
            "activity_name": "string | null",
            "role": "string | null",
            "organization": "string | null",
            "start_date": "YYYY-MM-DD | null",
            "end_date": "YYYY-MM-DD | null",
            "description": "string | null",
        }
    ],
    "languages": [
        {
            "language": "string | null",
            "proficiency": "string | null",
        }
    ],
    "extracted_keywords": ["string", "..."],
}
