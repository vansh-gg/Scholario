from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import mysql.connector
import io, csv, os
from decimal import Decimal
from datetime import datetime, date

app = FastAPI(title="Scholario API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/style.css")
def serve_css():
    return FileResponse(os.path.join(BASE_DIR, "style.css"), media_type="text/css")

@app.get("/shared.js")
def serve_js():
    return FileResponse(os.path.join(BASE_DIR, "shared.js"), media_type="application/javascript")

@app.get("/{filename}.html")
def serve_html(filename: str):
    path = os.path.join(BASE_DIR, f"{filename}.html")
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(404, "Page not found")

def db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "scholario")
    )

def q(sql, params=(), one=False, commit=False):
    conn = db(); cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    if commit:
        conn.commit(); result = cur.lastrowid
    elif one:
        result = cur.fetchone()
    else:
        result = cur.fetchall()
    cur.close(); conn.close()
    return result

def flt(v):
    if v is None: return 0.0
    return float(v)

def clean_row(row):
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal): out[k] = float(v)
        elif isinstance(v, (datetime, date)): out[k] = str(v)
        else: out[k] = v
    return out

def clean_rows(rows): return [clean_row(dict(r)) for r in rows]

def log(user_id, action, details, ip="127.0.0.1"):
    try: q("INSERT INTO audit_log(user_id,action,details,ip_address) VALUES(%s,%s,%s,%s)", (user_id,action,details,ip), commit=True)
    except: pass

class LoginReq(BaseModel):
    reg_number: str; password: str

class SubmitReq(BaseModel):
    assignment_id: int; student_id: int; submission_text: str

class GradeReq(BaseModel):
    marks_obtained: int; remark_text: Optional[str] = ""; faculty_id: int

class AttendanceReq(BaseModel):
    student_id: int; class_id: int; date: str; status: str; marked_by: Optional[int] = None

class AssignmentReq(BaseModel):
    class_id: int; faculty_id: int; title: str; description: Optional[str] = ""
    difficulty: Optional[str] = "Medium"; due_date: str; max_marks: Optional[int] = 10

@app.post("/api/login")
def login(req: LoginReq):
    user = q("SELECT * FROM users WHERE reg_number=%s AND password=%s", (req.reg_number, req.password), one=True)
    if not user: raise HTTPException(400, "Invalid credentials")
    q("UPDATE users SET last_active=NOW() WHERE user_id=%s", (user["user_id"],), commit=True)
    log(user["user_id"], "LOGIN", f"{user['role'].title()} {user['name']} logged in")
    return {"user": {"user_id": user["user_id"], "name": user["name"], "email": user["email"], "role": user["role"], "reg_number": user["reg_number"]}}

def get_student_id(user_id):
    s = q("SELECT student_id FROM student WHERE user_id=%s", (user_id,), one=True)
    if not s: raise HTTPException(404, "Student not found")
    return s["student_id"]

def get_student_section(user_id):
    s = q("SELECT COALESCE(section,'AL2') as section FROM student WHERE user_id=%s", (user_id,), one=True)
    return s["section"] if s else "AL2"

def predict_grade(att_pct, sub_rate, avg_score):
    a = flt(att_pct); s = flt(sub_rate); sc = flt(avg_score)
    score = a * 0.4 + s * 0.3 + (sc * 10) * 0.3
    if score >= 90: return "O"
    if score >= 85: return "A+"
    if score >= 80: return "A"
    if score >= 75: return "B+"
    if score >= 70: return "B"
    return "F"

def calc_streak(student_id):
    rows = q("SELECT status FROM attendance WHERE student_id=%s ORDER BY date DESC LIMIT 30", (student_id,))
    streak = 0
    for r in rows:
        if r["status"] == "present": streak += 1
        else: break
    return streak

# ─────────────────────────────────────────────────────────────
# STUDENT ENDPOINTS
# The student table has one class_id per student (their primary/DBMS class).
# But assignments and attendance span ALL 5 classes via faculty_id linkage.
# We use section ('AL2'/'SAO') to group students correctly.
# For assignments: we join on faculty who teaches the student's section's class.
# ─────────────────────────────────────────────────────────────

