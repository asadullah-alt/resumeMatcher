import os
import sys
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone

# Attempt to import fitz (PyMuPDF)
try:
    import fitz
except ImportError:
    print("Error: PyMuPDF is required. Please install it using: pip install pymupdf")
    sys.exit(1)

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We will generate dicts that match the ProcessedResume model schema.
# This avoids Beanie initialization issues while still providing valid structured data.

SECTION_HEADERS = [
    "PROFESSIONAL PROFILE",
    "EDUCATION",
    "INTERNSHIP EXPERIENCE",
    "FINAL YEAR PROJECT",
    "TECHNICAL EXPERTISE"
]

def get_text_with_fonts(pdf_path):
    doc = fitz.open(pdf_path)
    lines = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b.get('type') == 0:  # text block
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        text = s.get("text", "").strip()
                        size = s.get("size", 0)
                        if text:
                            lines.append({"text": text, "size": size})
    return lines

def split_resumes(lines):
    if not lines:
        return []
    
    # Find the maximum font size to identify the name
    max_size = max(line["size"] for line in lines)
    resumes = []
    current_resume = []
    
    last_was_name = False
    for line in lines:
        # Threshold for name font size (within 0.5 of max size)
        is_name = line["size"] >= max_size - 0.5
        
        if is_name:
            if not last_was_name and current_resume:
                # We hit a new name, save the previous resume
                resumes.append(current_resume)
                current_resume = []
            last_was_name = True
        else:
            last_was_name = False
            
        current_resume.append(line)
        
    if current_resume:
        resumes.append(current_resume)
        
    return resumes

def extract_contact_info(name_lines):
    # Heuristic to extract email and phone
    email = None
    phone = None
    other_lines = []
    
    email_pattern = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    phone_pattern = re.compile(r"^\+?[0-9\s\-\(\)]{7,}$")
    
    for line in name_lines:
        words = line.split()
        line_email = next((w for w in words if email_pattern.match(w)), None)
        if line_email:
            email = line_email
            
        line_phone = next((w for w in words if phone_pattern.match(w)), None)
        if line_phone:
            phone = line_phone
            
        if not line_email and not line_phone:
            other_lines.append(line)
            
    return email, phone, other_lines

