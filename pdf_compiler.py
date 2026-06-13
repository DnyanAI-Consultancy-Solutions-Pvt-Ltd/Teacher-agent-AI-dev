import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ──────────────────────────────────────────────────────────────────────────────
# DETECT AND REGISTER MULTILINGUAL UNICODE FONTS
# ──────────────────────────────────────────────────────────────────────────────

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
DEFAULT_LATIN_FONT = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf")
DEVANAGARI_FONT = os.path.join(FONTS_DIR, "NotoSerifDevanagari-Regular.ttf")
DEVANAGARI_RANGE = (0x0900, 0x097F)

def contains_devanagari(text: str) -> bool:
    if not text:
        return False
    return any(DEVANAGARI_RANGE[0] <= ord(ch) <= DEVANAGARI_RANGE[1] for ch in text)

def safe_text_encode(text: str, is_unicode_ready: bool = True) -> str:
    if not text:
        return ""
    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "–": "-", "—": "-", "•": "-",
        "✅": "", "❌": "", "📘": "", "🎓": "", "🔍": "",
        "→": "->", "₹": "Rs.", "**": "", "###": "", "##": "", "#": ""
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if not is_unicode_ready:
        return text.encode("latin-1", "replace").decode("latin-1")
    return text

# ──────────────────────────────────────────────────────────────────────────────
# 1. ROUTE 1 COMPILER: STRUCTURED TABULAR SYLLABUS SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class AdvancedSyllabusPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.board_name = "CBSE"
        self.class_lvl = "10"
        self.stream_name = "General Education"
        self._unicode_ready = False
        self._active_font = "Helvetica"

    def register_custom_fonts(self, text_sample: str):
        if os.path.exists(DEVANAGARI_FONT) and contains_devanagari(text_sample):
            self.add_font("NotoSerifDevanagari", "", DEVANAGARI_FONT, uni=True)
            self._active_font = "NotoSerifDevanagari"
            self._unicode_ready = True
        elif os.path.exists(DEFAULT_LATIN_FONT):
            self.add_font("NotoSans", "", DEFAULT_LATIN_FONT, uni=True)
            self._active_font = "NotoSans"
            self._unicode_ready = True

    def header(self):
        self.set_fill_color(30, 41, 59) # Slate Dark Blue
        self.rect(0, 0, 210, 25, style="F")
        if self.page > 0:
            self.set_y(8)
            self.set_font(self._active_font, "B" if not self._unicode_ready else "", 14)
            self.set_text_color(255, 255, 255)
            self.cell(0, 8, "OFFICIAL ACADEMIC REGISTRATION CURRICULUM", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def footer(self):
        if self.page > 0:
            self.set_y(-15)
            self.set_font(self._active_font, "I" if not self._unicode_ready else "", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 5, "Generated dynamically via verified Board Matrix Records.", align="L")
            self.set_y(-15)
            self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def compile_curriculum_object_to_pdf(data, filename: str, output_dir: str = "outputs") -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, filename)
    
    pdf = AdvancedSyllabusPDF(orientation="P", unit="mm", format="A4")
    pdf.board_name = data.board
    pdf.class_lvl = data.class_level
    pdf.stream_name = data.stream
    
    # Analyze string contexts to register the correct multilingual fonts
    sample_check = f"{data.board} {data.stream}"
    pdf.register_custom_fonts(sample_check)
    
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 25, 15)
    
    pdf.add_page()
    pdf.set_font(pdf._active_font, "", 10)
    
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(15, 30, 180, 22, style="F")
    pdf.set_y(33)
    pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 5, f"BOARD RESIDENT CONTROL: {pdf.board_name.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._active_font, "", 10)
    pdf.cell(0, 5, f"Target Matrix Framework: {pdf.class_lvl} | Stream Segment: {pdf.stream_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)
    
    for subject in data.subjects:
        if pdf.get_y() > 230:
            pdf.add_page()
            
        pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 13)
        pdf.set_text_color(29, 78, 216) 
        pdf.cell(0, 8, f"Subject: {subject.subject_name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
        
        # Grid Table Formats
        pdf.set_fill_color(226, 232, 240)
        pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(20, 7, "Chapter", border=1, fill=True, align="C")
        pdf.cell(60, 7, "Core Chapter Title", border=1, fill=True, align="L")
        pdf.cell(100, 7, "Conceptual Core Sub-Topics Covered", border=1, fill=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.set_font(pdf._active_font, "", 9)
        pdf.set_text_color(51, 65, 85)
        
        for ch in subject.chapters:
            topics_sentence = ", ".join(ch.core_topics)
            if pdf.get_y() > 255:
                pdf.add_page()
                pdf.set_fill_color(226, 232, 240)
                pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 9)
                pdf.cell(20, 7, "Chapter", border=1, fill=True, align="C")
                pdf.cell(60, 7, "Core Chapter Title", border=1, fill=True, align="L")
                pdf.cell(100, 7, "Conceptual Core Sub-Topics Covered", border=1, fill=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font(pdf._active_font, "", 9)
            
            pdf.cell(20, 8, str(ch.chapter_number), border=1, align="C")
            pdf.cell(60, 8, safe_text_encode(ch.title[:32], pdf._unicode_ready), border=1, align="L")
            pdf.cell(100, 8, safe_text_encode(topics_sentence[:60], pdf._unicode_ready) + "...", border=1, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)
        
    pdf.output(pdf_path)
    return pdf_path


# ──────────────────────────────────────────────────────────────────────────────
# 2. ROUTE 2 COMPILER: PAPERS, BLUEPRINTS, NOTES (INSULATED FROM WRITE_HTML CRASHES)
# ──────────────────────────────────────────────────────────────────────────────

class UnstructuredEducationalPDF(FPDF):
    def __init__(self, report_title="AI Academic Document", citation_hint="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = report_title
        self.citation_hint = citation_hint
        self._unicode_ready = False
        self._active_font = "Helvetica"

    def register_custom_fonts(self, text_sample: str):
        if os.path.exists(DEVANAGARI_FONT) and contains_devanagari(text_sample):
            self.add_font("NotoSerifDevanagari", "", DEVANAGARI_FONT, uni=True)
            self._active_font = "NotoSerifDevanagari"
            self._unicode_ready = True
        elif os.path.exists(DEFAULT_LATIN_FONT):
            self.add_font("NotoSans", "", DEFAULT_LATIN_FONT, uni=True)
            self._active_font = "NotoSans"
            self._unicode_ready = True

    def header(self):
        self.set_fill_color(30, 41, 59) # Slate Dark Blue Header
        self.rect(0, 0, 210, 25, style="F")
        if self.page > 0:
            self.set_y(8)
            self.set_font(self._active_font, "B" if not self._unicode_ready else "", 13)
            self.set_text_color(255, 255, 255)
            self.cell(0, 8, safe_text_encode(self.report_title.upper(), self._unicode_ready), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def footer(self):
        if self.page > 0:
            self.set_y(-15)
            self.set_font(self._active_font, "I" if not self._unicode_ready else "", 7.5)
            self.set_text_color(148, 163, 184)
            if self.citation_hint:
                self.cell(0, 5, safe_text_encode(self.citation_hint, self._unicode_ready), align="L")
            self.set_y(-15)
            self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")


def compile_chat_history_to_pdf(chat_history, user_query, llm_config, output_dir="outputs", output_filename="educational_output.pdf", report_title="AI Custom Learning Document", citation_hint=""):
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, output_filename)
    
    useful_contents = [m.get("content", "").strip() for m in chat_history if m.get("content") and m.get("role") != "user"]
    main_text = useful_contents[-1] if useful_contents else "No response generated."

    pdf = UnstructuredEducationalPDF(report_title=report_title, citation_hint=citation_hint, orientation="P", unit="mm", format="A4")
    
    # Primary font check triggers unicode fonts BEFORE adding the initial page canvas boundary
    combined_sample = user_query + " " + main_text[:500]
    pdf.register_custom_fonts(combined_sample)
    
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(15, 25, 15)
    
    # Open the core document canvas safely
    pdf.add_page()
    
    # Render Student Input Query Reference Card Block
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(15, 30, 180, 16, style="F")
    pdf.set_y(32)
    pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 9)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(0, 4, "STUDENT INPUT QUERY REFERENCE:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(pdf._active_font, "I" if not pdf._unicode_ready else "", 9.5)
    pdf.set_text_color(15, 23, 42)
    
    clean_query = safe_text_encode(user_query, pdf._unicode_ready)
    pdf.cell(0, 5, f'"{clean_query[:85]}..."' if len(clean_query) > 85 else f'"{clean_query}"', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)
    
    # ──────────────────────────────────────────────────────────────────────────
    # INSULATED DEFENSIVE MULTILINGUAL TEXT RENDERER LOOP
    # ──────────────────────────────────────────────────────────────────────────
    pdf.set_text_color(51, 65, 85)
    
    for line in main_text.split("\n"):
        stripped_line = line.strip()
        if not stripped_line:
            pdf.ln(2)
            continue
            
        clean_line = safe_text_encode(stripped_line, pdf._unicode_ready)
        
        # Dynamic Section Header Font Controller
        if stripped_line.startswith("# ") or stripped_line.startswith("## ") or stripped_line.startswith("### "):
            pdf.ln(2)
            pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 12)
            pdf.set_text_color(29, 78, 216) # Section Header Blue
            pdf.multi_cell(0, 6, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif re.match(r"^SECTION|^PART|प्रश्न पत्र", clean_line, re.IGNORECASE):
            pdf.ln(3)
            pdf.set_font(pdf._active_font, "B" if not pdf._unicode_ready else "", 13)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(0, 7, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        else:
            # Standard Text Row Multi-Cell Render
            pdf.set_font(pdf._active_font, "", 10.5)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 5.5, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
    pdf.output(pdf_path)
    return pdf_path