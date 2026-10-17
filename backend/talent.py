"""Talent Acquisition Helper: explainable CV/job matching and placement tracking."""

import json
import os
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get("UNIFIED_DB_PATH", "data/unified.db")
_db_lock = Lock()

DEFAULT_JOBS = [
    {
        "id": "technical-support",
        "title": "Technical Support Advisor",
        "description": "Provide broadband and technology support, diagnose customer issues, follow troubleshooting processes, and document outcomes.",
        "skills": ["technical support", "troubleshooting", "customer service", "communication", "problem solving"],
        "qualifications": ["customer-facing experience", "technical or broadband knowledge"],
        "seniority": "mid",
        "industry": "telecommunications",
    },
    {
        "id": "customer-care",
        "title": "Customer Care Advisor",
        "description": "Handle customer enquiries, resolve problems with empathy, explain options clearly, and maintain accurate records.",
        "skills": ["customer service", "communication", "empathy", "case management", "problem solving"],
        "qualifications": ["customer-facing experience"],
        "seniority": "entry",
        "industry": "contact centre",
    },
    {
        "id": "sales-executive",
        "title": "Senior Sales Executive",
        "description": "Manage sales conversations, identify customer needs, achieve targets, build relationships, and support less experienced colleagues.",
        "skills": ["sales", "negotiation", "relationship management", "communication", "leadership", "targets"],
        "qualifications": ["sales experience", "evidence of achieving targets"],
        "seniority": "senior",
        "industry": "sales",
    },
]


