import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import numpy as np
import math # Added for colour difference calculation
from pathlib import Path
from reportlab.lib.pagesizes import A3, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

# Page config
st.set_page_config(page_title="Poster Generator", layout="wide")

# ... (All of your existing constants and functions like mm_to_pixels, get_scale_factor etc. remain exactly the same) ...
# Constants
A3_WIDTH_MM = 297
A3_HEIGHT_MM = 420
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 300  # pixels per inch
MM_TO_INCH = 1 / 25.4
BORDER_MM = 10
FONT_SCALE_MULTIPLIER = 4.0  # Adjust this to match Photoshop font sizes

# GitHub raw content URLs
GITHUB_IMAGE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_image.png"
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_logo.png"
GITHUB_TEXTURE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_texture.png"
GITHUB_FONT_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_font.otf"

def mm_to_pixels(mm, dpi=DPI):
    """Convert millimeters to pixels"""
    return int(mm * MM_TO_INCH * dpi)

def get_scale_factor(paper_size):
    """Get scale factor from A3 to selected paper size"""
    if paper_size == "A3":
        return 1.0
    else:  # A4
        return A4_WIDTH_MM / A3_WIDTH_MM

def cmyk_to_rgb(c, m, y, k):
    """Convert CMYK to RGB"""
    c = c / 100.0
    m = m / 100.0
    y = y / 100.0
    k = k / 100.0
    
    r = 255 * (1 - c) * (1 - k)
    g = 255 * (1 - m) * (1 - k)
    b = 255 * (1 - y) * (1 - k)
    
    return int(r), int(g), int(b)

def rgb_to_cmyk(r, g, b):
    """Convert RGB to CMYK"""
    if (r, g, b) == (0, 0, 0):
        return 0, 0, 0, 100
    
    # an empty case might lead to a division by zero error
    if r == 255 and g == 255 and b == 255:
        return 0, 0, 0, 0

    c = 1 - (r / 255.0)
    m = 1 - (g / 255.0)
    y = 1 - (b / 255.0)
    
    k = min(c, m, y)
    
    # Check for division by zero
    if (1 - k) == 0:
        return 0, 0, 0, 100

    c = int(((c - k) / (1 - k)) * 100)
    m = int(((m - k) / (1 - k)) * 100)
    y = int(((y - k) / (1 - k)) * 100)
    k = int(k * 100)
    
    return c, m, y, k

# --- ADDED: The Gamut Warning Function ---
def check_gamut_warning(original_rgb):
    """
    Checks if an RGB color is "out of gamut" for CMYK printing by doing a
    round-trip conversion and checking the color difference.
    """
    if not all(isinstance(c, int) for c in original_rgb):
        return False, None

    # 1. Convert original RGB to CMYK
    c, m, y, k = rgb_to_cmyk(*original_rgb)

    # 2. Convert that CMYK back to RGB
    round_trip_rgb = cmyk_to_rgb(c, m, y, k)

    # 3. Calculate the difference between the original and round-trip colors
    # A simple "Euclidean distance" in the color space
    r1, g1, b1 = original_rgb
    r2, g2, b2 = round_trip_rgb
    color_difference = math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)

    # 4. If the difference is significant, issue a warning.
    # The threshold of 30 is a good starting point, can be adjusted.
    if color_difference > 30:
        return True, round_trip_rgb
    else:
        return False, None
# --- END of new function ---