@app.get("/api/student/{user_id}/dashboard")
def student_dashboard(user_id: int):
    sid = get_student_id(user_id)
    section = get_student_section(user_id)

    # Attendance across ALL classes the student has records in
    att = q("SELECT COUNT(*) as total, SUM(status='present') as present, SUM(status='absent') as absent FROM attendance WHERE student_id=%s", (sid,), one=True)
    total = int(att["total"] or 1); present = int(att["present"] or 0)
    att_pct = round(present / total * 100, 1)

    # Assignments: all assignments for classes matching this student's section
    asgn = q("""
        SELECT a.assignment_id, sub.submission_id
        FROM assignment a
        JOIN class c ON c.class_id = a.class_id AND c.section = %s
        LEFT JOIN submission sub ON sub.assignment_id = a.assignment_id AND sub.student_id = %s
    """, (section, sid))
    submitted = sum(1 for a in asgn if a["submission_id"]); total_asgn = len(asgn)
    sub_rate = round(submitted / total_asgn * 100, 1) if total_asgn else 0.0

    scores = q("SELECT AVG(effective_marks) as avg FROM submission WHERE student_id=%s AND status='checked'", (sid,), one=True)
    avg_score = round(flt(scores["avg"]), 1)
    streak = calc_streak(sid)

    upcoming = q("""
        SELECT a.assignment_id, a.title, a.due_date, a.difficulty, a.max_marks,
               u.name as faculty_name, sub.status as my_status, sub.submission_id
        FROM assignment a
        JOIN class c ON c.class_id = a.class_id AND c.section = %s
        JOIN users u ON u.user_id = a.faculty_id
        LEFT JOIN submission sub ON sub.assignment_id = a.assignment_id AND sub.student_id = %s
        WHERE a.due_date >= NOW()
        ORDER BY a.due_date ASC LIMIT 5
    """, (section, sid))

    notifs = q("SELECT * FROM notification WHERE user_id=%s ORDER BY created_at DESC LIMIT 5", (user_id,))
    return {
        "student": {"student_id": sid},
        "attendance": {"percentage": att_pct, "present": present, "absent": int(att["absent"] or 0)},
        "assignments": {"total": total_asgn, "submitted": submitted, "rate": sub_rate},
        "avg_score": avg_score, "streak": streak,
        "predicted_grade": predict_grade(att_pct, sub_rate, avg_score),
        "upcoming_assignments": clean_rows(upcoming),
        "notifications": clean_rows(notifs)
    }

@app.get("/api/student/{user_id}/assignments")
def student_assignments(user_id: int):
    sid = get_student_id(user_id)
    section = get_student_section(user_id)
    rows = q("""
        SELECT a.assignment_id, a.title, a.description, a.difficulty, a.due_date, a.max_marks,
               u.name as faculty_name,
               sub.submission_id, sub.submitted_at, sub.status as sub_status,
               sub.marks_obtained, sub.effective_marks, sub.penalty_pct, sub.is_late,
               sub.plagiarism_flag, r.remark_text
        FROM assignment a
        JOIN class c ON c.class_id = a.class_id AND c.section = %s
        JOIN users u ON u.user_id = a.faculty_id
        LEFT JOIN submission sub ON sub.assignment_id = a.assignment_id AND sub.student_id = %s
        LEFT JOIN remark r ON r.submission_id = sub.submission_id
        ORDER BY a.due_date ASC
    """, (section, sid))
    return clean_rows(rows)

@app.get("/api/student/{user_id}/attendance")
def student_attendance(user_id: int):
    sid = get_student_id(user_id)
    records = q("SELECT a.date, a.status, c.subject FROM attendance a JOIN class c ON c.class_id=a.class_id WHERE a.student_id=%s ORDER BY a.date DESC", (sid,))
    stats_raw = q("SELECT c.subject, COUNT(*) as total, SUM(a.status='present') as present FROM attendance a JOIN class c ON c.class_id=a.class_id WHERE a.student_id=%s GROUP BY c.class_id, c.subject", (sid,))
    stats = []
    for s in stats_raw:
        tot = int(s["total"] or 1); pres = int(s["present"] or 0)
        stats.append({**clean_row(dict(s)), "percentage": round(pres / tot * 100, 1)})
    return {"records": clean_rows(records), "stats": stats}

@app.get("/api/student/{user_id}/remarks")
def student_remarks(user_id: int):
    sid = get_student_id(user_id)
    rows = q("SELECT r.remark_text, r.created_at, a.title as assignment_title, u.name as faculty_name, sub.marks_obtained, sub.effective_marks, sub.plagiarism_flag FROM remark r JOIN submission sub ON sub.submission_id=r.submission_id JOIN assignment a ON a.assignment_id=sub.assignment_id JOIN users u ON u.user_id=r.faculty_id WHERE sub.student_id=%s ORDER BY r.created_at DESC", (sid,))
    return clean_rows(rows)

