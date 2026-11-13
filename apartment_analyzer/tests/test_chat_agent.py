"""Tests for the agent tools and the tool-use loop (fake Claude client)."""

import json
from types import SimpleNamespace as NS

from apartment_analyzer.chat_agent import InvestmentAgent
from apartment_analyzer.tools import TOOLS, AgentSession


def test_tool_schemas_have_handlers():
    """Check every declared tool has a session method."""
    session = AgentSession()
    for tool in TOOLS:
        assert callable(getattr(session, tool["name"]))


def test_search_analyze_compare_demo():
    """Check the main tool chain on demo data."""
    s = AgentSession()
    found = json.loads(s.execute("search_listings", {
        "source": "demo", "zones": ["17e Sud"]})[0])
    assert found["found"] >= 2
    assert all(r["zone"] == "17e Sud" for r in found["listings"])
    lid = found["listings"][0]["id"]
    out, err = s.execute("analyze_listing", {"listing_id": lid})
    detail = json.loads(out)
    assert not err and 0 <= detail["score"] <= 10
    assert detail["price_label"] in ("low", "typical", "high")
    assert len(s.analyses) == 1
    ids = [r["id"] for r in found["listings"][:2]]
    comp = json.loads(s.execute("compare_listings",
                                {"listing_ids": ids})[0])
    assert len(comp["comparison"]) == 2


def test_settings_change_results():
    """Check a bigger down payment lowers the monthly payment."""
    s = AgentSession()
    args = {"price": 230000, "surface": 21, "zone": "8e",
            "quartier": "Europe", "dpe": "D"}
    before = json.loads(s.execute("analyze_custom_listing", args)[0])
    s.execute("update_settings", {"loan": {"down_payment": 80000}})
    after = json.loads(s.execute("analyze_custom_listing", args)[0])
    assert after["mortgage"]["monthly_payment"] < \
        before["mortgage"]["monthly_payment"]


def test_tool_errors_are_reported():
    """Check bad input returns is_error instead of raising."""
    s = AgentSession()
    assert s.execute("analyze_listing", {"listing_id": "L99"})[1]
    assert s.execute("update_settings", {"loan": {"foo": 1}})[1]
    assert s.execute("nope", {})[1]


class FakeClient:
    """Return scripted responses and record requests."""

    def __init__(self, responses):
        """Store the scripted responses."""
        self.responses = list(responses)
        self.calls = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_agent_loop_runs_tools():
    """Check the loop executes tools and returns the final text."""
    tool_use = NS(type="tool_use", id="t1", name="search_listings",
                  input={"source": "demo"})
    client = FakeClient([
        NS(stop_reason="tool_use", content=[tool_use]),
        NS(stop_reason="end_turn",
           content=[NS(type="text", text="Here are the best flats.")]),
    ])
    agent = InvestmentAgent(client=client)
    seen = []
    reply = agent.send("find flats", on_tool=lambda n, a: seen.append(n))
    assert reply == "Here are the best flats."
    assert seen == ["search_listings"]
    result = agent.messages[2]["content"][0]
    assert result["tool_use_id"] == "t1" and not result["is_error"]
    assert client.calls[0]["model"] == "claude-opus-5-5"
    assert len(agent.messages) == 4
