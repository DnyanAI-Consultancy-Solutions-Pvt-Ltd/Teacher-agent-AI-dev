import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ─────────────────────────────────────────
# MULTILINGUAL PATHS AND UNICODE DEFINITIONS
# ─────────────────────────────────────────

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
DEFAULT_LATIN_FONT = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf")
DEVANAGARI_FONT = os.path.join(FONTS_DIR, "NotoSerifDevanagari-Regular.ttf")

DEVANAGARI_RANGE = (0x0900, 0x097F)

def contains_devanagari(text: str) -> bool:
    if not text:
        return False
    return any(DEVANAGARI_RANGE[0] <= ord(ch) <= DEVANAGARI_RANGE[1] for ch in text)


# ─────────────────────────────────────────
# MULTILINGUAL COMPLIANT PDF DOCUMENT CLASS
# ─────────────────────────────────────────

class PDFDocument(FPDF):
    def __init__(self, citation_hint="Ref: NCERT / State Board syllabus", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.citation_hint = citation_hint
        self._unicode_ready = False
        self._active_font_family = "Helvetica"

    def register_unicode_fonts(self, needs_devanagari: bool):
        if self._unicode_ready:
            return

        try:
            if needs_devanagari and os.path.exists(DEVANAGARI_FONT):
                self.add_font("NotoSerifDevanagari", "", DEVANAGARI_FONT, uni=True)
                self._active_font_family = "NotoSerifDevanagari"
                self._unicode_ready = True
            elif os.path.exists(DEFAULT_LATIN_FONT):
                self.add_font("NotoSans", "", DEFAULT_LATIN_FONT, uni=True)
                self._active_font_family = "NotoSans"
                self._unicode_ready = True
            else:
                self._active_font_family = "Helvetica"
        except Exception:
            self._active_font_family = "Helvetica"

    def get_active_font_family(self) -> str:
        return self._active_font_family

    def footer(self):
        self.set_y(-13)
        self.set_font(self.get_active_font_family(), "I" if self.get_active_font_family() == "Helvetica" else "", 7)
        self.set_text_color(130, 130, 130)
        self.cell(
            0,
            5,
            safe_text(self.citation_hint, fallback_to_latin=not self._unicode_ready),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align="L",
        )

        self.set_y(-13)
        self.set_font(self.get_active_font_family(), "" if self.get_active_font_family() != "Helvetica" else "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


# ─────────────────────────────────────────
# CLEANING AND CHARACTER ENCODING MANAGERS
# ─────────────────────────────────────────

def safe_text(text: str, fallback_to_latin: bool = False) -> str:
    if not text:
        return ""

    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "•": "-",
        "✅": "", "❌": "", "📘": "", "🎓": "", "🔍": "",
        "→": "->", "₹": "Rs.", "**": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    if fallback_to_latin:
        return text.encode("latin-1", "replace").decode("latin-1")
    
    return text


def clean_text(text: str, fallback_to_latin: bool = False) -> str:
    if not text:
        return ""

    remove_patterns = [
        r"\[PLAN_DONE\]", r"\[CONCEPT_DONE\]", r"\[EXAMPLE_DONE\]",
        r"\[NOTES_DONE\]", r"\[QUIZ_DONE\]", r"^quiz_agent\s*$",
        r"^concept_agent\s*$", r"^notes_agent\s*$", r"^example_agent\s*$",
        r"^planner_agent\s*$", r"I am .*?_agent\.?",
        r"The orchestrator selected me\.?",
        r"---REFERENCE_METADATA_START---", r"---REFERENCE_METADATA_END---",
    ]

    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)

    return safe_text(text.strip(), fallback_to_latin=fallback_to_latin)


def split_reference_metadata(text: str):
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
        "citation_hint": "", "board": "", "class": "",
        "subject": "", "chapter_page": "", "explore_more": [],
    }

    if not metadata:
        return data

    lines = [line.rstrip() for line in metadata.split("\n") if line.strip()]
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
            data["explore_more"].append(clean)
        elif clean.lower().startswith("link:") and data["explore_more"]:
            data["explore_more"][-1] += f"\n{clean}"

    return data


def remove_duplicate_blocks(text: str) -> str:
    if not text:
        return ""

    markers = [
        "BIOLOGY PAPER", "MATHEMATICS PAPER", "MATHS PAPER",
        "MODEL QUESTION PAPER", "QUESTION PAPER", "अभ्यासक्रम", "प्रश्नपत्रिका"
    ]

    upper_text = text.upper()
    for marker in markers:
        if upper_text.count(marker) > 1:
            parts = re.split(marker, text, flags=re.IGNORECASE)
            last_part = parts[-1].strip()
            return f"{marker.title()}\n{last_part}"

    return text


