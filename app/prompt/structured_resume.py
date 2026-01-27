PROMPT = """
You are a JSON extraction engine. Convert the following resume text into precisely the JSON schema specified below.
- Map each resume section to the schema without inventing information.
- Always extract keywords from the resume text for the `extracted_keywords` field. The keywords should reflect the main skills, technologies, and relevant terms found in the resume.
- If a field is missing in the source text, use an empty string or empty list as appropriate.
- For each project, you must use the key project_name for the title and technologies_used for the list of tools used. Do not use the key 'name'.
- Preserve bullet points in the `description` arrays using short factual sentences.
- Use "Present" if an end date is ongoing and prefer YYYY-MM-DD where dates are available.
- For each entry in `conferences_trainings_workshops`, you must identify if it is a `conference`, `training`, or `workshop` and set the `type` field accordingly.
- Keep the sections organized: list technical skills, languages, publications, awards, extracurricular activities, and professional engagements (conferences, trainings, workshops) exactly as they appear.
- Do not compose any extra fields or commentary and output raw JSON only (no Markdown, no prose).

Schema:
```json
{0}
```

Resume:
```text
{1}
```

NOTE: Please output only a valid JSON matching the EXACT schema.
"""
