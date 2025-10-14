import streamlit as st
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import colorsys
import numpy as np
from pathlib import Path

# Page config
st.set_page_config(page_title="Poster Generator", layout="wide")

# Constants
A3_WIDTH_MM = 297
A3_HEIGHT_MM = 420
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
DPI = 72  # pixels per inch
MM_TO_INCH = 1 / 25.4
BORDER_MM = 10

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
    
    c = 1 - (r / 255.0)
    m = 1 - (g / 255.0)
    y = 1 - (b / 255.0)
    
    k = min(c, m, y)
    c = int(((c - k) / (1 - k)) * 100)
    m = int(((m - k) / (1 - k)) * 100)
    y = int(((y - k) / (1 - k)) * 100)
    k = int(k * 100)
    
    return c, m, y, k

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
    
    # Darken blend mode: min(base, overlay)
    darken = np.minimum(base_array[:, :, :3], overlay_array[:, :, :3])
    
    # Apply fill (scale the effect)
    fill_factor = fill / 100.0
    result = base_array[:, :, :3] * (1 - fill_factor) + darken * fill_factor
    
    # Apply opacity
    alpha = (overlay_array[:, :, 3] * opacity / 100.0).astype(int)
    result = np.concatenate([result, alpha[:, :, np.newaxis]], axis=2)
    
    result_img = Image.fromarray(result.astype('uint8'), 'RGBA')
    return result_img