def extract_best_response(chat_history):
    useful_contents = []
    ignored_names = {"Admin", "user", "orchestrator_agent", "chat_manager", "GroupChatManager"}

    for msg in chat_history:
        sender = msg.get("name", "") or msg.get("role", "")
        content = msg.get("content", "")

        if not content or sender in ignored_names:
            continue

        cleaned = content.strip()
        if cleaned:
            useful_contents.append(cleaned)

    if not useful_contents:
        return "No valid educational response was generated."

    final_text = useful_contents[-1]
    return remove_duplicate_blocks(final_text)


# ─────────────────────────────────────────
# SAFE PIPELINE RENDERING ENGINE
# ─────────────────────────────────────────

def safe_multi_cell(pdf, height, text, font_style="", font_size=10.5, align="L"):
    active_family = pdf.get_active_font_family()
    style_hook = font_style if active_family == "Helvetica" else ""
    
    pdf.set_font(active_family, style_hook, font_size)
    pdf.set_x(pdf.l_margin)
    
    fallback_flag = not pdf._unicode_ready
    clean_line = text.replace("### ", "").replace("⚠️ ", "").strip()
    processed_text = safe_text(clean_line, fallback_to_latin=fallback_flag)
    
    try:
        pdf.multi_cell(
            w=0,
            h=height,
            text=processed_text,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align=align,
            text_shaping=True
        )
    except TypeError:
        pdf.multi_cell(
            w=0,
            h=height,
            text=processed_text,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            align=align
        )


def draw_title(pdf, title):
    pdf.set_fill_color(29, 78, 216)
    pdf.rect(0, 0, 210, 28, style="F")

    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    safe_multi_cell(pdf, 9, title, "B", 18, align="C")
    pdf.ln(10)


def draw_section_header(pdf, title, citation_hint=""):
    pdf.ln(4)
    pdf.set_fill_color(219, 234, 254)
    pdf.set_text_color(30, 64, 175)
    
    active_family = pdf.get_active_font_family()
    style_hook = "B" if active_family == "Helvetica" else ""
    pdf.set_font(active_family, style_hook, 12)
    
    fallback_flag = not pdf._unicode_ready
    processed_title = safe_text(title, fallback_to_latin=fallback_flag)
    
    try:
        pdf.cell(
            0,
            8,
            processed_title,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            fill=True,
            text_shaping=True
        )
    except TypeError:
        pdf.cell(
            0,
            8,
            processed_title,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            fill=True
        )

    if citation_hint:
        style_sub = "I" if active_family == "Helvetica" else ""
        pdf.set_font(active_family, style_sub, 7)
        pdf.set_text_color(130, 130, 130)
        processed_hint = safe_text(citation_hint, fallback_to_latin=fallback_flag)
        try:
            pdf.cell(
                0,
                4,
                processed_hint,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="R",
                text_shaping=True
            )
        except TypeError:
            pdf.cell(
                0,
                4,
                processed_hint,
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
                align="R"
            )
    pdf.ln(2)


def write_reference_summary(pdf, metadata):
    if not metadata:
        return

    parsed = parse_metadata_lines(metadata)
    has_any_reference = any([
        parsed.get("board"), parsed.get("class"), parsed.get("subject"),
        parsed.get("chapter_page"), parsed.get("explore_more"),
    ])

    if not has_any_reference:
        return

    pdf.ln(6)
    draw_section_header(pdf, "Explore More", parsed.get("citation_hint", ""))

    pdf.set_text_color(75, 85, 99)
    compact_parts = []
    if parsed.get("board"): compact_parts.append(parsed["board"])
    if parsed.get("class"): compact_parts.append(parsed["class"])
    if parsed.get("subject"): compact_parts.append(parsed["subject"])

    if compact_parts:
        safe_multi_cell(pdf, 5, "Textbook Basis: " + " | ".join(compact_parts), "I", 8)

    if parsed.get("chapter_page"):
        safe_multi_cell(pdf, 5, "Chapter/Page Note: " + parsed["chapter_page"], "I", 8)

    pdf.ln(2)

    if parsed.get("explore_more"):
        pdf.set_text_color(45, 55, 72)
        for item in parsed["explore_more"][:5]:
            lines = item.split("\n")
            title = lines[0]
            link = ""
            for l in lines[1:]:
                if l.lower().startswith("link:"):
                    link = l.split(":", 1)[1].strip()

            safe_multi_cell(pdf, 5.5, title, "", 9)
            if link:
                pdf.set_text_color(90, 90, 90)
                safe_multi_cell(pdf, 4.5, "   " + link, "I", 7.5)
                pdf.set_text_color(45, 55, 72)


