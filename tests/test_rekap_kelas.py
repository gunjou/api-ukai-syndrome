import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from flask_restx import Api

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.absensi as A  # noqa: E402
from api.query.q_absensi import build_rekap_peserta  # noqa: E402

app = Flask(__name__)
app.config.update(JWT_SECRET_KEY="test-secret-test-secret-test-secret-123")
JWTManager(app)
Api(app).add_namespace(A.absensi_ns, path="/absensi")
with app.app_context():
    HEADERS = {"Authorization": "Bearer " + create_access_token(identity="7", additional_claims={"role": "mentor"})}


def row(id_peserta, tipe, status, jumlah):
    return {"id_peserta": id_peserta, "nama": f"P{id_peserta}", "nickname": None, "no_hp": "0812",
            "type_pertemuan": tipe, "status_kehadiran": status, "jumlah": jumlah}


def test_build_rekap_peserta():
    result = build_rekap_peserta([
        row(1, "ONLINE", "HADIR", 3),
        row(1, "ONLINE", "ALPHA", 1),
        row(1, "OFFLINE", "HADIR", 2),
        row(1, "OFFLINE", "IZIN", 2),
        row(1, "ONLINE", "BELUM", 2),  # jadwal belum dimulai
        row(2, None, None, 0),  # peserta tanpa jadwal
    ])

    p1, p2 = result
    assert (p1["total_pertemuan"], p1["terlaksana"], p1["belum_terlaksana"]) == (10, 8, 2)
    assert (p1["hadir"], p1["izin"], p1["alpha"]) == (5, 2, 1)
    assert p1["persentase_hadir"] == 62.5        # 5 dari 8 terlaksana
    assert p1["persentase_keseluruhan"] == 50.0  # 5 dari 10 jadwal
    assert p1["online"] == {
        "total_pertemuan": 6, "terlaksana": 4, "belum_terlaksana": 2,
        "hadir": 3, "izin": 0, "sakit": 0, "alpha": 1,
        "persentase_hadir": 75.0, "persentase_keseluruhan": 50.0,
    }
    assert p1["offline"]["persentase_hadir"] == 50.0
    assert p2["total_pertemuan"] == 0 and p2["persentase_hadir"] == 0 == p2["persentase_keseluruhan"]


def test_bukan_wali_kelas_ditolak():
    with patch.object(A, "is_wali_kelas", return_value=False), \
         patch.object(A, "get_rekap_absensi_kelas") as rekap:
        res = app.test_client().get("/absensi/rekap/kelas/5", headers=HEADERS)
    assert res.status_code == 404
    rekap.assert_not_called()


def test_filter_bulan():
    data = {"daftar_bulan": ["2026-09", "2026-10"], "peserta": build_rekap_peserta([row(1, "ONLINE", "HADIR", 1)])}
    with patch.object(A, "is_wali_kelas", return_value=True), \
         patch.object(A, "get_rekap_absensi_kelas", return_value=data) as rekap:
        client = app.test_client()
        bad = client.get("/absensi/rekap/kelas/5?bulan=2026-13", headers=HEADERS)
        ok = client.get("/absensi/rekap/kelas/5?bulan=2026-10", headers=HEADERS)

    assert bad.status_code == 400
    assert ok.status_code == 200
    rekap.assert_called_once_with(5, date(2026, 10, 1))
    meta = ok.get_json()["meta"]
    assert meta["filter"] == "BULAN" and meta["persentase_hadir_kelas"] == 100.0
    assert meta["persentase_keseluruhan_kelas"] == 100.0


def test_export_pdf():
    peserta = build_rekap_peserta([row(1, "ONLINE", "HADIR", 1), row(2, None, None, 0)])
    kelas = {"nama_kelas": "Beri & Beri", "nama_wali_kelas": "W", "nama_batch": "B",
             "tanggal_mulai": date(2026, 4, 4), "tanggal_selesai": date(2027, 2, 28)}
    with patch.object(A, "is_wali_kelas", return_value=True), \
         patch.object(A, "get_info_kelas_rekap", return_value=kelas), \
         patch.object(A, "get_rekap_absensi_kelas", return_value={"daftar_bulan": [], "peserta": peserta}):
        res = app.test_client().get("/absensi/rekap/kelas/5/export?bulan=2026-11", headers=HEADERS)

    assert res.status_code == 200 and res.data.startswith(b"%PDF")
    assert "rekap_kehadiran_beri_beri_2026-11.pdf" in res.headers["Content-Disposition"]


def test_format_nama_dan_no_hp():
    from api.query.q_absensi import format_nama, format_no_hp

    assert format_nama("MUH  IKHSAN") == "Muh Ikhsan"
    assert format_nama("Friska masuang") == "Friska Masuang"
    assert format_nama("qori'atul hafizah") == "Qori'atul Hafizah"
    assert format_nama("A.Saskia Dwi Miranda") == "A.Saskia Dwi Miranda"
    assert format_nama("ribka angelina c.s") == "Ribka Angelina C.S"

    assert format_no_hp("82154665020") == "082154665020"
    assert format_no_hp("085241609302") == "085241609302"
    assert format_no_hp("+62 851-5684-8275") == "085156848275"
    assert format_no_hp("‪+62\xa0877‑3689‑3156‬") == "087736893156"
    assert format_no_hp("0813 1037 4757 ") == "081310374757"
    assert format_no_hp("0895324+11") == "0895324+11"  # rusak, tidak ditebak
    assert format_no_hp(None) is None
