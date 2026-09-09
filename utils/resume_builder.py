from pathlib import Path
import base64
import re
from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable, Image as RLImage, PageBreak
)

TEMPLATES = {
    "classic": {"name": "Classic", "accent": "#2563eb", "font": "Helvetica"},
    "modern": {"name": "Modern", "accent": "#2563eb", "font": "Helvetica"},
    "minimal": {"name": "Minimal", "accent": "#475569", "font": "Helvetica"},
    "corporate": {"name": "Corporate", "accent": "#0f3d56", "font": "Helvetica"},
    "tech": {"name": "Tech", "accent": "#0f766e", "font": "Helvetica"},
    "fresher": {"name": "Fresher", "accent": "#7c3aed", "font": "Helvetica"},
    "two-column": {"name": "Two Column", "accent": "#2563eb", "font": "Helvetica"},
}


def clean(value):
    return (value or "").strip()


def safe_color(value, fallback="#2563eb"):
    value = clean(value)
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return colors.HexColor(value)
    return colors.HexColor(fallback)


def hex_rgb(value, fallback="#2563eb"):
    value = clean(value)
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        value = fallback
    return RGBColor.from_string(value[1:].upper())


def split_lines(value):
    return [x.strip().lstrip("•- ").strip() for x in clean(value).splitlines() if x.strip()]


def split_skills(value):
    return [x.strip() for x in clean(value).split(",") if x.strip()]


def photo_bytes(data):
    if not data or not data.startswith("data:image/") or "," not in data:
        return None
    try:
        return base64.b64decode(data.split(",", 1)[1])
    except Exception:
        return None


def _set_cell_shading(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = tcPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tcPr.append(shd)
    shd.set(qn("w:fill"), fill.lstrip("#"))


def _set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = tcPr.first_child_found_in("w:tcMar")
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tcMar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tcMar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def _add_docx_heading(doc, title, accent):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(title.upper())
    r.bold = True
    r.font.size = Pt(10.5)
    r.font.color.rgb = accent
    return p


def _add_docx_body(doc, text, accent=None):
    if not clean(text):
        return
    for line in split_lines(text):
        p = doc.add_paragraph(style="List Bullet") if len(split_lines(text)) > 1 else doc.add_paragraph()
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(line)
        r.font.size = Pt(9.5)
        if accent:
            r.font.color.rgb = RGBColor(40, 48, 60)


def build_docx(data, output):
    template = clean(data.get("template")) or "classic"
    cfg = TEMPLATES.get(template, TEMPLATES["classic"])
    accent_hex = clean(data.get("accent_color")) or cfg["accent"]
    accent = hex_rgb(accent_hex, cfg["accent"])
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(0.45 if template in {"modern", "tech", "two-column"} else 0.55)
    sec.bottom_margin = Inches(0.5)
    sec.left_margin = Inches(0.58)
    sec.right_margin = Inches(0.58)

    photo = photo_bytes(data.get("photo_data", ""))
    if template == "two-column":
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        table.columns[0].width = Inches(2.0)
        table.columns[1].width = Inches(4.65)
        left, right = table.rows[0].cells
        _set_cell_shading(left, accent_hex)
        _set_cell_margins(left, 180, 160, 180, 160)
        _set_cell_margins(right, 100, 220, 100, 100)
        left.vertical_alignment = right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
        if photo:
            p = left.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(BytesIO(photo), width=Inches(1.15), height=Inches(1.15))
        p = left.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(clean(data.get("name")) or "Your Name")
        r.bold = True; r.font.size = Pt(16); r.font.color.rgb = RGBColor(255,255,255)
        for label, value in [("CONTACT", " | ".join(filter(None,[clean(data.get("email")),clean(data.get("phone")),clean(data.get("location"))]))), ("LINKEDIN", clean(data.get("linkedin"))), ("SKILLS", clean(data.get("skills")))]:
            if value:
                h=left.add_paragraph(); rr=h.add_run(label); rr.bold=True; rr.font.size=Pt(8); rr.font.color.rgb=RGBColor(220,235,255)
                b=left.add_paragraph(); br=b.add_run(value); br.font.size=Pt(8.5); br.font.color.rgb=RGBColor(255,255,255)
        _docx_sections(right, data, accent)
    else:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if photo:
            p.add_run().add_picture(BytesIO(photo), width=Inches(1.0), height=Inches(1.0))
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(clean(data.get("name")) or "Your Name"); r.bold=True; r.font.size=Pt(22 if template != "fresher" else 20); r.font.color.rgb=accent
        contact = " | ".join(filter(None,[clean(data.get("email")),clean(data.get("phone")),clean(data.get("location")),clean(data.get("linkedin"))]))
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; rr=p.add_run(contact); rr.font.size=Pt(9)
        if template in {"modern", "corporate", "tech"}:
            p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(3); p.add_run().add_break();
        _docx_sections(doc, data, accent)
    doc.save(output)


def _docx_sections(container, data, accent):
    def heading(title): return _add_docx_heading(container, title, accent)
    if clean(data.get("summary")):
        heading("Professional Summary"); _add_docx_body(container, data["summary"], accent)
    skills=split_skills(data.get("skills"))
    if skills:
        heading("Skills"); p=container.add_paragraph(); p.paragraph_format.space_after=Pt(3); r=p.add_run(" • ".join(skills)); r.font.size=Pt(9.5)
    for title,key in [("Experience","experience"),("Projects","projects")]:
        lines=split_lines(data.get(key));
        if lines: heading(title); _add_docx_body(container, "\n".join(lines), accent)
    if clean(data.get("education")):
        heading("Education"); _add_docx_body(container, data["education"], accent)
    lines=split_lines(data.get("certifications"));
    if lines: heading("Certifications"); _add_docx_body(container, "\n".join(lines), accent)


class ResumeDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="normal", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate(id="resume", frames=frame)])