def parse_resume(resume_lines):
    name_lines = []
    sections = {k: [] for k in SECTION_HEADERS}
    current_section = None
    
    for line in resume_lines:
        text = line["text"]
        upper_text = text.upper()
        
        # Check if this line matches a header
        matched_header = None
        for header in SECTION_HEADERS:
            if header in upper_text and len(upper_text) <= len(header) + 5:
                matched_header = header
                break
                
        if matched_header:
            current_section = matched_header
            continue
            
        if current_section is None:
            name_lines.append(text)
        else:
            sections[current_section].append(text)
            
    # Process Personal Data
    name_text = " ".join(name_lines[:1]) if name_lines else "Unknown"
    name_parts = name_text.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    email, phone, _ = extract_contact_info(name_lines[1:])
    
    personal_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone
    }
    
    # Process Summary
    summary = " ".join(sections["PROFESSIONAL PROFILE"])
    
    # Process Education
    education = []
    edu_lines = [l for l in sections["EDUCATION"] if l]
    if edu_lines:
        current_edu = {}
        for i, line in enumerate(edu_lines):
            if i == 0:
                current_edu["degree"] = line
            elif i == 1:
                # Extract year
                year_match = re.search(r'\b(20\d{2})\b', line)
                if year_match:
                    current_edu["end_date"] = year_match.group(1)
                    line = re.sub(r'\(\s*' + year_match.group(1) + r'\s*\)', '', line)
                    line = line.replace(year_match.group(1), "")
                
                # Extract GPA
                gpa_match = re.search(r'\b(\d\.\d{1,2}(?:/\d(?:\.\d)?)?)\b', line)
                if gpa_match:
                    current_edu["grade"] = gpa_match.group(1)
                    line = line.replace(gpa_match.group(0), "")
                
                # Cleanup institution name
                line = re.sub(r'[, \-]+$', '', line).strip()
                current_edu["institution"] = line
            else:
                current_edu["description"] = current_edu.get("description", "") + " " + line
        education.append(current_edu)
        
    # Process Experience
    experiences = []
    exp_lines = [l for l in sections["INTERNSHIP EXPERIENCE"] if l]
    
    date_pattern = re.compile(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|20\d{2}).*(?:-|to|–).*?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|20\d{2}|Present)', re.IGNORECASE)
    
    i = 0
    current_exp = None
    while i < len(exp_lines):
        line = exp_lines[i]
        
        # Look ahead for a date line
        if i + 1 < len(exp_lines) and date_pattern.search(exp_lines[i+1]) and len(exp_lines[i+1]) < 60:
            if current_exp:
                if "job_title" not in current_exp:
                    current_exp["job_title"] = "Intern"
                experiences.append(current_exp)
                
            current_exp = {
                "company": exp_lines[i],
                "start_date": exp_lines[i+1],
                "description": []
            }
            
            i += 2
            if i < len(exp_lines):
                # Try to extract job title from the next line if it has a bullet
                if not exp_lines[i].startswith("•") and "•" in exp_lines[i]:
                    parts = exp_lines[i].split("•", 1)
                    if len(parts[0]) < 60:
                        current_exp["job_title"] = parts[0].strip()
                        current_exp["description"].append("• " + parts[1].strip() if len(parts) > 1 else "")
                    else:
                        current_exp["description"].append(exp_lines[i])
                else:
                    current_exp["description"].append(exp_lines[i])
                i += 1 # Increment to skip the job title/first description line that we just processed
        else:
            if current_exp is None:
                current_exp = {"company": "", "description": []}
            current_exp["description"].append(line)
            i += 1
            
    if current_exp:
        # Fallback for job_title if missing
        if "job_title" not in current_exp:
            current_exp["job_title"] = "Intern"
        experiences.append(current_exp)
        
    # Process Projects
    projects = []
    proj_lines = [l for l in sections["FINAL YEAR PROJECT"] if l]
    if proj_lines:
        projects.append({
            "project_name": proj_lines[0] if len(proj_lines) > 0 else "Final Year Project",
            "description": " ".join(proj_lines[1:]) if len(proj_lines) > 1 else ""
        })
        
    # Process Skills
    skills = []
    stop_words = [
        "Skilled in", "Experienced", "Hands-on", "Proﬁcient", "Proficient", 
        "Beginner-level", "Led projects", "Managed", "Produced", "Created", 
        "Capable of", "Knowledgeable", "Familiar with", "Expertise in",
        "Working knowledge", "Basic understanding"
    ]
    
    for line in sections["TECHNICAL EXPERTISE"]:
        line = line.strip()
        line = re.sub(r'^[•\-\*]\s*', '', line)
        if not line:
            continue
            
        # Check for colon-separated heading
        if ':' in line:
            heading = line.split(':')[0].strip()
            if heading and len(heading.split()) <= 6:
                skills.append({"skill_name": heading})
            continue
            
        # Check for stop words
        found_sw = False
        for sw in stop_words:
            if sw in line:
                heading = line.split(sw)[0].strip()
                if heading and len(heading.split()) <= 6:
                    skills.append({"skill_name": heading})
                found_sw = True
                break
                
        if found_sw:
            continue
            
        # If no stop word or colon, check if it looks like a heading
        if ',' not in line and '.' not in line and len(line.split()) <= 6:
            # Also ensure it doesn't start with a stop word lowercase
            if not any(line.lower().startswith(sw.lower().split()[0]) for sw in stop_words):
                skills.append({"skill_name": line})
                
    # Fallback if no headings were found
    if not skills:
        skill_text = " ".join(sections["TECHNICAL EXPERTISE"])
        if skill_text:
            skill_items = re.split(r'[,|•;]', skill_text)
            for item in skill_items:
                item = item.strip()
                if item:
                    skills.append({"skill_name": item})
                
    return {
        "user_id": "bulk_import",
        "resume_name": f"{first_name} {last_name} Resume".strip(),
        "resume_id": f"bulk_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        "default": False,
        "personal_data": personal_data,
        "summary": summary,
        "education": education,
        "experiences": experiences,
        "projects": projects,
        "skills": skills,
        "processed_at": datetime.now(timezone.utc).isoformat()
    }

def process_pdfs_in_directory(input_dir, output_dir):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    processed_count = 0
    error_count = 0
    
    for pdf_file in input_path.rglob('*.pdf'):
        print(f"Processing: {pdf_file}")
        try:
            lines = get_text_with_fonts(str(pdf_file))
            resume_blocks = split_resumes(lines)
            
            print(f"  Found {len(resume_blocks)} resume(s) in {pdf_file.name}")
            
            for i, block in enumerate(resume_blocks):
                parsed_data = parse_resume(block)
                
                # Save to JSON
                first_name = parsed_data["personal_data"]["first_name"]
                safe_name = re.sub(r'[^a-zA-Z0-9]', '_', first_name).lower()
                out_filename = f"{pdf_file.stem}_resume_{i+1}_{safe_name}.json"
                out_file_path = output_path / out_filename
                
                with open(out_file_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_data, f, indent=4)
                    
                processed_count += 1
        except Exception as e:
            print(f"  Error processing {pdf_file}: {e}")
            error_count += 1
            
    print(f"\nProcessing complete!")
    print(f"Successfully processed {processed_count} resumes.")
    print(f"Errors encountered in {error_count} PDFs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk extract and parse structured PDFs.")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing folders of PDFs.")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save the output JSON files.")
    
    args = parser.parse_args()
    
    process_pdfs_in_directory(args.input_dir, args.output_dir)
