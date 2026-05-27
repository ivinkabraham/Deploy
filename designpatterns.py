# Design Patterns

import streamlit as st
from PIL import Image
from openai import OpenAI
import prompts

OPENAICLIENT = OpenAI()
    
def Spaces():
    st.markdown(""" <style> .block-container {padding-top: 2rem;} h1 {margin-top: 1rem; } </style> """, unsafe_allow_html=True)

def describe_pattern():
    pattern = st.session_state["selected_pattern"]
    models = [  "ReAct", "Planner Executor", "Multi-Agent Collaborator", "Reflection", "Tool-Using",
            "Memory Augmented", "Hierarchical", "Human-In-The-Loop", "Retrieval-Augmented", "Event Driven", 'Quit']

    if pattern != "Quit" and pattern is not None:
        if pattern == models[0]:
            desc = "The ReAct (Reason + Act) design pattern enables AI agents to iteratively reason through a problem and take actions using tools or external systems until a goal is achieved"
        elif pattern == models[1]:
            desc = "The Planner–Executor design pattern separates high-level task planning from execution, where one agent creates a step-by-step plan and another agent or system carries out the actions"
        elif pattern == models[2]:
            desc = "The Multi-Agent Collaborator design pattern enables multiple specialized agents to work together, share context, and collaboratively solve complex tasks"
        elif pattern == models[3]:
            desc = "The Reflection design pattern enables an AI agent to review, critique, and improve its own responses iteratively before producing the final output."
        elif pattern == models[4]:
            desc = "The Tool-Using design pattern allows AI agents to invoke external tools, APIs, databases, or functions to complete tasks accurately and efficiently."
        elif pattern == models[5]:
            desc = "The Memory-Augmented design pattern enables AI agents to store, retrieve, and use past interactions or contextual knowledge to improve future decisions and responses."
        elif pattern == models[6]:
            desc = "The Hierarchical design pattern organizes agents into supervisor-worker structures where higher-level agents delegate and coordinate tasks among specialized sub-agents."
        elif pattern == models[7]:
            desc = "The Human-In-The-Loop design pattern incorporates human review, approval, or intervention during critical stages of AI decision-making."
        elif pattern == models[8]:
            desc = "The Retrieval-Augmented design pattern enhances AI responses by retrieving relevant information from external knowledge sources before generating answers"
        elif pattern == models[9]:
            desc = "The Event-Driven design pattern enables AI agents to react automatically to specific events, triggers, or system changes in real time."
            
        prompt = prompts.prompt[pattern]
    else:
        desc = None
        prompt = None
    
    return(desc,prompt)
    
def mainmenu():
    st.subheader("Selected Pattern : " + st.session_state["selected_pattern"])
    
    desc,prompt = describe_pattern()
    
    c1,c2,c3 = st.columns([0.4,0.2,0.4])
    
    if desc is not None:
        # c1.write(desc)
        c1.markdown( f"<p style='font-size:24px;'>{desc}</p>", unsafe_allow_html=True)

        prompt = c3.text_area("Sample Prompt", value=prompt,height=500)
        
def main():
    Spaces()
    mainmenu()