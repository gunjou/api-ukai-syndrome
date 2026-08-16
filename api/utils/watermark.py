from io import BytesIO
from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFilter,
    ImageFont,
    ImageOps,
)


# ============================================================
# PATH
# ============================================================

# Struktur:
#
# api/
# ├── assets/
# │   ├── logo_syndrome.svg
# │   └── logo_syndrome.png
# └── utils/
#     └── watermark.py

BASE_DIR = Path(__file__).resolve().parents[1]

LOGO_PATH = BASE_DIR / "assets" / "logo_syndrome.png"


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def add_watermark(
    image_file,
    watermark_text: str,
    date_text: str,
    time_text: str,
    latitude: float | None = None,
    longitude: float | None = None,
    accuracy: float | None = None,
):
    """
    Menambahkan modern camera-style watermark
    pada gambar.

    Watermark berada di kanan bawah.

    Isi watermark:
        - Logo
        - SYNDROME UKAI
        - ATTENDANCE VERIFICATION
        - Watermark title
        - Tanggal
        - Waktu
        - Latitude
        - Longitude
        - GPS accuracy

    Args:
        image_file:
            FileStorage dari Flask request.files.

        watermark_text:
            Judul watermark.

            Contoh:
                "CHECK-IN MENTOR"

        date_text:
            Tanggal.

            Contoh:
                "16 August 2026"

        time_text:
            Waktu.

            Contoh:
                "17:37:20 WIB"

        latitude:
            Latitude GPS.

        longitude:
            Longitude GPS.

        accuracy:
            GPS accuracy dalam meter.

    Returns:
        tuple:
            (
                BytesIO,
                filename,
                mimetype
            )

    Raises:
        ValueError:
            Jika image tidak valid atau logo tidak ditemukan.
    """

    if not image_file:
        raise ValueError(
            "Image file wajib diisi"
        )

    # ========================================================
    # LOAD IMAGE
    # ========================================================

    try:
        image = Image.open(
            image_file.stream
        )

        image.load()

    except Exception as e:
        raise ValueError(
            f"File bukan gambar yang valid: {e}"
        )

    # ========================================================
    # FIX EXIF ORIENTATION
    #
    # Kamera HP sering menyimpan orientation
    # di metadata EXIF.
    # ========================================================

    try:
        image = ImageOps.exif_transpose(
            image
        )

    except Exception:
        pass

    # ========================================================
    # CONVERT TO RGBA
    # ========================================================

    image = image.convert(
        "RGBA"
    )

    width, height = image.size

    # ========================================================
    # RESPONSIVE SCALE
    #
    # Baseline:
    #
    # 1080 px -> 1.0
    # 2160 px -> 2.0
    # 720 px  -> 0.67
    #
    # Dibatasi agar watermark tidak terlalu kecil
    # atau terlalu besar.
    # ========================================================

    scale = (
        min(width, height)
        / 1080
    )

    scale = max(
        0.65,
        min(scale, 3.0),
    )

    # ========================================================
    # GENERAL DIMENSIONS
    # ========================================================

    margin = int(
        28 * scale
    )

    panel_padding = int(
        20 * scale
    )

    panel_radius = int(
        24 * scale
    )

    # ========================================================
    # PANEL WIDTH
    #
    # Maksimal 400 * scale
    # ========================================================

    panel_width = int(
        min(
            width * 0.86,
            400 * scale,
        )
    )

    # Pastikan panel tidak keluar dari image.

    max_panel_width = (
        width
        - (margin * 2)
    )

    panel_width = min(
        panel_width,
        max_panel_width,
    )

    # ========================================================
    # FONT
    # ========================================================

    brand_font = _get_font(
        int(20 * scale),
        bold=True,
    )

    subtitle_font = _get_font(
        int(13 * scale),
        bold=False,
    )

    title_font = _get_font(
        int(17 * scale),
        bold=True,
    )

    date_font = _get_font(
        int(17 * scale),
        bold=True,
    )

    time_font = _get_font(
        int(29 * scale),
        bold=True,
    )

    # GPS dibuat lebih besar
    gps_font = _get_font(
        int(18 * scale),
        bold=True,
    )

    meta_label_font = _get_font(
        int(14 * scale),
        bold=True,
    )

    meta_font = _get_font(
        int(14 * scale),
        bold=False,
    )

    # ========================================================
    # LOGO
    # ========================================================

    logo_size = int(
        48 * scale
    )

    logo = _load_logo(
        LOGO_PATH,
        logo_size,
    )

    # ========================================================
    # DRAW CONTEXT
    # ========================================================

    dummy_image = Image.new(
        "RGBA",
        (1, 1),
    )

    dummy_draw = ImageDraw.Draw(
        dummy_image
    )

    # ========================================================
    # NORMALIZE TEXT
    # ========================================================

    watermark_text = (
        watermark_text
        or "CHECK-IN MENTOR"
    )

    date_text = (
        date_text
        or ""
    )

    time_text = (
        time_text
        or ""
    )

    # ========================================================
    # GPS TEXT
    # ========================================================

    gps_text = None

    if (
        latitude is not None
        and longitude is not None
    ):
        gps_text = (
            f"{latitude:.6f}, "
            f"{longitude:.6f}"
        )

    # ========================================================
    # ACCURACY TEXT
    # ========================================================

    accuracy_text = None

    if accuracy is not None:
        accuracy_text = (
            f"±{accuracy:.0f} m"
        )

    # ========================================================
    # CONTENT WIDTH
    # ========================================================

    content_width = (
        panel_width
        - (panel_padding * 2)
    )

    # ========================================================
    # BRAND SECTION
    # ========================================================

    brand_height = int(
        54 * scale
    )

    # ========================================================
    # SPACING
    # ========================================================

    section_spacing = int(
        12 * scale
    )

    small_spacing = int(
        6 * scale
    )

    # ========================================================
    # PANEL HEIGHT CALCULATION
    # ========================================================

    total_height = (
        brand_height
    )

    # --------------------------------------------------------
    # CHECK-IN TITLE
    # --------------------------------------------------------

    total_height += (
        section_spacing
        + int(24 * scale)
    )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    if date_text:

        total_height += (
            small_spacing
            + int(24 * scale)
        )

    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if time_text:

        total_height += (
            int(2 * scale)
            + int(38 * scale)
        )

    # --------------------------------------------------------
    # GPS
    # --------------------------------------------------------

    if gps_text:

        total_height += (
            section_spacing
            + int(14 * scale)
            + int(24 * scale)
        )

    # --------------------------------------------------------
    # ACCURACY
    # --------------------------------------------------------

    if accuracy_text:

        total_height += (
            small_spacing
            + int(19 * scale)
        )

    # --------------------------------------------------------
    # FINAL PANEL HEIGHT
    # --------------------------------------------------------

    panel_height = (
        total_height
        + panel_padding * 2
    )

    # ========================================================
    # PANEL POSITION
    #
    # RIGHT BOTTOM
    # ========================================================

    panel_x2 = (
        width
        - margin
    )

    panel_y2 = (
        height
        - margin
    )

    panel_x1 = (
        panel_x2
        - panel_width
    )

    panel_y1 = (
        panel_y2
        - panel_height
    )

    # ========================================================
    # OVERLAY
    # ========================================================

    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0),
    )

    # ========================================================
    # SHADOW
    # ========================================================

    shadow = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0),
    )

    shadow_draw = ImageDraw.Draw(
        shadow
    )

    shadow_offset = int(
        7 * scale
    )

    shadow_draw.rounded_rectangle(
        (
            panel_x1,
            panel_y1 + shadow_offset,
            panel_x2,
            panel_y2 + shadow_offset,
        ),
        radius=panel_radius,
        fill=(
            0,
            0,
            0,
            125,
        ),
    )

    shadow = shadow.filter(
        ImageFilter.GaussianBlur(
            int(12 * scale)
        )
    )

    overlay = Image.alpha_composite(
        overlay,
        shadow,
    )

    # ========================================================
    # GRADIENT PANEL
    #
    # Top:
    # rgba(155, 50, 25, 225)
    #
    # Bottom:
    # rgba(66, 19, 18, 225)
    # ========================================================

    gradient_panel = _create_gradient_panel(
        width=int(panel_width),
        height=int(panel_height),
        radius=panel_radius,
        top_color=(
            48,
            16,
            16,
            225,
        ),
        bottom_color=(
            116,
            32,
            32,
            225,
        ),
    )

    overlay.alpha_composite(
        gradient_panel,
        (
            int(panel_x1),
            int(panel_y1),
        ),
    )

    draw = ImageDraw.Draw(
        overlay
    )

    # ========================================================
    # PANEL BORDER
    # ========================================================

    draw.rounded_rectangle(
        (
            panel_x1,
            panel_y1,
            panel_x2,
            panel_y2,
        ),
        radius=panel_radius,
        outline=(
            255,
            255,
            255,
            55,
        ),
        width=max(
            1,
            int(1.2 * scale),
        ),
    )

    # ========================================================
    # CURRENT Y
    # ========================================================

    content_x = (
        panel_x1
        + panel_padding
    )

    current_y = (
        panel_y1
        + panel_padding
    )

    # ========================================================
    # BRAND
    # ========================================================

    logo_y = (
        current_y
        + (
            brand_height
            - logo_size
        ) // 2
    )

    overlay.alpha_composite(
        logo,
        (
            int(content_x),
            int(logo_y),
        ),
    )

    # --------------------------------------------------------
    # Brand text
    # --------------------------------------------------------

    brand_x = (
        content_x
        + logo_size
        + int(14 * scale)
    )

    brand_y = (
        current_y
        + int(5 * scale)
    )

    draw.text(
        (
            int(brand_x),
            int(brand_y),
        ),
        "SYNDROME UKAI",
        font=brand_font,
        fill=(
            255,
            255,
            255,
            245,
        ),
    )

    # --------------------------------------------------------
    # Subtitle
    # --------------------------------------------------------

    draw.text(
        (
            int(brand_x),
            int(
                brand_y
                + int(24 * scale)
            ),
        ),
        "ATTENDANCE VERIFICATION",
        font=subtitle_font,
        fill=(
            235,
            205,
            198,
            205,
        ),
    )

    current_y += brand_height

    # ========================================================
    # CHECK-IN TITLE
    # ========================================================

    current_y += section_spacing

    draw.text(
        (
            int(content_x),
            int(current_y),
        ),
        watermark_text,
        font=title_font,
        fill=(
            255,
            255,
            255,
            240,
        ),
    )

    current_y += int(
        24 * scale
    )

    # ========================================================
    # DATE
    # ========================================================

    if date_text:

        current_y += small_spacing

        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            date_text.upper(),
            font=date_font,
            fill=(
                245,
                220,
                215,
                225,
            ),
        )

        current_y += int(
            24 * scale
        )

    # ========================================================
    # TIME
    # ========================================================

    if time_text:

        current_y += int(
            2 * scale
        )

        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            time_text,
            font=time_font,
            fill=(
                255,
                255,
                255,
                255,
            ),
        )

        current_y += int(
            38 * scale
        )

    # ========================================================
    # GPS
    # ========================================================

    if gps_text:

        current_y += section_spacing

        # Label
        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            "GPS",
            font=meta_label_font,
            fill=(
                235,
                190,
                180,
                215,
            ),
        )

        current_y += int(
            14 * scale
        )

        # Latitude + Longitude
        #
        # Dibuat lebih besar daripada metadata lainnya.

        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            gps_text,
            font=gps_font,
            fill=(
                255,
                255,
                255,
                245,
            ),
        )

        current_y += int(
            24 * scale
        )

    # ========================================================
    # GPS ACCURACY
    # ========================================================

    if accuracy_text:

        current_y += small_spacing

        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            "GPS ACCURACY",
            font=meta_label_font,
            fill=(
                235,
                190,
                180,
                215,
            ),
        )

        current_y += int(
            14 * scale
        )

        draw.text(
            (
                int(content_x),
                int(current_y),
            ),
            accuracy_text,
            font=meta_font,
            fill=(
                245,
                220,
                215,
                220,
            ),
        )

    # ========================================================
    # COMPOSITE
    # ========================================================

    result = Image.alpha_composite(
        image,
        overlay,
    )

    # ========================================================
    # OUTPUT
    # ========================================================

    output = BytesIO()

    original_mimetype = (
        image_file.mimetype or ""
    ).lower()

    # --------------------------------------------------------
    # JPEG
    # --------------------------------------------------------

    if original_mimetype in (
        "image/jpeg",
        "image/jpg",
    ):

        result = result.convert(
            "RGB"
        )

        result.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        mimetype = "image/jpeg"
        extension = ".jpg"

    # --------------------------------------------------------
    # WEBP
    # --------------------------------------------------------

    elif original_mimetype == "image/webp":

        result.save(
            output,
            format="WEBP",
            quality=92,
            method=6,
        )

        mimetype = "image/webp"
        extension = ".webp"

    # --------------------------------------------------------
    # PNG
    # --------------------------------------------------------

    elif original_mimetype == "image/png":

        result.save(
            output,
            format="PNG",
            optimize=True,
        )

        mimetype = "image/png"
        extension = ".png"

    # --------------------------------------------------------
    # UNKNOWN FORMAT
    # --------------------------------------------------------

    else:

        result = result.convert(
            "RGB"
        )

        result.save(
            output,
            format="JPEG",
            quality=92,
            optimize=True,
        )

        mimetype = "image/jpeg"
        extension = ".jpg"

    # ========================================================
    # RESET STREAM
    # ========================================================

    output.seek(0)

    # ========================================================
    # FILENAME
    # ========================================================

    original_filename = (
        image_file.filename
        or "evidence"
    )

    original_stem = Path(
        original_filename
    ).stem

    filename = (
        f"{original_stem}"
        f"_watermarked"
        f"{extension}"
    )

    return (
        output,
        filename,
        mimetype,
    )