def build_pdf(data, output):
    template = clean(data.get("template")) or "classic"
    cfg = TEMPLATES.get(template, TEMPLATES["classic"])
    accent_hex = clean(data.get("accent_color")) or cfg["accent"]
    accent = safe_color(accent_hex, cfg["accent"])
    dark = colors.HexColor("#1f2937")
    muted = colors.HexColor("#64748b")
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="RName", fontName="Helvetica-Bold", fontSize=21, leading=24, textColor=accent, alignment=TA_CENTER, spaceAfter=3))
    styles.add(ParagraphStyle(name="RContact", fontName="Helvetica", fontSize=8.6, leading=11, textColor=muted, alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="RHead", fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=accent, spaceBefore=7, spaceAfter=4, keepWithNext=True))
    styles.add(ParagraphStyle(name="RBody", fontName="Helvetica", fontSize=9.2, leading=12.5, textColor=dark, spaceAfter=3))
    styles.add(ParagraphStyle(name="RBullet", fontName="Helvetica", fontSize=9.2, leading=12.5, textColor=dark, leftIndent=10, firstLineIndent=-7, spaceAfter=2))
    styles.add(ParagraphStyle(name="RSkill", fontName="Helvetica-Bold", fontSize=8.3, leading=10, textColor=accent, backColor=colors.HexColor("#f1f5f9"), borderPadding=4, spaceAfter=3))
    styles.add(ParagraphStyle(name="RSideHead", fontName="Helvetica-Bold", fontSize=8.3, leading=10, textColor=colors.white, spaceBefore=8, spaceAfter=3))
    styles.add(ParagraphStyle(name="RSide", fontName="Helvetica", fontSize=8, leading=10.5, textColor=colors.white, spaceAfter=5))

    margin=12.5*mm if template in {"modern","two-column"} else 15*mm
    doc=ResumeDocTemplate(str(output), pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=12*mm, bottomMargin=12*mm, title="Professional Resume")
    story=[]
    photo=photo_bytes(data.get("photo_data", ""))
    name=clean(data.get("name")) or "Your Name"
    contact=" | ".join(filter(None,[clean(data.get("email")),clean(data.get("phone")),clean(data.get("location")),clean(data.get("linkedin"))]))

    if template == "two-column":
        left=[]
        if photo:
            img=RLImage(BytesIO(photo), width=27*mm, height=27*mm); left += [img, Spacer(1,5)]
        left += [Paragraph(name, ParagraphStyle("sideName", parent=styles["RSideHead"], fontSize=13, leading=15, alignment=TA_CENTER))]
        for title,value in [("CONTACT",contact),("SKILLS",", ".join(split_skills(data.get("skills")))),("LINKEDIN",clean(data.get("linkedin")))]:
            if value:
                left += [Paragraph(title, styles["RSideHead"]), Paragraph(value.replace("&","&amp;"), styles["RSide"])]
        right=[]
        if clean(data.get("summary")): right += [Paragraph("PROFESSIONAL SUMMARY",styles["RHead"]), Paragraph(clean(data["summary"]).replace("\n","<br/>"),styles["RBody"])]
        for title,key in [("EXPERIENCE","experience"),("PROJECTS","projects"),("EDUCATION","education"),("CERTIFICATIONS","certifications")]:
            val=data.get(key)
            if clean(val):
                right.append(Paragraph(title,styles["RHead"]))
                lines=split_lines(val) if key != "education" else [clean(val)]
                for line in lines: right.append(Paragraph("• "+line.replace("&","&amp;"),styles["RBullet"]))
        tbl=Table([[left,right]], colWidths=[55*mm, doc.width-55*mm], hAlign="LEFT")
        tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(0,0),accent),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(0,0),7),("RIGHTPADDING",(0,0),(0,0),7),("TOPPADDING",(0,0),(0,0),10),("BOTTOMPADDING",(0,0),(0,0),10),("LEFTPADDING",(1,0),(1,0),13),("RIGHTPADDING",(1,0),(1,0),3)]))
        story.append(tbl)
    else:
        if photo:
            story.append(RLImage(BytesIO(photo), width=25*mm, height=25*mm, hAlign="CENTER")); story.append(Spacer(1,2))
        story.append(Paragraph(name,styles["RName"]))
        story.append(Paragraph(contact,styles["RContact"]))
        if template in {"modern","tech"}:
            story.append(Table([[""]],colWidths=[doc.width],rowHeights=[2.5],style=TableStyle([("BACKGROUND",(0,0),(-1,-1),accent)])))
        elif template != "minimal":
            story.append(HRFlowable(width="100%",thickness=0.6,color=accent,spaceAfter=2))
        if clean(data.get("summary")):
            story += [Paragraph("PROFESSIONAL SUMMARY",styles["RHead"]),Paragraph(clean(data["summary"]).replace("\n","<br/>"),styles["RBody"])]
        skills=split_skills(data.get("skills"))
        if skills:
            story.append(Paragraph("SKILLS",styles["RHead"]))
            if template in {"modern","tech","fresher"}:
                cells=[[Paragraph(s,styles["RSkill"]) for s in skills[:4]]]
                if len(cells[0])==1: cells[0].append("")
                t=Table(cells,colWidths=[doc.width/2]*2,hAlign="LEFT")
                t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),2),("RIGHTPADDING",(0,0),(-1,-1),2)])); story.append(t)
                if len(skills)>4: story.append(Paragraph(", ".join(skills[4:]),styles["RBody"]))
            else: story.append(Paragraph(", ".join(skills),styles["RBody"]))
        for title,key in [("EXPERIENCE","experience"),("PROJECTS","projects")]:
            lines=split_lines(data.get(key))
            if lines:
                story.append(Paragraph(title,styles["RHead"]))
                for line in lines: story.append(Paragraph("• "+line.replace("&","&amp;"),styles["RBullet"]))
        if clean(data.get("education")):
            story += [Paragraph("EDUCATION",styles["RHead"]),Paragraph(clean(data["education"]).replace("\n","<br/>"),styles["RBody"])]
        certs=split_lines(data.get("certifications"))
        if certs:
            story.append(Paragraph("CERTIFICATIONS",styles["RHead"]))
            for line in certs: story.append(Paragraph("• "+line.replace("&","&amp;"),styles["RBullet"]))
    doc.build(story)
