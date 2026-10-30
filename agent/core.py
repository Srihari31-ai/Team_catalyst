"""The ReAct loop: Thought -> Action -> Observation -> Decision. Returns answer + trace."""
import json
import re

import config
from agent.prompt_builder import build_system_prompt


def parse_json(text):
    """Pull the first JSON object out of a model reply (handles ```json fences and chatter)."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += text[i] == "{"
            depth -= text[i] == "}"
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
        start = text.find("{", start + 1)
    return None


class AgentExecutor:
    def __init__(self, llm, tools, role=None, max_iterations=None):
        self.llm, self.tools = llm, tools
        self.max_iterations = max_iterations or config.MAX_ITERATIONS
        self.system = build_system_prompt(tools, **({"role": role} if role else {}))

    def run(self, query, verbose=False):
        messages = [{"role": "user", "content": query}]
        trace, seen, nudges, sched_nudges, sol_nudges = [], {}, 0, 0, 0
        for step in range(self.max_iterations):
            force_final = any(n > config.MAX_SAME_TOOL_CALLS for n in seen.values())
            if force_final:
                messages.append({"role": "user", "content": "You repeated a tool. Give your final_answer now."})
            reply = self.llm.generate(self.system, messages)
            data = parse_json(reply)
            if data is None or not (data.get("action") or "final_answer" in data):
                messages += [{"role": "assistant", "content": reply or "(empty)"},
                             {"role": "user", "content": "Invalid format. Reply with ONE JSON object with an \"action\" or a \"final_answer\"."}]
                continue
            thought = str(data.get("thought", ""))
            grounded = any(t["tool"] != "list_files" and not t["observation"].startswith("ERROR") for t in trace)
            if "final_answer" in data and not grounded:
                nudges += 1
                if nudges <= 2:
                    messages += [{"role": "assistant", "content": json.dumps(data)},
                                 {"role": "user", "content": "Rejected: you have not read any data yet. Call read_file on a data file (list_files shows the names) or weak_topics now. Valid tool names: " + ", ".join(self.tools)}]
                    continue
                if nudges == 3 and self._auto_ground(trace, messages, verbose):
                    continue
                return "I could not read any data with the tools, so I cannot give a reliable answer.", trace
            called = {t["tool"] for t in trace}
            wants_plan = any(w in query.lower() for w in ("plan", "schedule"))
            if ("final_answer" in data and wants_plan and "make_schedule" in self.tools
                    and ("make_schedule" not in called or "{{" in str(data["final_answer"]))):
                sched_nudges += 1
                if sched_nudges <= 2:
                    messages += [{"role": "assistant", "content": json.dumps(data)},
                                 {"role": "user", "content": "Rejected: for a plan you must call curriculum_lookup with ALL weak topics, then make_schedule with the topics ordered weakest first, and copy the real text from their observations. No template placeholders."}]
                    continue
                auto = self._auto_plan(trace, verbose)
                if auto:
                    return auto, trace
            if ("final_answer" in data and "check_code" in called and sol_nudges < 1
                    and "def " in str(data["final_answer"])):
                sol_nudges += 1
                messages += [{"role": "assistant", "content": json.dumps(data)},
                             {"role": "user", "content": "Rejected: do not include a full code solution. Explain the cause of the failure and give hints only, so the student fixes it themselves."}]
                continue
            if "final_answer" in data:
                if verbose:
                    print(f"[Thought] {thought}\n[Final] {data['final_answer']}")
                return str(data["final_answer"]), trace
            name, args = data.get("action"), data.get("args") or {}
            key = (name, json.dumps(args, sort_keys=True, default=str))
            seen[key] = seen.get(key, 0) + 1
            observation = self._call_tool(name, args)
            trace.append({"thought": thought, "tool": name, "args": args, "observation": observation[:2000]})
            if verbose:
                print(f"[Thought] {thought}\n[Action] {name}({args})\n[Observation] {observation[:300]}")
            messages += [{"role": "assistant", "content": json.dumps(data)},
                         {"role": "user", "content": f"OBSERVATION: {observation}"}]
        return self._wrap_up(messages), trace

    def _auto_ground(self, trace, messages, verbose=False):
        """Guardrail recovery: read the first data file ourselves so the answer is grounded in real data."""
        listing = self._call_tool("list_files", {})
        names = [f.strip() for f in re.split(r"[\n,]", listing)
                 if f.strip().lower().endswith((".csv", ".json", ".txt", ".md"))]
        if not names:
            return False
        args = {"filename": names[0]}
        observation = self._call_tool("read_file", args)
        if observation.startswith("ERROR"):
            return False
        trace.append({"thought": "guardrail: read the data file before answering", "tool": "read_file",
                      "args": args, "observation": observation[:2000]})
        if verbose:
            print(f"[Guardrail] model skipped reading data, so reading {names[0]} automatically")
        messages += [{"role": "assistant", "content": json.dumps({"thought": "read the data", "action": "read_file", "args": args})},
                     {"role": "user", "content": f"OBSERVATION: {observation}\nNow answer using only this data."}]
        return True

    def _auto_plan(self, trace, verbose=False):
        """Guardrail fallback: build the plan from real tool outputs when the model skips the tools."""
        weak = next((t["observation"] for t in trace
                     if t["tool"] == "weak_topics" and not t["observation"].startswith("ERROR")), None)
        if weak is None:
            return None
        topics = [t.strip() for t in re.findall(r"^\d+\.\s*([^:\n]+):", weak, re.M)]
        if not topics:
            return None
        joined = ",".join(topics)
        notes = self._call_tool("curriculum_lookup", {"topics": joined})
        schedule = self._call_tool("make_schedule", {"topics": joined, "hours_per_day": 2})
        trace.append({"thought": "guardrail: model skipped curriculum_lookup, running it", "tool": "curriculum_lookup",
                      "args": {"topics": joined}, "observation": notes[:2000]})
        trace.append({"thought": "guardrail: model skipped make_schedule, running it", "tool": "make_schedule",
                      "args": {"topics": joined, "hours_per_day": 2}, "observation": schedule[:2000]})
        if verbose:
            print("[Guardrail] model skipped curriculum_lookup/make_schedule, running them automatically")
        return f"{weak}\n\nSTUDY NOTES\n{notes}\n\n{schedule}"

    def _call_tool(self, name, args):
        name = {"open_file": "read_file", "read_csv": "read_file"}.get(name, name)
        if "placeholder" in json.dumps(args, default=str).lower():
            return "ERROR: placeholder value. Use real values taken from earlier observations."
        tool = self.tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool '{name}'. Available: {', '.join(self.tools)}"
        try:
            return str(tool.execute(**args))
        except Exception as e:  # tool failures become observations, so the agent can recover
            return f"ERROR: {type(e).__name__}: {e}"

    def _wrap_up(self, messages):
        """Out of steps: ask once for a final answer from what we have."""
        messages.append({"role": "user", "content": "Step limit reached. Reply with a final_answer JSON now."})
        data = parse_json(self.llm.generate(self.system, messages)) or {}
        return str(data.get("final_answer") or "I could not finish within the step limit.")