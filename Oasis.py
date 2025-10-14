import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import numpy as np
import math
from pathlib import Path
from reportlab.lib.pagesizes import A3, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# Page config
st.set_page_config(page_title="Poster Generator", layout="wide")

# Constants
A3_WIDTH_MM = 297
A3_HEIGHT_MM = 420
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 300
MM_TO_INCH = 1 / 25.4
BORDER_MM = 10
FONT_SCALE_MULTIPLIER = 4.0

# GitHub raw content URLs
GITHUB_IMAGE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_image.png"
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_logo.png"
GITHUB_TEXTURE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_texture.png"
GITHUB_FONT_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_font.otf"

# --- All helper functions (mm_to_pixels, cmyk_to_rgb, etc.) remain the same ---
def mm_to_pixels(mm, dpi=DPI):
    return int(mm * MM_TO_INCH * dpi)

def get_scale_factor(paper_size):
    return 1.0 if paper_size == "A3" else A4_WIDTH_MM / A3_WIDTH_MM

def cmyk_to_rgb(c, m, y, k):
    c,m,y,k = c/100.0, m/100.0, y/100.0, k/100.0
    r = 255 * (1 - c) * (1 - k)
    g = 255 * (1 - m) * (1 - k)
    b = 255 * (1 - y) * (1 - k)
    return int(r), int(g), int(b)

def rgb_to_cmyk(r, g, b):
    if (r, g, b) == (0, 0, 0): return 0, 0, 0, 100
    if r == 255 and g == 255 and b == 255: return 0, 0, 0, 0
    c = 1 - (r / 255.0); m = 1 - (g / 255.0); y = 1 - (b / 255.0)
    k = min(c, m, y)
    if (1 - k) == 0: return 0, 0, 0, 100
    c = int(((c - k) / (1 - k)) * 100); m = int(((m - k) / (1 - k)) * 100)
    y = int(((y - k) / (1 - k)) * 100); k = int(k * 100)
    return c, m, y, k

def check_gamut_warning(original_rgb):
    if not all(isinstance(c, int) for c in original_rgb): return False, None
    c, m, y, k = rgb_to_cmyk(*original_rgb)
    round_trip_rgb = cmyk_to_rgb(c, m, y, k)
    r1, g1, b1 = original_rgb; r2, g2, b2 = round_trip_rgb
    color_difference = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)
    return (True, round_trip_rgb) if color_difference > 30 else (False, None)

