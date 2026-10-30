# Team Catalyst: Adaptive Syllabus Coach & Debug Tutor

AgentX Challenge 2026 (SRMIST Tiruchirappalli), Education & Pedagogy track.

A ReAct agent (Thought -> Action -> Observation -> Decision) in plain Python that finds a student's weak topics from test scores, retrieves matching study notes, builds a 3-day remedial schedule, and gives practice problems with sandboxed code checking and hint-based feedback.

Built on the AgentX starter kit. Free-tier friendly: Gemini or Groq as the model, no credit card needed.

## What it does

1. **Reads weak topics** from `scores.csv` (topic/score tables and G1-G3 style grade columns).
2. **Retrieves curriculum segments** (summary, key points, practice ideas) for those topics.
3. **Builds a 3-day remedial schedule** (Learn, Practice, Test and review) with hours split by weakness.
4. **Generates a practice problem**, runs the student's code in a sandbox, and explains failures with hints (no full solutions).

## Tools

| Tool | What it does |
|---|---|
| `weak_topics` | Ranks a student's topics weakest first; detects columns and score scale automatically |
| `curriculum_lookup` | Returns notes and practice ideas for one or more topics |
| `make_schedule` | Builds the 3-day schedule; the weakest topic gets the most time |
| `generate_problem` | Picks a practice problem for a topic |
| `check_code` | Runs student code against hidden tests in a separate process (5 s timeout, blocked file/system access, import allow-list) and returns pass/fail feedback |
| `list_files`, `read_file`, `sql_query`, `calculator`, `web_search` | Starter data and utility tools |

## Guardrails and error recovery (agent/core.py)

- **Grounding guard:** a final answer is rejected until the agent has read real data with a tool (listing files does not count).
- **Auto-recovery:** if the model still skips reading data, the loop reads the data file itself and continues.
- **Plan enforcement:** a study-plan answer must come from `curriculum_lookup` and `make_schedule`; if the model skips them or returns template placeholders, the loop runs them and builds the plan from their real output.
- **Tutor rule:** answers that include a full code solution after `check_code` are rejected, so the student gets hints only.
- **Tool errors become observations:** unknown tool names, bad arguments and tool failures are returned to the model so it can recover. Common wrong names (`open_file`) are mapped to the right tool.
- **Loop cap:** `MAX_ITERATIONS` in `config/__init__.py`, plus a repeat-call guard.

## Run it

```
git clone https://github.com/Srihari31-ai/Team_catalyst.git
cd Team_catalyst
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env
```

Add `GEMINI_API_KEY` and/or `GROQ_API_KEY` to `.env`. Keys come only from environment variables; never commit `.env`.

```
python main.py --dry-run "test"                                   # works with no key
python main.py "Which topics is student S1 weak in?"
python main.py "Make a study plan for student S1"
python main.py "Check this code for recursion: def factorial(n): return n * factorial(n - 1)"
python main.py --json "Which topics is student S1 weak in?"      # judges' contract
```

## Judging contract

- `python main.py --json "<query>"` prints ONE JSON line: `{"answer": "...", "trace": [{"thought","tool","args","observation"}]}`. Logs go to stderr.
- Data is read from `AGENTX_DATA_DIR` (default `./data`); nothing is hardcoded.
- If data is empty or a tool fails, the agent still returns an answer.

## Data

`data/scores.csv` with columns `student,topic,score`. The tools also accept UCI Student Performance style files (`G1,G2,G3`).

## Tests

```
python -m unittest discover tests
```

## Limits

The code sandbox is a basic subprocess sandbox (timeout, import allow-list, blocked file and system access), not a hardened security boundary. The built-in curriculum covers common DSA topics; unknown topics get a generic plan.