@app.post("/api/student/submit")
def student_submit(req: SubmitReq):
    existing = q("SELECT submission_id FROM submission WHERE assignment_id=%s AND student_id=%s", (req.assignment_id, req.student_id), one=True)
    if existing: raise HTTPException(400, "Already submitted")
    asgn = q("SELECT due_date FROM assignment WHERE assignment_id=%s", (req.assignment_id,), one=True)
    is_late = datetime.now() > asgn["due_date"] if asgn else False
    penalty = 10 if is_late else 0
    others = q("SELECT submission_text FROM submission WHERE assignment_id=%s AND submission_text IS NOT NULL", (req.assignment_id,))
    def sim(a, b):
        if not a or not b: return 0
        aw = set(a.lower().split()); bw = set(b.lower().split())
        return len(aw & bw) / len(aw | bw) if (aw | bw) else 0
    plag_flag = False; plag_note = None
    for o in others:
        if sim(req.submission_text, o["submission_text"]) > 0.6:
            plag_flag = True; plag_note = "High text similarity detected with another submission"; break
    sid = q("INSERT INTO submission(assignment_id,student_id,submission_text,is_late,penalty_pct,plagiarism_flag,plagiarism_note) VALUES(%s,%s,%s,%s,%s,%s,%s)", (req.assignment_id, req.student_id, req.submission_text, is_late, penalty, plag_flag, plag_note), commit=True)
    log(None, "SUBMIT", f"Student {req.student_id} submitted assignment {req.assignment_id}")
    return {"submission_id": sid, "is_late": is_late, "plagiarism_flag": plag_flag}

@app.get("/api/notifications/{user_id}")
def get_notifs(user_id: int):
    return clean_rows(q("SELECT * FROM notification WHERE user_id=%s ORDER BY created_at DESC", (user_id,)))

@app.get("/api/notifications/{user_id}/unread-count")
def unread_count(user_id: int):
    r = q("SELECT COUNT(*) as count FROM notification WHERE user_id=%s AND is_read=0", (user_id,), one=True)
    return {"count": int(r["count"] or 0)}

@app.put("/api/notifications/{notif_id}/read")
def mark_read(notif_id: int):
    q("UPDATE notification SET is_read=1 WHERE notif_id=%s", (notif_id,), commit=True); return {"ok": True}

@app.put("/api/notifications/{user_id}/read-all")
def mark_all_read(user_id: int):
    q("UPDATE notification SET is_read=1 WHERE user_id=%s", (user_id,), commit=True); return {"ok": True}

# ─────────────────────────────────────────────────────────────
# FACULTY ENDPOINTS
# Each faculty teaches ONE subject across BOTH sections (AL2 + SAO).
# So Mr. Bean (DBMS) teaches class_id=1 (AL2) AND class_id=6 (SAO).
# total_students = all students in BOTH sections = 114 (or those in faculty's classes).
# ─────────────────────────────────────────────────────────────

