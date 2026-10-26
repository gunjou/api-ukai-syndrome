import io
import os
import calendar
from datetime import date, datetime, time

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from ..utils.config import get_wib



# ============================================================================ #
#                                #ANCHOR - CONFIG                              #
# ============================================================================ #

# Tarif honor mentor per 1 jam mengajar (Rupiah)
PAYROLL_TARIF_PER_JAM = int(os.getenv("PAYROLL_TARIF_PER_JAM", 100000))

STATUS_SESI_PENUH = "PENUH"
STATUS_SESI_SEBAGIAN = "SEBAGIAN"
STATUS_SESI_BELUM_CHECK_OUT = "BELUM_CHECK_OUT"
STATUS_SESI_TIDAK_HADIR = "TIDAK_HADIR"

STATUS_SESI_COUNTER = {
    STATUS_SESI_PENUH: "sesi_penuh",
    STATUS_SESI_SEBAGIAN: "sesi_sebagian",
    STATUS_SESI_BELUM_CHECK_OUT: "sesi_belum_check_out",
    STATUS_SESI_TIDAK_HADIR: "sesi_tidak_hadir"
}

NAMA_BULAN = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


# ============================================================================ #
#                               #ANCHOR - HELPER                               #
# ============================================================================ #

def get_periode_bulan(tahun, bulan):
    """Tanggal 1 s/d tanggal terakhir bulan (28/29/30/31)"""

    last_day = calendar.monthrange(tahun, bulan)[1]

    return date(tahun, bulan, 1), date(tahun, bulan, last_day)


def hitung_honor(menit):
    """Honor = menit x tarif / 60, dibulatkan ke rupiah terdekat (tanpa float)"""

    return (int(menit) * PAYROLL_TARIF_PER_JAM + 30) // 60


def format_durasi(menit):
    """165 -> '2 jam 45 menit', 180 -> '3 jam', 0 -> '0 menit'"""

    if menit is None:
        return None

    jam, sisa = divmod(int(menit), 60)

    if jam and sisa:
        return f"{jam} jam {sisa} menit"

    if jam:
        return f"{jam} jam"

    return f"{sisa} menit"


def format_value(value):
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.strftime("%H:%M:%S")

    return value


# ============================================================================ #
#                          #ANCHOR - SLIP HONOR (PDF)                          #
# ============================================================================ #

BRAND_NAME = "Syndrome Ukai"

# api/export/e_slip_payroll.py -> api/assets/logo_syndrome.png
BRAND_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "logo_syndrome.png"
)

# ------------------------------------------------------------------ #
# Palet warna brand Syndrome Ukai
# - Emas  #D38C0F : warna logo  -> aksen (brand, garis, highlight)
# - Marun #8F1B1B : warna aksen -> struktur (header tabel, judul, total)
# - Turunan hangat untuk background, border, dan teks
# ------------------------------------------------------------------ #

SLIP_HEX_GOLD = "#D38C0F"
SLIP_HEX_GOLD_DARK = "#A86F0B"      # emas gelap, kontras lebih baik untuk teks kecil
SLIP_HEX_MAROON = "#8F1B1B"
SLIP_HEX_MAROON_DARK = "#6E1414"
SLIP_HEX_CREAM = "#FBF4E6"          # background kartu & baris total
SLIP_HEX_CREAM_SOFT = "#FDFAF4"     # zebra baris tabel
SLIP_HEX_BORDER = "#EAD9BF"
SLIP_HEX_TEXT = "#2B1D1A"           # cokelat sangat gelap (lebih hangat dari hitam)
SLIP_HEX_MUTED = "#7A6A60"

SLIP_COLOR_GOLD = colors.HexColor(SLIP_HEX_GOLD)
SLIP_COLOR_GOLD_DARK = colors.HexColor(SLIP_HEX_GOLD_DARK)
SLIP_COLOR_PRIMARY = colors.HexColor(SLIP_HEX_MAROON)
SLIP_COLOR_PRIMARY_DARK = colors.HexColor(SLIP_HEX_MAROON_DARK)
SLIP_COLOR_LIGHT = colors.HexColor(SLIP_HEX_CREAM)
SLIP_COLOR_ZEBRA = colors.HexColor(SLIP_HEX_CREAM_SOFT)
SLIP_COLOR_BORDER = colors.HexColor(SLIP_HEX_BORDER)
SLIP_COLOR_TEXT = colors.HexColor(SLIP_HEX_TEXT)
SLIP_COLOR_MUTED = colors.HexColor(SLIP_HEX_MUTED)

