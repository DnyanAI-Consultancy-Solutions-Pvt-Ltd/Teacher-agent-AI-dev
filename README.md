# AI Learning Mentor: Multilingual Multi-Agent Curriculum Pipeline

Welcome to the **AI Learning Mentor** repository! This project is an enterprise-grade, fault-tolerant educational framework designed to dynamically generate certified textbook syllabus maps, study guides, and lesson blueprints across **English, Hindi, and Marathi mediums**.

If you are new to AI Agents, Python virtual environments, or automated PDF compilation—**this guide is built for you**. It documents our complete engineering journey from a single basic script to a multi-agent orchestrated system.

## Project Evolution: From Scratch to Production

### Day 1: The Monolithic Foundation
We began with a simple concept: take an incoming user prompt, pass it to a single Large Language Model (LLM) request, take the resulting plain text, and dump it into a standard `FPDF` sheet. 

* **The Problem:** It failed immediately under real-world school environments. Standard LLMs hallucinated non-existent chapters when asked trick questions. Furthermore, when rendering regional language outputs (Hindi/Marathi), the standard PDF engines threw fatal font encoding exceptions, broke text alignments, or cut content off entirely at the borders.

### Day 2: The Multi-Agent Enterprise Transformation
To solve these challenges, we refactored the entire codebase into a **Multi-Agent Architecture** managed by Microsoft's AutoGen framework and fortified by a hardware-accelerated rendering core. We broke responsibilities down across an organized network of specialized AI personas (`syllabus_agent`, `concept_agent`, `curator_agent`, etc.) and introduced a hard **Data Verification Guardrail** that cross-references live directories to stop AI hallucinations before they are ever typed into a document.

## Core Architecture & Agent Layout

Our system uses an assembly-line design to process, optimize, and safely format educational content:
┌───────────────────────────────┐
              │    User Terminal Interface    │
              └───────────────┬───────────────┘
                              │
                 [ Step 1: analyze_request ]
                              ▼
              ┌───────────────────────────────┐
              │  Semantic Keyword Interceptor │ ──► (Maps 'Algebra' to 'Mathematics')
              └───────────────┬───────────────┘
                              │
               [ Step 2: Live Verification ]
                              ▼
     ================= VERIFICATION LAYER =================
    │                                                      │
    │  Checks live indexes via official_web_reader_tool    │
    │  IF input violates boundaries (e.g., Chapter 850):  │
    │  ► SHORT-CIRCUIT: Generate Verification Notice PDF  │
    │                                                      │
     =======================  ┬  ==========================
                              │ (Passed Verification)
                              ▼
              ┌───────────────────────────────┐
              │ AutoGen Multi-Agent Assembly  │
              │ (Syllabus ➔ Curriculum ➔ LLM) │
              └───────────────┬───────────────┘
                              │
               [ Step 3: Optimization Loop ]
                              ▼
              ┌───────────────────────────────┐
              │ Reference, Note & Quality     │ ──► (Strips out internal [PLAN_DONE] tags)
              │ Checker Refining Agents       │
              └───────────────┬───────────────┘
                              │
                [ Step 4: Dynamic Compiler ]
                              ▼
              ┌───────────────────────────────┐
              │  Failsafe Unicode PDF Engine  │ ──► (Auto try/except Font-Shaping hooks)
              └───────────────────────────────┘

### The Specialized Agent Assembly Line:
* **Syllabus Agent (`syllabus_agent`)**: Extracts structural textbook indices, chapters, and marking weights directly from official reference logs.
* **Curriculum & Outcome Agents**: Map conceptual educational objectives and draft descriptive learning outcomes aligned with national standards.
* **Concept Agent (`concept_agent`)**: Acts as a senior classroom instructor to author in-depth, pedagogical explanations of the verified material.
* **Curator & Quality Checker Agents**: Act as a formatting editor. They parse the combined text output, strip out all internal AI system tags (`[PLAN_DONE]`, `[CONCEPT_DONE]`), and verify that raw system keys never leak onto a student's screen.

---

## ⚙️ Step-by-Step Environment & Dependency Setup

Follow these precise steps to provision a clean workspace environment on your local machine.

### Step 1: Initialize Your Project Directory
Open your operating system terminal (or command prompt) and run:
```bash
mkdir ai-learning-mentor
cd ai-learning-mentor

# Create required pipeline output and typography storage assets
mkdir outputs
mkdir fonts

**Step 2: Establish an Isolated Python Virtual Environment**
An isolated virtual environment (venv) ensures that your educational agent libraries never conflict with other python assets installed on your computer.
# Create the virtual sandbox environment
python -m venv venv

# Activate the sandbox environment:
# On Windows (Command Prompt):
call venv\Scripts\activate
# On macOS / Linux:
source venv/bin/activate

**Step 3: Install Production Package Matrix**
With your virtual environment active, run the following installation command to fetch our official package stack:
**pip install pyautogen fpdf2 python-dotenv certifi groq**

Why these packages matter to our project:

pyautogen: Powers our multi-agent orchestration, conversation handling, and supervisor loops.

fpdf2: Our core vector document rendering graphics engine, supporting advanced layouts.

python-dotenv: Securely handles system variables and runtime options from external configuration files.

certifi / groq: Connects the framework to ultra-low-latency Llama-3.1 cloud inferences using encrypted hardware channels.

**Step 4: Install Multilingual Font Subsystems (Crucial!)**
Python standard packages do not natively contain structural curves for Devanagari (Hindi/Marathi) alphabets. You must manually add them to your folder so the PDF compiler can switch families on the fly:

Download Noto Sans (Regular) and save it exactly as: fonts/NotoSans-Regular.ttf

Download Noto Serif Devanagari (Regular) and save it exactly as: fonts/NotoSerifDevanagari-Regular.ttf

**Step 5: Secure Your Credentials**
Create a brand new file named exactly .env in the root folder of your project and populate it with your private cloud inference authorization key:
GROQ_API_KEY=gsk_your_secret_production_key_here

**Operational Execution Blueprint**
Launch your terminal workspace console loop using: python teacher.py

**Functional Test Execution Cases**
Execution Case A: The Verified Success Path
Input a classic cross-disciplinary secondary instruction request: Enter your query (or type exit): Provide a comprehensive syllabus breakdown for Class 10 CBSE Mathematics Algebra