def load_image_from_github(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        st.error(f"Failed to load image from {url}: {e}")
        return None

def apply_blend_darken(base, overlay, opacity, fill):
    overlay_array = np.array(overlay.convert('RGBA')).astype(float)
    base_array = np.array(base.convert('RGBA')).astype(float)
    darken = np.minimum(base_array[:, :, :3], overlay_array[:, :, :3])
    fill_factor = fill / 100.0
    result_rgb = base_array[:, :, :3] * (1 - fill_factor) + darken * fill_factor
    # Combine with the original base alpha channel
    result_a = base_array[:, :, 3:]
    result = np.concatenate([result_rgb, result_a], axis=2)
    return Image.fromarray(result.astype('uint8'), 'RGBA')

def draw_text_with_tracking(draw, text, y_pos, font, tracking, poster_width, fill_color=(255, 255, 255)):
    tracking_pixels = (font.size / 1000) * tracking
    char_widths = [draw.textlength(char, font=font) for char in text]
    total_width = sum(char_widths) + tracking_pixels * (len(text) - 1)
    current_x = (poster_width - total_width) / 2
    for i, char in enumerate(text):
        draw.text((current_x, y_pos), char, font=font, fill=fill_color)
        current_x += char_widths[i] + tracking_pixels

# --- Core Create Poster Function ---
# CHANGED: Now accepts 4 lines of text
def create_poster(paper_size, bg_color, tracking, text_lines_data):
    """Create the poster image"""
    scale = get_scale_factor(paper_size)
    
    width_mm = A3_WIDTH_MM if paper_size == "A3" else A4_WIDTH_MM
    height_mm = A3_HEIGHT_MM if paper_size == "A3" else A4_HEIGHT_MM
    width_px, height_px = mm_to_pixels(width_mm), mm_to_pixels(height_mm)
    
    # CHANGED: Start with an RGBA canvas to preserve transparency throughout
    poster = Image.new('RGBA', (width_px, height_px), (*bg_color, 255))
    
    texture = load_image_from_github(GITHUB_TEXTURE_URL)
    if texture:
        texture = texture.resize((width_px, height_px), Image.Resampling.LANCZOS)
        poster = apply_blend_darken(poster, texture, opacity=100, fill=95)
        # REMOVED: poster = poster.convert('RGB') -> This was the cause of the white overlay!

    main_image = load_image_from_github(GITHUB_IMAGE_URL)
    if main_image:
        main_image = main_image.convert('RGBA')
        new_width_px = mm_to_pixels(297 * scale)
        new_height_px = int(new_width_px * (main_image.height / main_image.width))
        main_image = main_image.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
        poster.paste(main_image, ((width_px - new_width_px) // 2, height_px - new_height_px), main_image)
    
    logo = load_image_from_github(GITHUB_LOGO_URL)
    if logo:
        logo = logo.convert('RGBA')
        logo_width_px, logo_height_px = mm_to_pixels(217.76 * scale), mm_to_pixels(99.14 * scale)
        logo = logo.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)
        logo_top_px = mm_to_pixels(70.6 * scale)
        poster.paste(logo, ((width_px - logo_width_px) // 2, logo_top_px - (logo_height_px // 2)), logo)
    
    draw = ImageDraw.Draw(poster)
    
    try:
        font_data = io.BytesIO(requests.get(GITHUB_FONT_URL).content)
        # ADDED: Loop through all text lines to draw them
        for line in text_lines_data:
            if line['text']: # Only draw if there is text
                font_data.seek(0)
                font = ImageFont.truetype(font_data, int(line['size'] * FONT_SCALE_MULTIPLIER))
                top_px = mm_to_pixels(line['y_mm'])
                draw_text_with_tracking(draw, line['text'], top_px, font, tracking, width_px)
    except Exception as e:
        st.error(f"Could not load or draw font: {e}")

    border_px = mm_to_pixels(BORDER_MM)
    draw.rectangle([(0, 0), (width_px, height_px)], outline=(0, 0, 0), width=border_px)
    
    # Return the final poster, still in RGBA mode
    return poster


# --- Streamlit UI ---
st.title("🎨 Poster Generator")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Settings")
    paper_size = st.radio("Paper Size", ["A3", "A4"])
    st.subheader("Background Color")
    color_mode = st.radio("Color Input Method", ["Color Wheel", "RGB", "CMYK"])
    
    bg_color = (255,255,255) # Default
    if color_mode == "Color Wheel":
        h, s, v = st.slider("H",0.0,1.0,0.0), st.slider("S",0.0,1.0,1.0), st.slider("V",0.0,1.0,1.0)
        bg_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
    elif color_mode == "RGB":
        r,g,b = st.slider("R",0,255,255), st.slider("G",0,255,255), st.slider("B",0,255,255)
        bg_color = (r, g, b)
    else:
        c,m,y,k = st.slider("C",0,100,0),st.slider("M",0,100,0),st.slider("Y",0,100,0),st.slider("K",0,100,0)
        bg_color = cmyk_to_rgb(c, m, y, k)
    
    is_out_of_gamut, closest_cmyk_in_rgb = check_gamut_warning(bg_color)
    swatch_col1, swatch_col2 = st.columns(2)
    swatch_col1.image(Image.new('RGB', (100, 50), bg_color), caption="Screen Colour")
    if is_out_of_gamut:
        swatch_col2.image(Image.new('RGB', (100, 50), closest_cmyk_in_rgb), caption="Closest Print Colour")
        st.warning("This colour may appear different when printed.", icon="🎨")

with col2:
    st.subheader("Text Content")
    page_height_mm = A3_HEIGHT_MM if paper_size == "A3" else A4_HEIGHT_MM
    tracking = st.slider("Letter Spacing (Tracking)", -50, 200, 50)
    
    # ADDED: UI for 4 text lines based on your PDF
    text_lines_data = []
    with st.expander("Line 1: Top Line", expanded=True):
        text1 = st.text_input("Text", "COMPANY")
        size1 = st.slider("Font Size (pt)", 10, 250, 43, key="size1")
        y_mm1 = st.slider("Vertical Position (mm)", 0, page_height_mm, 280, key="y1")
        text_lines_data.append({"text": text1, "size": size1, "y_mm": y_mm1})

    with st.expander("Line 2: Main Heading", expanded=True):
        text2 = st.text_input("Text", "oasis", key="text2")
        size2 = st.slider("Font Size (pt)", 10, 250, 162, key="size2")
        y_mm2 = st.slider("Vertical Position (mm)", 0, page_height_mm, 300, key="y2")
        text_lines_data.append({"text": text2, "size": size2, "y_mm": y_mm2})

    with st.expander("Line 3: Sub-Heading", expanded=True):
        text3 = st.text_input("Text", "chicago", key="text3")
        size3 = st.slider("Font Size (pt)", 10, 250, 43, key="size3")
        y_mm3 = st.slider("Vertical Position (mm)", 0, page_height_mm, 360, key="y3")
        text_lines_data.append({"text": text3, "size": size3, "y_mm": y_mm3})
        
    with st.expander("Line 4: Venue & Date", expanded=True):
        text4 = st.text_input("Text", "SOLDIER FIELD | 08.28.2025", key="text4")
        size4 = st.slider("Font Size (pt)", 10, 250, 24, key="size4")
        y_mm4 = st.slider("Vertical Position (mm)", 0, page_height_mm, 387, key="y4")
        text_lines_data.append({"text": text4, "size": size4, "y_mm": y_mm4})


# --- Live Preview ---
st.divider()
st.subheader("Live Background Colour Preview")
preview_width_px = 600
aspect_ratio = page_height_mm / (A3_WIDTH_MM if paper_size == "A3" else A4_WIDTH_MM)
preview_height_px = int(preview_width_px * aspect_ratio)
live_color_preview = Image.new('RGB', (preview_width_px, preview_height_px), bg_color)
st.image(live_color_preview, caption=f"Real-time preview of your background on {paper_size} paper.")

# --- Generate Button ---
st.divider()
if st.button("Generate Final Poster", key="generate", type="primary"):
    with st.spinner("Creating your masterpiece..."):
        try:
            poster_rgba = create_poster(paper_size, bg_color, tracking, text_lines_data)
            
            # For display and PNG, we can use the RGBA version
            poster_for_display = poster_rgba.copy()
            st.subheader("Your Final Poster")
            st.image(poster_for_display, caption=f"Final Poster ({paper_size})")
            
            # Prepare PNG bytes (keeps transparency)
            img_bytes = io.BytesIO()
            poster_rgba.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            # Prepare PDF bytes (needs to be converted to RGB before saving)
            poster_rgb_for_pdf = poster_rgba.convert("RGB")
            pdf_bytes = io.BytesIO()
            page_size = A3 if paper_size == "A3" else A4
            c = canvas.Canvas(pdf_bytes, pagesize=page_size)
            from reportlab.lib.utils import ImageReader
            with io.BytesIO() as temp_buffer:
                poster_rgb_for_pdf.save(temp_buffer, format='PNG')
                temp_buffer.seek(0)
                c.drawImage(ImageReader(temp_buffer), 0, 0, width=page_size[0], height=page_size[1])
            c.save()
            pdf_bytes.seek(0)

            dl_col1, dl_col2 = st.columns(2)
            dl_col1.download_button("Download Poster (PNG)", img_bytes, f"poster_{paper_size}.png", "image/png", use_container_width=True)
            dl_col2.download_button("Download Poster (PDF)", pdf_bytes, f"poster_{paper_size}.pdf", "application/pdf", use_container_width=True)

        except Exception as e:
            st.error(f"Oh no, something went wrong: {e}")
