"""
app_web.py
Streamlit web interface for CampusVoice.
Deployed on Google Cloud Run.
"""

import streamlit as st
from agent_mcp import ask

st.set_page_config(
    page_title="CampusVoice",
    page_icon="🎓",
    layout="centered",
)

st.title("🎓 CampusVoice")
st.caption("AI-powered student sentiment agent — powered by Gemini + Elasticsearch")

st.markdown("""
Ask anything about student experiences at **UTK** or **Vanderbilt University**,
based on thousands of real Rate My Professors reviews.
""")

# School filter
school = st.radio(
    "Filter by school:",
    ["Both schools", "UTK only", "Vanderbilt only"],
    horizontal=True,
)

school_map = {
    "Both schools": None,
    "UTK only": "utk",
    "Vanderbilt only": "vanderbilt",
}

# Example questions
st.markdown("**Try asking:**")
examples = [
    "What are students at UTK complaining about most?",
    "How does Vanderbilt compare to UTK for engineering students?",
    "What do students say about intro CS courses at Vanderbilt?",
    "Which professors at UTK are most praised by students?",
    "What are the biggest challenges for students at Vanderbilt?",
]
cols = st.columns(2)
for i, ex in enumerate(examples):
    if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
        st.session_state["question"] = ex

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input
question = st.chat_input("Ask a question about student life...")

# Handle example button clicks
if "question" in st.session_state and st.session_state["question"]:
    question = st.session_state.pop("question")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    school_filter = school_map[school]
    full_question = question
    if school_filter:
        full_question = f"[Filter to {school_filter} only] {question}"

    with st.chat_message("assistant"):
        with st.spinner("Searching student reviews..."):
            try:
                answer = ask(full_question)
            except Exception as e:
                answer = f"Error: {e}"
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
