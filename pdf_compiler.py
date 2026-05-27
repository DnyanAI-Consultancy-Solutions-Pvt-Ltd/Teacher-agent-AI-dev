import os
import re
import autogen
from fpdf import FPDF
from fpdf.enums import XPos, YPos


class PDFDocument(FPDF):
    def header(self):
        # Header is left blank to remove "AI Educational Framework Report"
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(113, 128, 150)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="R")


def safe_text(text: str) -> str:
    if not text:
        return ""

    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "•": "-",
        "✅": "", "❌": "", "📘": "", "🎓": "", "🔍": "", "→": "->", "₹": "Rs."
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.encode("latin-1", "replace").decode("latin-1")


def clean_text(text: str) -> str:
    if not text:
        return ""

    remove_patterns = [
        r"\[PLAN_DONE\]", r"\[CONCEPT_DONE\]", r"\[EXAMPLE_DONE\]",
        r"\[NOTES_DONE\]", r"\[QUIZ_DONE\]", r"I am .*?_agent\.?",
        r"The orchestrator selected me\.?"
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    return safe_text(text.strip())


def safe_multi_cell(pdf, height, text, font_family="Helvetica", font_style="", font_size=10.5, align="L"):
    pdf.set_font(font_family, font_style, font_size)
    pdf.multi_cell(
        w=0, h=height, text=safe_text(text), 
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align=align
    )


def write_text_to_pdf(pdf, text):
    # Specialized logic to detect and render the centered Model Paper header
    for line in text.split("\n"):
        line = line.rstrip()
        if not line.strip():
            pdf.ln(2)
            continue

        # Handle centered header logic
        if "MODEL QUESTION PAPER" in line:
            safe_multi_cell(pdf, 8, line, "Helvetica", "B", 14, align="C")
            continue
        if "CLASS" in line and ("SUBJECT" in line or "SOCIAL SCIENCES" in line):
            safe_multi_cell(pdf, 8, line, "Helvetica", "B", 12, align="C")
            pdf.ln(2)
            continue
        if "Time Allowed" in line and "Maximum Marks" in line:
            safe_multi_cell(pdf, 8, line, "Helvetica", "", 11, align="C")
            pdf.cell(0, 1, "________________________________________________________", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
            pdf.ln(5)
            continue

        # Standard text rendering
        pdf.set_text_color(45, 55, 72)
        safe_multi_cell(pdf, 6, line, "Helvetica", "", 10.5)


def compile_chat_history_to_pdf(chat_history, user_query, llm_config, output_dir="outputs", output_filename="educational_output.pdf", report_title=""):
    os.makedirs(output_dir, exist_ok=True)
    
    # We filter for quiz content to apply the new formatting
    is_quiz = "MODEL QUESTION PAPER" in str(chat_history)
    
    pdf = PDFDocument()
    pdf.alias_nb_pages()
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    # Direct writing of the synthesized response
    raw_materials = ""
    for msg in chat_history:
        content = msg.get("content", "")
        if content:
            raw_materials += clean_text(content) + "\n"
    
    write_text_to_pdf(pdf, raw_materials)

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)
    return pdf_path