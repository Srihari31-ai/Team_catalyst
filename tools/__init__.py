"""Tool registry. To add a tool: subclass Tool in a new file, then add it to build_tools()."""


class Tool:
    name = "tool"
    description = ""
    args_doc = "{}"

    def execute(self, **kwargs):
        raise NotImplementedError


def build_tools():
    from tools.calculator import Calculator
    from tools.data_query import ListFiles, ReadFile, SqlQuery
    from tools.web_search import WebSearch
    from tools.weak_topics import WeakTopics
    from tools.study_tools import CurriculumLookup, MakeSchedule
    from tools.code_sandbox import GenerateProblem, CheckCode
    tools = [ListFiles(), ReadFile(), SqlQuery(), Calculator(), WebSearch(), WeakTopics(), CurriculumLookup(), MakeSchedule(), GenerateProblem(), CheckCode()]
    return {t.name: t for t in tools}