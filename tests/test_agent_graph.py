"""Integration tests for the EcomScout-AI LangGraph workflow."""

from ecomscout_ai.graph.agent_graph import build_agent_graph


def make_initial_state() -> dict:
    """Build the initial state used by the workflow tests."""
    return {
        "user_query": "Analyze bluetooth earphone market",
        "task_plan": [],
        "products": [],
        "clean_data": [],
        "analysis_result": {},
        "strategy": "",
        "report": "",
    }


def test_agent_graph_runs_end_to_end() -> None:
    """The compiled graph should produce every expected output field."""
    graph = build_agent_graph()

    result = graph.invoke(make_initial_state())

    assert result["task_plan"]
    assert result["products"]
    assert result["clean_data"]
    assert result["analysis_result"]
    assert result["strategy"]
    assert result["report"]


def test_final_report_contains_required_sections() -> None:
    """The generated report should include the required Markdown sections."""
    graph = build_agent_graph()

    result = graph.invoke(make_initial_state())
    report = result["report"]

    assert report.startswith("# ")
    assert "## 用户需求" in report
    assert "## 执行计划" in report
    assert "## 商品样本" in report
    assert "## 市场分析" in report
    assert "## 策略建议" in report
