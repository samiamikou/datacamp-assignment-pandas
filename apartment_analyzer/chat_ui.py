"""Streamlit chat panel for the interactive agent."""

from dataclasses import replace

import streamlit as st

from .chat_agent import InvestmentAgent

EXAMPLES = [
    "Trouve-moi les meilleurs studios dans le 17e sud et le 8e",
    "Apport 40 000 EUR, taux 3,1 % sur 20 ans, revenus 4 500 EUR/mois",
    "Compare les 3 meilleurs et dis-moi lequel visiter",
]


def _new_agent(loan, rental):
    agent = InvestmentAgent()
    agent.session.loan = replace(loan, price=0)
    agent.session.rental = rental
    return agent


def _render_history(render_analysis):
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            for tool in msg.get("tools", []):
                st.caption(f"tool: {tool}")
            st.markdown(msg["text"])
            for a in msg.get("analyses", []):
                with st.container(border=True):
                    render_analysis(a)


def _ask(agent, prompt):
    tools = []
    before = len(agent.session.analyses)
    import anthropic
    try:
        with st.spinner("The agent is working..."):
            text = agent.send(prompt, on_tool=lambda n, a: tools.append(
                f"{n}({', '.join(f'{k}={v}' for k, v in a.items())})"))
    except anthropic.AuthenticationError:
        text = ("No valid Anthropic credentials. Set ANTHROPIC_API_KEY "
                "(or run `ant auth login`) and restart the app.")
    except anthropic.APIError as exc:
        text = f"Claude API error: {exc}"
    st.session_state.chat.append({
        "role": "assistant", "text": text, "tools": tools,
        "analyses": agent.session.analyses[before:]})


def render_chat(loan, rental, render_analysis):
    """Render the chat tab; sidebar settings seed the agent."""
    if "agent" not in st.session_state:
        try:
            st.session_state.agent = _new_agent(loan, rental)
        except Exception as exc:  # missing SDK or credentials
            st.error(f"Cannot start the agent: {exc}")
            return
        st.session_state.chat = []
    agent = st.session_state.agent
    cols = st.columns([1, 1, 3])
    if cols[0].button("Use sidebar settings"):
        agent.session.loan = replace(loan, price=0)
        agent.session.rental = rental
        st.toast("Agent settings updated from the sidebar.")
    if cols[1].button("New conversation"):
        del st.session_state["agent"]
        st.rerun()
    with st.expander("Agent's current mortgage / rental settings"):
        st.json(agent.session.settings())
    if not st.session_state.chat:
        st.info("Ask me anything, e.g.:\n\n" + "\n\n".join(
            f"- {e}" for e in EXAMPLES))
    _render_history(render_analysis)
    prompt = st.chat_input("Ask the agent...")
    if prompt:
        st.session_state.chat.append({"role": "user", "text": prompt})
        _ask(agent, prompt)
        st.rerun()
