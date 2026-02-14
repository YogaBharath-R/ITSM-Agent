import streamlit as st
import os
from dotenv import load_dotenv
from phi.agent import Agent, RunResponse
from phi.run.response import RunEvent
from agents import *
from Constants import *

# ---------------------------------
# Load ENV
# ---------------------------------
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY not set")
    st.stop()

# ---------------------------------
# Agent Initialization (Cached)
# ---------------------------------
@st.cache_resource
def get_agent() -> Agent:
    return Agent(
        model=Groq_Clint,
        system_prompt=ITSM_AGENT_SYSTEM_PROMPT,
        team=[
            Task_Analyzer,
            Incident_Analyzer,
            Ticket_Creation,
            Root_Cause_Analysis,
            resolution_discovery
        ],
        instructions=[
            "Analyze user input.",
            "Delegate to ONLY ONE appropriate team member.",
            "Do not call multiple team members.",
            "Return final answer after delegation."
        ],
        markdown=True,
        show_tool_calls=True,
        debug_mode=True
    )

Sister = get_agent()

# ---------------------------------
# Helper Functions
# ---------------------------------
def get_agent_name_from_function(function_name: str) -> str:
    agent_map = {
        "transfer_task_to_task_analyzer": "📊 Task Analyzer",
        "transfer_task_to_incident_analyzer": "🔍 Incident Analyzer",
        "transfer_task_to_ticket_creation": "🎫 Ticket Creation",
        "transfer_task_to_root_cause_analysis": "🔬 Root Cause Analysis",
        "transfer_task_to_resolution_discovery": "💡 Resolution Discovery"
    }
    return agent_map.get(function_name, "🤖 Agent")

# ---------------------------------
# UI Setup
# ---------------------------------
st.set_page_config(page_title="ITSM Agent", layout="wide")
st.title("🎫 ITSM Ticket Orchestrator")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 📧 Email Interface")
    
    # Email-style input fields
    email_from = st.text_input(
        "From:",
        placeholder="ntid@itsm.com"
    )
    email_to = st.text_input(
        "To:",
        value="support@itsm.com",
        placeholder="support@itsm.com"
    )
    
    email_subject = st.text_input(
        "Subject:",
        placeholder="Brief description of the incident..."
    )
    
    email_body = st.text_area(
        "Body:",
        height=200,
        placeholder="Describe the incident in detail...\n\nInclude:\n- What happened\n- When it occurred\n- Error messages or logs\n- Impact on users/systems"
    )
    
    # Combine email fields into user_input for processing
    user_input = f"""reported by {email_from} Subject: {email_subject}

{email_body}"""

with col2:
    st.markdown("### 🤖 Agent Team")
    st.markdown("""
    1. 🔍 Incident Analyzer  
    2. 🎫 Ticket Creation  
    3. 🔬 Root Cause Analysis  
    4. 💡 Resolution Discovery  
    """)

