import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import numpy as np
from reportlab.lib.pagesizes import A3, A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader # Ensure this is imported

# Page config
st.set_page_config(page_title="Poster Generator", layout="wide")

# (All constants and helper functions like mm_to_pixels, get_scale_factor, etc., remain the same)
# ...
A3_WIDTH_MM = 297
A3_HEIGHT_MM = 420
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 300
MM_TO_INCH = 1 / 25.4
BORDER_MM = 10
FONT_SCALE_MULTIPLIER = 4.0

GITHUB_IMAGE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_image.png"
GITHUB_LOGO_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_logo.png"
GITHUB_TEXTURE_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_texture.png"
GITHUB_FONT_URL = "https://raw.githubusercontent.com/kevfromglasgow/oasisposter/main/oasis_font.otf"

def mm_to_pixels(mm, dpi=DPI):
    return int(mm * MM_TO_INCH * dpi)

def get_scale_factor(paper_size):
    return 1.0 if paper_size == "A3" else A4_WIDTH_MM / A3_WIDTH_MM

def cmyk_to_rgb(c, m, y, k):
    c, m, y, k = c / 100.0, m / 100.0, y / 100.0, k / 100.0
    r = 255 * (1 - c) * (1 - k)
    g = 255 * (1 - m) * (1 - k)
    b = 255 * (1 - y) * (1 - k)
    return int(r), int(g), int(b)

def rgb_to_cmyk(r, g, b):
    if (r, g, b) == (0, 0, 0):
        return 0, 0, 0, 100
    c = 1 - (r / 255.0)
    m = 1 - (g / 255.0)
    y = 1 - (b / 255.0)
    k = min(c, m, y)
    if k == 1.0:
        return 0, 0, 0, 100
    c = int(((c - k) / (1 - k)) * 100)
    m = int(((m - k) / (1 - k)) * 100)
    y = int(((y - k) / (1 - k)) * 100)
    k = int(k * 100)
    return c, m, y, k

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
    result = base_array[:, :, :3] * (1 - fill_factor) + darken * fill_factor
    alpha = (overlay_array[:, :, 3] * opacity / 100.0).astype(int)
    result = np.concatenate([result, alpha[:, :, np.newaxis]], axis=2)
    return Image.fromarray(result.astype('uint8'), 'RGBA')

def draw_text_with_tracking(draw, text, y_pos, font, tracking, poster_width, fill_color=(255, 255, 255)):
    tracking_pixels = (font.size / 1000) * tracking
    char_widths = [draw.textlength(char, font=font) for char in text]
    total_width = sum(char_widths) + tracking_pixels * (len(text) - 1)
    current_x = (poster_width - total_width) / 2
    for i, char in enumerate(text):
        draw.text((current_x, y_pos), char, font=font, fill=fill_color)
        current_x += char_widths[i] + tracking_pixels

