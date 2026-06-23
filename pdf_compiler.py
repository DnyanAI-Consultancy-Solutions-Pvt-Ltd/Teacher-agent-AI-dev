import os
import re
from fpdf import FPDF
from fpdf.enums import XPos, YPos

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
DEVANAGARI_FONT_REGULAR = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf") 
DEVANAGARI_FONT_BOLD = os.path.join(FONTS_DIR, "NotoSans-Bold.ttf")

def safe_text_encode(text: str) -> str:
    if not text: return ""
    replacements = {
        "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "•": "-",
        "###": "", "##": "", "#": "", "**": "", "*": "", '"': ""
    }
    for old, new in replacements.items(): text = text.replace(old, new)
    return text

class UnstructuredEducationalPDF(FPDF):
    def __init__(self, report_title="AI Academic Document", citation_hint="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report_title = report_title
        self.citation_hint = citation_hint
        self._active_font = "Helvetica"

    def register_custom_fonts(self):
        if os.path.exists(DEVANAGARI_FONT_REGULAR):
            self.add_font("NotoDevanagari", "", DEVANAGARI_FONT_REGULAR)
            if os.path.exists(DEVANAGARI_FONT_BOLD):
                self.add_font("NotoDevanagari", "B", DEVANAGARI_FONT_BOLD)
            self._active_font = "NotoDevanagari"
            try: self.set_text_shaping(True)
            except Exception: pass
        else:
            self._active_font = "Helvetica"

    def header(self):
        self.set_fill_color(30, 41, 59) 
        self.rect(0, 0, 210, 24, style="F")
        if self.page > 0:
            self.set_y(8)
            self.set_font(self._active_font, "B", 11)
            self.set_text_color(255, 255, 255)
            self.cell(0, 6, safe_text_encode(self.report_title.upper()), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def footer(self):
        if self.page > 0:
            self.set_y(-15)
            self.set_font(self._active_font, "", 8)
            self.set_text_color(148, 163, 184)
            if self.citation_hint:
                self.cell(0, 5, safe_text_encode(self.citation_hint), align="L")
            self.set_y(-15)
            self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="R")

def compile_exam_paper_to_pdf(main_text: str, ctx: dict, filename: str, output_dir: str = "outputs", include_answer_key: bool = False) -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, filename)
    
    variety = ctx.get("output_variety", "study_notes")
    variety_label = variety.replace('_', ' ').upper()
    
    pdf = UnstructuredEducationalPDF(
        report_title=f"{ctx.get('board', 'BOARD')} {variety_label}: STANDARD {ctx.get('class_level', 'IX')}", 
        citation_hint=f"Ref: {ctx.get('board', 'Board')} Curriculum Blueprint"
    )
    pdf.register_custom_fonts()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(16, 28, 16)
    pdf.add_page()
    
    if variety == "paperset":
        pdf.set_y(28)
        pdf.set_font(pdf._active_font, "B", 13)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, safe_text_encode(ctx.get('board', 'BOARD EXAM').upper()), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.set_font(pdf._active_font, "B", 11)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 5, f"EVALUATION EXAM: CLASS {ctx.get('class_level', '9')}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        subj_label = ctx.get('subject', 'General').upper()
        stream_txt = f" | Stream: {ctx.get('stream')}" if ctx.get('stream') else ""
        pdf.cell(0, 5, f"SUBJECT: {subj_label} ({ctx.get('language', 'English')} Medium{stream_txt})", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
        
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())
        pdf.ln(2)
        
        pdf.set_font(pdf._active_font, "B", 10)
        curr_y = pdf.get_y()
        pdf.cell(90, 5, f"TIME ALLOWED: {ctx.get('time_allowed', '3 Hours')}", align="L")
        pdf.set_xy(106, curr_y)
        pdf.cell(88, 5, f"MAXIMUM MARKS: {ctx.get('max_marks', 100)} MARKS", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())
        pdf.ln(5)

    elif variety == "official_syllabus":
        pdf.set_y(28)
        pdf.set_font(pdf._active_font, "B", 14)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, f"{ctx.get('board', 'BOARD')} OFFICIAL SYLLABUS MATRIX", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.set_font(pdf._active_font, "B", 10)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, f"Grade Level: Standard {ctx.get('class_level')} | Course: {ctx.get('subject')}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.5)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())
        pdf.ln(4)
        
        pdf.set_fill_color(30, 41, 59)
        pdf.set_font(pdf._active_font, "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(55, 8, " CHAPTER / UNIT MODULE", border=1, fill=True, align="L")
        pdf.cell(123, 8, " SUBTOPICS & CURRICULUM CONTENTS", border=1, fill=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    else:
        pdf.set_y(28)
        pdf.set_font(pdf._active_font, "B", 15)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 6, f"OFFICIAL ACADEMIC STUDY NOTES", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.set_font(pdf._active_font, "", 10)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 5, f"Subject: {ctx.get('subject')} | Framework: {ctx.get('board')} (Class {ctx.get('class_level')})", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)
        pdf.set_draw_color(30, 41, 59)
        pdf.set_line_width(0.6)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())
        pdf.ln(5)

    in_answer_key = False
    skipping_lines = False
    
    for line in main_text.split("\n"):
        stripped_line = line.strip()
        if not stripped_line or "EVALUATION EXAMINATION" in stripped_line or "OFFICIAL BOARD" in stripped_line:
            continue
            
        clean_line = safe_text_encode(stripped_line)
        
        if not include_answer_key and clean_line.startswith("Answer:"):
            continue

        if any(term in clean_line for term in [
            "Specialist_Creator matches", "format blueprint ordered", "full text block exactly",
            "string appended at", "Task Review", "Content Review", "Formatting Review", "Grammar Review",
            "The content text provided", "Here is the full text", "with the string '' appended"
        ]):
            continue

        if pdf.get_y() > 235:
            pdf.add_page()
            if variety == "official_syllabus":
                pdf.set_fill_color(30, 41, 59)
                pdf.set_font(pdf._active_font, "B", 10)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(55, 8, " CHAPTER / UNIT MODULE", border=1, fill=True, align="L")
                pdf.cell(123, 8, " SUBTOPICS & CURRICULUM CONTENTS", border=1, fill=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if clean_line.startswith("[Image of") and clean_line.endswith("]"):
            pdf.ln(3)
            img_description = clean_line.replace("[Image of", "").replace("]", "").strip()
            
            start_img_y = pdf.get_y()
            pdf.set_fill_color(248, 250, 252)
            pdf.set_draw_color(148, 163, 184)
            pdf.set_line_width(0.35)
            
            pdf.rect(16, start_img_y, 178, 34, style="FD")
            
            pdf.set_xy(18, start_img_y + 4)
            pdf.set_font(pdf._active_font, "B", 9.5)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(174, 5, "📊 TEXTBOOK GEOMETRIC GRAPH & DIAGRAM COGNITIVE ANCHOR", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.set_xy(22, start_img_y + 11)
            pdf.set_font(pdf._active_font, "I", 8.5)
            pdf.set_text_color(71, 85, 105)
            pdf.multi_cell(166, 4.5, f"Illustration Objective: {img_description}", border=0, align="C")
            
            pdf.set_y(start_img_y + 39)
            continue

        if "### EXAM_ANSWER_KEY_SECTION" in stripped_line or "ANSWER KEY APPENDIX" in stripped_line:
            in_answer_key = True
            if not include_answer_key:
                skipping_lines = True
                continue
            pdf.add_page()
            pdf.set_y(28)
            pdf.set_font(pdf._active_font, "B", 12)
            pdf.set_text_color(220, 38, 38)
            pdf.cell(0, 6, "OFFICIAL EVALUATION GUIDE & ANSWER KEY APPENDIX", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_draw_color(220, 38, 38)
            pdf.line(16, pdf.get_y(), 194, pdf.get_y())
            pdf.ln(4)
            continue

        if "EXT_LINK_PORTAL_TRIGGER" in stripped_line:
            skipping_lines = False
            pdf.ln(6)
            pdf.set_font(pdf._active_font, "B", 10)
            pdf.set_text_color(29, 78, 216)
            pdf.cell(0, 5, "VERIFIED CURRICULUM LINKS & PORTALS:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
            continue

        if "Official Board Reference" in clean_line or "Official Textbook" in clean_line:
            font_style = "" if pdf._active_font == "NotoDevanagari" else "I"
            pdf.set_font(pdf._active_font, font_style, 9.5)
            pdf.set_text_color(37, 99, 235)
            display_link = re.sub(r'^[-\s*•]+', '  ', clean_line)
            pdf.multi_cell(0, 5, display_link, border=0, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            continue

        if skipping_lines:
            continue

        if variety == "official_syllabus":
            pdf.set_font(pdf._active_font, "", 9.5)
            pdf.set_text_color(51, 65, 85)
            
            if ":" in clean_line:
                left_col, right_col = clean_line.split(":", 1)
                left_col = left_col.strip()
                right_col = right_col.strip()
            else:
                left_col = "Topic Module"
                right_col = clean_line
                
            start_y = pdf.get_y()
            pdf.set_xy(16, start_y)
            pdf.set_font(pdf._active_font, "B", 9.5)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(55, 6, left_col, border=0, align="L")
            end_y_1 = pdf.get_y()
            
            pdf.set_xy(71, start_y)
            pdf.set_font(pdf._active_font, "", 9.5)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(123, 6, right_col, border=0, align="L")
            end_y_2 = pdf.get_y()
            
            max_row_height = max(end_y_1, end_y_2) - start_y + 2
            pdf.rect(16, start_y, 55, max_row_height)
            pdf.rect(71, start_y, 123, max_row_height)
            pdf.set_y(start_y + max_row_height)

        else:
            if any(clean_line.upper().startswith(p) for p in ["SECTION", "UNIT", "CHAPTER"]) or ("Notes" in clean_line and clean_line.endswith("Notes")):
                pdf.ln(4)
                pdf.set_fill_color(241, 245, 249)
                pdf.set_draw_color(203, 213, 225)
                sect_y = pdf.get_y()
                pdf.rect(16, sect_y, 178, 8, style="FD")
                
                pdf.set_fill_color(30, 41, 59) if not in_answer_key else pdf.set_fill_color(220, 38, 38)
                pdf.rect(16, sect_y, 2.5, 8, style="F")
                
                pdf.set_xy(21, sect_y + 1.5)
                pdf.set_font(pdf._active_font, "B", 10)
                pdf.set_text_color(30, 41, 59) if not in_answer_key else pdf.set_text_color(185, 28, 28)
                pdf.cell(0, 5, clean_line.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_y(sect_y + 11)
                
            elif re.match(r'^\d+\.', clean_line):
                pdf.ln(1.5)
                pdf.set_font(pdf._active_font, "B", 10)
                pdf.set_text_color(30, 41, 59) if not in_answer_key else pdf.set_text_color(185, 28, 28)
                
                if "(" in clean_line and any(m in clean_line.lower() for m in ["mark", "marks"]):
                    try:
                        base_text = clean_line.rsplit("(", 1)[0].strip()
                        marks_text = "(" + clean_line.rsplit("(", 1)[1].strip()
                        
                        pdf.multi_cell(145, 5, base_text, border=0, align="L", new_x=XPos.WBR, new_y=YPos.TOP)
                        pdf.cell(33, 5, marks_text, border=0, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    except Exception:
                        pdf.multi_cell(0, 5, clean_line, border=0, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.multi_cell(0, 5, clean_line, border=0, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    
            elif re.match(r'^[a-d\)]', clean_line) or clean_line.startswith("[a)") or clean_line.startswith("- a)"):
                pdf.set_font(pdf._active_font, "", 9.5)
                pdf.set_text_color(71, 85, 105)
                pdf.multi_cell(0, 5, "            " + clean_line, border=0, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.set_font(pdf._active_font, "", 10)
                pdf.set_text_color(51, 65, 85)
                pdf.multi_cell(0, 5.5, clean_line, border=0, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(pdf_path)
    return pdf_path

def compile_chat_history_to_pdf(chat_history, user_query, llm_config, output_dir="outputs", output_filename="educational_output.pdf", report_title="AI Custom Document", citation_hint=""):
    useful_contents = [m.get("content", "").strip() for m in chat_history if m.get("content")]
    main_text = useful_contents[-1] if useful_contents else ""
    
    if "SECTION A" in main_text:
        ctx_mock = {
            "board": "CBSE", "class_level": "9", "subject": "Science", "language": "English",
            "time_allowed": "3 Hours", "max_marks": 100, "output_variety": "paperset"
        }
        return compile_exam_paper_to_pdf(main_text, ctx_mock, output_filename, output_dir, include_answer_key=False)

    pdf = UnstructuredEducationalPDF(report_title=report_title, citation_hint=citation_hint)
    pdf.register_custom_fonts()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 28, 18)
    pdf.add_page()
    
    pdf.set_y(28)
    pdf.set_font(pdf._active_font, "", 10)
    pdf.set_text_color(51, 65, 85)
    for line in main_text.split("\n"):
        pdf.multi_cell(0, 5.5, safe_text_encode(line.strip()), border=0)
    pdf.output(os.path.join(output_dir, output_filename))
    return os.path.join(output_dir, output_filename)