def load_image_from_github(url):
    """Load an image from GitHub URL"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        st.error(f"Failed to load image from {url}: {e}")
        return None

def apply_blend_darken(base, overlay, opacity, fill):
    """Apply Darken blend mode with opacity and fill"""
    overlay_array = np.array(overlay.convert('RGBA')).astype(float)
    base_array = np.array(base.convert('RGBA')).astype(float)
    
    darken = np.minimum(base_array[:, :, :3], overlay_array[:, :, :3])
    fill_factor = fill / 100.0
    result = base_array[:, :, :3] * (1 - fill_factor) + darken * fill_factor
    alpha = (overlay_array[:, :, 3] * opacity / 100.0).astype(int)
    result = np.concatenate([result, alpha[:, :, np.newaxis]], axis=2)
    
    result_img = Image.fromarray(result.astype('uint8'), 'RGBA')
    return result_img

def draw_text_with_tracking(draw, text, y_pos, font, tracking, poster_width, fill_color=(255, 255, 255)):
    """Draws horizontally centered text with character spacing (tracking)."""
    tracking_pixels = (font.size / 1000) * tracking
    char_widths = [draw.textlength(char, font=font) for char in text]
    total_width = sum(char_widths) + tracking_pixels * (len(text) - 1)
    current_x = (poster_width - total_width) / 2
    for i, char in enumerate(text):
        draw.text((current_x, y_pos), char, font=font, fill=fill_color)
        current_x += char_widths[i] + tracking_pixels

def create_poster(paper_size, bg_color, line1_text, line1_size, line1_y_mm, line2_text, line2_size, line2_y_mm, tracking, font):
    # This function remains the same
    scale = get_scale_factor(paper_size)
    
    if paper_size == "A3":
        width_mm, height_mm = A3_WIDTH_MM, A3_HEIGHT_MM
    else:
        width_mm, height_mm = A4_WIDTH_MM, A4_HEIGHT_MM
    
    width_px = mm_to_pixels(width_mm)
    height_px = mm_to_pixels(height_mm)
    
    poster = Image.new('RGB', (width_px, height_px), bg_color)
    
    texture = load_image_from_github(GITHUB_TEXTURE_URL)
    if texture:
        texture = texture.resize((width_px, height_px), Image.Resampling.LANCZOS)
        poster = apply_blend_darken(poster, texture, opacity=100, fill=95)
        poster = poster.convert('RGB')
    
    main_image = load_image_from_github(GITHUB_IMAGE_URL)
    if main_image:
        if main_image.mode != 'RGBA':
            main_image = main_image.convert('RGBA')
        
        main_width_mm = 297
        new_width_mm = main_width_mm * scale
        new_width_px = mm_to_pixels(new_width_mm)
        aspect_ratio = main_image.height / main_image.width
        new_height_px = int(new_width_px * aspect_ratio)
        main_image = main_image.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
        
        x = (width_px - new_width_px) // 2
        y = height_px - new_height_px
        poster.paste(main_image, (x, y), main_image)
    
    logo = load_image_from_github(GITHUB_LOGO_URL)
    if logo:
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        logo_top_mm = 70.6 * scale
        logo_top_px = mm_to_pixels(logo_top_mm)
        logo_width_mm = 217.76 * scale
        logo_height_mm = 99.14 * scale
        logo_width_px = mm_to_pixels(logo_width_mm)
        logo_height_px = mm_to_pixels(logo_height_mm)
        logo = logo.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)
        
        logo_x = (width_px - logo_width_px) // 2
        logo_y = logo_top_px - (logo_height_px // 2)
        poster.paste(logo, (logo_x, logo_y), logo)
    
    draw = ImageDraw.Draw(poster)
    
    try:
        font_data = io.BytesIO(requests.get(GITHUB_FONT_URL).content)
        font1 = ImageFont.truetype(font_data, int(line1_size * FONT_SCALE_MULTIPLIER))
        font_data.seek(0)
        font2 = ImageFont.truetype(font_data, int(line2_size * FONT_SCALE_MULTIPLIER))
    except:
        font1 = ImageFont.load_default()
        font2 = ImageFont.load_default()

    line1_top_px = mm_to_pixels(line1_y_mm)
    line2_top_px = mm_to_pixels(line2_y_mm)

    draw_text_with_tracking(draw, line1_text, line1_top_px, font1, tracking, width_px)
    draw_text_with_tracking(draw, line2_text, line2_top_px, font2, tracking, width_px)
    
    border_px = mm_to_pixels(BORDER_MM)
    draw.rectangle([(0, 0), (width_px, height_px)], outline=(0, 0, 0), width=border_px)
    
    return poster

# Streamlit UI
st.title("🎨 Poster Generator")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Settings")
    
    paper_size = st.radio("Paper Size", ["A3", "A4"])
    
    st.subheader("Background Color")
    color_mode = st.radio("Color Input Method", ["Color Wheel", "RGB", "CMYK"])
    
    # Initialise bg_color
    bg_color = (255, 255, 255)

    if color_mode == "Color Wheel":
        hue = st.slider("Hue", 0.0, 1.0, 0.0)
        saturation = st.slider("Saturation", 0.0, 1.0, 1.0)
        value = st.slider("Value", 0.0, 1.0, 1.0)
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        bg_color = tuple(int(c * 255) for c in rgb)
    elif color_mode == "RGB":
        r = st.slider("Red", 0, 255, 255)
        g = st.slider("Green", 0, 255, 255)
        b = st.slider("Blue", 0, 255, 255)
        bg_color = (r, g, b)
    else: # CMYK
        c = st.slider("Cyan", 0, 100, 0)
        m = st.slider("Magenta", 0, 100, 0)
        y = st.slider("Yellow", 0, 100, 0)
        k = st.slider("Black (K)", 0, 100, 0)
        bg_color = cmyk_to_rgb(c, m, y, k)
    
    # --- UI CHANGE: Gamut Warning Display ---
    is_out_of_gamut, closest_cmyk_in_rgb = check_gamut_warning(bg_color)

    # Create two columns for the color swatches
    swatch_col1, swatch_col2 = st.columns(2)
    with swatch_col1:
        color_preview_swatch = Image.new('RGB', (100, 50), bg_color)
        st.image(color_preview_swatch, caption="Screen Colour (RGB)")

    if is_out_of_gamut:
        with swatch_col2:
            # Show the closest printable color next to the chosen one
            cmyk_preview_swatch = Image.new('RGB', (100, 50), closest_cmyk_in_rgb)
            st.image(cmyk_preview_swatch, caption="Closest Print Colour")
        st.warning("This colour is very vibrant and may appear different when printed. The swatch on the right is a closer representation of the printed colour.", icon="🎨")
    # --- END of UI Change ---


with col2:
    # ... (The text content part of your UI remains exactly the same) ...
    st.subheader("Text Content")
    
    if paper_size == "A3":
        page_height_mm = A3_HEIGHT_MM
    else:
        page_height_mm = A4_HEIGHT_MM

    tracking = st.slider("Letter Spacing (Tracking)", -50, 200, 50, help="Adjusts the space between letters. Standard design value (+50).")

    st.markdown("---")
    
    line1_text = st.text_input("Line 1 Text", "oasis")
    line1_size = st.slider("Line 1 Font Size (pt)", 50, 250, 162)
    line1_y_mm = st.slider("Line 1 Vertical Position (mm from top)", 0, page_height_mm, 330)
    
    st.markdown("---")

    line2_text = st.text_input("Line 2 Text", "chicago")
    line2_size = st.slider("Line 2 Font Size (pt)", 20, 100, 43)
    line2_y_mm = st.slider("Line 2 Vertical Position (mm from top)", 0, page_height_mm, 387)

# ... (The rest of your code, including the live preview and generate button, remains exactly the same) ...
st.divider()
st.subheader("Live Background Colour Preview")

preview_width_px = 600
if paper_size == "A3":
    aspect_ratio = A3_HEIGHT_MM / A3_WIDTH_MM
else:
    aspect_ratio = A4_HEIGHT_MM / A4_WIDTH_MM
preview_height_px = int(preview_width_px * aspect_ratio)

live_color_preview = Image.new('RGB', (preview_width_px, preview_height_px), bg_color)
st.image(live_color_preview, caption=f"A real-time preview of your background colour on {paper_size} paper.")


st.divider()
if st.button("Generate Final Poster", key="generate", type="primary"):
    with st.spinner("Creating your masterpiece..."):
        try:
            poster = create_poster(
                paper_size, bg_color, line1_text, line1_size, line1_y_mm,
                line2_text, line2_size, line2_y_mm, tracking, None
            )
            
            st.subheader("Your Final Poster")
            st.image(poster, caption=f"Final Poster ({paper_size})")
            
            img_bytes = io.BytesIO()
            poster.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            pdf_bytes = io.BytesIO()
            page_size = A3 if paper_size == "A3" else A4
            c = canvas.Canvas(pdf_bytes, pagesize=page_size)

            from reportlab.lib.utils import ImageReader
            temp_buffer = io.BytesIO()
            poster.save(temp_buffer, format='PNG')
            temp_buffer.seek(0)
            c.drawImage(ImageReader(temp_buffer), 0, 0, width=page_size[0], height=page_size[1])

            c.save()
            pdf_bytes.seek(0)

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    label="Download Poster (PNG)",
                    data=img_bytes,
                    file_name=f"poster_{paper_size}.png",
                    mime="image/png",
                    use_container_width=True
                )
            with dl_col2:
                st.download_button(
                    label="Download Poster (PDF)",
                    data=pdf_bytes,
                    file_name=f"poster_{paper_size}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        except Exception as e:
            st.error(f"Oh no, something went wrong during poster creation: {e}")