@app.get("/api/faculty/{user_id}/dashboard")
def faculty_dashboard(user_id: int):
    # Get all classes this faculty teaches (both AL2 and SAO sections)
    classes = q("SELECT * FROM class WHERE faculty_id=%s ORDER BY section, class_id", (user_id,))
    class_ids = [c["class_id"] for c in classes] or [0]
    fmt = ",".join(["%s"] * len(class_ids))

    # Count all students enrolled in any class taught by this faculty
    total_students = int(q(
        f"SELECT COUNT(DISTINCT st.student_id) as n FROM student st WHERE st.class_id IN ({fmt})",
        tuple(class_ids), one=True
    )["n"])

    # If still 0, count by section matching (fallback for students linked to class 1 only)
    if total_students == 0 and classes:
        sections = list(set(c["section"] if "section" in c and c["section"] else "AL2" for c in classes))
        fmt2 = ",".join(["%s"] * len(sections))
        total_students = int(q(
            f"SELECT COUNT(DISTINCT st.student_id) as n FROM student st WHERE COALESCE(st.section,'AL2') IN ({fmt2})",
            tuple(sections), one=True
        )["n"])

    pending = int(q(f"SELECT COUNT(*) as n FROM submission sub JOIN assignment a ON a.assignment_id=sub.assignment_id WHERE a.faculty_id=%s AND sub.status='submitted'", (user_id,), one=True)["n"])
    at_risk = int(q("SELECT COUNT(*) as n FROM at_risk WHERE resolved=0", one=True)["n"])
    plag = int(q(f"SELECT COUNT(*) as n FROM submission sub JOIN assignment a ON a.assignment_id=sub.assignment_id WHERE a.faculty_id=%s AND sub.plagiarism_flag=1", (user_id,), one=True)["n"])
    total_asgn = int(q("SELECT COUNT(*) as n FROM assignment WHERE faculty_id=%s", (user_id,), one=True)["n"])

    recent_subs = q("""
        SELECT sub.submission_id, sub.submitted_at, sub.status, sub.is_late, sub.plagiarism_flag,
               u.name as student_name, u.reg_number,
               a.title as assignment_title, c.subject, a.max_marks
        FROM submission sub
        JOIN student st ON st.student_id = sub.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        JOIN class c ON c.class_id = a.class_id
        WHERE a.faculty_id = %s
        ORDER BY sub.submitted_at DESC LIMIT 10
    """, (user_id,))

    return {
        "classes": clean_rows(classes),
        "stats": {
            "total_students": total_students,
            "pending_grading": pending,
            "at_risk_students": at_risk,
            "plagiarism_flags": plag,
            "total_assignments": total_asgn,
            "workload_score": total_asgn * 10 + pending * 5
        },
        "recent_submissions": clean_rows(recent_subs)
    }

@app.get("/api/faculty/{user_id}/submissions")
def faculty_submissions(user_id: int):
    rows = q("""
        SELECT sub.submission_id, sub.submission_text, sub.submitted_at, sub.status,
               sub.marks_obtained, sub.effective_marks, sub.penalty_pct, sub.is_late,
               sub.plagiarism_flag,
               u.name as student_name, u.reg_number,
               a.title as assignment_title, c.subject, a.max_marks, r.remark_text
        FROM submission sub
        JOIN student st ON st.student_id = sub.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        JOIN class c ON c.class_id = a.class_id
        LEFT JOIN remark r ON r.submission_id = sub.submission_id
        WHERE a.faculty_id = %s
        ORDER BY sub.submitted_at DESC
    """, (user_id,))
    return clean_rows(rows)

@app.put("/api/faculty/grade/{submission_id}")
def grade_submission(submission_id: int, req: GradeReq):
    sub = q("SELECT * FROM submission WHERE submission_id=%s", (submission_id,), one=True)
    if not sub: raise HTTPException(404, "Submission not found")
    penalty = int(sub["penalty_pct"] or 0)
    effective = round(req.marks_obtained * (1 - penalty / 100))
    q("UPDATE submission SET marks_obtained=%s, effective_marks=%s, status='checked' WHERE submission_id=%s", (req.marks_obtained, effective, submission_id), commit=True)
    if req.remark_text:
        q("INSERT INTO remark(submission_id,faculty_id,remark_text) VALUES(%s,%s,%s)", (submission_id, req.faculty_id, req.remark_text), commit=True)
    student_user = q("SELECT u.user_id FROM users u JOIN student st ON st.user_id=u.user_id WHERE st.student_id=%s", (sub["student_id"],), one=True)
    asgn = q("SELECT title FROM assignment WHERE assignment_id=%s", (sub["assignment_id"],), one=True)
    if student_user and asgn:
        q("INSERT INTO notification(user_id,title,message,type) VALUES(%s,%s,%s,%s)", (student_user["user_id"], "Assignment Graded", f"'{asgn['title']}' graded. Score: {effective}", "success"), commit=True)
    log(req.faculty_id, "GRADE", f"Graded submission #{submission_id} — {req.marks_obtained} marks")
    return {"ok": True, "effective_marks": effective}

@app.get("/api/faculty/{user_id}/attendance/{class_id}/{date}")
def get_attendance(user_id: int, class_id: int, date: str):
    # Get the section for this class
    cls = q("SELECT COALESCE(section,'AL2') as section FROM class WHERE class_id=%s", (class_id,), one=True)
    sec = cls["section"] if cls else "AL2"
    # Return all students in this section
    return clean_rows(q("""
        SELECT st.student_id, u.name, u.reg_number,
               COALESCE(a.status, 'not_marked') as status
        FROM student st
        JOIN users u ON u.user_id = st.user_id
        LEFT JOIN attendance a ON a.student_id = st.student_id
            AND a.class_id = %s AND a.date = %s
        WHERE COALESCE(st.section, 'AL2') = %s
        ORDER BY u.reg_number
    """, (class_id, date, sec)))