STATUS_SESI_SLIP = {
    STATUS_SESI_PENUH: ("Penuh", "#2F7D4F"),
    STATUS_SESI_SEBAGIAN: ("Sebagian", SLIP_HEX_GOLD_DARK),
    STATUS_SESI_BELUM_CHECK_OUT: ("Belum check-out", "#C2560F"),
    STATUS_SESI_TIDAK_HADIR: ("Tidak hadir", SLIP_HEX_MAROON)
}

NAMA_BULAN_SINGKAT = [
    "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
]

NAMA_HARI_SINGKAT = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def format_rupiah(angka):
    return "Rp " + f"{int(angka):,}".replace(",", ".")


def format_durasi_singkat(menit):
    """165 -> '2j 45m', 180 -> '3j', 0 -> '0m'"""

    jam, sisa = divmod(int(menit or 0), 60)

    if jam and sisa:
        return f"{jam}j {sisa}m"

    if jam:
        return f"{jam}j"

    return f"{sisa}m"


def format_tanggal_indonesia(value, dengan_hari=False):
    """date -> '01 Oktober 2026' / 'Kam, 01 Okt'"""

    if dengan_hari:
        return (
            f"{NAMA_HARI_SINGKAT[value.weekday()]}, "
            f"{value.day:02d} {NAMA_BULAN_SINGKAT[value.month]}"
        )

    return f"{value.day:02d} {NAMA_BULAN[value.month]} {value.year}"


def terbilang_rupiah(angka):
    """575000 -> 'Lima ratus tujuh puluh lima ribu rupiah'"""

    satuan = [
        "", "satu", "dua", "tiga", "empat", "lima", "enam",
        "tujuh", "delapan", "sembilan", "sepuluh", "sebelas"
    ]

    def _terbilang(n):
        if n < 12:
            return satuan[n]

        if n < 20:
            return f"{_terbilang(n - 10)} belas"

        if n < 100:
            return f"{_terbilang(n // 10)} puluh {_terbilang(n % 10)}"

        if n < 200:
            return f"seratus {_terbilang(n - 100)}"

        if n < 1000:
            return f"{_terbilang(n // 100)} ratus {_terbilang(n % 100)}"

        if n < 2000:
            return f"seribu {_terbilang(n - 1000)}"

        if n < 1_000_000:
            return f"{_terbilang(n // 1000)} ribu {_terbilang(n % 1000)}"

        if n < 1_000_000_000:
            return f"{_terbilang(n // 1_000_000)} juta {_terbilang(n % 1_000_000)}"

        return f"{_terbilang(n // 1_000_000_000)} miliar {_terbilang(n % 1_000_000_000)}"

    angka = int(angka)

    if angka == 0:
        return "Nol rupiah"

    hasil = " ".join(_terbilang(angka).split())

    return f"{hasil} rupiah".capitalize()


class _SlipCanvas(pdf_canvas.Canvas):
    """Canvas dengan footer 'Halaman X dari Y' di setiap halaman"""

    def __init__(self, *args, footer_text="", **kwargs):
        super().__init__(*args, **kwargs)
        self._footer_text = footer_text
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_page = len(self._saved_page_states)

        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total_page)
            super().showPage()

        super().save()

    def _draw_footer(self, total_page):
        width, _ = A4

        self.setStrokeColor(SLIP_COLOR_GOLD)
        self.setLineWidth(0.8)
        self.line(15 * mm, 14 * mm, width - 15 * mm, 14 * mm)

        self.setFont("Helvetica", 7)
        self.setFillColor(SLIP_COLOR_MUTED)
        self.drawString(15 * mm, 9.5 * mm, self._footer_text)

        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(SLIP_COLOR_PRIMARY)
        self.drawRightString(
            width - 15 * mm,
            9.5 * mm,
            f"Halaman {self._pageNumber} dari {total_page}"
        )


