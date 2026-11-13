import io
import os
import re
import calendar
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable, Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)

from ..utils.config import get_wib
# Tema, logo, style, dan footer disamakan dengan slip payroll
from .e_slip_payroll import (
    BRAND_LOGO_PATH, BRAND_NAME, NAMA_BULAN,
    SLIP_COLOR_BORDER, SLIP_COLOR_GOLD, SLIP_COLOR_LIGHT, SLIP_COLOR_MUTED,
    SLIP_COLOR_PRIMARY, SLIP_COLOR_PRIMARY_DARK, SLIP_COLOR_ZEBRA,
    SLIP_HEX_GOLD_DARK, SLIP_HEX_MAROON,
    _SlipCanvas, _slip_styles, format_tanggal_indonesia
)


PAGE_SIZE = landscape(A4)
CONTENT_WIDTH = PAGE_SIZE[0] - 30 * mm


class _RekapCanvas(_SlipCanvas):
    """Footer slip payroll, lebarnya mengikuti halaman landscape"""

    def _draw_footer(self, total_page):
        width = self._pagesize[0]

        self.setStrokeColor(SLIP_COLOR_GOLD)
        self.setLineWidth(0.8)
        self.line(15 * mm, 14 * mm, width - 15 * mm, 14 * mm)

        self.setFont("Helvetica", 7)
        self.setFillColor(SLIP_COLOR_MUTED)
        self.drawString(15 * mm, 9.5 * mm, self._footer_text)

        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(SLIP_COLOR_PRIMARY)
        self.drawRightString(width - 15 * mm, 9.5 * mm, f"Halaman {self._pageNumber} dari {total_page}")


def _warna_persen(value):
    if value >= 80:
        return "#2F7D4F"
    if value >= 60:
        return SLIP_HEX_GOLD_DARK
    return SLIP_HEX_MAROON


def _fmt(value):
    """40.0 -> '40%', 73.33 -> '73.33%'"""
    return f"{value:g}%"


def _persen(value, styles, style="td_center"):
    return Paragraph(f"<font color='{_warna_persen(value)}'><b>{_fmt(value)}</b></font>", styles[style])


def resolve_periode_rekap(kelas, bulan):
    """bulan (date) -> 1 bulan; None -> periode batch kelas (ALL)"""

    if bulan:
        akhir = bulan.replace(day=calendar.monthrange(bulan.year, bulan.month)[1])
        return f"{NAMA_BULAN[bulan.month]} {bulan.year}", bulan, akhir

    return "Keseluruhan (ALL)", kelas["tanggal_mulai"], kelas["tanggal_selesai"]


def _header(styles, periode_label):
    brand_block = [
        Paragraph(BRAND_NAME, styles["brand"]),
        Paragraph("LEARN • GROW • BE THE BEST", styles["brand_sub"])
    ]

    title_block = [
        Paragraph("REKAP KEHADIRAN KELAS", styles["doc_title"]),
        Paragraph(f"Periode {periode_label}", styles["doc_sub"])
    ]

    if os.path.exists(BRAND_LOGO_PATH):
        logo_width, logo_height = ImageReader(BRAND_LOGO_PATH).getSize()
        target_height = 16 * mm
        logo = Image(BRAND_LOGO_PATH, width=target_height * logo_width / logo_height, height=target_height)
        data = [[logo, brand_block, title_block]]
        col_widths = [logo.drawWidth + 4 * mm, None, 90 * mm]
    else:
        data = [[brand_block, title_block]]
        col_widths = [None, 90 * mm]

    header = Table(data, colWidths=col_widths)
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 2, SLIP_COLOR_PRIMARY)
    ]))

    # Garis ganda: marun tebal + emas tipis
    return [header, HRFlowable(width="100%", thickness=0.8, color=SLIP_COLOR_GOLD, spaceBefore=1.2, spaceAfter=0)]