# ============================================================
# GRADIENT PANEL
# ============================================================

def _create_gradient_panel(
    width: int,
    height: int,
    radius: int,
    top_color: tuple,
    bottom_color: tuple,
):
    """
    Membuat panel gradient vertikal.

    Gradient:

        top_color
            ↓
        bottom_color

    Contoh:

        rgba(155, 50, 25, 225)
                ↓
        rgba(66, 19, 18, 225)

    Gradient dibuat sebagai image terpisah,
    kemudian diberi rounded mask.
    """

    gradient = Image.new(
        "RGBA",
        (
            width,
            height,
        ),
    )

    pixels = gradient.load()

    top_r, top_g, top_b, top_a = (
        top_color
    )

    bottom_r, bottom_g, bottom_b, bottom_a = (
        bottom_color
    )

    for y in range(height):

        if height <= 1:
            ratio = 0.0
        else:
            ratio = (
                y
                / (height - 1)
            )

        r = int(
            top_r
            + (
                bottom_r
                - top_r
            )
            * ratio
        )

        g = int(
            top_g
            + (
                bottom_g
                - top_g
            )
            * ratio
        )

        b = int(
            top_b
            + (
                bottom_b
                - top_b
            )
            * ratio
        )

        a = int(
            top_a
            + (
                bottom_a
                - top_a
            )
            * ratio
        )

        for x in range(width):

            pixels[x, y] = (
                r,
                g,
                b,
                a,
            )

    # ========================================================
    # ROUNDED MASK
    # ========================================================

    mask = Image.new(
        "L",
        (
            width,
            height,
        ),
        0,
    )

    mask_draw = ImageDraw.Draw(
        mask
    )

    mask_draw.rounded_rectangle(
        (
            0,
            0,
            width - 1,
            height - 1,
        ),
        radius=radius,
        fill=255,
    )

    gradient.putalpha(
        mask
    )

    return gradient