def _slip_styles():
    base = {
        "fontName": "Helvetica",
        "fontSize": 8.5,
        "leading": 11,
        "textColor": SLIP_COLOR_TEXT
    }

    return {
        "brand": ParagraphStyle("brand", **{**base, "fontName": "Helvetica-Bold", "fontSize": 15, "leading": 18, "textColor": SLIP_COLOR_GOLD}),
        "brand_sub": ParagraphStyle("brand_sub", **{**base, "fontSize": 8, "textColor": SLIP_COLOR_MUTED}),
        "doc_title": ParagraphStyle("doc_title", **{**base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 16, "alignment": TA_RIGHT, "textColor": SLIP_COLOR_PRIMARY}),
        "doc_sub": ParagraphStyle("doc_sub", **{**base, "alignment": TA_RIGHT, "textColor": SLIP_COLOR_GOLD_DARK}),
        "section": ParagraphStyle("section", **{**base, "fontName": "Helvetica-Bold", "fontSize": 10, "leading": 13, "textColor": SLIP_COLOR_PRIMARY}),
        "label": ParagraphStyle("label", **{**base, "fontSize": 7.5, "textColor": SLIP_COLOR_MUTED}),
        "value": ParagraphStyle("value", **{**base, "fontName": "Helvetica-Bold"}),
        "card_label": ParagraphStyle("card_label", **{**base, "fontSize": 7.5, "alignment": TA_CENTER, "textColor": SLIP_COLOR_MUTED}),
        "card_value": ParagraphStyle("card_value", **{**base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 16, "alignment": TA_CENTER, "textColor": SLIP_COLOR_PRIMARY_DARK}),
        "card_label_hl": ParagraphStyle("card_label_hl", **{**base, "fontSize": 7.5, "alignment": TA_CENTER, "textColor": colors.HexColor("#F3D9A4")}),
        "card_value_hl": ParagraphStyle("card_value_hl", **{**base, "fontName": "Helvetica-Bold", "fontSize": 13, "leading": 16, "alignment": TA_CENTER, "textColor": colors.white}),
        "body": ParagraphStyle("body", **base),
        "body_right": ParagraphStyle("body_right", **{**base, "alignment": TA_RIGHT}),
        "body_bold_right": ParagraphStyle("body_bold_right", **{**base, "fontName": "Helvetica-Bold", "alignment": TA_RIGHT, "textColor": SLIP_COLOR_PRIMARY}),
        "th": ParagraphStyle("th", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7.5, "leading": 9.5, "textColor": colors.white}),
        "th_center": ParagraphStyle("th_center", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7.5, "leading": 9.5, "alignment": TA_CENTER, "textColor": colors.white}),
        "td": ParagraphStyle("td", **{**base, "fontSize": 7.5, "leading": 9.5}),
        "td_center": ParagraphStyle("td_center", **{**base, "fontSize": 7.5, "leading": 9.5, "alignment": TA_CENTER}),
        "td_right": ParagraphStyle("td_right", **{**base, "fontSize": 7.5, "leading": 9.5, "alignment": TA_RIGHT}),
        "td_muted": ParagraphStyle("td_muted", **{**base, "fontSize": 6.5, "leading": 8.5, "textColor": SLIP_COLOR_MUTED}),
        "note": ParagraphStyle("note", **{**base, "fontSize": 7, "leading": 9.5, "textColor": SLIP_COLOR_MUTED}),
        "sign": ParagraphStyle("sign", **{**base, "alignment": TA_CENTER})
    }


def _slip_header(styles, periode):
    brand_block = [
        Paragraph(BRAND_NAME, styles["brand"]),
        # Paragraph("Sistem Manajemen Kelas &amp; Mentor", styles["brand_sub"])
        Paragraph("LEARN • GROW • BE THE BEST", styles["brand_sub"])
    ]

    title_block = [
        Paragraph("SLIP HONOR MENTOR", styles["doc_title"]),
        Paragraph(f"Periode {periode['nama_bulan']}", styles["doc_sub"])
    ]

    if os.path.exists(BRAND_LOGO_PATH):
        logo_width, logo_height = ImageReader(BRAND_LOGO_PATH).getSize()
        target_height = 16 * mm
        logo = Image(
            BRAND_LOGO_PATH,
            width=target_height * logo_width / logo_height,
            height=target_height
        )

        data = [[logo, brand_block, title_block]]
        col_widths = [logo.drawWidth + 4 * mm, None, 70 * mm]

    else:
        data = [[brand_block, title_block]]
        col_widths = [None, 70 * mm]

    header = Table(data, colWidths=col_widths)
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 2, SLIP_COLOR_PRIMARY)
    ]))

    # Garis ganda: marun tebal + emas tipis
    return [
        header,
        HRFlowable(width="100%", thickness=0.8, color=SLIP_COLOR_GOLD, spaceBefore=1.2, spaceAfter=0)
    ]