def _info_kelas(styles, kelas, periode_label, mulai, akhir, tanggal_cetak):
    def _pair(label, value):
        return [Paragraph(label, styles["label"]), Paragraph(escape(str(value or "-")), styles["value"])]

    rentang = f"{format_tanggal_indonesia(mulai)} - {format_tanggal_indonesia(akhir)}"

    data = [
        _pair("Kelas", kelas["nama_kelas"]) + [""] + _pair("Periode", periode_label),
        _pair("Wali Kelas", kelas["nama_wali_kelas"]) + [""] + _pair("Rentang Tanggal", rentang),
        _pair("Batch", kelas["nama_batch"]) + [""] + _pair("Tanggal Cetak", tanggal_cetak)
    ]

    table = Table(data, colWidths=[26 * mm, 100 * mm, 15 * mm, 30 * mm, 96 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2)
    ]))

    return table


def _summary_cards(styles, ringkasan):
    cards = [
        ("Total Peserta", str(ringkasan["total_peserta"]), False),
        ("Kehadiran (Keseluruhan)", _fmt(ringkasan["persentase_keseluruhan_kelas"]), False),
        ("Kehadiran (Terlaksana)", _fmt(ringkasan["persentase_hadir_kelas"]), True)
    ]

    row = []

    for label, value, highlight in cards:
        suffix = "_hl" if highlight else ""
        row.append([
            Paragraph(label, styles[f"card_label{suffix}"]),
            Spacer(1, 2),
            Paragraph(value, styles[f"card_value{suffix}"])
        ])

    table = Table([row], colWidths=[CONTENT_WIDTH / 3] * 3)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (1, 0), SLIP_COLOR_LIGHT),
        ("BACKGROUND", (2, 0), (2, 0), SLIP_COLOR_PRIMARY),
        ("LINEABOVE", (0, 0), (1, 0), 2, SLIP_COLOR_GOLD),
        ("LINEABOVE", (2, 0), (2, 0), 2, SLIP_COLOR_PRIMARY_DARK),
        ("LINEAFTER", (0, 0), (1, 0), 3, colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
    ]))

    return table


def _tipe_cell(styles, value):
    if not value["total_pertemuan"]:
        return Paragraph("-", styles["td_center"])

    return [
        Paragraph(f"{value['hadir']}/{value['terlaksana']}", styles["td_center"]),
        Paragraph(
            f"{_fmt(value['persentase_hadir'])} · {_fmt(value['persentase_keseluruhan'])}",
            styles["td_muted_center"]
        )
    ]


def _tabel_peserta(styles, peserta):
    header = [
        Paragraph(label, styles["th" if label in ("Nama Peserta", "No. HP") else "th_center"])
        for label in (
            "No", "Nama Peserta", "No. HP", "Terlaksana / Jadwal", "Hadir", "Izin", "Sakit", "Alpha",
            "Online", "Offline", "Kehadiran (Terlaksana)", "Kehadiran (Keseluruhan)"
        )
    ]

    data = [header]

    for index, row in enumerate(peserta, start=1):
        data.append([
            Paragraph(str(index), styles["td_center"]),
            Paragraph(escape(row["nama"] or "-"), styles["td"]),
            Paragraph(escape(row["no_hp"] or "-"), styles["td"]),
            Paragraph(f"{row['terlaksana']}/{row['total_pertemuan']}", styles["td_center"]),
            Paragraph(str(row["hadir"]), styles["td_center"]),
            Paragraph(str(row["izin"]), styles["td_center"]),
            Paragraph(str(row["sakit"]), styles["td_center"]),
            Paragraph(f"<font color='{SLIP_HEX_MAROON}'><b>{row['alpha']}</b></font>", styles["td_center"]),
            _tipe_cell(styles, row["online"]),
            _tipe_cell(styles, row["offline"]),
            _persen(row["persentase_hadir"], styles),
            _persen(row["persentase_keseluruhan"], styles)
        ])

    if not peserta:
        data.append([Paragraph("Tidak ada peserta aktif pada kelas ini", styles["td_center"])] + [""] * 11)

    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLIP_COLOR_PRIMARY),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, SLIP_COLOR_GOLD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, SLIP_COLOR_BORDER)
    ]

    for row_index in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), SLIP_COLOR_ZEBRA))

    if not peserta:
        style.append(("SPAN", (0, 1), (-1, 1)))

    table = Table(
        data,
        colWidths=[w * mm for w in (8, 60, 28, 20, 13, 12, 12, 13, 26, 26, 24, 25)],
        repeatRows=1
    )
    table.setStyle(TableStyle(style))

    return table