@app.post("/api/faculty/attendance")
def mark_attendance(req: AttendanceReq):
    q("INSERT INTO attendance(student_id,class_id,date,status,marked_by) VALUES(%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status=%s, marked_by=%s", (req.student_id, req.class_id, req.date, req.status, req.marked_by, req.status, req.marked_by), commit=True)
    return {"ok": True}

@app.post("/api/faculty/assignment")
def create_assignment(req: AssignmentReq):
    aid = q("INSERT INTO assignment(class_id,faculty_id,title,description,difficulty,due_date,max_marks) VALUES(%s,%s,%s,%s,%s,%s,%s)", (req.class_id, req.faculty_id, req.title, req.description, req.difficulty, req.due_date, req.max_marks), commit=True)
    # Notify all students in the same section as this class
    cls = q("SELECT COALESCE(section,'AL2') as section FROM class WHERE class_id=%s", (req.class_id,), one=True)
    sec = cls["section"] if cls else "AL2"
    students = q("SELECT u.user_id FROM users u JOIN student st ON st.user_id=u.user_id WHERE COALESCE(st.section,'AL2')=%s", (sec,))
    for s in students:
        q("INSERT INTO notification(user_id,title,message,type) VALUES(%s,%s,%s,%s)", (s["user_id"], "New Assignment", f"New: {req.title}. Due: {req.due_date}", "info"), commit=True)
    log(req.faculty_id, "CREATE_ASSIGNMENT", f"Created: {req.title}")
    return {"assignment_id": aid}

@app.get("/api/faculty/{user_id}/at-risk")
def faculty_atrisk(user_id: int):
    rows = q("""
        SELECT ar.risk_id, ar.reason, ar.att_pct, ar.flagged_at,
               u.name, u.reg_number,
               (SELECT COUNT(*) FROM submission sub WHERE sub.student_id=ar.student_id) as submitted_count
        FROM at_risk ar
        JOIN student st ON st.student_id = ar.student_id
        JOIN users u ON u.user_id = st.user_id
        WHERE ar.resolved = 0
        ORDER BY ar.att_pct ASC
    """)
    return clean_rows(rows)

@app.get("/api/faculty/{user_id}/plagiarism")
def faculty_plagiarism(user_id: int):
    flagged = q("""
        SELECT sub.submission_id, sub.submission_text, sub.submitted_at,
               sub.plagiarism_note, sub.is_late, sub.assignment_id,
               u.name as student_name, u.reg_number,
               a.title as assignment_title, a.max_marks
        FROM submission sub
        JOIN student st ON st.student_id = sub.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        WHERE a.faculty_id = %s AND sub.plagiarism_flag = 1
        ORDER BY sub.assignment_id, sub.submitted_at
    """, (user_id,))
    result = []
    for f in flagged:
        f = clean_row(dict(f))
        others = clean_rows(q("""
            SELECT sub.submission_id, sub.submission_text, sub.submitted_at,
                   u.name as student_name, u.reg_number
            FROM submission sub
            JOIN student st ON st.student_id = sub.student_id
            JOIN users u ON u.user_id = st.user_id
            WHERE sub.assignment_id = %s AND sub.submission_id != %s
            ORDER BY sub.submitted_at
        """, (f["assignment_id"], f["submission_id"])))
        f["similar_submissions"] = others; result.append(f)
    return result