def _slip_info_mentor(styles, mentor, periode, nomor_slip, tanggal_cetak):
    def _pair(label, value):
        return [Paragraph(label, styles["label"]), Paragraph(value or "-", styles["value"])]

    periode_label = (
        f"{format_tanggal_indonesia(periode['start_date'])} - "
        f"{format_tanggal_indonesia(periode['end_date'])}"
    )

    data = [
        _pair("Nama Mentor", mentor["nama_mentor"]) + [""] + _pair("No. Slip", nomor_slip),
        _pair("Nickname", mentor["nickname_mentor"]) + [""] + _pair("Periode", periode_label),
        _pair("Email", mentor["email"]) + [""] + _pair("Tanggal Cetak", tanggal_cetak)
    ]

    table = Table(data, colWidths=[24 * mm, 64 * mm, 4 * mm, 24 * mm, 64 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2)
    ]))

    return table


def _slip_summary_cards(styles, ringkasan):
    cards = [
        ("Jumlah Sesi", str(ringkasan["jumlah_sesi"]), False),
        ("Total Jam Dibayar", ringkasan["total_jam_dibayar_label"], False),
        ("Tarif per Jam", format_rupiah(PAYROLL_TARIF_PER_JAM), False),
        ("Total Honor", format_rupiah(ringkasan["honor"]), True)
    ]

    row = []

    for label, value, highlight in cards:
        suffix = "_hl" if highlight else ""
        row.append([
            Paragraph(label, styles[f"card_label{suffix}"]),
            Spacer(1, 2),
            Paragraph(value, styles[f"card_value{suffix}"])
        ])

    table = Table([row], colWidths=[42 * mm, 42 * mm, 42 * mm, 54 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (2, 0), SLIP_COLOR_LIGHT),
        ("BACKGROUND", (3, 0), (3, 0), SLIP_COLOR_PRIMARY),
        ("LINEABOVE", (0, 0), (2, 0), 2, SLIP_COLOR_GOLD),
        ("LINEABOVE", (3, 0), (3, 0), 2, SLIP_COLOR_PRIMARY_DARK),
        ("LINEAFTER", (0, 0), (2, 0), 3, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
    ]))

    return table


def _slip_perhitungan(styles, ringkasan):
    status_label = " &nbsp;·&nbsp; ".join(
        f"{STATUS_SESI_SLIP[status][0]}: <b>{ringkasan[counter]}</b>"
        for status, counter in STATUS_SESI_COUNTER.items()
    )

    data = [
        [Paragraph("Total durasi sesuai jadwal", styles["body"]),
         Paragraph(ringkasan["total_jam_jadwal_label"], styles["body_right"])],
        [Paragraph("Total durasi aktual (check-in s/d check-out)", styles["body"]),
         Paragraph(format_durasi(ringkasan["total_menit_aktual"]), styles["body_right"])],
        [Paragraph("Total durasi dibayar (maksimal sesuai jadwal)", styles["body"]),
         Paragraph(
             f"{ringkasan['total_jam_dibayar_label']} ({ringkasan['total_menit_dibayar']} menit)",
             styles["body_right"]
         )],
        [Paragraph("Tarif per jam", styles["body"]),
         Paragraph(format_rupiah(PAYROLL_TARIF_PER_JAM), styles["body_right"])],
        [Paragraph(
            f"<font color='{SLIP_HEX_MAROON}'><b>Total honor</b></font> &nbsp;<font color='{SLIP_HEX_MUTED}' size='7'>"
            f"({ringkasan['total_menit_dibayar']} menit × {format_rupiah(PAYROLL_TARIF_PER_JAM)} / 60)</font>",
            styles["body"]
         ),
         Paragraph(format_rupiah(ringkasan["honor"]), styles["body_bold_right"])],
        [Paragraph(f"<i>Terbilang: {terbilang_rupiah(ringkasan['honor'])}</i>", styles["note"]), ""],
        [Paragraph(f"Status sesi &nbsp; {status_label}", styles["note"]), ""]
    ]

    table = Table(data, colWidths=[130 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, SLIP_COLOR_BORDER),
        ("LINEBELOW", (0, 0), (-1, 2), 0.5, SLIP_COLOR_BORDER),
        ("LINEABOVE", (0, 4), (-1, 4), 1, SLIP_COLOR_GOLD),
        ("BACKGROUND", (0, 4), (-1, 4), SLIP_COLOR_LIGHT),
        ("SPAN", (0, 5), (-1, 5)),
        ("SPAN", (0, 6), (-1, 6)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5)
    ]))

    return table


