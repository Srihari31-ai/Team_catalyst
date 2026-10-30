import ast
import json
import subprocess
import sys
import tempfile

from tools import Tool

# Small problem bank. Each problem has hidden tests, a hint, and optionally banned names.
PROBLEMS = {
    "recursion": {
        "keys": ("recurs",),
        "func": "factorial",
        "statement": "Write a recursive function factorial(n) that returns n! for n >= 0 (factorial(0) is 1). Do not use loops.",
        "example": "factorial(5) -> 120",
        "tests": [{"args": [0], "expected": 1}, {"args": [1], "expected": 1},
                  {"args": [5], "expected": 120}, {"args": [7], "expected": 5040}],
        "hint": "Write the base case first (n <= 1 returns 1), then return n * factorial(n - 1).",
        "banned": (),
    },
    "sorting": {
        "keys": ("sort",),
        "func": "sort_list",
        "statement": "Write a function sort_list(nums) that returns a NEW list with the numbers in ascending order. Do not use sorted() or .sort().",
        "example": "sort_list([3, 1, 2]) -> [1, 2, 3]",
        "tests": [{"args": [[3, 1, 2]], "expected": [1, 2, 3]}, {"args": [[]], "expected": []},
                  {"args": [[5, 5, 1]], "expected": [1, 5, 5]}, {"args": [[9, -1, 4, 0]], "expected": [-1, 0, 4, 9]}],
        "hint": "Try insertion sort: take each item and insert it into the already sorted left part.",
        "banned": ("sorted", "sort"),
    },
    "arrays": {
        "keys": ("array", "list"),
        "func": "max_subarray_sum",
        "statement": "Write a function max_subarray_sum(nums) that returns the largest sum of any contiguous part of the list (the list has at least one number).",
        "example": "max_subarray_sum([1, -2, 3, 4, -1]) -> 7",
        "tests": [{"args": [[1, -2, 3, 4, -1]], "expected": 7}, {"args": [[-3, -1, -2]], "expected": -1},
                  {"args": [[5]], "expected": 5}, {"args": [[2, -1, 2, 3, -9, 4]], "expected": 6}],
        "hint": "Keep the best sum ending at each position: cur = max(x, cur + x), and track the best seen so far.",
        "banned": (),
    },
}

GENERAL = {
    "func": "add_all",
    "statement": "Write a function add_all(nums) that returns the sum of the list without using sum().",
    "example": "add_all([1, 2, 3]) -> 6",
    "tests": [{"args": [[1, 2, 3]], "expected": 6}, {"args": [[]], "expected": 0}, {"args": [[-1, 1]], "expected": 0}],
    "hint": "Start a total at 0 and add each item to it in a loop.",
    "banned": ("sum",),
}

ALLOWED_IMPORTS = ("math", "itertools", "functools", "collections")
BLOCKED_NAMES = ("open", "exec", "eval", "compile", "input", "__import__", "globals", "locals",
                 "vars", "getattr", "setattr", "delattr", "breakpoint", "exit", "quit")


def _problem_for(topic):
    t = str(topic or "").lower()
    for p in PROBLEMS.values():
        if any(k in t for k in p["keys"]):
            return p
    return GENERAL