# ---------------------------------
# RUN BUTTON
# ---------------------------------
if st.button("🚀 Run Agent", type="primary", use_container_width=True):

    if not email_subject.strip() and not email_body.strip():
        st.warning("⚠️ Please enter incident details")
        st.stop()

    status_container = st.container()
    steps_container = st.container()
    final_container = st.container()

    with status_container:
        progress_bar = st.progress(0)
        status_text = st.empty()

    with steps_container:
        st.markdown("## 📋 Execution Steps")
        steps_placeholder = st.empty()

    try:
        execution_steps = []
        step_count = 0
        current_agent = None
        full_content = ""
        run_id = None

        response_stream = Sister.run(
            user_input,
            stream=True,
            stream_intermediate_steps=True
        )

        for response_chunk in response_stream:

            if not isinstance(response_chunk, RunResponse):
                continue

            event = response_chunk.event
            content = response_chunk.content
            run_id = response_chunk.run_id
            

            # ---------------------------------
            # RUN STARTED
            # ---------------------------------
            if event == RunEvent.run_started.value:
                step_count += 1
                progress_bar.progress(0.1)
                status_text.info("🚀 Orchestrator analyzing request")

                execution_steps.append({
                    "icon": "🚀",
                    "title": "Orchestrator Started",
                    "content": "Analyzing incident and determining workflow",
                    "type": "info"
                })

            # ---------------------------------
            # TOOL CALL STARTED (Delegation Only)
            # ---------------------------------
            elif event == RunEvent.tool_call_started.value:

                if not response_chunk.tools:
                    continue

                tool_info = response_chunk.tools[-1]
                function_name = tool_info.get("function_name")

                # Skip internal/system tools
                if not function_name:
                    continue

                if not function_name.startswith("transfer_task_to_"):
                    continue

                current_agent = get_agent_name_from_function(function_name)

                step_count += 1
                progress_bar.progress(min(step_count / 10, 0.9))
                status_text.info(f"🔄 Delegating to {current_agent}")

                execution_steps.append({
                    "icon": "🔄",
                    "title": f"Delegating to {current_agent}",
                    "content": "Task transferred successfully",
                    "type": "delegation"
                })

            # ---------------------------------
            # TOOL CALL COMPLETED
            # ---------------------------------
            elif event == RunEvent.tool_call_completed.value:

                if not content:
                    continue

                content_str = str(content)

                # Detect agent from response (bulletproof method)
                detected_agent = None
                if "transfer_task_to_" in content_str:
                    for key in [
                        "task_analyzer",
                        "incident_analyzer",
                        "ticket_creation",
                        "root_cause_analysis",
                        "resolution_discovery"
                    ]:
                        if key in content_str:
                            detected_agent = get_agent_name_from_function(
                                f"transfer_task_to_{key}"
                            )
                            break

                agent_name = detected_agent or current_agent or "🤖 Agent"

                step_count += 1
                progress_bar.progress(min(step_count / 10, 0.95))

                execution_steps.append({
                    "icon": "✅",
                    "title": f"{agent_name} - Completed",
                    "content": content_str,
                    "type": "success"
                })

                current_agent = None

            # ---------------------------------
            # FINAL RESPONSE CONTENT
            # ---------------------------------
            elif event == RunEvent.run_response.value:
                if isinstance(content, str):
                    full_content += content

            # ---------------------------------
            # RUN COMPLETED
            # ---------------------------------
            elif event == RunEvent.run_completed.value:
                progress_bar.progress(1.0)
                status_text.success("✨ Workflow completed successfully")

                execution_steps.append({
                    "icon": "✨",
                    "title": "Orchestration Completed",
                    "content": "All agents finished successfully",
                    "type": "success"
                })

            # ---------------------------------
            # Render Steps Live
            # ---------------------------------
            with steps_placeholder.container():
                for idx, step in enumerate(execution_steps, 1):
                    expanded = step["type"] in ["delegation", "success"]

                    with st.expander(
                        f"{step['icon']} Step {idx}: {step['title']}",
                        expanded=expanded
                    ):
                        if step["type"] == "info":
                            st.info(step["content"])
                        elif step["type"] == "delegation":
                            st.warning(step["content"])
                        elif step["type"] == "success":
                            st.success(step["content"])

        status_container.empty()

        # ---------------------------------
        # FINAL REPORT
        # ---------------------------------
        with final_container:
            st.markdown("---")
            st.markdown("## ✅ Final ITSM Report")

            if full_content:
                st.markdown(full_content)

                st.download_button(
                    label="📥 Download Report",
                    data=full_content,
                    file_name=f"itsm_report_{run_id}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            else:
                st.info("No final content generated")

    except Exception as e:
        status_container.empty()
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)

# ---------------------------------
# Sidebar
# ---------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown(f"""
    - Model: Groq  
    - Debug Mode: Enabled  
    - Stream Steps: Enabled  
    - Team Size: {len(Sister.team)}  
    """)