def _catatan(styles):
    return KeepTogether([Paragraph(
        f"<font color='{SLIP_HEX_MAROON}'><b>Catatan</b></font><br/>"
        "1. <b>Terlaksana</b> = jadwal yang sudah dimulai saat dokumen dicetak; "
        "<b>Jadwal</b> = seluruh jadwal pada periode.<br/>"
        "2. Peserta yang tidak absen pada jadwal yang sudah dimulai dihitung <b>Alpha</b>.<br/>"
        "3. <b>Kehadiran (Terlaksana)</b> = hadir ÷ pertemuan terlaksana; "
        "<b>Kehadiran (Keseluruhan)</b> = hadir ÷ seluruh jadwal periode.<br/>"
        "4. Kolom Online / Offline: hadir/terlaksana, di bawahnya persentase terlaksana · keseluruhan.<br/>"
        "5. Jadwal dihitung dari jadwal kelas dan jadwal kelompok belajar yang diikuti peserta.",
        styles["note"]
    )])


def build_rekap_kelas_pdf(kelas, bulan, peserta, ringkasan):
    """
    Membuat PDF rekap kehadiran per peserta satu kelas (A4 landscape).

    kelas     : hasil get_info_kelas_rekap()
    bulan     : date tanggal 1 bulan filter, None = keseluruhan (periode batch)
    peserta   : hasil get_rekap_absensi_kelas()["peserta"]
    ringkasan : hasil ringkasan_rekap_kelas()
    """

    styles = _slip_styles()
    styles["td_muted_center"] = ParagraphStyle("td_muted_center", parent=styles["td_muted"], alignment=TA_CENTER)
    periode_label, mulai, akhir = resolve_periode_rekap(kelas, bulan)

    now = get_wib()
    tanggal_cetak = format_tanggal_indonesia(now.date())

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=PAGE_SIZE,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=f"Rekap Kehadiran Kelas - {kelas['nama_kelas']} - {periode_label}",
        author=BRAND_NAME
    )

    story = [
        *_header(styles, periode_label),
        Spacer(1, 6 * mm),
        _info_kelas(styles, kelas, periode_label, mulai, akhir, tanggal_cetak),
        Spacer(1, 6 * mm),
        _summary_cards(styles, ringkasan),
        Spacer(1, 6 * mm),
        Paragraph("Rekap Kehadiran Peserta", styles["section"]),
        Spacer(1, 2 * mm),
        _tabel_peserta(styles, peserta),
        Spacer(1, 6 * mm),
        _catatan(styles)
    ]

    footer_text = (
        f"Dokumen ini dibuat otomatis oleh sistem {BRAND_NAME} "
        f"pada {now.strftime('%d/%m/%Y %H:%M')} WIB  ·  Kelas {kelas['nama_kelas']}"
    )

    doc.build(story, canvasmaker=lambda *args, **kwargs: _RekapCanvas(*args, footer_text=footer_text, **kwargs))

    buffer.seek(0)

    slug_kelas = re.sub(r"[^A-Za-z0-9]+", "_", kelas["nama_kelas"] or "kelas").strip("_").lower()
    slug_periode = bulan.strftime("%Y-%m") if bulan else "all"

    return buffer, f"rekap_kehadiran_{slug_kelas}_{slug_periode}.pdf", "application/pdf"