def write_text_to_pdf(pdf, text, citation_hint=""):
    fallback_flag = not pdf._unicode_ready
    for line in text.split("\n"):
        line = clean_text(line.rstrip(), fallback_to_latin=fallback_flag)
        if not line:
            pdf.ln(2)
            continue

        upper_line = line.upper()

        if any(m in upper_line for m in ["QUESTION PAPER", "PAPER", "अभ्यासक्रम", "प्रश्नपत्रिका"]):
            pdf.ln(2)
            pdf.set_text_color(17, 24, 39)
            safe_multi_cell(pdf, 8, line, "B", 16, align="C")

            if citation_hint:
                pdf.set_text_color(130, 130, 130)
                safe_multi_cell(pdf, 4, citation_hint, "I", 7, align="R")
            pdf.ln(2)
            continue

        if "CLASS" in upper_line and "SUBJECT" in upper_line:
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 7, line, "B", 12, align="C")
            pdf.ln(2)
            continue

        if "TIME" in upper_line and "MARK" in upper_line:
            pdf.set_text_color(75, 85, 99)
            safe_multi_cell(pdf, 7, line, "", 11, align="C")
            pdf.ln(3)
            pdf.set_draw_color(191, 219, 254)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(5)
            continue

        if upper_line.startswith("SECTION") or upper_line.startswith("ANSWER KEY") or upper_line.startswith("PART"):
            draw_section_header(pdf, line, citation_hint)
            continue

        if line.startswith("# ") or line.startswith("## "):
            draw_section_header(pdf, line.replace("# ", "").replace("## ", ""), citation_hint)
            continue

        if line.startswith("### "):
            pdf.set_text_color(31, 41, 55)
            safe_multi_cell(pdf, 7, line.replace("### ", ""), "B", 12)
            continue

        if re.match(r"^\d+\.", line):
            pdf.set_text_color(31, 41, 55)
            safe_multi_cell(pdf, 6.5, line, "", 10.5)
            pdf.ln(1)
            continue

        if re.match(r"^\s*[A-D]\)", line):
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 5.8, "   " + line.strip(), "", 10)
            continue

        if line.startswith("- "):
            pdf.set_text_color(55, 65, 81)
            safe_multi_cell(pdf, 6, line, "", 10.3)
            continue

        pdf.set_text_color(45, 55, 72)
        safe_multi_cell(pdf, 6, line, "", 10.5)


# ─────────────────────────────────────────
# MAIN INTEGRATED COMPILER PIPELINE ENTRY
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

    parsed_metadata = parse_metadata_lines(metadata)
    metadata_citation = parsed_metadata.get("citation_hint", "")
    if metadata_citation:
        citation_hint = metadata_citation

    sample_header_check = "User Question / विद्यार्थी प्रश्न"
    prefer_devanagari = (
        contains_devanagari(main_text) or 
        contains_devanagari(user_query) or 
        contains_devanagari(sample_header_check)
    )

    pdf = PDFDocument(citation_hint=citation_hint)
    pdf.register_unicode_fonts(needs_devanagari=prefer_devanagari)
    
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 20, 15)
    pdf.add_page()

    draw_title(pdf, report_title)

    # REMOVED the buggy 'set_add_page_trigger' line causing your crash
    pdf.set_fill_color(248, 250, 252)
    pdf.set_text_color(75, 85, 99)
    
    active_family = pdf.get_active_font_family()
    style_hook = "B" if active_family == "Helvetica" else ""
    pdf.set_font(active_family, style_hook, 9)
    
    fallback_flag = not pdf._unicode_ready
    processed_header = safe_text("User Question / विद्यार्थी प्रश्न", fallback_to_latin=fallback_flag)
    
    try:
        pdf.cell(
            0,
            7,
            processed_header,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            fill=True,
            text_shaping=True
        )
    except TypeError:
        pdf.cell(
            0,
            7,
            processed_header,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            fill=True
        )

    pdf.set_text_color(31, 41, 55)
    safe_multi_cell(pdf, 6, user_query, "", 10)
    pdf.ln(5)

    main_text = clean_text(main_text, fallback_to_latin=not pdf._unicode_ready)
    
    write_text_to_pdf(pdf, main_text, citation_hint)
    write_reference_summary(pdf, metadata)

    pdf_path = os.path.join(output_dir, output_filename)
    pdf.output(pdf_path)

    return pdf_path