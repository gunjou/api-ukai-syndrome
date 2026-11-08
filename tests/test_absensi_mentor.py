import io
import math
import sys

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_jwt_extended import JWTManager, create_access_token
from flask_restx import Api

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api.absensi as A  # noqa: E402

LAT, LON = -6.2, 106.8
M_PER_DEG = 6371000 * math.pi / 180
NOW = datetime(2026, 11, 8, 12, 0, 0)

app = Flask(__name__)
app.config.update(JWT_SECRET_KEY="test-secret-test-secret-test-secret-123")
JWTManager(app)
Api(app).add_namespace(A.absensi_ns, path="/absensi")
with app.app_context():
    TOKEN = create_access_token(identity="1", additional_claims={"role": "mentor"})


def post(path, form, row):
    update, insert = MagicMock(return_value={"ok": 1}), MagicMock(return_value={"ok": 1})
    cdn = MagicMock(ok=True)
    cdn.json.return_value = {"url": "http://cdn/x.jpg"}
    with patch.object(A, "get_user_nickname", return_value={"nickname": "m", "nama": "m"}), \
         patch.object(A, "get_absensi_mentor_for_checkout", return_value=row), \
         patch.object(A, "get_jadwal_absensi_mentor", return_value=row), \
         patch.object(A, "update_absensi_mentor_checkout", update), \
         patch.object(A, "insert_absensi_mentor_checkin", insert), \
         patch.object(A, "add_watermark", return_value=(io.BytesIO(b"x"), "a.jpg", "image/jpeg")) as watermark, \
         patch.object(A, "get_wib", return_value=NOW), \
         patch.object(A.requests, "post", return_value=cdn):
        res = app.test_client().post(
            path,
            headers={"Authorization": f"Bearer {TOKEN}"},
            content_type="multipart/form-data",
            data={"id_jadwal": "1", **form},
        )
    return res, update, insert, watermark


def checkout(meters=0, accuracy="10", in_acc=100.0, lat=None, lon=LON, check_in_at=NOW - timedelta(hours=3), end="11:00:00"):
    row = {
        "id_absensi_mentor": 1, "check_in_at": check_in_at.isoformat(), "check_out_at": None,
        "check_in_latitude": LAT, "check_in_longitude": LON, "check_in_accuracy": in_acc,
        "type_pertemuan": "OFFLINE", "tanggal_efektif": "2026-11-08", "waktu_selesai_efektif": end,
    }
    form = {"latitude": str(LAT + meters / M_PER_DEG if lat is None else lat), "longitude": str(lon),
            "evidence": (io.BytesIO(b"x"), "a.jpg")}
    if accuracy is not None:
        form["accuracy"] = accuracy
    return post("/absensi/mentor/check-out", form, row)


def checkin(lat, accuracy):
    return post("/absensi/mentor/check-in", {
        "latitude": str(lat), "longitude": str(LON), "accuracy": str(accuracy),
        "evidence_url": (io.BytesIO(b"x"), "a.jpg"),
    }, {"sudah_check_in": False, "type_pertemuan": "OFFLINE"})


@pytest.mark.parametrize("in_acc, out_acc, expected", [
    (10, 10, 120), (50, 50, 200), (100, 100, 300), (300, 300, 300), (None, 10, 210),
])
def test_radius_grows_with_accuracy_and_is_capped(in_acc, out_acc, expected):
    assert A.get_checkout_radius(in_acc, out_acc) == expected


@pytest.mark.parametrize("meters, in_acc, accuracy, status", [
    (119, 10.0, "10", 200),
    (121, 10.0, "10", 400),
    (160, 80.0, "80", 200),
    (299, 200.0, "200", 200),
    (301, 200.0, "200", 400),
])
def test_checkout_radius(meters, in_acc, accuracy, status):
    assert checkout(meters, accuracy, in_acc)[0].status_code == status


def test_rejection_hides_limit():
    res = checkout(125, "10", 10.0)[0].get_json()
    assert res["message"] == (
        "Anda berada di luar area check-in. "
        "Bergeser sekitar 6 meter ke arah selatan lalu coba lagi."
    )
    assert "data" not in res


@pytest.mark.parametrize("to_lat, to_lon, expected", [
    (LAT + 0.001, LON, "utara"), (LAT + 0.001, LON + 0.001, "timur laut"),
    (LAT, LON + 0.001, "timur"), (LAT - 0.001, LON + 0.001, "tenggara"),
    (LAT - 0.001, LON, "selatan"), (LAT - 0.001, LON - 0.001, "barat daya"),
    (LAT, LON - 0.001, "barat"), (LAT + 0.001, LON - 0.001, "barat laut"),
])
def test_compass_direction(to_lat, to_lon, expected):
    assert A.compass_direction(LAT, LON, to_lat, to_lon) == expected


def test_real_accuracy_is_stored_and_missing_uses_default():
    assert checkout(0, "42")[1].call_args[0][0]["accuracy"] == 42
    assert checkout(0, None)[1].call_args[0][0]["accuracy"] == 100


def test_too_inaccurate_is_rejected():
    res, update, *_ = checkout(0, "301")
    body = res.get_json()
    assert res.status_code == 400 and body["message"].startswith("Akurasi GPS terlalu rendah.")
    assert not any(ch.isdigit() for ch in body["message"]) and "data" not in body
    assert not update.called


@pytest.mark.parametrize("lat, lon, accuracy", [
    ("nan", "nan", "10"), ("inf", LON, "10"), ("999", LON, "10"), (LAT, "999", "10"), (LAT, LON, "-1"), (LAT, LON, "nan"),
])
def test_invalid_location_rejected(lat, lon, accuracy):
    res, update, *_ = checkout(lat=lat, lon=lon, accuracy=accuracy)
    assert res.status_code == 400 and res.get_json()["message"] == "Koordinat lokasi tidak valid"
    assert not update.called


def test_checkin_stores_real_accuracy_and_validates():
    assert checkin(LAT, 42)[2].call_args[0][0]["accuracy"] == 42
    res, _, insert, _ = checkin(999, 42)
    assert res.status_code == 400 and not insert.called


@pytest.mark.parametrize("minutes_ago, end, status", [
    (30, "14:00:00", 400),   # belum 2 jam, jadwal belum selesai
    (121, "14:00:00", 200),  # sudah 2 jam
    (30, "11:59:00", 200),   # jadwal efektif sudah selesai
])
def test_server_enforces_earliest_checkout(minutes_ago, end, status):
    assert checkout(check_in_at=NOW - timedelta(minutes=minutes_ago), end=end)[0].status_code == status


def test_checkout_photo_labeled_checkout():
    assert checkout()[3].call_args.kwargs["watermark_text"].startswith("CHECK-OUT")