def _slip_rincian(styles, rincian, ringkasan):
    header = [
        Paragraph("No", styles["th_center"]),
        Paragraph("Tanggal", styles["th"]),
        Paragraph("Jam Jadwal", styles["th"]),
        Paragraph("Kelas / Kelompok", styles["th"]),
        Paragraph("Kehadiran", styles["th"]),
        Paragraph("Dibayar", styles["th_center"]),
        Paragraph("Honor", styles["th_center"]),
        Paragraph("Status", styles["th"])
    ]

    data = [header]

    for index, sesi in enumerate(rincian, start=1):
        tanggal = date.fromisoformat(sesi["tanggal"])

        nama_kelas = ", ".join(
            kelas["nama_kelas"] or kelas["nama_kelompok"] or "-"
            for kelas in sesi["kelas"]
        )

        keterangan_kelas = f"{sesi['jumlah_kelas']} kelas · {sesi['type_pertemuan']}"

        check_in = sesi["check_in_at"][11:16] if sesi["check_in_at"] else None
        check_out = sesi["check_out_at"][11:16] if sesi["check_out_at"] else None

        if check_in and check_out:
            kehadiran = f"{check_in} - {check_out}"
        elif check_in:
            kehadiran = f"{check_in} - ?"
        else:
            kehadiran = "-"

        status_label, status_color = STATUS_SESI_SLIP[sesi["status_sesi"]]

        data.append([
            Paragraph(str(index), styles["td_center"]),
            Paragraph(format_tanggal_indonesia(tanggal, dengan_hari=True), styles["td"]),
            Paragraph(f"{sesi['waktu_mulai'][:5]} - {sesi['waktu_selesai'][:5]}", styles["td"]),
            [Paragraph(nama_kelas, styles["td"]), Paragraph(keterangan_kelas, styles["td_muted"])],
            Paragraph(kehadiran, styles["td"]),
            Paragraph(format_durasi_singkat(sesi["durasi_dibayar_menit"]), styles["td_center"]),
            Paragraph(format_rupiah(sesi["honor"]), styles["td_right"]),
            Paragraph(f"<font color='{status_color}'><b>{status_label}</b></font>", styles["td"])
        ])

    if not rincian:
        data.append([
            Paragraph("Tidak ada sesi mengajar pada periode ini", styles["td_center"]),
            "", "", "", "", "", "", ""
        ])

    data.append([
        "", "", "", Paragraph(f"<font color='{SLIP_HEX_MAROON}'><b>Total</b></font>", styles["td"]), "",
        Paragraph(f"<font color='{SLIP_HEX_MAROON}'><b>{format_durasi_singkat(ringkasan['total_menit_dibayar'])}</b></font>", styles["td_center"]),
        Paragraph(f"<font color='{SLIP_HEX_MAROON}'><b>{format_rupiah(ringkasan['honor'])}</b></font>", styles["td_right"]),
        ""
    ])

    last_row = len(data) - 1

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLIP_COLOR_PRIMARY),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, SLIP_COLOR_GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, last_row - 1), 0.4, SLIP_COLOR_BORDER),
        ("LINEABOVE", (0, last_row), (-1, last_row), 1, SLIP_COLOR_PRIMARY),
        ("BACKGROUND", (0, last_row), (-1, last_row), SLIP_COLOR_LIGHT)
    ]

    for row_index in range(2, last_row, 2):
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), SLIP_COLOR_ZEBRA))

    if not rincian:
        style.append(("SPAN", (0, 1), (-1, 1)))

    table = Table(
        data,
        colWidths=[8 * mm, 19 * mm, 20 * mm, 47 * mm, 21 * mm, 15 * mm, 23 * mm, 27 * mm],
        repeatRows=1
    )
    table.setStyle(TableStyle(style))

    return table


