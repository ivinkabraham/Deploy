# -*- coding: utf-8 -*-

import streamlit as st
import designpatterns
import time,os, datetime

if "selected_pattern" not in st.session_state:
    st.session_state["selected_pattern"] = None
    
st.set_page_config(layout='wide')

now = datetime.datetime.now()
today = now.strftime('%A') + ", " + now.strftime("%B %d, %Y")
st.sidebar.button(today,icon="⏳")

# Sidebar header
st.sidebar.title("Design Patterns")
st.sidebar.write("Reusable architectural approaches that define how AI agents reason, collaborate, plan, use tools, and make decisions to solve complex tasks autonomously")
st.sidebar.write("Help developers build scalable, reliable, and maintainable AI systems using structured workflows such as ReAct, Planner-Executor, Reflection, and Multi-Agent Collaboration.")


models = [  "ReAct", "Planner Executor", "Multi-Agent Collaborator", "Reflection", "Tool-Using",
            "Memory Augmented", "Hierarchical", "Human-In-The-Loop", "Retrieval-Augmented", "Event Driven", 'Quit']

parent_model = st.sidebar.selectbox("Demo", models,index=None)

st.session_state["selected_pattern"] = parent_model



if (parent_model is not None and parent_model != "Quit"):
    designpatterns.main()
elif parent_model == "Quit":
    st.header("Close Application")
    st.subheader("Are you sure you want to terminate this session ?")
    st.write("\n")
    c1, c2 = st.columns(2)
    btn_close = c1.button("✅", help="Close Application")
    if btn_close:
        with (st.spinner("Closing application ...")):
            time.sleep(2)

            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]

        st.success("Session closed. You can safely close the browser tab.")
        st.stop()
    
else:
    pass