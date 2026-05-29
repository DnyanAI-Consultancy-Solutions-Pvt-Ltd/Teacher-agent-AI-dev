import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos


# ─────────────────────────────────────────
# PDF CLASS
# ─────────────────────────────────────────

class PDFDocument(FPDF):
    def __init__(self, citation_hint="Ref: NCERT / State Board syllabus", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.citation_hint = citation_hint

    def footer(self):
        self.set_y(-13)

        # Minimal citation in bottom-left corner
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(
            0,
            5,
            safe_text(self.citation_hint),
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
        r"---REFERENCE_METADATA_START---",
        r"---REFERENCE_METADATA_END---",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    return safe_text(text.strip())


# ─────────────────────────────────────────
# REFERENCE METADATA PARSING
# ─────────────────────────────────────────

def split_reference_metadata(text: str):
    """
    Splits main content and hidden reference metadata block.

    Expected metadata format:
    ---REFERENCE_METADATA_START---
    Citation Hint: ...
    Board/Book: ...
    Class: ...
    Subject: ...
    Chapter/Page: ...
    Explore More:
    1. ...
       Link: ...
    ---REFERENCE_METADATA_END---
    """

    if not text:
        return "", ""

    pattern = r"---REFERENCE_METADATA_START---(.*?)---REFERENCE_METADATA_END---"
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)

    if not match:
        return text, ""

    metadata = match.group(1).strip()
    main_text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()

    return main_text, metadata


def parse_metadata_lines(metadata: str):
    data = {
        "citation_hint": "",
        "board": "",
        "class": "",
        "subject": "",
        "chapter_page": "",
        "explore_more": [],
    }

    if not metadata:
        return data

    lines = [line.rstrip() for line in metadata.split("\n") if line.strip()]

    current_item = None

    for line in lines:
        clean = line.strip()

        if clean.lower().startswith("citation hint:"):
            data["citation_hint"] = clean.split(":", 1)[1].strip()

        elif clean.lower().startswith("board/book:"):
            data["board"] = clean.split(":", 1)[1].strip()

        elif clean.lower().startswith("class:"):
            data["class"] = clean.split(":", 1)[1].strip()

        elif clean.lower().startswith("subject:"):
            data["subject"] = clean.split(":", 1)[1].strip()

        elif clean.lower().startswith("chapter/page:"):
            data["chapter_page"] = clean.split(":", 1)[1].strip()

        elif re.match(r"^\d+\.", clean):
            current_item = clean
            data["explore_more"].append(current_item)

        elif clean.lower().startswith("link:") and data["explore_more"]:
            data["explore_more"][-1] += f"\n{clean}"

    return data


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

        cleaned = content.strip()

        if cleaned:
            useful_contents.append(cleaned)

    if not useful_contents:
        return "No valid educational response was generated."

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


def draw_section_header(pdf, title, citation_hint=""):
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

    # Minimal citation in corner under section header
    if citation_hint:
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(
            0,
            4,
            safe_text(citation_hint),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="R",
        )

    pdf.ln(2)


def write_reference_summary(pdf, metadata):
    """
    Writes small textbook/chapter info and Explore More section at end.
    """

    if not metadata:
        return

    parsed = parse_metadata_lines(metadata)

    has_any_reference = any(
        [
            parsed.get("board"),
            parsed.get("class"),
            parsed.get("subject"),
            parsed.get("chapter_page"),
            parsed.get("explore_more"),
        ]
    )

    if not has_any_reference:
        return

    pdf.ln(6)
    draw_section_header(pdf, "Explore More", parsed.get("citation_hint", ""))

    # Compact academic basis
    pdf.set_text_color(75, 85, 99)
    pdf.set_font("Helvetica", "I", 8)

    compact_parts = []

    if parsed.get("board"):
        compact_parts.append(parsed["board"])

    if parsed.get("class"):
        compact_parts.append(parsed["class"])

    if parsed.get("subject"):
        compact_parts.append(parsed["subject"])

    if compact_parts:
        safe_multi_cell(
            pdf,
            5,
            "Textbook Basis: " + " | ".join(compact_parts),
            "Helvetica",
            "I",
            8,
        )

    if parsed.get("chapter_page"):
        safe_multi_cell(
            pdf,
            5,
            "Chapter/Page Note: " + parsed["chapter_page"],
            "Helvetica",
            "I",
            8,
        )

    pdf.ln(2)

    # Explore More resource links
    if parsed.get("explore_more"):
        pdf.set_text_color(45, 55, 72)

        for item in parsed["explore_more"][:5]:
            lines = item.split("\n")
            title = lines[0]
            link = ""

            for l in lines[1:]:
                if l.lower().startswith("link:"):
                    link = l.split(":", 1)[1].strip()

            safe_multi_cell(pdf, 5.5, title, "Helvetica", "", 9)

            if link:
                pdf.set_text_color(90, 90, 90)
                safe_multi_cell(pdf, 4.5, "   " + link, "Helvetica", "I", 7.5)
                pdf.set_text_color(45, 55, 72)


def write_text_to_pdf(pdf, text, citation_hint=""):
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

            # small citation near title, right aligned
            if citation_hint:
                pdf.set_text_color(130, 130, 130)
                safe_multi_cell(pdf, 4, citation_hint, "Helvetica", "I", 7, align="R")

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
            draw_section_header(pdf, line, citation_hint)
            continue

        # Headings
        if line.startswith("# "):
            draw_section_header(pdf, line.replace("# ", ""), citation_hint)
            continue

        if line.startswith("## "):
            draw_section_header(pdf, line.replace("## ", ""), citation_hint)
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
    citation_hint="Ref: NCERT / State Board syllabus",
):
    os.makedirs(output_dir, exist_ok=True)

    full_text = extract_best_response(chat_history)

    main_text, metadata = split_reference_metadata(full_text)

    # Prefer metadata citation if available
    parsed_metadata = parse_metadata_lines(metadata)
    metadata_citation = parsed_metadata.get("citation_hint", "")

    if metadata_citation:
        citation_hint = metadata_citation

    main_text = clean_text(main_text)

    pdf = PDFDocument(citation_hint=citation_hint)
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

    write_text_to_pdf(pdf, main_text, citation_hint)

    # Explore More / compact references at end
    write_reference_summary(pdf, metadata)

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)

    return pdf_path