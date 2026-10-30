import csv
import os

from tools import Tool

_TOPIC_COLS = ("topic", "subject", "skill", "concept", "chapter", "module")
_SCORE_COLS = ("score", "marks", "mark", "grade", "percent", "result")
_STUDENT_COLS = ("student", "student_id", "studentid", "id", "name", "roll")


def _find(cols, names):
    lower = {c.lower().strip(): c for c in cols}
    for n in names:
        if n in lower:
            return lower[n]
    return None


def _num(v):
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None


class WeakTopics(Tool):
    name = "weak_topics"
    description = ("Rank a student's topics from weakest to strongest using the scores file. "
                   "Works with topic/score tables and G1-G3 style grade columns. "
                   "Use this FIRST for any weak-topic or study-plan question.")
    args_doc = '{"student": "S1", "filename": "scores.csv", "threshold": 50, "top_n": 5}'

    def execute(self, student=None, filename="scores.csv", threshold=50, top_n=5):
        try:
            threshold = float(threshold)
            return self._run(student, filename, threshold if threshold > 0 else 50, int(top_n))
        except Exception as e:
            return f"ERROR: weak_topics failed: {e}"

    def _run(self, student, filename, threshold, top_n):
        path = os.path.join(os.environ.get("AGENTX_DATA_DIR", "./data"), filename)
        if not os.path.exists(path):
            return f"ERROR: {filename} not found. Call list_files first."
        with open(path, newline="", encoding="utf-8-sig") as f:
            text = f.read()
        if not text.strip():
            return "ERROR: file is empty."
        lines_in = text.splitlines()
        delim = ";" if lines_in[0].count(";") > lines_in[0].count(",") else ","
        rows = list(csv.DictReader(lines_in, delimiter=delim))
        if not rows:
            return "ERROR: file has no data rows."
        cols = list(rows[0].keys())

        # pick the rows for this student (if the file has a student column)
        student_col = _find(cols, _STUDENT_COLS)
        note = ""
        if student is not None and student_col:
            sid = str(student).strip().lower()
            picked = [r for r in rows if str(r[student_col]).strip().lower() == sid]
            if not picked:
                ids = sorted({str(r[student_col]) for r in rows})[:10]
                return f"ERROR: student '{student}' not found. Some ids: {ids}"
        else:
            picked = rows
            if student is not None:
                note = " (no student id column, so all rows were used)"

        # long format: one row per student+topic; wide format: one column per topic/grade
        topic_col = _find(cols, _TOPIC_COLS)
        score_col = _find(cols, _SCORE_COLS)
        data = {}
        if topic_col and score_col:
            for r in picked:
                v = _num(r[score_col])
                if v is not None:
                    data.setdefault(str(r[topic_col]).strip(), []).append(v)
            all_vals = [_num(r[score_col]) for r in rows]
        else:
            wide = [c for c in cols if c.lower().startswith("g") and c[1:].isdigit()]
            if not wide:
                wide = [c for c in cols if c != student_col
                        and sum(_num(r[c]) is not None for r in rows) > len(rows) / 2]
            for c in wide:
                vals = [_num(r[c]) for r in picked if _num(r[c]) is not None]
                if vals:
                    data[c] = vals
            all_vals = [_num(r[c]) for r in rows for c in wide]

        all_vals = [v for v in all_vals if v is not None]
        if not data or not all_vals:
            return "ERROR: no numeric scores found. Use read_file to inspect the columns."

        top = max(all_vals)
        scale = 100 if top > 20 else (20 if top > 10 else 10)
        ranked = sorted((sum(v) / len(v), t) for t, v in data.items())

        out = []
        for i, (avg, t) in enumerate(ranked[:top_n], 1):
            pct = avg / scale * 100
            flag = "WEAK" if pct < threshold else "ok"
            out.append(f"{i}. {t}: avg {avg:.1f}/{scale} ({pct:.0f}%) {flag}")
        who = f"student {student}" if student is not None and student_col else "all rows"
        return (f"Topics for {who}{note}, weakest first (weak = below {threshold:.0f}%):\n"
                + "\n".join(out))