# ============================================================
# FONT
# ============================================================

def _get_font(
    font_size: int,
    bold: bool = False,
):
    """
    Mencari font yang tersedia pada environment.

    Priority:
        1. Linux
        2. macOS
        3. Windows

    Jika tidak ditemukan,
    menggunakan default font Pillow.
    """

    if bold:

        font_candidates = [
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",

            # macOS
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",

            # Windows
            "C:/Windows/Fonts/arialbd.ttf",
        ]

    else:

        font_candidates = [
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",

            # macOS
            "/System/Library/Fonts/Supplemental/Arial.ttf",

            # Windows
            "C:/Windows/Fonts/arial.ttf",
        ]

    for font_path in font_candidates:

        try:

            return ImageFont.truetype(
                font_path,
                font_size,
            )

        except (
            OSError,
            IOError,
        ):
            continue

    return ImageFont.load_default()


# ============================================================
# LOGO
# ============================================================

def _load_logo(
    logo_path: Path,
    size: int,
):
    """
    Load logo PNG dan resize.

    Logo sebaiknya memiliki background
    transparan.
    """

    if not logo_path.exists():

        raise ValueError(
            f"Logo tidak ditemukan: {logo_path}"
        )

    try:

        logo = Image.open(
            logo_path
        ).convert("RGBA")

        logo = logo.resize(
            (
                size,
                size,
            ),
            Image.Resampling.LANCZOS,
        )

        return logo

    except Exception as e:

        raise ValueError(
            f"Gagal memproses logo: {e}"
        )
