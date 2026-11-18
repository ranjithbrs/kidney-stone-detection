import os
import io
import pptx
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

PPTX_PATH = r"c:\Users\B Ranjith\Downloads\project\NEFROAI_X_final_ppt.pptx"
PPTX_SRC = r"C:\Users\B Ranjith\.gemini\antigravity\brain\93b33a10-3caf-4d1a-9ddb-9510ba00e8fd\.user_uploaded\media_1793859615656_06a93436.pptx"
PPTX_MAIN_ONLY = r"c:\Users\B Ranjith\Downloads\project\NEFROAI_X_final_ppt_main_only.pptx"

prs = pptx.Presentation(PPTX_PATH)
slide1 = prs.slides[0]

# Create new slide with blank layout (layout index 4)
new_slide = prs.slides.add_slide(prs.slide_layouts[4])

# Move new_slide to index 22 (so it becomes Slide 23, immediately after Slide 22 Conclusion)
sldIdLst = prs.slides._sldIdLst
sld_elem = sldIdLst[-1]
sldIdLst.remove(sld_elem)
sldIdLst.insert(22, sld_elem)

# 1. Copy decorative pictures from Slide 1
for s in slide1.shapes:
    if s.shape_type == pptx.enum.shapes.MSO_SHAPE_TYPE.PICTURE:
        stream = io.BytesIO(s.image.blob)
        new_slide.shapes.add_picture(stream, s.left, s.top, s.width, s.height)

# 2. Add Top College Header text (matching Slide 1)
# Header: Nehru Institute of Engineering and Technology
h_box = new_slide.shapes.add_textbox(Pt(14.7), Pt(6.7), Pt(690.7), Pt(30.8))
tf_h = h_box.text_frame
tf_h.word_wrap = True
tf_h.margin_top = Pt(0)
tf_h.margin_bottom = Pt(0)
p_h = tf_h.paragraphs[0]
p_h.text = "NEHRU INSTITUTE OF ENGINEERING AND TECHNOLOGY"
p_h.alignment = PP_ALIGN.CENTER
p_h.font.size = Pt(13.0)
p_h.font.bold = True
p_h.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

# Sub-header: Autonomous & Department
sub_box = new_slide.shapes.add_textbox(Pt(46.4), Pt(38.0), Pt(629.6), Pt(100.0))
tf_sub = sub_box.text_frame
tf_sub.word_wrap = True
tf_sub.margin_top = Pt(0)
tf_sub.margin_bottom = Pt(0)

p1 = tf_sub.paragraphs[0]
p1.text = "(AUTONOMOUS)"
p1.alignment = PP_ALIGN.CENTER
p1.font.size = Pt(8.5)
p1.font.bold = True
p1.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

p2 = tf_sub.add_paragraph()
p2.text = "(Approved by AICTE, New Delhi and Affiliated to Anna University, Chennai) | Accredited by NAAC “A+”"
p2.alignment = PP_ALIGN.CENTER
p2.font.size = Pt(7.5)
p2.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

p3 = tf_sub.add_paragraph()
p3.text = "Thirumalayampalayam, Coimbatore - 641 105"
p3.alignment = PP_ALIGN.CENTER
p3.font.size = Pt(7.5)
p3.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

p4 = tf_sub.add_paragraph()
p4.text = "DEPARTMENT OF COMPUTER SCIENCE AND BUSINESS SYSTEMS"
p4.alignment = PP_ALIGN.CENTER
p4.font.size = Pt(9.5)
p4.font.bold = True
p4.font.color.rgb = RGBColor(0x8C, 0x1D, 0x24) # NIET maroon / accent

# 3. Central "THANK YOU" Title
ty_box = new_slide.shapes.add_textbox(Pt(40.0), Pt(156.0), Pt(640.0), Pt(42.0))
tf_ty = ty_box.text_frame
tf_ty.margin_top = Pt(0)
tf_ty.margin_bottom = Pt(0)
p_ty = tf_ty.paragraphs[0]
p_ty.text = "THANK YOU"
p_ty.alignment = PP_ALIGN.CENTER
p_ty.font.size = Pt(36.0)
p_ty.font.bold = True
p_ty.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

# Subtitle: Questions & Answers / Project Defense Discussion
qa_box = new_slide.shapes.add_textbox(Pt(40.0), Pt(200.0), Pt(640.0), Pt(24.0))
tf_qa = qa_box.text_frame
tf_qa.margin_top = Pt(0)
tf_qa.margin_bottom = Pt(0)
p_qa = tf_qa.paragraphs[0]
p_qa.text = "Questions & Answers  |  Project Review Discussion"
p_qa.alignment = PP_ALIGN.CENTER
p_qa.font.size = Pt(13.0)
p_qa.font.bold = True
p_qa.font.color.rgb = RGBColor(0xB2, 0x6A, 0x00) # Gold / Amber

# 4. Details Container Card
card = new_slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Pt(35.0), Pt(228.0), Pt(650.0), Pt(138.0))
card.fill.solid()
card.fill.fore_color.rgb = RGBColor(0xF4, 0xF6, 0xFB)
card.line.color.rgb = RGBColor(0x1F, 0x38, 0x64)
card.line.width = Pt(1.0)