# ─────────────────────────────────────────────────────────────
# ADMIN ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/api/admin/dashboard")
def admin_dashboard():
    students = int(q("SELECT COUNT(*) as n FROM users WHERE role='student'", one=True)["n"])
    faculty  = int(q("SELECT COUNT(*) as n FROM users WHERE role='faculty'", one=True)["n"])
    asgn     = int(q("SELECT COUNT(*) as n FROM assignment", one=True)["n"])
    subs     = int(q("SELECT COUNT(*) as n FROM submission", one=True)["n"])
    plag     = int(q("SELECT COUNT(*) as n FROM submission WHERE plagiarism_flag=1", one=True)["n"])
    at_risk  = int(q("SELECT COUNT(*) as n FROM at_risk WHERE resolved=0", one=True)["n"])
    att = q("SELECT COUNT(*) as total, SUM(status='present') as present FROM attendance", one=True)
    att_overall = round(flt(att["present"]) / max(flt(att["total"]), 1) * 100, 1)

    # Class health — group by subject (not class_id) to merge AL2+SAO for same subject
    class_stats = q("""
        SELECT c.subject,
               ROUND(100.0*SUM(a.status='present')/NULLIF(COUNT(a.attendance_id),0),1) as att_pct,
               COUNT(DISTINCT st.student_id) as student_count,
               COUNT(DISTINCT asn.assignment_id) as assignment_count
        FROM class c
        LEFT JOIN attendance a ON a.class_id = c.class_id
        LEFT JOIN student st ON COALESCE(st.section,'AL2') = COALESCE(c.section,'AL2')
            AND st.class_id IN (SELECT class_id FROM class WHERE subject=c.subject)
        LEFT JOIN assignment asn ON asn.class_id = c.class_id
        GROUP BY c.subject
        ORDER BY c.subject
    """)

    workload = q("""
        SELECT u.name,
               COUNT(DISTINCT cl.class_id) as classes,
               COUNT(DISTINCT a.assignment_id) as total_assignments,
               COUNT(DISTINCT CASE WHEN sub.status='submitted' THEN sub.submission_id END) as pending_grading
        FROM users u
        JOIN class cl ON cl.faculty_id = u.user_id
        LEFT JOIN assignment a ON a.faculty_id = u.user_id
        LEFT JOIN submission sub ON sub.assignment_id = a.assignment_id
        WHERE u.role = 'faculty'
        GROUP BY u.user_id
        ORDER BY u.name
    """)

    return {
        "totals": {"students": students, "faculty": faculty, "assignments": asgn, "submissions": subs,
                   "plagiarism": plag, "at_risk": at_risk, "att_overall": att_overall},
        "class_stats": clean_rows(class_stats),
        "faculty_workload": clean_rows(workload)
    }

@app.get("/api/admin/students")
def admin_students():
    rows = q("""
        SELECT
            u.user_id,
            u.name,
            u.reg_number,
            u.last_active,
            COALESCE(st.section, 'AL2') as section,
            c.subject,
            ROUND(
                100.0 * SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(a.attendance_id), 0),
            1) as att_pct,
            COUNT(DISTINCT sub.submission_id) as submissions,
            ar.reason as risk_reason
        FROM users u
        JOIN student st ON st.user_id = u.user_id
        JOIN class c ON c.class_id = st.class_id
        LEFT JOIN attendance a ON a.student_id = st.student_id
        LEFT JOIN submission sub ON sub.student_id = st.student_id
        LEFT JOIN (
            SELECT student_id, reason
            FROM at_risk
            WHERE resolved = 0
            ORDER BY flagged_at DESC
            LIMIT 1000
        ) ar ON ar.student_id = st.student_id
        WHERE u.role = 'student'
        GROUP BY u.user_id, u.name, u.reg_number, u.last_active, st.section, c.subject, ar.reason
        ORDER BY COALESCE(st.section, 'AL2'), u.reg_number
    """)
    return clean_rows(rows)

@app.get("/api/admin/at-risk")
def admin_atrisk():
    rows = q("""
        SELECT ar.risk_id, ar.reason, ar.att_pct, ar.flagged_at, u.name, u.reg_number,
               ROUND(100.0*SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
               /NULLIF(COUNT(a.attendance_id),0),1) as live_att_pct
        FROM at_risk ar
        JOIN student st ON st.student_id = ar.student_id
        JOIN users u ON u.user_id = st.user_id
        LEFT JOIN attendance a ON a.student_id = ar.student_id
        WHERE ar.resolved = 0
        GROUP BY ar.risk_id, ar.reason, ar.att_pct, ar.flagged_at, u.name, u.reg_number
        ORDER BY ar.att_pct ASC
    """)
    return clean_rows(rows)

@app.put("/api/admin/at-risk/{risk_id}/resolve")
def resolve_risk(risk_id: int):
    q("UPDATE at_risk SET resolved=1 WHERE risk_id=%s", (risk_id,), commit=True); return {"ok": True}

