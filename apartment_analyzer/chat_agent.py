"""Interactive investment agent powered by Claude (tool use).

Terminal usage::

    export ANTHROPIC_API_KEY=...   # or `ant auth login`
    python -m apartment_analyzer.chat_agent
"""

from .tools import TOOLS, AgentSession

MODEL = "claude-opus-5-5"
MAX_TOOL_ROUNDS = 12

SYSTEM_PROMPT = """\
You are a Paris real-estate investment advisor helping one user find and \
evaluate a buy-to-let flat in Paris 8e, 16e Nord (75116) and 17e Sud \
(Ternes, Plaine Monceau). Default criteria: 200 000 - 250 000 EUR, 19 m2 \
minimum.

Use the tools for every number: search listings, analyze them, compare them, \
and update the user's mortgage and rental variables whenever they mention \
one (down payment, rate, duration, income, furnished or not, tax bracket, \
rent, works...). Never invent listings, prices or figures. If the live \
source fails, say so and offer the fictional demo data or manual entry; \
always label demo listings as fictional.

When you present a listing, cover: price vs neighbourhood (low / typical / \
high and the % gap), monthly mortgage payment, legal maximum rent \
(encadrement des loyers), costs, net yield, monthly cash-flow after tax, \
and your mark /10 with the main reasons. The interface already draws the \
price bar and the mark, so do not redraw them. Give a clear opinion: \
whether to visit, negotiate (suggest a target price) or skip. Mention \
regulatory risks (DPE F/G rental bans, rent cap) when relevant. Market \
references are approximations: remind the user to check DVF and the \
official rent cap before an offer. You are a decision aid, not a licensed \
financial advisor.

Reply in the user's language (French or English), concisely, with short \
tables or bullet points when comparing listings."""


def _text(content):
    return "\n".join(b.text for b in content
                     if getattr(b, "type", "") == "text").strip()


class InvestmentAgent:
    """Multi-turn conversation with tool calls over an AgentSession."""

    def __init__(self, client=None, session=None, model=MODEL,
                 effort="medium"):
        """Create the agent; the client defaults to anthropic.Anthropic()."""
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.session = session or AgentSession()
        self.model = model
        self.effort = effort
        self.messages = []

    def _call(self):
        return self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=self.messages,
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

    def _run_tools(self, content, on_tool):
        results = []
        for block in content:
            if getattr(block, "type", "") != "tool_use":
                continue
            if on_tool:
                on_tool(block.name, block.input)
            out, is_error = self.session.execute(block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": out, "is_error": is_error})
        return results

    def send(self, user_text, on_tool=None):
        """Send a user message, run tools until Claude answers; return text.

        ``on_tool(name, args)`` is called before each tool execution.
        """
        self.messages.append({"role": "user", "content": user_text})
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self._call()
            # Keep full content (thinking + tool_use blocks) unchanged.
            self.messages.append({"role": "assistant",
                                  "content": resp.content})
            if resp.stop_reason == "refusal":
                return "Sorry, I can't help with that request."
            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason != "tool_use":
                text = _text(resp.content)
                if resp.stop_reason == "max_tokens":
                    text += "\n\n(Answer truncated - ask me to continue.)"
                return text
            self.messages.append({"role": "user", "content":
                                  self._run_tools(resp.content, on_tool)})
        return "I stopped after too many tool calls - please rephrase."


def main():
    """Run the agent in the terminal."""
    agent = InvestmentAgent()
    print("Paris flat investment agent - type 'quit' to exit.\n"
          "Example: 'Cherche des studios dans le 17e sud, apport 30k, "
          "taux 3.1% sur 25 ans, meuble, TMI 30%'\n")
    while True:
        try:
            text = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("quit", "exit", "q"):
            break
        if text:
            reply = agent.send(text, on_tool=lambda n, a: print(
                f"  [tool] {n} {a}"))
            print(f"\nagent > {reply}\n")


if __name__ == "__main__":
    main()
