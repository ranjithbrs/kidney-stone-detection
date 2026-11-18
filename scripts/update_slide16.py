import os
import pptx
from pptx.util import Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

PPTX_SRC = r"C:\Users\B Ranjith\.gemini\antigravity\brain\93b33a10-3caf-4d1a-9ddb-9510ba00e8fd\.user_uploaded\media_1793859615656_06a93436.pptx"
PPTX_BACKUP = r"c:\Users\B Ranjith\Downloads\project\NEFROAI_X_final_ppt_backup.pptx"
PPTX_OUT_PROJECT = r"c:\Users\B Ranjith\Downloads\project\NEFROAI_X_final_ppt.pptx"

# Backup original
if not os.path.exists(PPTX_BACKUP):
    import shutil
    shutil.copyfile(PPTX_SRC, PPTX_BACKUP)
    print("Backup created at:", PPTX_BACKUP)

prs = pptx.Presentation(PPTX_SRC)
slide16 = prs.slides[15]

# Identify shapes on Slide 16
# Shape 6: Synthetic demo banner
# Shape 7: Rounded Rectangle 20 (Step 1)
# Shape 8: Rounded Rectangle 21 (Step 2)
# Shape 9: Rounded Rectangle 22 (Step 3)
# Shape 10: Screenshot evidence note

shape_dict = {s.name: s for s in slide16.shapes}
banner = shape_dict.get("Synthetic demo banner")
card1 = shape_dict.get("Rounded Rectangle 20")
card2 = shape_dict.get("Rounded Rectangle 21")
card3 = shape_dict.get("Rounded Rectangle 22")
note = shape_dict.get("Screenshot evidence note")

# 1. Update Banner
if banner:
    banner.top = Pt(48.0)
    banner.height = Pt(28.0)
    banner.left = Pt(21.6)
    banner.width = Pt(676.8)
    tf = banner.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Demonstration Workflow  |  Live multi-engine evaluation using documented synthetic patient presets (Controlled research software)"
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

# 2. Add the 3 real UI screenshots
# Aspect ratio of images is 1374 x 957 -> 1.4357
img_w = Pt(212.4)
img_h = Pt(147.9)
img_top = Pt(82.0)

img1_path = r"c:\Users\B Ranjith\Downloads\project\docs\images\screenshot_real_assessment.png"
img2_path = r"c:\Users\B Ranjith\Downloads\project\docs\images\screenshot_real_explainability.png"
img3_path = r"c:\Users\B Ranjith\Downloads\project\docs\images\screenshot_real_longitudinal.png"

pic1 = slide16.shapes.add_picture(img1_path, Pt(21.6), img_top, img_w, img_h)
pic2 = slide16.shapes.add_picture(img2_path, Pt(253.4), img_top, img_w, img_h)
pic3 = slide16.shapes.add_picture(img3_path, Pt(485.3), img_top, img_w, img_h)

# Add subtle border to pictures
for pic in [pic1, pic2, pic3]:
    pic.line.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    pic.line.width = Pt(1.0)

# 3. Add Title labels under pictures
def add_label(left, top, width, height, text):
    tx_box = slide16.shapes.add_textbox(left, top, width, height)
    tf = tx_box.text_frame
    tf.word_wrap = True
    tf.margin_top = Pt(0)
    tf.margin_bottom = Pt(0)
    tf.margin_left = Pt(0)
    tf.margin_right = Pt(0)
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(10.0)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
    return tx_box

label_top = Pt(233.0)
label_h = Pt(18.0)
add_label(Pt(21.6), label_top, img_w, label_h, "1 · Patient Clinical Assessment")
add_label(Pt(253.4), label_top, img_w, label_h, "2 · Explainability & Findings (XAI)")
add_label(Pt(485.3), label_top, img_w, label_h, "3 · Longitudinal Trajectory Engine")

# 4. Reposition and restyle Cards (Shape 7, 8, 9) below labels
card_top = Pt(252.0)
card_h = Pt(112.0)

def populate_card(card, title, bullets, fill_color, line_color):
    card.top = card_top
    card.height = card_h
    card.fill.solid()
    card.fill.fore_color.rgb = fill_color
    card.line.color.rgb = line_color
    card.line.width = Pt(1.0)
    tf = card.text_frame
    tf.word_wrap = True
    tf.clear()
    
    # Title paragraph
    p0 = tf.paragraphs[0]
    p0.text = title
    p0.font.size = Pt(9.5)
    p0.font.bold = True
    p0.font.color.rgb = line_color
    p0.space_after = Pt(3)
    
    # Bullets
    for b in bullets:
        p = tf.add_paragraph()
        p.text = f"• {b}"
        p.font.size = Pt(8.2)
        p.font.color.rgb = RGBColor(0x2A, 0x2A, 0x2A)
        p.space_after = Pt(1.5)

card1_bullets = [
    "Biomarker input panel & synthetic presets",
    "Calibrated risk probability & clinical triage tier",
    "18-cell KDIGO CGA risk matrix & care actions"
]
populate_card(card1, "Multi-Engine Triage & CGA Staging", card1_bullets, RGBColor(0xF2, 0xF5, 0xFA), RGBColor(0x1F, 0x38, 0x64))

card2_bullets = [
    "Patient-specific TreeSHAP waterfall attribution",
    "Local surrogate LIME decision boundaries",
    "Verifiable biomarker contribution transparency"
]
populate_card(card2, "Transparent Local & Global XAI", card2_bullets, RGBColor(0xF2, 0xF5, 0xFA), RGBColor(0x1F, 0x38, 0x64))

card3_bullets = [
    "Historical eGFR trajectory & LMM slope",
    "4-variable Tangri KFRE 2-yr / 5-yr failure risk",
    "Rapid progression alert (>5 mL/min/1.73m²/yr)"
]
populate_card(card3, "Disease Progression & KFRE Risk", card3_bullets, RGBColor(0xF2, 0xF5, 0xFA), RGBColor(0x1F, 0x38, 0x64))

# 5. Remove the placeholder warning note (Shape 10)
if note:
    sp = note._element
    sp.getparent().remove(sp)
    print("Removed placeholder warning note successfully!")

# Save to destination paths
prs.save(PPTX_OUT_PROJECT)
prs.save(PPTX_SRC)
print(f"Saved updated presentation to:\n  - {PPTX_OUT_PROJECT}\n  - {PPTX_SRC}")
