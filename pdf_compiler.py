import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos


# ─────────────────────────────────────────
# PDF CLASS
# ─────────────────────────────────────────

class PDFDocument(FPDF):
    def footer(self):
        self.set_y(-13)

        # Minimal citation in bottom-left corner
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(
            0,
            5,
            "Ref: NCERT / State Board syllabus",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="L",
        )

        # Page number in bottom-right corner
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


# ─────────────────────────────────────────
# TEXT CLEANING
# ─────────────────────────────────────────

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
        "**": "",
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
        r"^quiz_agent\s*$",
        r"^concept_agent\s*$",
        r"^notes_agent\s*$",
        r"^example_agent\s*$",
        r"^planner_agent\s*$",
        r"I am .*?_agent\.?",
        r"The orchestrator selected me\.?",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    return safe_text(text.strip())


def remove_duplicate_blocks(text: str) -> str:
    """
    Removes repeated model paper blocks if agent/chat history contains duplicate responses.
    Keeps only the last complete generated response.
    """
    if not text:
        return ""

    markers = [
        "BIOLOGY PAPER",
        "MATHEMATICS PAPER",
        "MATHS PAPER",
        "MODEL QUESTION PAPER",
        "QUESTION PAPER",
    ]

    upper_text = text.upper()

    for marker in markers:
        if upper_text.count(marker) > 1:
            parts = re.split(marker, text, flags=re.IGNORECASE)
            last_part = parts[-1].strip()
            return f"{marker.title()}\n{last_part}"

    return text


def extract_best_response(chat_history):
    """
    Picks the final useful assistant/agent response instead of printing all messages.
    This prevents repeated PDF output.
    """
    useful_contents = []

    ignored_names = {
        "Admin",
        "user",
        "orchestrator_agent",
        "chat_manager",
        "GroupChatManager",
    }

    for msg in chat_history:
        sender = msg.get("name", "") or msg.get("role", "")
        content = msg.get("content", "")

        if not content:
            continue

        if sender in ignored_names:
            continue

        cleaned = clean_text(content)

        if cleaned:
            useful_contents.append(cleaned)

    if not useful_contents:
        return "No valid educational response was generated."

    # Use only the last meaningful response
    final_text = useful_contents[-1]

    return remove_duplicate_blocks(final_text)


# ─────────────────────────────────────────
# PDF HELPERS
# ─────────────────────────────────────────

def safe_multi_cell(
    pdf,
    height,
    text,
    font_family="Helvetica",
    font_style="",
    font_size=10.5,
    align="L",
):
    pdf.set_font(font_family, font_style, font_size)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(
        w=0,
        h=height,
        text=safe_text(text),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align=align,
    )


def draw_title(pdf, title):
    pdf.set_fill_color(29, 78, 216)
    pdf.rect(0, 0, 210, 28, style="F")

    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    safe_multi_cell(pdf, 9, title, "Helvetica", "B", 18, align="C")

    pdf.ln(10)


def draw_section_header(pdf, title):
    pdf.ln(4)
    pdf.set_fill_color(219, 234, 254)
    pdf.set_text_color(30, 64, 175)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(
        0,
        8,
        safe_text(title),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        fill=True,
    )

    # Minimal corner citation under section header
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(
        0,
        4,
        "Ref: syllabus/textbook aligned",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        align="R",
    )
    pdf.ln(2)


def write_text_to_pdf(pdf, text):
    for line in text.split("\n"):
        line = clean_text(line.rstrip())

        if not line:
            pdf.ln(2)
            continue

        upper_line = line.upper()

        # Main paper title
        if (
            "MODEL QUESTION PAPER" in upper_line
            or "QUESTION PAPER" in upper_line
            or "BIOLOGY PAPER" in upper_line
            or "MATHEMATICS PAPER" in upper_line
            or "MATHS PAPER" in upper_line
        ):
            pdf.ln(2)
            pdf.set_text_color(17, 24, 39)
            safe_multi_cell(pdf, 8, line, "Helvetica", "B", 16, align="C")
            pdf.ln(2)
            continue

        # Class / Subject line
        if "CLASS" in upper_line and "SUBJECT" in upper_line:
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 7, line, "Helvetica", "B", 12, align="C")
            pdf.ln(2)
            continue

        # Time / Marks line
        if "TIME" in upper_line and "MARK" in upper_line:
            pdf.set_text_color(75, 85, 99)
            safe_multi_cell(pdf, 7, line, "Helvetica", "", 11, align="C")
            pdf.ln(3)

            pdf.set_draw_color(191, 219, 254)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(5)
            continue

        # Sections
        if (
            upper_line.startswith("SECTION")
            or upper_line.startswith("ANSWER KEY")
            or upper_line.startswith("PART")
        ):
            draw_section_header(pdf, line)
            continue

        # Headings
        if line.startswith("# "):
            draw_section_header(pdf, line.replace("# ", ""))
            continue

        if line.startswith("## "):
            draw_section_header(pdf, line.replace("## ", ""))
            continue

        if line.startswith("### "):
            pdf.set_text_color(31, 41, 55)
            safe_multi_cell(pdf, 7, line.replace("### ", ""), "Helvetica", "B", 12)
            continue

        # Questions
        if re.match(r"^\d+\.", line):
            pdf.set_text_color(31, 41, 55)
            safe_multi_cell(pdf, 6.5, line, "Helvetica", "", 10.5)
            pdf.ln(1)
            continue

        # Options
        if re.match(r"^[A-D]\)", line.strip()):
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 5.8, "   " + line, "Helvetica", "", 10)
            continue

        # Bullets
        if line.startswith("- "):
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 6, line, "Helvetica", "", 10.3)
            continue

        # Normal paragraph
        pdf.set_text_color(45, 55, 72)
        safe_multi_cell(pdf, 6, line, "Helvetica", "", 10.5)


# ─────────────────────────────────────────
# MAIN PDF COMPILER
# ─────────────────────────────────────────

def compile_chat_history_to_pdf(
    chat_history,
    user_query,
    llm_config,
    output_dir="outputs",
    output_filename="educational_output.pdf",
    report_title="AI Education Report",
):
    os.makedirs(output_dir, exist_ok=True)

    final_text = extract_best_response(chat_history)

    pdf = PDFDocument()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    draw_title(pdf, report_title)

    # User question block
    pdf.set_fill_color(248, 250, 252)
    pdf.set_text_color(75, 85, 99)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(
        0,
        7,
        "User Question",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        fill=True,
    )

    pdf.set_text_color(31, 41, 55)
    safe_multi_cell(pdf, 6, user_query, "Helvetica", "", 10)
    pdf.ln(5)

    write_text_to_pdf(pdf, final_text)

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)

    return pdf_path