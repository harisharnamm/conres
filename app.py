import io
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple

from flask import Flask, jsonify, render_template, request, send_file
from docx import Document

app = Flask(__name__)

STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "your", "have", "has", "are", "was",
    "will", "can", "our", "you", "about", "into", "across", "using", "their", "they", "them",
    "but", "not", "all", "any", "job", "role", "team", "years", "year", "work", "experience",
}

SECTION_ALIASES = {
    "summary": ["summary", "profile", "objective"],
    "experience": ["experience", "employment", "work history", "professional experience"],
    "skills": ["skills", "technical skills", "core competencies"],
    "education": ["education", "academic"],
    "certifications": ["certification", "licenses", "credentials"],
}

OUTPUT_CACHE: Dict[str, Dict] = {}


@dataclass
class OptimizationContext:
    job_description: str
    industry: str
    role_level: str
    company_size: str


def extract_keywords(text: str, max_keywords: int = 20) -> List[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z+\-]{2,}", text.lower())
    filtered = [t for t in tokens if t not in STOPWORDS]
    counts = Counter(filtered)
    return [kw for kw, _ in counts.most_common(max_keywords)]


def normalize_heading(text: str) -> str:
    cleaned = re.sub(r"[^a-z ]", "", text.lower()).strip()
    for section, aliases in SECTION_ALIASES.items():
        if any(alias in cleaned for alias in aliases):
            return section
    return "other"


def detect_sections(doc: Document) -> Dict[str, int]:
    sections = Counter()
    for paragraph in doc.paragraphs:
        if paragraph.style and "heading" in paragraph.style.name.lower():
            sections[normalize_heading(paragraph.text)] += 1
        elif paragraph.text.strip().isupper() and len(paragraph.text.strip()) < 40:
            sections[normalize_heading(paragraph.text)] += 1
    return dict(sections)


def score_paragraph(text: str, keywords: List[str]) -> int:
    t = text.lower()
    return sum(2 if kw in t else 0 for kw in keywords)


def emphasize_keywords(doc: Document, keywords: List[str]) -> Tuple[int, Dict[str, int]]:
    changes = 0
    section_changes = Counter()
    active_section = "other"

    for paragraph in doc.paragraphs:
        if paragraph.style and "heading" in paragraph.style.name.lower():
            active_section = normalize_heading(paragraph.text)
            continue

        para_score = score_paragraph(paragraph.text, keywords)
        if para_score == 0:
            continue

        # Preserve original content while emphasizing relevant terms.
        for run in paragraph.runs:
            run_text_lower = run.text.lower()
            if any(kw in run_text_lower for kw in keywords):
                if not run.bold:
                    run.bold = True
                    changes += 1
                    section_changes[active_section] += 1

    return changes, dict(section_changes)


def single_page_check(doc: Document) -> Tuple[bool, str]:
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    word_count = len(text.split())
    para_count = len([p for p in doc.paragraphs if p.text.strip()])
    if word_count > 900 or para_count > 65:
        return False, "Resume appears longer than a single-page format. Processing is limited to concise one-page resumes."
    return True, "Single-page format check passed."


def build_preview(doc: Document) -> str:
    blocks = []
    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        blocks.append(f"<p>{p.text}</p>")
    return "".join(blocks)


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/optimize")
def optimize_resume():
    file = request.files.get("resume")
    if not file or not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "Please upload a valid DOCX resume."}), 400

    context = OptimizationContext(
        job_description=request.form.get("job_description", ""),
        industry=request.form.get("industry", "General"),
        role_level=request.form.get("role_level", "Individual Contributor"),
        company_size=request.form.get("company_size", "Any"),
    )

    try:
        source_bytes = file.read()
        document = Document(io.BytesIO(source_bytes))
    except Exception:
        return jsonify({"error": "Unable to parse DOCX. Please upload a non-corrupted Word document."}), 400

    single_page_ok, single_page_message = single_page_check(document)
    if not single_page_ok:
        return jsonify({"error": single_page_message}), 400

    keywords = extract_keywords(context.job_description)
    sections = detect_sections(document)
    change_count, section_changes = emphasize_keywords(document, keywords)

    output = io.BytesIO()
    document.save(output)
    output.seek(0)

    doc_id = str(uuid.uuid4())
    OUTPUT_CACHE[doc_id] = {
        "bytes": output.read(),
        "summary": {
            "keyword_count": len(keywords),
            "top_keywords": keywords[:10],
            "sections_detected": sections,
            "format_integrity": "Preserved original DOCX layout and structure while emphasizing job-relevant terms.",
            "changes_applied": change_count,
            "section_emphasis": section_changes,
            "target_profile": {
                "industry": context.industry,
                "role_level": context.role_level,
                "company_size": context.company_size,
            },
        },
        "preview": build_preview(document),
        "filename": f"optimized_{file.filename}",
        "single_page_message": single_page_message,
    }

    return jsonify({
        "document_id": doc_id,
        "summary": OUTPUT_CACHE[doc_id]["summary"],
        "preview_html": OUTPUT_CACHE[doc_id]["preview"],
        "message": single_page_message,
    })


@app.get("/api/download/<document_id>")
def download(document_id: str):
    payload = OUTPUT_CACHE.get(document_id)
    if not payload:
        return jsonify({"error": "Document not found. Please optimize again."}), 404

    return send_file(
        io.BytesIO(payload["bytes"]),
        as_attachment=True,
        download_name=payload["filename"],
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
