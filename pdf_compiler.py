import os
import re
import autogen
from fpdf import FPDF
from fpdf.enums import XPos, YPos


class PDFDocument(FPDF):
    def header(self):
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(113, 128, 150)
        self.cell(
            0,
            10,
            "AI Educational Framework Report",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(113, 128, 150)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="R")


def safe_text(text: str) -> str:
    if not text:
        return ""

    replacements = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "•": "-",
        "✅": "",
        "❌": "",
        "📘": "",
        "🎓": "",
        "🔍": "",
        "→": "->",
        "₹": "Rs.",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.encode("latin-1", "replace").decode("latin-1")


def clean_text(text: str) -> str:
    if not text:
        return ""

    remove_patterns = [
        r"\[PLAN_DONE\]",
        r"\[CONCEPT_DONE\]",
        r"\[EXAMPLE_DONE\]",
        r"\[NOTES_DONE\]",
        r"\[QUIZ_DONE\]",
        r"I am .*?_agent\.?",
        r"The orchestrator selected me\.?",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return safe_text(text.strip())


def safe_multi_cell(pdf, height, text, font_family="Helvetica", font_style="", font_size=10.5):
    pdf.set_font(font_family, font_style, font_size)
    pdf.set_x(pdf.l_margin)

    pdf.multi_cell(
        w=0,
        h=height,
        text=safe_text(text),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def extract_agent_material(chat_history):
    """
    Robust extraction for both:
    - group chat logs
    - direct agent logs
    - normalized logs from teacher.py
    """
    ignored_senders = {
        "Admin",
        "user",
        "orchestrator_agent",
        "chat_manager",
        "GroupChatManager",
    }

    raw_materials = ""

    for msg in chat_history:
        sender = msg.get("name", "") or msg.get("role", "") or "assistant"
        content = msg.get("content", "")

        if not content:
            continue

        if sender in ignored_senders:
            continue

        if sender == "assistant":
            sender = "education_agent"

        cleaned = clean_text(content)

        if cleaned:
            raw_materials += f"\n\n### Contribution from {sender}:\n{cleaned}"

    return raw_materials.strip()


def synthesize_response(raw_materials, user_query, llm_config):
    """
    Uses LLM to clean final output.
    If LLM fails, fallback to raw materials so PDF is never empty.
    """
    if not raw_materials:
        return "No valid educational response was generated."

    try:
        synthesis_agent = autogen.AssistantAgent(
            name="synthesizer",
            llm_config=llm_config,
            system_message="""
You are an expert educational report compiler.

Your job:
- Convert educational agent outputs into one clean final answer.
- Remove all agent names, internal tags, and chat meta-commentary.
- Keep the answer focused on the user's original question.
- Do not invent unsupported facts.
- If source links are present, preserve them under a Sources section.
- If the content is a quiz, worksheet, mock test, paper set, or question paper, keep questions and answer key clearly separated.
- If code is present, keep code blocks clean and readable.
- Use clear headings.
"""
        )

        extraction_prompt = f"""
Original User Question:
{user_query}

Raw Agent Logs:
{raw_materials}

Create the final clean educational response.
Do not include internal agent names or system notes.
"""

        refined_response = synthesis_agent.generate_reply(
            messages=[{"role": "user", "content": extraction_prompt}]
        )

        if refined_response:
            return clean_text(refined_response)

        return clean_text(raw_materials)

    except Exception:
        return clean_text(raw_materials)


def write_text_to_pdf(pdf, text):
    pdf.set_text_color(45, 55, 72)
    in_code_block = False

    for line in text.split("\n"):
        line = line.rstrip()

        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            pdf.ln(2)
            continue

        if in_code_block:
            pdf.set_text_color(45, 55, 72)
            safe_multi_cell(pdf, 5, line, "Courier", "", 9)
            continue

        if line.startswith("# "):
            pdf.ln(5)
            pdf.set_text_color(26, 54, 93)
            safe_multi_cell(pdf, 9, line.replace("# ", ""), "Helvetica", "B", 18)
            pdf.ln(2)

        elif line.startswith("## "):
            pdf.ln(4)
            pdf.set_text_color(43, 108, 176)
            safe_multi_cell(pdf, 8, line.replace("## ", ""), "Helvetica", "B", 15)
            pdf.ln(2)

        elif line.startswith("### "):
            pdf.ln(3)
            pdf.set_text_color(74, 85, 104)
            safe_multi_cell(pdf, 7, line.replace("### ", ""), "Helvetica", "B", 12)

        elif line.strip().startswith("- "):
            pdf.set_text_color(45, 55, 72)
            safe_multi_cell(pdf, 6, line, "Helvetica", "", 10.5)
            pdf.ln(1)

        elif line.strip():
            pdf.set_text_color(45, 55, 72)
            safe_multi_cell(pdf, 6, line, "Helvetica", "", 10.5)
            pdf.ln(2)

        else:
            pdf.ln(2)


def compile_chat_history_to_pdf(
    chat_history,
    user_query,
    llm_config,
    output_dir="outputs",
    output_filename="educational_output.pdf",
    report_title="Curated Education Guide",
):
    print("\n[System] Group chat complete. Synthesizing clean response and compiling PDF...")

    os.makedirs(output_dir, exist_ok=True)

    raw_materials = extract_agent_material(chat_history)
    refined_response = synthesize_response(raw_materials, user_query, llm_config)

    if not refined_response.strip():
        refined_response = "No valid educational response was generated."

    pdf = PDFDocument()
    pdf.alias_nb_pages()
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    pdf.set_text_color(26, 54, 93)
    safe_multi_cell(pdf, 12, report_title, "Helvetica", "B", 22)

    pdf.set_text_color(74, 85, 104)
    safe_multi_cell(pdf, 6, f"User Question: {user_query}", "Helvetica", "", 10)
    pdf.ln(5)

    pdf.set_draw_color(49, 130, 206)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)

    write_text_to_pdf(pdf, refined_response)

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)

    print(f"[System] Success! Clean synthesized output saved to PDF: {pdf_path}")
    return pdf_path


def compile_direct_answer_to_pdf(
    answer,
    user_query,
    output_dir="outputs",
    output_filename="exam_info_output.pdf",
    report_title="Exam Information Report",
):
    print("\n[System] Compiling direct answer to PDF...")

    os.makedirs(output_dir, exist_ok=True)

    pdf = PDFDocument()
    pdf.alias_nb_pages()
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    pdf.set_text_color(26, 54, 93)
    safe_multi_cell(pdf, 12, report_title, "Helvetica", "B", 22)

    pdf.set_text_color(74, 85, 104)
    safe_multi_cell(pdf, 6, f"User Question: {user_query}", "Helvetica", "", 10)
    pdf.ln(5)

    pdf.set_draw_color(49, 130, 206)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)

    write_text_to_pdf(pdf, clean_text(answer))

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)

    print(f"[System] Success! Direct answer saved to PDF: {pdf_path}")
    return pdf_path