def _scan(tree, problem):
    """Basic safety scan. Returns a reason string if the code must be rejected."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"import '{a.name}' is not allowed in the sandbox"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"import from '{node.module}' is not allowed in the sandbox"
        elif isinstance(node, ast.Name):
            if node.id in BLOCKED_NAMES:
                return f"'{node.id}' is not allowed in the sandbox"
            if node.id in problem["banned"]:
                return f"this problem does not allow '{node.id}'"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                return "dunder attributes are not allowed in the sandbox"
            if node.attr in problem["banned"]:
                return f"this problem does not allow '.{node.attr}'"
    return ""


# Runs inside a separate Python process: loads the student's code, runs each test, prints JSON.
_RUNNER = r'''
import builtins, json, sys
data = json.loads(sys.stdin.read())
sys.setrecursionlimit(1500)
_real = builtins.__import__
def _imp(name, *a, **k):
    if name.split(".")[0] not in ("math", "itertools", "functools", "collections"):
        raise ImportError("import not allowed: " + name)
    return _real(name, *a, **k)
banned = ("open", "exec", "eval", "compile", "input", "breakpoint", "exit", "quit", "__import__")
safe = {k: getattr(builtins, k) for k in dir(builtins) if k not in banned}
safe["__import__"] = _imp
ns = {"__builtins__": safe, "__name__": "student"}
out = {"load_error": None, "results": []}
try:
    exec(data["code"], ns)
except BaseException as e:
    out["load_error"] = type(e).__name__ + ": " + str(e)
else:
    fn = ns.get(data["func"])
    if not callable(fn):
        out["load_error"] = "function " + data["func"] + " is not defined"
    else:
        for t in data["tests"]:
            try:
                got = fn(*t["args"])
                out["results"].append({"args": t["args"], "expected": t["expected"], "got": got, "ok": got == t["expected"]})
            except BaseException as e:
                out["results"].append({"args": t["args"], "expected": t["expected"], "got": None, "ok": False,
                                       "error": type(e).__name__ + ": " + str(e)})
print("@@RESULT@@" + json.dumps(out, default=str))
'''


class GenerateProblem(Tool):
    name = "generate_problem"
    description = ("Generate a practice coding problem for a topic (use the student's weakest topic). "
                   "Returns the problem statement and the function name to implement.")
    args_doc = '{"topic": "recursion"}'

    def execute(self, topic=""):
        p = _problem_for(topic)
        return (f"PRACTICE PROBLEM (topic: {topic or 'general'})\n{p['statement']}\n"
                f"Function name: {p['func']}\nExample: {p['example']}\n"
                f"When the student submits code, call check_code with the same topic.")


class CheckCode(Tool):
    name = "check_code"
    description = ("Run the student's Python code in a sandbox against the tests for the topic's practice problem "
                   "and return pass/fail feedback. Pass the code exactly as the student wrote it.")
    args_doc = '{"topic": "recursion", "code": "def factorial(n): ..."}'

    def execute(self, topic="", code=""):
        p = _problem_for(topic)
        code = str(code or "")
        if not code.strip():
            return "ERROR: no code was given."
        if len(code) > 5000:
            return "ERROR: code is too long (max 5000 characters)."
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"SYNTAX ERROR on line {e.lineno}: {e.msg}. Fix the syntax and run again."
        reason = _scan(tree, p)
        if reason:
            return f"REJECTED: {reason}."

        payload = json.dumps({"code": code, "func": p["func"], "tests": p["tests"]})
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", _RUNNER], input=payload, capture_output=True,
                                  text=True, timeout=5, cwd=tempfile.gettempdir())
        except subprocess.TimeoutExpired:
            return "TIMEOUT: the code ran longer than 5 seconds (infinite loop or runaway recursion?)."
        if "@@RESULT@@" not in proc.stdout:
            return "ERROR: the sandbox failed to run the code. " + (proc.stderr or "")[-300:]
        out = json.loads(proc.stdout.rsplit("@@RESULT@@", 1)[1])
        if out["load_error"]:
            return f"Your code failed to load: {out['load_error']}\nHint: {p['hint']}"

        lines, passed, recursion_err = [], 0, False
        for r in out["results"]:
            call = f"{p['func']}({', '.join(repr(a) for a in r['args'])})"
            if r["ok"]:
                passed += 1
                lines.append(f"PASS {call} -> {r['got']!r}")
            elif r.get("error"):
                recursion_err = recursion_err or r["error"].startswith("RecursionError")
                lines.append(f"FAIL {call} raised {r['error']}")
            else:
                lines.append(f"FAIL {call} returned {r['got']!r}, expected {r['expected']!r}")
        head = f"Passed {passed}/{len(out['results'])} tests."
        if passed == len(out["results"]):
            tail = "All tests passed. Next: explain the time complexity, or try a harder problem."
        else:
            tail = "Hint: " + p["hint"]
            if recursion_err:
                tail += " A RecursionError usually means the base case is missing or never reached."
        return head + "\n" + "\n".join(lines) + "\n" + tail