def init_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS talent_candidates (
                id TEXT PRIMARY KEY, filename TEXT NOT NULL, cv_text TEXT NOT NULL,
                profile TEXT NOT NULL, created_at TEXT NOT NULL, owner_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS talent_jobs (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, job_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS talent_placements (
                id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, job_id TEXT NOT NULL,
                placement_date TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, owner_id TEXT
            )
        """)
        for alter in [
            "ALTER TABLE talent_candidates ADD COLUMN owner_id TEXT",
            "ALTER TABLE talent_placements ADD COLUMN owner_id TEXT",
        ]:
            try: conn.execute(alter)
            except sqlite3.OperationalError: pass
        conn.commit()
        for job in DEFAULT_JOBS:
            conn.execute(
                "INSERT OR IGNORE INTO talent_jobs (id, title, job_data, created_at) VALUES (?, ?, ?, ?)",
                (job["id"], job["title"], json.dumps(job), datetime.utcnow().isoformat()),
            )
        conn.commit()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"\b" + re.escape(phrase.lower()) + r"\b", text.lower()) is not None


def extract_text(data: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".html", ".htm"}:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return _normalise(soup.get_text(" "))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
            import io
            return _normalise(" ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages))
        except ImportError:
            raise ValueError("PDF support requires the optional pypdf package")
    if suffix == ".docx":
        try:
            from docx import Document
            import io
            return _normalise(" ".join(p.text for p in Document(io.BytesIO(data)).paragraphs))
        except ImportError:
            raise ValueError("DOCX support requires the optional python-docx package")
    return _normalise(data.decode("utf-8", errors="ignore"))


def _section(text: str, labels: List[str]) -> str:
    pattern = r"(?:" + "|".join(re.escape(label) for label in labels) + r")\s*[:\-]?\s*(.*?)(?=\s+(?:experience|employment|work history|education|skills|certifications?|qualifications?|responsibilities|achievements?)\s*[:\-]|$)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def analyse_cv(text: str, filename: str) -> Dict[str, Any]:
    years = [int(value) for value in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text)]
    experience_years = max(0, max(years) - min(years)) if len(years) >= 2 else 0
    jobs = re.findall(r"(?:19\d{2}|20\d{2})\s*(?:-|to)\s*(?:19\d{2}|20\d{2}|present|current)", text, re.IGNORECASE)
    skills_text = _section(text, ["skills", "technical skills", "core skills"])
    qualifications = _section(text, ["qualifications", "education", "certifications", "certificates"])
    profile = {
        "filename": filename,
        "summary": text[:500],
        "work_experience": _section(text, ["experience", "employment", "work history"]),
        "skills": skills_text,
        "qualifications": qualifications,
        "education": _section(text, ["education"]),
        "certifications": _section(text, ["certifications", "certificates"]),
        "responsibilities": _section(text, ["responsibilities", "duties"]),
        "achievements": _section(text, ["achievements", "accomplishments"]),
        "career_progression": "promotion" in text.lower() or "promoted" in text.lower() or "senior" in text.lower(),
        "experience_years": experience_years,
        "job_history_count": len(jobs),
        "industry_keywords": [industry for industry in ["telecommunications", "technology", "sales", "retail", "finance", "healthcare", "contact centre", "customer service"] if _contains(text, industry)],
        "seniority": "senior" if _contains(text, "senior") or _contains(text, "manager") else "mid" if experience_years >= 3 else "entry",
    }
    return profile


def list_jobs() -> List[Dict[str, Any]]:
    init_db()
    with _connect() as conn:
        return [json.loads(row["job_data"]) for row in conn.execute("SELECT job_data FROM talent_jobs ORDER BY title")]


def save_candidate(filename: str, cv_text: str, owner_id: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    candidate_id = str(uuid.uuid4())
    profile = analyse_cv(cv_text, filename)
    with _db_lock, _connect() as conn:
        conn.execute("INSERT INTO talent_candidates (id, filename, cv_text, profile, created_at, owner_id) VALUES (?, ?, ?, ?, ?, ?)", (candidate_id, filename, cv_text, json.dumps(profile), datetime.utcnow().isoformat(), owner_id))
        conn.commit()
    return {"id": candidate_id, "profile": profile}


def _job_terms(job: Dict[str, Any]) -> List[str]:
    return list(dict.fromkeys([*(job.get("skills") or []), *(job.get("qualifications") or []), job.get("industry", ""), job.get("title", "")]))


def assess_candidate(candidate: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    profile = candidate.get("profile", candidate)
    source = " ".join(str(value) for value in profile.values()).lower()
    terms = _job_terms(job)
    matched = [term for term in terms if term and _contains(source, term)]
    missing = [term for term in terms if term and term not in matched]
    score = round((len(matched) / max(1, len(terms))) * 72)
    if job.get("seniority") == profile.get("seniority"):
        score += 15
    elif job.get("seniority") == "entry" and profile.get("seniority") == "mid":
        score += 8
    if job.get("industry") in profile.get("industry_keywords", []):
        score += 13
    score = min(99, max(1, score))
    concerns = []
    if missing:
        concerns.append("Missing or unverified requirements: " + ", ".join(missing[:4]))
    if not profile.get("experience_years"):
        concerns.append("The CV does not provide enough dated employment information to estimate experience length.")
    return {
        "job_id": job["id"], "job_title": job["title"], "suitability_score": score,
        "matched_requirements": matched, "missing_requirements": missing,
        "strongest_advantages": matched[:5], "concerns": concerns,
        "explanation": f"The CV matches {len(matched)} of {len(terms)} job-relevant terms, with a {profile.get('seniority', 'unknown')} seniority signal.",
    }


def retention_assessment(profile: Dict[str, Any], suitability: Dict[str, Any]) -> Dict[str, Any]:
    score = 50
    factors_for, factors_against = [], []
    if profile.get("career_progression"):
        score += 15; factors_for.append("Career progression signals are present")
    if profile.get("experience_years", 0) >= 2:
        score += 12; factors_for.append("The CV shows at least two years between dated roles")
    if profile.get("job_history_count", 0) <= 4:
        score += 8; factors_for.append("The available job history does not show frequent changes")
    if suitability["suitability_score"] >= 75:
        score += 15; factors_for.append("Strong role alignment may reduce mismatch risk")
    else:
        score -= 15; factors_against.append("Lower role alignment may increase mismatch risk")
    if profile.get("job_history_count", 0) >= 6:
        score -= 15; factors_against.append("Many recorded job changes warrant discussion")
    return {"retention_score": min(95, max(5, score)), "factors_for": factors_for, "factors_against": factors_against, "disclaimer": "AI-based estimate from the supplied CV and job criteria; it is not a guarantee of future behaviour."}


def evaluate(candidate_id: str, selected_job_id: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT id, filename, profile, owner_id FROM talent_candidates WHERE id = ?", (candidate_id,)).fetchone()
    if not row or (owner_id and row["owner_id"] not in (None, owner_id)):
        raise ValueError("Candidate not found")
    candidate = {"id": row["id"], "filename": row["filename"], "profile": json.loads(row["profile"])}
    jobs = list_jobs()
    assessments = [assess_candidate(candidate, job) for job in jobs]
    selected = next((item for item in assessments if item["job_id"] == selected_job_id), None) or assessments[0]
    retention = retention_assessment(candidate["profile"], selected)
    alternatives = sorted([item for item in assessments if item["job_id"] != selected["job_id"]], key=lambda item: item["suitability_score"], reverse=True)
    return {"candidate": candidate, "selected": selected, "retention": retention, "alternatives": alternatives}


def create_placement(candidate_id: str, job_id: str, placement_date: Optional[str] = None, owner_id: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    with _connect() as conn:
        candidate_row = conn.execute("SELECT profile, owner_id FROM talent_candidates WHERE id = ?", (candidate_id,)).fetchone()
    job = next((item for item in list_jobs() if item["id"] == job_id), None)
    if not candidate_row or (owner_id and candidate_row["owner_id"] not in (None, owner_id)) or not job:
        raise ValueError("Candidate or job not found")
    profile = json.loads(candidate_row["profile"])
    original_fit = assess_candidate({"profile": profile}, job)
    original_retention = retention_assessment(profile, original_fit)
    placement = {
        "id": str(uuid.uuid4()), "candidate_id": candidate_id, "job_id": job_id,
        "job_title": job["title"], "placement_date": placement_date or date.today().isoformat(),
        "original_suitability_score": original_fit["suitability_score"],
        "original_retention_score": original_retention["retention_score"],
        "milestones": {key: {"status": "pending", "notes": ""} for key in ["day_1", "week_1", "month_1", "month_2", "month_3"]},
    }
    with _db_lock, _connect() as conn:
        conn.execute("INSERT INTO talent_placements (id, candidate_id, job_id, placement_date, data, created_at, owner_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (placement["id"], candidate_id, job_id, placement["placement_date"], json.dumps(placement), datetime.utcnow().isoformat(), owner_id))
        conn.commit()
    return placement


def update_placement(placement_id: str, milestone: str, status: str, notes: str, owner_id: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    with _db_lock, _connect() as conn:
        row = conn.execute("SELECT data, owner_id FROM talent_placements WHERE id = ?", (placement_id,)).fetchone()
        if not row or (owner_id and row["owner_id"] not in (None, owner_id)): raise ValueError("Placement not found")
        placement = json.loads(row["data"])
        if milestone not in placement["milestones"]: raise ValueError("Unknown milestone")
        placement["milestones"][milestone] = {"status": status, "notes": notes}
        conn.execute("UPDATE talent_placements SET data = ? WHERE id = ?", (json.dumps(placement), placement_id)); conn.commit()
    return placement


def placement_report(placement_id: str, owner_id: Optional[str] = None) -> Dict[str, Any]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT data, owner_id FROM talent_placements WHERE id = ?", (placement_id,)).fetchone()
    if not row or (owner_id and row["owner_id"] not in (None, owner_id)): raise ValueError("Placement not found")
    placement = json.loads(row["data"])
    milestones = list(placement["milestones"].values())
    completed = sum(item["status"] in {"completed", "active", "successful"} for item in milestones)
    success = round((completed / len(milestones)) * 100)
    placement["placement_success_score"] = success
    placement["status"] = "successful" if success >= 80 else "needs_review" if success >= 50 else "at_risk"
    return placement


def generate_advertisement(offer: str, preferences: Dict[str, str]) -> Dict[str, Any]:
    text = _normalise(offer)
    title = preferences.get("title") or (_section(text, ["job title", "role", "position"]) or "New Opportunity").split(".")[0]
    tone = preferences.get("tone", "professional")
    platform = preferences.get("platform", "general recruitment platform")
    target = preferences.get("target_profile", "candidates with relevant experience")
    language = preferences.get("language", "English")
    advertisement = f"{title}\n\nJoin us as a {title} and make an impact. This opportunity is designed for {target}.\n\nWhat you will do\n{text}\n\nWhy consider this role\nThe position offers the responsibilities, requirements, and benefits described in the original job offer. Please review the full details carefully before applying.\n\nWho we are looking for\nWe welcome applicants who can demonstrate the qualifications, skills, and experience stated in the offer.\n\nHow to apply\nApply through the advertised recruitment process and include the information requested by the employer.\n\nTone: {tone} | Platform: {platform} | Language: {language}"
    return {"title": title, "advertisement": advertisement, "preferences": preferences, "source_basis": "Generated strictly from the supplied job offer and advertising preferences."}
