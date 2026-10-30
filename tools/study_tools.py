from tools import Tool

# Small built-in curriculum. Each topic has a summary, key points and practice ideas.
# "keys" are lowercase fragments used to match topic names from the data.
CURRICULUM = {
    "arrays": {
        "keys": ("array",),
        "summary": "Contiguous memory with O(1) index access; inserting or deleting in the middle costs O(n).",
        "points": ["Indexing and traversal", "Insert/delete shifting cost",
                   "Two-pointer and sliding-window patterns", "Edge cases: empty array, one element, out of bounds"],
        "practice": ["Reverse an array in place", "Find the maximum subarray sum", "Rotate an array by k"],
    },
    "recursion": {
        "keys": ("recurs",),
        "summary": "A function solves a problem by calling itself on a smaller input until it hits a base case.",
        "points": ["Always write the base case first", "Trace the call stack on paper",
                   "Each call must move toward the base case", "Memoize or go iterative when calls repeat"],
        "practice": ["Factorial and Fibonacci", "Sum of digits", "Generate all permutations", "Tower of Hanoi"],
    },
    "sorting": {
        "keys": ("sort",),
        "summary": "Ordering data. Know the trade-offs between simple O(n^2) sorts and O(n log n) sorts.",
        "points": ["Bubble/insertion/selection sort are O(n^2) but simple",
                   "Merge sort: O(n log n), stable, needs extra memory",
                   "Quick sort: O(n log n) average, pivot choice matters", "Stability and in-place sorting"],
        "practice": ["Implement insertion sort and merge sort", "Sort records by two keys", "Count swaps in bubble sort"],
    },
    "searching": {
        "keys": ("search",),
        "summary": "Linear search checks every item; binary search halves a sorted range each step.",
        "points": ["Linear search is O(n)", "Binary search is O(log n) and needs sorted data",
                   "Off-by-one errors in low/high/mid", "Searching on the answer space"],
        "practice": ["Binary search (iterative and recursive)", "First and last occurrence", "Search in a rotated array"],
    },
    "linked lists": {
        "keys": ("linked", "pointer"),
        "summary": "Nodes connected by next pointers; cheap inserts and deletes, no random access.",
        "points": ["Node and next pointer", "Insert/delete at head, tail and middle",
                   "Reversing a list", "Fast/slow pointers for the middle and cycles"],
        "practice": ["Reverse a linked list", "Detect a cycle", "Merge two sorted lists"],
    },
    "stacks and queues": {
        "keys": ("stack", "queue"),
        "summary": "A stack is last-in-first-out; a queue is first-in-first-out.",
        "points": ["Push/pop and enqueue/dequeue", "Balanced brackets with a stack",
                   "BFS uses a queue, DFS uses a stack"],
        "practice": ["Valid parentheses", "Queue using two stacks", "Next greater element"],
    },
    "trees": {
        "keys": ("tree", "bst"),
        "summary": "Hierarchical data with a root and children; binary search trees keep order for fast lookup.",
        "points": ["Root, leaf, height, depth", "Inorder/preorder/postorder traversal",
                   "BST insert and search", "Level-order traversal with a queue"],
        "practice": ["Height of a binary tree", "Validate a BST", "Lowest common ancestor"],
    },
    "graphs": {
        "keys": ("graph",),
        "summary": "Nodes and edges. Choose an adjacency list or matrix, then traverse with BFS or DFS.",
        "points": ["Adjacency list vs matrix", "BFS for shortest path in unweighted graphs",
                   "DFS and connected components", "Cycle detection"],
        "practice": ["Number of islands", "Shortest path in a grid", "Detect a cycle in a directed graph"],
    },
    "dynamic programming": {
        "keys": ("dynamic", "memo"),
        "summary": "Break a problem into overlapping subproblems and store results to avoid recomputing.",
        "points": ["Overlapping subproblems and optimal substructure", "Top-down (memoization) vs bottom-up (table)",
                   "Define the state and transition first", "Classics: knapsack, LCS, coin change"],
        "practice": ["Fibonacci with memoization", "Coin change", "Longest common subsequence"],
    },
}

GENERIC = {
    "summary": "No stored notes for this topic, so a general plan is used.",
    "points": ["Review the core definitions and formulas", "Work through two solved examples"],
    "practice": ["Solve 3 problems of increasing difficulty", "Explain the solution out loud"],
}


def _as_list(topics):
    if isinstance(topics, (list, tuple)):
        items = topics
    else:
        items = str(topics or "").replace(";", ",").split(",")
    return [str(t).strip() for t in items if str(t).strip()]


def _match(topic):
    t = topic.lower()
    for entry in CURRICULUM.values():
        if any(k in t for k in entry["keys"]):
            return entry
    return None


class CurriculumLookup(Tool):
    name = "curriculum_lookup"
    description = ("Retrieve study notes (summary, key points, practice problems) for one or more topics. "
                   "Call it after weak_topics, with the weakest topics.")
    args_doc = '{"topics": "recursion,sorting"}'

    def execute(self, topics=""):
        names = _as_list(topics)
        if not names:
            return "ERROR: give at least one topic, e.g. {\"topics\": \"recursion,sorting\"}"
        blocks = []
        for name in names[:6]:
            entry = _match(name)
            found = entry is not None
            entry = entry or GENERIC
            blocks.append(
                f"TOPIC: {name}{'' if found else ' (no stored notes, generic plan)'}\n"
                f"Summary: {entry['summary']}\n"
                f"Key points: {'; '.join(entry['points'])}\n"
                f"Practice: {'; '.join(entry['practice'])}")
        return "\n\n".join(blocks)


class MakeSchedule(Tool):
    name = "make_schedule"
    description = ("Build a 3-day remedial study schedule. Pass topics ordered weakest first; "
                   "the weakest topic gets the most time. Use this instead of writing a schedule yourself.")
    args_doc = '{"topics": "recursion,sorting,arrays", "hours_per_day": 2}'

    def execute(self, topics="", hours_per_day=2):
        names = _as_list(topics)[:5]
        if not names:
            return "ERROR: give topics ordered weakest first, e.g. {\"topics\": \"recursion,sorting\"}"
        try:
            hours = float(hours_per_day)
        except (ValueError, TypeError):
            hours = 2.0
        if hours <= 0:
            hours = 2.0

        n = len(names)
        weights = [n - i for i in range(n)]  # weakest topic gets the biggest share
        total_w = sum(weights)
        days = [("Learn", "Study", "points"), ("Practice", "Practice", "practice"),
                ("Test and review", "Timed quiz", None)]

        lines = [f"3-day remedial schedule (about {hours:g}h per day, weakest topic first):"]
        for d, (title, verb, field) in enumerate(days, 1):
            lines.append(f"Day {d} - {title}")
            for name, w in zip(names, weights):
                h = max(0.5, round(hours * w / total_w * 2) / 2)
                entry = _match(name) or GENERIC
                if field:
                    task = entry[field][min(d - 1, len(entry[field]) - 1)]
                    lines.append(f"  - {name} ({h:g}h): {verb}: {task}")
                else:
                    lines.append(f"  - {name} ({h:g}h): {verb} on {name}, then redo every question you missed")
        return "\n".join(lines)