# Project title inside card
title_box = new_slide.shapes.add_textbox(Pt(45.0), Pt(233.0), Pt(630.0), Pt(32.0))
tf_t = title_box.text_frame
tf_t.word_wrap = True
tf_t.margin_top = Pt(0)
tf_t.margin_bottom = Pt(0)
pt0 = tf_t.paragraphs[0]
pt0.text = "NEFROAI-X: A Three-Engine CKD Risk Assessment & Clinical Decision-Support Research Platform"
pt0.font.size = Pt(10.5)
pt0.font.bold = True
pt0.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

pt1 = tf_t.add_paragraph()
pt1.text = "Batch No.: 12  ·  Final Year, Department of Computer Science and Business Systems"
pt1.font.size = Pt(9.0)
pt1.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

# Left Column: Team Members
team_box = new_slide.shapes.add_textbox(Pt(50.0), Pt(270.0), Pt(310.0), Pt(88.0))
tf_team = team_box.text_frame
tf_team.margin_top = Pt(0)
tf_team.margin_bottom = Pt(0)

p_th = tf_team.paragraphs[0]
p_th.text = "Project Batch Members:"
p_th.font.size = Pt(9.5)
p_th.font.bold = True
p_th.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

members = [
    ("721423244010", "ANUSHA PP"),
    ("721423244049", "RANJITH B"),
    ("721423244053", "SANTHOSH M"),
    ("721423244056", "SRIPRIYAN S")
]
for reg, name in members:
    pm = tf_team.add_paragraph()
    pm.text = f"•  {reg}  &  {name}"
    pm.font.size = Pt(8.5)
    pm.font.color.rgb = RGBColor(0x2A, 0x2A, 0x2A)

# Right Column: Guide & Platform
guide_box = new_slide.shapes.add_textbox(Pt(375.0), Pt(270.0), Pt(300.0), Pt(88.0))
tf_g = guide_box.text_frame
tf_g.margin_top = Pt(0)
tf_g.margin_bottom = Pt(0)

p_gh = tf_g.paragraphs[0]
p_gh.text = "Internal Guide:"
p_gh.font.size = Pt(9.5)
p_gh.font.bold = True
p_gh.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

pg1 = tf_g.add_paragraph()
pg1.text = "Prof. ANJU P"
pg1.font.size = Pt(9.0)
pg1.font.bold = True
pg1.font.color.rgb = RGBColor(0x2A, 0x2A, 0x2A)

pg2 = tf_g.add_paragraph()
pg2.text = "Assistant Professor, Dept. of CSBS, NIET"
pg2.font.size = Pt(8.0)
pg2.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

pg3 = tf_g.add_paragraph()
pg3.text = "Platform Designation:"
pg3.font.size = Pt(8.5)
pg3.font.bold = True
pg3.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
pg3.space_before = Pt(3)

pg4 = tf_g.add_paragraph()
pg4.text = "Investigational research software · v1.0 · c8262cb"
pg4.font.size = Pt(7.8)
pg4.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

# 5. Footer department text & slide number 23
foot_box = new_slide.shapes.add_textbox(Pt(168.2), Pt(384.3), Pt(438.8), Pt(16.0))
tf_f = foot_box.text_frame
p_f = tf_f.paragraphs[0]
p_f.text = "Computer Science and Business systems ,Nehru Institute of Engineering and Technology"
p_f.font.size = Pt(8.0)
p_f.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

num_box = new_slide.shapes.add_textbox(Pt(680.7), Pt(385.7), Pt(30.6), Pt(14.0))
tf_n = num_box.text_frame
p_n = tf_n.paragraphs[0]
p_n.text = "23"
p_n.font.size = Pt(8.0)
p_n.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

# 6. Update Slide Numbers for Backup Slides (now slides 24, 25, 26)
for i, slide_idx in enumerate([23, 24, 25]):
    s = prs.slides[slide_idx]
    # Update slide number placeholder if present
    for sh in s.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip().isdigit():
            sh.text_frame.text = str(slide_idx + 1)
        # Update title to clearly indicate Appendix
        if sh.has_text_frame and "Backup" in sh.text_frame.text:
            sh.text_frame.text = sh.text_frame.text.replace("Backup", "Appendix / Defense")

# Save primary updated presentation (26 slides with Thank You + Appendix)
prs.save(PPTX_PATH)
prs.save(PPTX_SRC)
print(f"Saved primary deck (with Thank You at Slide 23) to:\n  - {PPTX_PATH}\n  - {PPTX_SRC}")

# 7. Also create a clean "Main Presentation Only" version (strictly 23 slides, ending at Thank You)
prs_main = pptx.Presentation(PPTX_PATH)
# Delete slides 24, 25, 26 (from end backwards)
rIdLst = prs_main.slides._sldIdLst
for _ in range(3):
    del rIdLst[-1]

prs_main.save(PPTX_MAIN_ONLY)
print(f"Saved clean presentation (strictly 23 slides, ending on Thank You) to:\n  - {PPTX_MAIN_ONLY}")