def create_poster(paper_size, bg_color, line1_text, line1_size, line1_y_mm, line2_text, line2_size, line2_y_mm, tracking, font):
    # This function remains the same, it still generates an RGB image for display
    # The CMYK conversion will happen right before the PDF is created.
    scale = get_scale_factor(paper_size)
    
    if paper_size == "A3":
        width_mm, height_mm = A3_WIDTH_MM, A3_HEIGHT_MM
    else:
        width_mm, height_mm = A4_WIDTH_MM, A4_HEIGHT_MM
    
    width_px, height_px = mm_to_pixels(width_mm), mm_to_pixels(height_mm)
    
    poster = Image.new('RGB', (width_px, height_px), bg_color)
    
    texture = load_image_from_github(GITHUB_TEXTURE_URL)
    if texture:
        texture = texture.resize((width_px, height_px), Image.Resampling.LANCZOS)
        poster = apply_blend_darken(poster, texture, opacity=100, fill=95).convert('RGB')
    
    main_image = load_image_from_github(GITHUB_IMAGE_URL)
    if main_image:
        if main_image.mode != 'RGBA': main_image = main_image.convert('RGBA')
        new_width_px = mm_to_pixels(297 * scale)
        new_height_px = int(new_width_px * (main_image.height / main_image.width))
        main_image = main_image.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
        poster.paste(main_image, ((width_px - new_width_px) // 2, height_px - new_height_px), main_image)
    
    logo = load_image_from_github(GITHUB_LOGO_URL)
    if logo:
        if logo.mode != 'RGBA': logo = logo.convert('RGBA')
        logo_width_px, logo_height_px = mm_to_pixels(217.76 * scale), mm_to_pixels(99.14 * scale)
        logo = logo.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)
        logo_top_px = mm_to_pixels(70.6 * scale)
        poster.paste(logo, ((width_px - logo_width_px) // 2, logo_top_px - (logo_height_px // 2)), logo)
    
    draw = ImageDraw.Draw(poster)
    
    try:
        font_data = io.BytesIO(requests.get(GITHUB_FONT_URL).content)
        font1 = ImageFont.truetype(font_data, int(line1_size * FONT_SCALE_MULTIPLIER))
        font_data.seek(0)
        font2 = ImageFont.truetype(font_data, int(line2_size * FONT_SCALE_MULTIPLIER))
    except:
        font1, font2 = ImageFont.load_default(), ImageFont.load_default()

    line1_top_px = mm_to_pixels(line1_y_mm)
    line2_top_px = mm_to_pixels(line2_y_mm)

    draw_text_with_tracking(draw, line1_text, line1_top_px, font1, tracking, width_px)
    draw_text_with_tracking(draw, line2_text, line2_top_px, font2, tracking, width_px)
    
    border_px = mm_to_pixels(BORDER_MM)
    draw.rectangle([(0, 0), (width_px, height_px)], outline=(0, 0, 0), width=border_px)
    
    return poster
# --- End of create_poster function ---


# Streamlit UI
st.title("🎨 Poster Generator")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Settings")
    paper_size = st.radio("Paper Size", ["A3", "A4"])
    st.subheader("Background Colour")
    color_mode = st.radio("Colour Input Method", ["Colour Wheel", "RGB", "CMYK"], help="CMYK is recommended for print work.")
    
    if color_mode == "Color Wheel":
        hue = st.slider("Hue", 0.0, 1.0, 0.0); saturation = st.slider("Saturation", 0.0, 1.0, 1.0); value = st.slider("Value", 0.0, 1.0, 1.0)
        rgb = colorsys.hsv_to_rgb(hue, saturation, value)
        bg_color_rgb = tuple(int(c * 255) for c in rgb)
    elif color_mode == "RGB":
        r = st.slider("Red", 0, 255, 255); g = st.slider("Green", 0, 255, 255); b = st.slider("Blue", 0, 255, 255)
        bg_color_rgb = (r, g, b)
    else: # CMYK
        c = st.slider("Cyan", 0, 100, 0); m = st.slider("Magenta", 0, 100, 0); y = st.slider("Yellow", 0, 100, 0); k = st.slider("Black (K)", 0, 100, 0)
        bg_color_rgb = cmyk_to_rgb(c, m, y, k)
    
    # --- ADDED: Soft Proof for Print Preview ---
    st.markdown("##### Colour Previews")
    
    # 1. Show the vibrant screen colour
    swatch_rgb = Image.new('RGB', (100, 50), bg_color_rgb)
    st.image(swatch_rgb, caption="Screen Colour (RGB)")

    # 2. Convert to CMYK and back to RGB to simulate the print conversion
    c, m, y, k = rgb_to_cmyk(bg_color_rgb[0], bg_color_rgb[1], bg_color_rgb[2])
    simulated_rgb = cmyk_to_rgb(c, m, y, k)
    swatch_cmyk_sim = Image.new('RGB', (100, 50), simulated_rgb)
    st.image(swatch_cmyk_sim, caption="Print Preview (Simulated CMYK)")
    st.info("The 'Print Preview' shows how the colour may look when printed. It will often appear less vibrant than the 'Screen Colour'.")
    # --- End of Soft Proof section ---

with col2:
    st.subheader("Text Content")
    page_height_mm = A3_HEIGHT_MM if paper_size == "A3" else A4_HEIGHT_MM
    tracking = st.slider("Letter Spacing (Tracking)", -50, 200, 50, help="Adjusts the space between letters.")
    st.markdown("---")
    line1_text = st.text_input("Line 1 Text", "oasis")
    line1_size = st.slider("Line 1 Font Size (pt)", 50, 250, 162)
    line1_y_mm = st.slider("Line 1 Vertical Position (mm from top)", 0, page_height_mm, 330)
    st.markdown("---")
    line2_text = st.text_input("Line 2 Text", "chicago")
    line2_size = st.slider("Line 2 Font Size (pt)", 20, 100, 43)
    line2_y_mm = st.slider("Line 2 Vertical Position (mm from top)", 0, page_height_mm, 387)

# Live Background Colour Preview (remains unchanged)
st.divider()
st.subheader("Live Background Colour Preview")
preview_width_px = 600
aspect_ratio = (A3_HEIGHT_MM / A3_WIDTH_MM) if paper_size == "A3" else (A4_HEIGHT_MM / A4_WIDTH_MM)
preview_height_px = int(preview_width_px * aspect_ratio)
live_color_preview = Image.new('RGB', (preview_width_px, preview_height_px), bg_color_rgb)
st.image(live_color_preview, caption=f"A real-time preview of your background colour on {paper_size} paper.")

# Generate Button and Final Output
st.divider()
if st.button("Generate Final Poster", key="generate", type="primary"):
    with st.spinner("Creating your masterpiece..."):
        try:
            # Generate the poster in RGB as before
            poster_rgb = create_poster(
                paper_size, bg_color_rgb, line1_text, line1_size, line1_y_mm,
                line2_text, line2_size, line2_y_mm, tracking, None
            )
            
            st.subheader("Your Final Poster (RGB Preview)")
            st.image(poster_rgb, caption=f"Final Poster ({paper_size})")
            
            # --- Download Buttons ---
            # For PNG, we save the RGB version as it's a screen format
            img_bytes = io.BytesIO()
            poster_rgb.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            # --- MODIFIED: PDF Generation with CMYK Conversion ---
            st.info("Generating a print-ready CMYK PDF. The colours in the PDF will match the 'Print Preview'.")
            
            # 1. Convert the final poster to CMYK mode
            poster_cmyk = poster_rgb.convert('CMYK')
            
            # 2. Save the CMYK image to the PDF
            pdf_bytes = io.BytesIO()
            page_size = A3 if paper_size == "A3" else A4
            c = canvas.Canvas(pdf_bytes, pagesize=page_size)
            
            with io.BytesIO() as temp_img_buffer:
                # Save the CMYK image as a TIFF, a good format for CMYK
                poster_cmyk.save(temp_img_buffer, format='TIFF')
                temp_img_buffer.seek(0)
                img_for_pdf = ImageReader(temp_img_buffer)
                c.drawImage(img_for_pdf, 0, 0, width=page_size[0], height=page_size[1])

            c.save()
            pdf_bytes.seek(0)
            # --- End of PDF Generation ---

            dl_col1, dl_col2 = st.columns(2)
            dl_col1.download_button(
                label="Download as PNG (for Screen)", data=img_bytes,
                file_name=f"poster_{paper_size}_RGB.png", mime="image/png", use_container_width=True
            )
            dl_col2.download_button(
                label="Download as PDF (for Print)", data=pdf_bytes,
                file_name=f"poster_{paper_size}_CMYK.pdf", mime="application/pdf", use_container_width=True
            )

        except Exception as e:
            st.error(f"Oh no, something went wrong during poster creation: {e}")
