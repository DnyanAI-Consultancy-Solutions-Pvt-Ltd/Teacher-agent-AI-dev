import os
import streamlit as st
import base64
from datetime import datetime
from teacher import agentic_analyze_request, run_pure_autogen_pipeline
from pdf_compiler import compile_exam_paper_to_pdf

st.set_page_config(
    page_title="AI Multi-Agent Academic Portal",
    page_icon="🎓",
    layout="wide"
)

st.markdown("""
    <style>
    .main { background-color: #f8fafc; }
    .stButton>button {
        background-color: #1e293b !important;
        color: white !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 0.5rem 2rem !important;
    }
    .stButton>button:hover { background-color: #334155 !important; }
    h1 { color: #0f172a; font-family: 'Helvetica Neue', sans-serif; }
    </style>
""", unsafe_allow_html=True)

st.title("🎓 AI Multi-Agent Academic Portal")
st.caption("Enterprise Domain System for Syllabuses, Study Notes, and Rigor-Balanced Question Papers")

if "final_output_text" not in st.session_state:
    st.session_state.final_output_text = ""
if "compiled_pdf_path" not in st.session_state:
    st.session_state.compiled_pdf_path = None

st.sidebar.header("🛠️ Configuration Controls")

user_query_input = st.sidebar.text_area(
    "Enter Your Academic Request:",
    placeholder="e.g., Generate a science exam paper for 9th class, or Create history notes for 11th class",
    help="Type your instruction naturally. The Prominent Orchestrator will analyze the intent automatically."
)

export_pdf_toggle = st.sidebar.toggle("Compile Downloadable PDF Asset", value=True)

language_medium = "English"
academic_stream = "General Track"

if user_query_input:
    inferred_ctx = agentic_analyze_request(user_query_input)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Detected Context Parameters")
    st.sidebar.info(f"**Format Variety:** {inferred_ctx['output_variety'].replace('_', ' ').title()}\n\n"
                    f"**Grade Level:** Standard {inferred_ctx['class_level']}\n\n"
                    f"**Board:** {inferred_ctx['board']}")

    if inferred_ctx["is_higher_secondary"]:
        st.sidebar.warning("⚡ Higher Secondary Grade Detected: Stream Selection Required")
        stream_select = st.sidebar.selectbox(
            "Select Academic Stream Layer:",
            ["Science Track (PCM/PCB)", "Commerce Track", "Arts & Humanities"]
        )
        if "Commerce" in stream_select: academic_stream = "Commerce"
        elif "Arts" in stream_select: academic_stream = "Arts"
        else: academic_stream = "Science"
        
        inferred_ctx["stream"] = academic_stream
    else:
        st.sidebar.success("🏫 Secondary Grade Detected: Medium Selection Required")
        medium_select = st.sidebar.selectbox(
            "Select Layout Instruction Medium:",
            ["English Medium Instruction Layer", "Marathi Medium Instruction Layer (मराठी)"]
        )
        if "Marathi" in medium_select:
            language_medium = "Marathi"
            inferred_ctx["board"] = "Maharashtra State Board"
        else:
            language_medium = "English"
            
        inferred_ctx["language"] = language_medium
else:
    inferred_ctx = None

if st.sidebar.button("Launch Agent Orchestration"):
    if not user_query_input.strip():
        st.error("Please enter a valid request prompt in the input tray first.")
    else:
        if inferred_ctx and inferred_ctx.get("output_variety") == "non_educational_reject":
            st.error("🛑 Request Rejected: Out of Scope. Please enter a valid educational curriculum query.")
        else:
            with st.spinner("🚀 Spawning workspace group chat. Query Analyzer Agent is decoding intents..."):
                try:
                    raw_result_text = run_pure_autogen_pipeline(user_query_input, inferred_ctx)
                    st.session_state.final_output_text = raw_result_text
                    
                    if export_pdf_toggle:
                        final_payload = raw_result_text
                        if "Official Board Reference" not in final_payload and "Official Textbook" not in final_payload:
                            final_payload += f"\n\n### EXT_LINK_PORTAL_TRIGGER\n- Official Textbook Repository Portal: https://ebalbharati.in\n"
                        
                        pdf_filename = f"{inferred_ctx['subject'].lower().replace(', ', '_')}_{inferred_ctx['output_variety']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                        
                        compiled_pdf = compile_exam_paper_to_pdf(
                            main_text=final_payload,
                            ctx=inferred_ctx,
                            filename=pdf_filename,
                            output_dir="outputs",
                            include_answer_key=inferred_ctx["with_answers"]
                        )
                        st.session_state.compiled_pdf_path = compiled_pdf
                    else:
                        st.session_state.compiled_pdf_path = None
                        
                except Exception as e:
                    st.error(f"Pipeline Engine Interruption Failure: {str(e)}")

if st.session_state.final_output_text:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📝 Live Academic Content Markdown Stream")
        # Handle paper set notification override visually on the dashboard
        if inferred_ctx and inferred_ctx.get("output_variety") == "paperset":
            st.info("📊 **Question Paper Generated Successfully.** Full content view is redirected strictly to the PDF canvas display pane.")
        else:
            st.markdown(st.session_state.final_output_text)
        
    with col2:
        st.subheader("📄 Compiled Document Asset Export View")
        if st.session_state.compiled_pdf_path and os.path.exists(st.session_state.compiled_pdf_path):
            with open(st.session_state.compiled_pdf_path, "rb") as f:
                pdf_bytes = f.read()
                b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                
            st.success(f"File successfully compiled: `{os.path.basename(st.session_state.compiled_pdf_path)}`")
            
            st.download_button(
                label="📥 Download Export PDF File",
                data=pdf_bytes,
                file_name=os.path.basename(st.session_state.compiled_pdf_path),
                mime="application/pdf"
            )
            
            pdf_display_iframe = f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="750mm" style="border:1px solid #cbd5e1; border-radius:6px;"></iframe>'
            st.markdown(pdf_display_iframe, unsafe_allow_html=True)
        else:
            st.info("⚡ PDF Compilation step was skipped or disabled for this run frame.")
else:
    st.info("👋 Welcome to the Multi-Agent Interactive Terminal. Complete the left configuration profile and launch generation to see output grids.")