def create_poster(paper_size, bg_color, line1_text, line1_size, line2_text, line2_size, font):
    """Create the poster image"""
    scale = get_scale_factor(paper_size)
    
    if paper_size == "A3":
        width_mm, height_mm = A3_WIDTH_MM, A3_HEIGHT_MM
    else:
        width_mm, height_mm = A4_WIDTH_MM, A4_HEIGHT_MM
    
    width_px = mm_to_pixels(width_mm)
    height_px = mm_to_pixels(height_mm)
    
    # Create base image with background color
    poster = Image.new('RGB', (width_px, height_px), bg_color)
    
    # Load and apply texture
    texture = load_image_from_github(GITHUB_TEXTURE_URL)
    if texture:
        texture = texture.resize((width_px, height_px), Image.Resampling.LANCZOS)
        poster = apply_blend_darken(poster, texture, opacity=100, fill=95)
        poster = poster.convert('RGB')
    
    # Load main image
    main_image = load_image_from_github(GITHUB_IMAGE_URL)
    if main_image:
        # Convert to RGBA if not already to preserve transparency
        if main_image.mode != 'RGBA':
            main_image = main_image.convert('RGBA')
        
        # Scale the image based on paper size
        main_width_mm = 297  # Assume original is A3 width
        new_width_mm = main_width_mm * scale
        new_width_px = mm_to_pixels(new_width_mm)
        aspect_ratio = main_image.height / main_image.width
        new_height_px = int(new_width_px * aspect_ratio)
        
        main_image = main_image.resize((new_width_px, new_height_px), Image.Resampling.LANCZOS)
        
        # Position at bottom center
        x = (width_px - new_width_px) // 2
        y = height_px - new_height_px
        poster.paste(main_image, (x, y), main_image)
    
    # Load and position logo
    logo = load_image_from_github(GITHUB_LOGO_URL)
    if logo:
        # Convert to RGBA for transparency
        if logo.mode != 'RGBA':
            logo = logo.convert('RGBA')
        
        logo_top_mm = 70.6 * scale
        logo_top_px = mm_to_pixels(logo_top_mm)
        
        # Logo dimensions at A3: 217.76W x 99.14H
        logo_width_mm = 217.76 * scale
        logo_height_mm = 99.14 * scale
        logo_width_px = mm_to_pixels(logo_width_mm)
        logo_height_px = mm_to_pixels(logo_height_mm)
        
        logo = logo.resize((logo_width_px, logo_height_px), Image.Resampling.LANCZOS)
        
        # Center horizontally, position from top
        logo_x = (width_px - logo_width_px) // 2
        logo_y = logo_top_px - (logo_height_px // 2)
        poster.paste(logo, (logo_x, logo_y), logo)
    
    # Add text lines
    draw = ImageDraw.Draw(poster)
    
    try:
        font1 = ImageFont.truetype(io.BytesIO(requests.get(GITHUB_FONT_URL).content), line1_size)
        font2 = ImageFont.truetype(io.BytesIO(requests.get(GITHUB_FONT_URL).content), line2_size)
    except:
        font1 = ImageFont.load_default()
        font2 = ImageFont.load_default()
    
    line1_top_mm = 367 * scale
    line1_top_px = mm_to_pixels(line1_top_mm)
    
    # Line 2 is 72pt below Line 1
    line2_offset_px = int((72 * MM_TO_INCH * DPI))
    line2_top_px = line1_top_px + line2_offset_px
    
    # Draw text centered in WHITE for visibility on blue background
    bbox1 = draw.textbbox((0, 0), line1_text, font=font1)
    line1_width = bbox1[2] - bbox1[0]
    line1_x = (width_px - line1_width) // 2
    draw.text((line1_x, line1_top_px), line1_text, fill=(255, 255, 255), font=font1)
    
    bbox2 = draw.textbbox((0, 0), line2_text, font=font2)
    line2_width = bbox2[2] - bbox2[0]
    line2_x = (width_px - line2_width) // 2
    draw.text((line2_x, line2_top_px), line2_text, fill=(255, 255, 255), font=font2)
    
    # Add 10mm black border - from edge to edge
    border_mm = 10
    border_px = mm_to_pixels(border_mm)
    
    # Draw rectangle from outer edge (0,0) to inner edge (border_px, border_px) on each side
    draw.rectangle(
        [(0, 0), (width_px, height_px)],
        outline=(0, 0, 0),
        width=border_px
    )
    
    return poster

# Streamlit UI
st.title("🎨 Poster Generator")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Settings")
    
    # Paper size
    paper_size = st.radio("Paper Size", ["A3", "A4"])
    
    # Color selection
    st.subheader("Background Color")
    color_mode = st.radio("Color Input Method", ["Color Wheel", "RGB", "CMYK"])
    
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
    
    else:  # CMYK
        c = st.slider("Cyan", 0, 100, 0)
        m = st.slider("Magenta", 0, 100, 0)
        y = st.slider("Yellow", 0, 100, 0)
        k = st.slider("Black (K)", 0, 100, 0)
        bg_color = cmyk_to_rgb(c, m, y, k)
    
    # Show color preview
    col_preview = st.columns(1)[0]
    color_preview = Image.new('RGB', (100, 50), bg_color)
    st.image(color_preview, use_container_width=False)

with col2:
    st.subheader("Text Content")
    
    line1_text = st.text_input("Line 1 Text", "oasis")
    line1_size = st.slider("Line 1 Font Size (pt)", 50, 250, 161)
    
    line2_text = st.text_input("Line 2 Text", "chicago")
    line2_size = st.slider("Line 2 Font Size (pt)", 20, 100, 43)
    
    st.info("Line 2 will appear 72pt below Line 1")

# Generate button
if st.button("Generate Poster", key="generate"):
    with st.spinner("Creating your poster..."):
        try:
            poster = create_poster(
                paper_size,
                bg_color,
                line1_text,
                line1_size,
                line2_text,
                line2_size,
                None
            )
            
            # Display poster
            st.image(poster, caption=f"Preview ({paper_size})")
            
            # Download button
            img_bytes = io.BytesIO()
            poster.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            st.download_button(
                label="Download Poster (PNG)",
                data=img_bytes,
                file_name=f"poster_{paper_size}.png",
                mime="image/png"
            )
        except Exception as e:
            st.error(f"Error generating poster: {e}")