def _slip_catatan_dan_ttd(styles, mentor, tanggal_cetak):
    catatan = Paragraph(
        f"<font color='{SLIP_HEX_MAROON}'><b>Catatan</b></font><br/>"
        "1. Satu sesi = jadwal dengan tanggal, jam mulai, dan jam selesai yang sama. "
        "Banyak kelas dalam satu sesi dibayar satu kali.<br/>"
        "2. Durasi dibayar = durasi aktual check-in s/d check-out, maksimal sebesar durasi jadwal.<br/>"
        "3. Sesi <b>Belum check-out</b> dan <b>Tidak hadir</b> tidak dibayar. "
        "Hubungi admin untuk koreksi data absensi.<br/>"
        "4. Total honor dihitung dari total menit dibayar, sehingga dapat berbeda beberapa rupiah "
        "dari penjumlahan honor per sesi karena pembulatan.",
        styles["note"]
    )

    def _kolom_ttd(judul, nama):
        kolom = Table([
            [Paragraph(judul, styles["sign"])],
            [Spacer(1, 15 * mm)],
            [Paragraph(f"<b>{nama}</b>", styles["sign"])]
        ], colWidths=[60 * mm])

        kolom.setStyle(TableStyle([
            ("LINEABOVE", (0, 2), (0, 2), 0.8, SLIP_COLOR_GOLD),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0)
        ]))

        return kolom

    ttd = Table([[
        _kolom_ttd("Mentor", mentor["nama_mentor"] or "-"),
        _kolom_ttd(f"{BRAND_NAME}, {tanggal_cetak}", "Admin / Keuangan")
    ]], colWidths=[90 * mm, 90 * mm])

    ttd.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0)
    ]))

    return KeepTogether([catatan, Spacer(1, 6 * mm), ttd])


def build_slip_payroll_pdf(mentor, periode, detail):
    """
    Membuat slip honor mentor (PDF A4).

    mentor  : hasil get_mentor_payroll()
    periode : hasil resolve_bulan() -> bulan, nama_bulan, start_date, end_date
    detail  : hasil get_detail_payroll_mentor() -> ringkasan, rincian
    """

    styles = _slip_styles()
    ringkasan = detail["ringkasan"]
    rincian = detail["rincian"]

    now = get_wib()
    tanggal_cetak = format_tanggal_indonesia(now.date())
    nomor_slip = f"SU/HNR/{periode['bulan'].replace('-', '')}/{int(mentor['id_mentor']):04d}"

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=f"Slip Honor Mentor - {mentor['nama_mentor']} - {periode['nama_bulan']}",
        author=BRAND_NAME
    )

    story = [
        *_slip_header(styles, periode),
        Spacer(1, 6 * mm),
        _slip_info_mentor(styles, mentor, periode, nomor_slip, tanggal_cetak),
        Spacer(1, 6 * mm),
        _slip_summary_cards(styles, ringkasan),
        Spacer(1, 6 * mm),
        Paragraph("Perhitungan Honor", styles["section"]),
        Spacer(1, 2 * mm),
        _slip_perhitungan(styles, ringkasan),
        Spacer(1, 6 * mm),
        Paragraph("Rincian Sesi Mengajar", styles["section"]),
        Spacer(1, 2 * mm),
        _slip_rincian(styles, rincian, ringkasan),
        Spacer(1, 6 * mm),
        _slip_catatan_dan_ttd(styles, mentor, tanggal_cetak)
    ]

    footer_text = (
        f"Dokumen ini dibuat otomatis oleh sistem {BRAND_NAME} "
        f"pada {now.strftime('%d/%m/%Y %H:%M')} WIB  ·  No. {nomor_slip}"
    )

    doc.build(
        story,
        canvasmaker=lambda *args, **kwargs: _SlipCanvas(*args, footer_text=footer_text, **kwargs)
    )

    buffer.seek(0)

    return (
        buffer,
        f"slip_honor_mentor_{int(mentor['id_mentor']):04d}_{periode['bulan']}.pdf",
        "application/pdf"
    )