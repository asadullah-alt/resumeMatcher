PROMPT = """
You are the best cover letter writer ever. 
Job Posting:
```json
{0}
```
Resume Details:
'''json
{1}
```

Given the Job Posting and Resume Details, write a compelling cover letter that highlights the candidate's relevant skills and experiences.
The cover letter should be tailored to the job description, emphasizing how the candidate's background makes them a strong fit for the role.
Structure the cover letter as follows:
1. Introduction: Briefly introduce the candidate and express enthusiasm for the position.
2. Body: Highlight key skills, experiences, and achievements from the resume that align with the job requirements in the form of paragraphs.
3. Conclusion: Reiterate interest in the role and express eagerness to contribute to the company.
4. Dont add * or | or any other wierd characters in the cover letter.
NOTE: ONLY OUTPUT THE COVER LETTER IN MARKDOWN FORMAT.

"""
