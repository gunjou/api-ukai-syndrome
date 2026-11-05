import re
import sys
import zipfile

from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.query import q_jadwal_bulk as bulk  # noqa: E402


# ============================================================================ #
#                              #ANCHOR - PARSE DATE                            #
# ============================================================================ #

@pytest.mark.parametrize("value, expected", [
    (46330, date(2026, 11, 4)),
    (46740, date(2027, 12, 19)),
    (46330.0, date(2026, 11, 4)),
    ("46330", date(2026, 11, 4)),
    ("46330.0", date(2026, 11, 4)),
    (20000, date(1954, 10, 3)),
    (80000, date(2119, 1, 11)),
    (datetime(2026, 11, 4, 8, 0), date(2026, 11, 4)),
    (pd.Timestamp("2026-11-04"), date(2026, 11, 4)),
    (date(2026, 11, 4), date(2026, 11, 4)),
    ("2026-11-04", date(2026, 11, 4)),
    ("04-11-2026", date(2026, 11, 4)),
    ("04/11/2026", date(2026, 11, 4)),
    ("2026/11/04", date(2026, 11, 4)),
])
def test_parse_bulk_date_valid(value, expected):
    assert bulk.parse_bulk_date(value) == expected


@pytest.mark.parametrize("value", [
    None, float("nan"), pd.NaT, "", "bukan tanggal", "nan", "inf",
    19999, 80001, "19999", "80001", 13, True, False,
])
def test_parse_bulk_date_invalid(value):
    assert bulk.parse_bulk_date(value) is None


# ============================================================================ #
#                              #ANCHOR - PARSE TIME                            #
# ============================================================================ #

@pytest.mark.parametrize("value, expected", [
    (0.54166666, time(13, 0)),
    (0.79166666, time(19, 0)),
    (0.797222, time(19, 8)),
    ("0.5416666", time(13, 0)),
    ("0.797222", time(19, 8)),
    ("0.5", time(12, 0)),
    ("0.25", time(6, 0)),
    ("0", time(0, 0)),
    ("13.00", time(13, 0)),
    ("9.30", time(9, 30)),
    ("00.25", time(0, 25)),
    ("13:00", time(13, 0)),
    ("13:00:30", time(13, 0, 30)),
    (time(13, 0, 30, 500), time(13, 0, 30)),
    (datetime(2026, 11, 4, 13, 0, 30, 500), time(13, 0, 30)),
    (timedelta(hours=19, minutes=7, seconds=59), time(19, 8)),
    (pd.Timedelta(hours=13), time(13, 0)),
])
def test_parse_bulk_time_valid(value, expected):
    result = bulk.parse_bulk_time(value)

    assert result == expected
    assert result.microsecond == 0


@pytest.mark.parametrize("value", [
    None, float("nan"), pd.NaT, "", "abc", "1.5", "25.00", "13.60",
    "13.5", "-0.5", True,
])
def test_parse_bulk_time_invalid(value):
    assert bulk.parse_bulk_time(value) is None


# ============================================================================ #
#                              #ANCHOR - READ FILE                             #
# ============================================================================ #

def make_upload(content, filename):
    file = MagicMock()
    file.filename = filename
    file.stream = BytesIO(content)
    return file


def invalid_schema_styles(styles):
    # XML tetap well-formed, tapi nilainya ditolak openpyxl
    # ("could not read stylesheet from None")
    return re.sub(
        rb'<patternFill patternType="\w+"',
        b'<patternFill patternType="bogus"',
        styles,
        count=1
    )


def malformed_styles(styles):
    return b"<styleSheet><broken"


def make_xlsx(rows, styles_mutator=None):
    buffer = BytesIO()
    pd.DataFrame(rows).to_excel(buffer, index=False, engine="openpyxl")

    if styles_mutator is None:
        return buffer.getvalue()

    output = BytesIO()

    with zipfile.ZipFile(BytesIO(buffer.getvalue())) as source:
        with zipfile.ZipFile(output, "w") as target:
            for item in source.namelist():
                target.writestr(
                    item,
                    styles_mutator(source.read(item))
                    if item == "xl/styles.xml"
                    else source.read(item)
                )

    return output.getvalue()


def test_read_xlsx_styles_rusak_fallback_calamine():
    content = make_xlsx(
        [
            {"tanggal": 46330, "waktu_mulai": 0.54166666},
            {"tanggal": None, "waktu_mulai": None},
            {"tanggal": 46740, "waktu_mulai": 0.797222},
        ],
        styles_mutator=invalid_schema_styles
    )

    with pytest.raises(Exception, match="could not read stylesheet"):
        pd.read_excel(BytesIO(content), engine="openpyxl")

    df = bulk.read_bulk_jadwal_file(make_upload(content, "jadwal.xlsx"))

    assert list(df.index) == [0, 1]
    assert bulk.parse_bulk_date(df.loc[1, "tanggal"]) == date(2027, 12, 19)
    assert bulk.parse_bulk_time(df.loc[1, "waktu_mulai"]) == time(19, 8)


@pytest.mark.parametrize("content", [
    b"bukan file xlsx",
    make_xlsx([{"tanggal": 46330}], styles_mutator=malformed_styles),
])
def test_read_xlsx_tidak_terbaca_raise_value_error(content):
    upload = make_upload(content, "jadwal.xlsx")

    with pytest.raises(ValueError, match="File XLSX tidak dapat dibaca"):
        bulk.read_bulk_jadwal_file(upload)