@app.post("/api/admin/refresh-at-risk")
def refresh_atrisk():
    q("DELETE FROM at_risk WHERE resolved=0", commit=True)
    students = q("""
        SELECT st.student_id, st.class_id,
               ROUND(100.0*SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)/NULLIF(COUNT(a.attendance_id),0),1) as att_pct,
               COUNT(DISTINCT sub.submission_id) as sub_count,
               (SELECT COUNT(*) FROM assignment asn WHERE asn.class_id = st.class_id) as total_asgn
        FROM student st
        LEFT JOIN attendance a ON a.student_id = st.student_id
        LEFT JOIN submission sub ON sub.student_id = st.student_id
        GROUP BY st.student_id, st.class_id
    """)
    flagged = 0
    for s in students:
        att = flt(s["att_pct"]); total = int(s["total_asgn"] or 1)
        sub_rate = round(int(s["sub_count"] or 0) / total * 100, 1)
        reasons = []
        if att > 0 and att < 75: reasons.append(f"Attendance {att}% < 75%")
        if sub_rate < 50 and total > 0: reasons.append(f"Submissions {sub_rate}% < 50%")
        if reasons:
            q("INSERT INTO at_risk(student_id,reason,att_pct,sub_rate) VALUES(%s,%s,%s,%s)", (s["student_id"], " · ".join(reasons), att, sub_rate), commit=True); flagged += 1
    return {"flagged": flagged}

@app.get("/api/admin/plagiarism")
def admin_plagiarism():
    rows = q("""
        SELECT sub.submission_id, sub.submission_text, sub.plagiarism_note, sub.submitted_at,
               sub.assignment_id, u.name as student_name, u.reg_number,
               a.title as assignment_title, c.subject, u2.name as faculty_name
        FROM submission sub
        JOIN student st ON st.student_id = sub.student_id
        JOIN users u ON u.user_id = st.user_id
        JOIN assignment a ON a.assignment_id = sub.assignment_id
        JOIN class c ON c.class_id = a.class_id
        JOIN users u2 ON u2.user_id = a.faculty_id
        WHERE sub.plagiarism_flag = 1
        ORDER BY sub.assignment_id, sub.submitted_at DESC
    """)
    result = []
    for f in rows:
        f = clean_row(dict(f))
        others = clean_rows(q("""
            SELECT sub.submission_id, sub.submission_text, sub.submitted_at,
                   u.name as student_name, u.reg_number
            FROM submission sub
            JOIN student st ON st.student_id = sub.student_id
            JOIN users u ON u.user_id = st.user_id
            WHERE sub.assignment_id = %s AND sub.submission_id != %s
            ORDER BY sub.submitted_at
        """, (f["assignment_id"], f["submission_id"])))
        f["similar_submissions"] = others; result.append(f)
    return result

@app.get("/api/admin/audit-log")
def audit_log(limit: int = 100):
    rows = q("SELECT al.log_id, al.action, al.details, al.ip_address, al.created_at, u.name as user_name, u.role as user_role FROM audit_log al LEFT JOIN users u ON u.user_id=al.user_id ORDER BY al.created_at DESC LIMIT %s", (limit,))
    return clean_rows(rows)

@app.get("/api/export/students")
def export_students():
    rows = q("""SELECT u.reg_number, u.name, u.email,
                       COALESCE(st.section,'AL2') as section,
                       ROUND(100.0*SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)/NULLIF(COUNT(a.attendance_id),0),1) as att_pct,
                       COUNT(DISTINCT sub.submission_id) as submissions
                FROM users u
                JOIN student st ON st.user_id=u.user_id
                LEFT JOIN attendance a ON a.student_id=st.student_id
                LEFT JOIN submission sub ON sub.student_id=st.student_id
                WHERE u.role='student'
                GROUP BY u.user_id, st.section
                ORDER BY st.section, u.reg_number""")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["reg_number","name","email","section","att_pct","submissions"])
    writer.writeheader()
    for row in rows: writer.writerow({k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=students.csv"})

@app.get("/api/export/attendance/{class_id}")
def export_attendance(class_id: int):
    rows = q("SELECT u.reg_number, u.name, a.date, a.status FROM attendance a JOIN student st ON st.student_id=a.student_id JOIN users u ON u.user_id=st.user_id WHERE a.class_id=%s ORDER BY a.date DESC, u.reg_number", (class_id,))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["reg_number","name","date","status"])
    writer.writeheader()
    for row in rows: writer.writerow({k: str(v) if isinstance(v, (Decimal, date, datetime)) else v for k, v in row.items()})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=attendance.csv"})

if __name__ == "__main__":
    import uvicorn, threading, webbrowser, time
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
