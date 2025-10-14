import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import numpy as np
from reportlab.lib.pagesizes import A3, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader # ADDED: Important for PDF generation

# --- Page Config ---
st.set_page_config(page_title="Poster Generator", layout="wide")

# --- Caching Functions ---
@st.cache_data
def get_font_bytes():
    """Downloads and caches the font file bytes."""
    GITHUB_FONT_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_font.otf"
    try:
        response = requests.get(GITHUB_FONT_URL)
        response.raise_for_status()
        return io.BytesIO(response.content)
    except Exception as e:
        st.error(f"Failed to load font: {e}")
        return None

@st.cache_data
def load_image_from_github_cached(url):
    """Downloads and caches an image from a URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Use BytesIO to ensure the object is consistent for caching
        return io.BytesIO(response.content)
    except Exception as e:
        st.error(f"Failed to load image from {url}: {e}")
        return None

# --- Constants & Helpers ---
A3_WIDTH_MM, A3_HEIGHT_MM = 297, 420
A4_WIDTH_MM, A4_HEIGHT_MM = 210, 297
DPI = 300
MM_TO_INCH = 1 / 25.4
FONT_SCALE_MULTIPLIER = 4.0

GITHUB_IMAGE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_image.png"
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_logo.png"
GITHUB_TEXTURE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_texture.png"

def mm_to_pixels(mm, dpi=DPI):
    return int(mm * MM_TO_INCH * dpi)

def get_scale_factor(paper_size):
    return 1.0 if paper_size == "A3" else A4_WIDTH_MM / A3_WIDTH_MM

def cmyk_to_rgb(c, m, y, k):
    c, m, y, k = c / 100.0, m / 100.0, y / 100.0, k / 100.0
    r = 255 * (1 - c) * (1 - k); g = 255 * (1 - m) * (1 - k); b = 255 * (1 - y) * (1 - k)
    return int(r), int(g), int(b)

def apply_blend_darken(base, overlay):
    overlay_array = np.array(overlay.convert('RGBA')).astype(float)
    base_array = np.array(base.convert('RGBA')).astype(float)
    darken = np.minimum(base_array[:, :, :3], overlay_array[:, :, :3])
    fill_factor = 95 / 100.0
    result = base_array[:, :, :3] * (1 - fill_factor) + darken * fill_factor
    alpha = overlay_array[:, :, 3]
    result = np.concatenate([result, alpha[:, :, np.newaxis]], axis=2)
    return Image.fromarray(result.astype('uint8'), 'RGBA')

def draw_text_with_tracking(draw, text, y_pos, font, tracking, poster_width):
    tracking_pixels = (font.size / 1000) * tracking
    char_widths = [draw.textlength(char, font=font) for char in text]
    total_width = sum(char_widths) + tracking_pixels * (len(text) - 1)
    current_x = (poster_width - total_width) / 2
    for i, char in enumerate(text):
        draw.text((current_x, y_pos), char, font=font, fill=(255, 255, 255))
        current_x += char_widths[i] + tracking_pixels

# --- Core Function ---
# MOST IMPORTANT CHANGE: Cache the entire poster creation process
@st.cache_data
def create_poster(paper_size, bg_color, line1_text, line1_size, line1_y_mm, line2_text, line2_size, line2_y_mm, tracking):
    """Generates the poster image. This function is cached for performance."""
    scale = get_scale_factor(paper_size)
    width_mm = A3_WIDTH_MM if paper_size == "A3" else A4_WIDTH_MM
    height_mm = A3_HEIGHT_MM if paper_size == "A3" else A4_HEIGHT_MM
    width_px, height_px = mm_to_pixels(width_mm), mm_to_pixels(height_mm)

    poster = Image.new('RGB', (width_px, height_px), bg_color)
    
    texture_bytes = load_image_from_github_cached(GITHUB_TEXTURE_URL)
    if texture_bytes:
        texture = Image.open(texture_bytes)
        texture = texture.resize((width_px, height_px), Image.Resampling.LANCZOS)
        poster = apply_blend_darken(poster, texture).convert('RGB')
    
    main_image_bytes = load_image_from_github_cached(GITHUB_IMAGE_URL)
    if main_image_bytes:
        main_image = Image.open(main_image_bytes).convert('RGBA')
        new_width_px = mm_to_pixels(297 * scale)
        new_height_px = int(new_width_px * (main_image.height / main_image.width))
        main_image = main_image.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
        poster.paste(main_image, ((width_px - new_width_px) // 2, height_px - new_height_px), main_image)
    
    logo_bytes = load_image_from_github_cached(GITHUB_LOGO_URL)
    if logo_bytes:
        logo = Image.open(logo_bytes).convert('RGBA')
        logo_width_px, logo_height_px = mm_to_pixels(217.76 * scale), mm_to_pixels(99.14 * scale)
        logo = logo.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)
        logo_top_px = mm_to_pixels(70.6 * scale)
        poster.paste(logo, ((width_px - logo_width_px) // 2, logo_top_px - (logo_height_px // 2)), logo)
    
    draw = ImageDraw.Draw(poster)
    font_bytes = get_font_bytes()
    if font_bytes:
        font_bytes.seek(0)
        font1 = ImageFont.truetype(font_bytes, int(line1_size * FONT_SCALE_MULTIPLIER))
        font_bytes.seek(0)
        font2 = ImageFont.truetype(font_bytes, int(line2_size * FONT_SCALE_MULTIPLIER))
    else:
        font1, font2 = ImageFont.load_default(), ImageFont.load_default()

    draw_text_with_tracking(draw, line1_text, mm_to_pixels(line1_y_mm), font1, tracking, width_px)
    draw_text_with_tracking(draw, line2_text, mm_to_pixels(line2_y_mm), font2, tracking, width_px)
    
    draw.rectangle([(0, 0), (width_px, height_px)], outline=(0, 0, 0), width=mm_to_pixels(10))
    return poster

# --- Streamlit UI ---
st.title("🎨 Real-Time Poster Generator")
st.markdown("Adjust the settings in the sidebar to see the poster update instantly.")

# --- UI Controls in Sidebar ---
with st.sidebar:
    st.header("Settings")
    
    paper_size = st.radio("Paper Size", ["A3", "A4"], horizontal=True)
    page_height_mm = A3_HEIGHT_MM if paper_size == "A3" else A4_HEIGHT_MM
    
    with st.expander("Background Color", expanded=True):
        color_mode = st.radio("Color Input", ["Color Wheel", "RGB", "CMYK"])
        if color_mode == "Color Wheel":
            h = st.slider("Hue", 0.0, 1.0, 0.0); s = st.slider("Saturation", 0.0, 1.0, 1.0); v = st.slider("Value", 0.0, 1.0, 1.0)
            bg_color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))
        elif color_mode == "RGB":
            r = st.slider("Red", 0, 255, 255); g = st.slider("Green", 0, 255, 255); b = st.slider("Blue", 0, 255, 255)
            bg_color = (r, g, b)
        else:
            c = st.slider("Cyan", 0, 100, 0); m = st.slider("Magenta", 0, 100, 0); y = st.slider("Yellow", 0, 100, 0); k = st.slider("Black (K)", 0, 100, 0)
            bg_color = cmyk_to_rgb(c, m, y, k)
        st.image(Image.new('RGB', (100, 50), bg_color), caption='Selected Color')

    with st.expander("Text & Layout", expanded=True):
        tracking = st.slider("Letter Spacing (Tracking)", -50, 200, 50)
        st.markdown("---")
        line1_text = st.text_input("Line 1 Text", "oasis")
        line1_size = st.slider("Line 1 Font Size (pt)", 50, 250, 162)
        line1_y_mm = st.slider("Line 1 Vertical Position (mm)", 0, page_height_mm, 325)
        st.markdown("---")
        line2_text = st.text_input("Line 2 Text", "chicago")
        line2_size = st.slider("Line 2 Font Size (pt)", 20, 100, 43)
        line2_y_mm = st.slider("Line 2 Vertical Position (mm)", 0, page_height_mm, 387)

# --- Main Page Display ---
# This part now runs very fast thanks to the caching on create_poster
poster_image = create_poster(
    paper_size, bg_color, line1_text, line1_size, line1_y_mm,
    line2_text, line2_size, line2_y_mm, tracking
)

st.subheader("Live Preview")
st.image(poster_image, caption=f"Live Preview ({paper_size})", use_container_width=True)

st.subheader("Download")
# Prepare PNG bytes
img_bytes = io.BytesIO()
poster_image.save(img_bytes, format='PNG', dpi=(DPI, DPI))
img_bytes.seek(0)

# Prepare PDF bytes
pdf_bytes = io.BytesIO()
page_size = A3 if paper_size == "A3" else A4
c = canvas.Canvas(pdf_bytes, pagesize=page_size)

# FIXED: Save poster to a temp buffer and pass it to ImageReader
with io.BytesIO() as temp_img_buffer:
    poster_image.save(temp_img_buffer, format='PNG')
    temp_img_buffer.seek(0)
    # Use ImageReader to robustly handle the image data
    img_for_pdf = ImageReader(temp_img_buffer)
    c.drawImage(img_for_pdf, 0, 0, width=page_size[0], height=page_size[1])

c.save()
pdf_bytes.seek(0)

# Show download buttons
dl_col1, dl_col2 = st.columns(2)
dl_col1.download_button(
    "Download Poster (PNG)", img_bytes, f"poster_{paper_size}.png", "image/png", use_container_width=True
)
dl_col2.download_button(
    "Download Poster (PDF)", pdf_bytes, f"poster_{paper_size}.pdf", "application/pdf", use_container_width=True
)