# ============================================================================ #
#                           #ANCHOR - VALIDASI BENTROK                         #
# ============================================================================ #

def make_row(kelompok, mulai, selesai, tanggal=46330):
    return {
        "nama_kelas": None,
        "nama_kelompok": kelompok,
        "mentor": "Kak A",
        "tanggal": tanggal,
        "waktu_mulai": mulai,
        "waktu_selesai": selesai,
        "topik": "T",
        "catatan": None,
        "type_pertemuan": "OFFLINE",
    }


def make_online_row(mulai, selesai):
    return {
        **make_row(None, mulai, selesai),
        "nama_kelas": "Kelas A",
        "type_pertemuan": "ONLINE",
    }


def make_existing(id_jadwal, id_kelompok, mulai, selesai, type_pertemuan="OFFLINE"):
    return {
        "id_jadwal": id_jadwal,
        "id_paketkelas": None,
        "id_kelompok": id_kelompok,
        "id_mentor": 1,
        "type_pertemuan": type_pertemuan,
        "tanggal": date(2026, 11, 4),
        "waktu_mulai": mulai,
        "waktu_selesai": selesai,
    }


def run_validate(rows, existing=()):
    upload = make_upload(make_xlsx(rows), "jadwal.xlsx")

    with (
        patch.object(bulk, "get_connection", return_value=MagicMock())
    ), (
        patch.object(bulk, "get_bulk_paketkelas_mapping", return_value={"kelas a": [5]})
    ), (
        patch.object(bulk, "get_bulk_mentor_mapping", return_value={"kak a": {1}})
    ), (
        patch.object(bulk, "get_bulk_kelompok_mapping", return_value={"k1": [10], "k2": [20]})
    ), (
        patch.object(bulk, "get_bulk_mentor_kelas_mapping", return_value={(1, 5)})
    ), (
        patch.object(bulk, "get_existing_jadwal_for_bulk", return_value=list(existing))
    ):
        result = bulk.validate_bulk_jadwal(upload, "jadwal.xlsx", 1)

    return {
        item["row"]: [error["message"] for error in item["errors"]]
        for item in result["errors"]
    }


def test_waktu_mulai_setelah_selesai_invalid():
    errors = run_validate([make_row("K1", "14:00", "13:00")])

    assert errors[2] == ["waktu_selesai harus lebih besar dari waktu_mulai"]


def test_bentrok_mentor_beda_kelompok_dalam_file():
    errors = run_validate([
        make_row("K1", "14:00", "19:00"),
        make_row("K2", "15:00", "16:00"),
    ])

    assert errors == {
        3: ["Mentor bentrok dengan row 2 di dalam file (14:00–19:00)"]
    }


def test_duplikat_dalam_file_bukan_bentrok():
    errors = run_validate([
        make_row("K1", "14:00", "19:00"),
        make_row("K1", "14:00", "19:00"),
    ])

    assert errors == {3: ["Jadwal duplicate dengan row 2 di dalam file"]}


def test_jam_bersambung_tidak_bentrok():
    errors = run_validate([
        make_row("K1", "13:00", "14:00"),
        make_row("K2", "14:00", "15:00"),
    ])

    assert errors == {}


def test_bentrok_mentor_dengan_database_beda_target():
    errors = run_validate(
        [make_row("K1", "15:00", "16:00")],
        [make_existing(123, 20, time(14, 0), time(19, 0))]
    )

    assert errors == {
        2: ["Mentor bentrok dengan jadwal di database (id_jadwal 123, 14:00–19:00)"]
    }


def test_duplikat_database_diprioritaskan_atas_bentrok():
    errors = run_validate(
        [make_row("K1", "14:00", "19:00")],
        [
            make_existing(1, 20, time(15, 0), time(16, 0)),
            make_existing(2, 10, time(14, 0), time(19, 0)),
        ]
    )

    assert errors == {2: ["Jadwal sudah terdaftar di database"]}


def test_slot_sama_type_sama_dalam_file_tidak_bentrok():
    errors = run_validate([
        make_row("K1", "14:00", "19:00"),
        make_row("K2", "14:00", "19:00"),
    ])

    assert errors == {}


def test_slot_sama_type_beda_dalam_file_bentrok():
    errors = run_validate([
        make_row("K1", "14:00", "19:00"),
        make_online_row("14:00", "19:00"),
    ])

    assert errors == {
        3: ["Mentor bentrok dengan row 2 di dalam file (14:00\u201319:00)"]
    }


def test_slot_group_tetap_bentrok_dengan_jam_overlap_lain():
    errors = run_validate([
        make_row("K1", "14:00", "19:00"),
        make_row("K2", "14:00", "19:00"),
        make_online_row("15:00", "16:00"),
    ])

    assert errors == {
        4: ["Mentor bentrok dengan row 2 di dalam file (14:00\u201319:00)"]
    }


def test_slot_sama_type_sama_dengan_database_tidak_bentrok():
    errors = run_validate(
        [make_row("K1", "14:00", "19:00")],
        [make_existing(123, 20, time(14, 0), time(19, 0))]
    )

    assert errors == {}


def test_slot_sama_type_beda_dengan_database_bentrok():
    errors = run_validate(
        [make_row("K1", "14:00", "19:00")],
        [make_existing(123, None, time(14, 0), time(19, 0), "ONLINE")]
    )

    assert errors == {
        2: ["Mentor bentrok dengan jadwal di database (id_jadwal 123, 14:00\u201319:00)"]
    }
