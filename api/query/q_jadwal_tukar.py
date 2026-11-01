from datetime import datetime, timedelta

from sqlalchemy import text, bindparam
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_value
from ..utils.config import get_connection, get_wib


# ============================================================================ #
#                                   KONSTANTA                                  #
# ============================================================================ #

STATUS_PENDING = "PENDING"
STATUS_DITERIMA = "DITERIMA"
STATUS_DITOLAK = "DITOLAK"
STATUS_DIBATALKAN = "DIBATALKAN"
STATUS_KADALUARSA = "KADALUARSA"

STATUS_TUKAR = (
    STATUS_PENDING,
    STATUS_DITERIMA,
    STATUS_DITOLAK,
    STATUS_DIBATALKAN,
    STATUS_KADALUARSA,
)

AKSI_DIAJUKAN = "DIAJUKAN"

SISI_ASAL = "ASAL"
SISI_TUJUAN = "TUJUAN"

EFF_TANGGAL = "COALESCE(j.tanggal_reschedule, j.tanggal)"
EFF_MULAI = "COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai)"
EFF_SELESAI = "COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai)"


class TukarError(Exception):
    """Error bisnis yang dibawa ke handler sebagai (message, http_code)."""

    def __init__(self, message, code=400, expire=False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.expire = expire


# ============================================================================ #
#                                 HELPER INTERNAL                              #
# ============================================================================ #

def _fmt_time(value):
    return value.strftime("%H:%M") if value else None


def _group_summary(group):
    return {
        "id_mentor": group["id_mentor"],
        "nama_mentor": group.get("nama_mentor"),
        "tanggal": group["tanggal"].isoformat(),
        "waktu_mulai": _fmt_time(group["waktu_mulai"]),
        "waktu_selesai": _fmt_time(group["waktu_selesai"]),
        "total_jadwal": len(group["id_jadwal_list"]),
        "id_jadwal_list": group["id_jadwal_list"],
    }


def _fetch_group_rows(conn, id_mentor, tanggal, waktu_mulai, waktu_selesai, lock=False):
    rows = conn.execute(text(f"""
        SELECT
            j.id_jadwal,
            j.id_mentor,
            j.id_paketkelas,
            pk.nama_kelas,
            j.id_kelompok,
            kb.nama_kelompok,
            j.topik,
            j.type_pertemuan,
            {EFF_TANGGAL} AS tanggal_efektif,
            {EFF_MULAI} AS waktu_mulai_efektif,
            {EFF_SELESAI} AS waktu_selesai_efektif
        FROM jadwal_kelas j
        LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
        LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
        WHERE j.id_mentor = :id_mentor
          AND j.status = 1
          AND {EFF_TANGGAL} = :tanggal
          AND {EFF_MULAI} = :waktu_mulai
          AND {EFF_SELESAI} = :waktu_selesai
        ORDER BY j.id_jadwal
        {"FOR UPDATE OF j" if lock else ""}
    """), {
        "id_mentor": id_mentor,
        "tanggal": tanggal,
        "waktu_mulai": waktu_mulai,
        "waktu_selesai": waktu_selesai,
    }).mappings().all()

    return [dict(r) for r in rows]


def _build_group(conn, rows):
    if not rows:
        return None

    first = rows[0]
    nama = conn.execute(
        text("SELECT nama FROM users WHERE id_user = :id"),
        {"id": first["id_mentor"]}
    ).scalar()

    return {
        "id_mentor": first["id_mentor"],
        "nama_mentor": nama,
        "tanggal": first["tanggal_efektif"],
        "waktu_mulai": first["waktu_mulai_efektif"],
        "waktu_selesai": first["waktu_selesai_efektif"],
        "id_jadwal_list": [r["id_jadwal"] for r in rows],
        "paketkelas_list": sorted({r["id_paketkelas"] for r in rows if r["id_paketkelas"] is not None}),
        "jadwal": rows,
    }


def _get_group_by_jadwal(conn, id_jadwal, lock=False):
    """Ambil seluruh grup (mentor + tanggal + jam efektif) dari satu id_jadwal."""

    base = conn.execute(text(f"""
        SELECT
            j.id_mentor,
            {EFF_TANGGAL} AS tanggal,
            {EFF_MULAI} AS waktu_mulai,
            {EFF_SELESAI} AS waktu_selesai
        FROM jadwal_kelas j
        WHERE j.id_jadwal = :id_jadwal
          AND j.status = 1
    """), {"id_jadwal": id_jadwal}).mappings().fetchone()

    if not base:
        return None

    rows = _fetch_group_rows(
        conn,
        base["id_mentor"],
        base["tanggal"],
        base["waktu_mulai"],
        base["waktu_selesai"],
        lock=lock,
    )

    return _build_group(conn, rows)


def _insert_log(conn, id_request, aksi, status_lama, status_baru, id_user, keterangan, now):
    conn.execute(text("""
        INSERT INTO jadwal_tukar_log (
            id_request, aksi, status_lama, status_baru,
            id_user, keterangan, created_at
        ) VALUES (
            :id_request, :aksi, :status_lama, :status_baru,
            :id_user, :keterangan, :now
        )
    """), {
        "id_request": id_request,
        "aksi": aksi,
        "status_lama": status_lama,
        "status_baru": status_baru,
        "id_user": id_user,
        "keterangan": keterangan,
        "now": now,
    })


def _set_status(conn, id_request, status_lama, status_baru, id_user, keterangan, now, catatan_respon=None, responded=False):
    conn.execute(text(f"""
        UPDATE jadwal_tukar_request
        SET status = :status,
            updated_at = :now
            {", catatan_respon = :catatan_respon, responded_at = :now" if responded else ""}
        WHERE id_request = :id_request
    """), {
        "status": status_baru,
        "now": now,
        "catatan_respon": catatan_respon,
        "id_request": id_request,
    })

    _insert_log(conn, id_request, status_baru, status_lama, status_baru, id_user, keterangan, now)


def expire_pending_lewat(conn):
    """Request PENDING yang salah satu grupnya sudah dimulai -> KADALUARSA."""

    now = get_wib()

    expired = conn.execute(text("""
        UPDATE jadwal_tukar_request
        SET status = :kadaluarsa,
            updated_at = :now
        WHERE status = :pending
          AND LEAST(
                tanggal_asal + waktu_mulai_asal,
                tanggal_tujuan + waktu_mulai_tujuan
              ) <= :now
        RETURNING id_request
    """), {
        "kadaluarsa": STATUS_KADALUARSA,
        "pending": STATUS_PENDING,
        "now": now,
    }).scalars().all()

    for id_request in expired:
        _insert_log(
            conn, id_request, STATUS_KADALUARSA, STATUS_PENDING, STATUS_KADALUARSA,
            None, "Jadwal sudah dimulai sebelum request direspon", now
        )


def _ids_have_absensi(conn, ids):
    stmt = text("""
        SELECT 1
        WHERE EXISTS (
            SELECT 1 FROM absensi_mentor WHERE id_jadwal IN :ids AND status = 1
        )
        OR EXISTS (
            SELECT 1 FROM absensi_peserta WHERE id_jadwal IN :ids AND status = 1
        )
    """).bindparams(bindparam("ids", expanding=True))

    return bool(conn.execute(stmt, {"ids": list(ids)}).fetchone())


def _ids_in_pending(conn, ids, exclude_request=None):
    stmt = text("""
        SELECT r.id_request
        FROM jadwal_tukar_request_detail d
        JOIN jadwal_tukar_request r ON r.id_request = d.id_request
        WHERE r.status = :pending
          AND d.id_jadwal IN :ids
          AND (CAST(:exclude AS INTEGER) IS NULL OR r.id_request <> :exclude)
        LIMIT 1
    """).bindparams(bindparam("ids", expanding=True))

    return conn.execute(stmt, {
        "pending": STATUS_PENDING,
        "ids": list(ids),
        "exclude": exclude_request,
    }).scalar()


def _mentor_missing_kelas(conn, id_mentor, paketkelas_list):
    """Return daftar id_paketkelas yang mentor TIDAK terdaftar."""

    if not paketkelas_list:
        return []

    stmt = text("""
        SELECT id_paketkelas
        FROM mentorkelas
        WHERE id_user = :id_mentor
          AND status = 1
          AND id_paketkelas IN :ids
    """).bindparams(bindparam("ids", expanding=True))

    terdaftar = set(conn.execute(stmt, {
        "id_mentor": id_mentor,
        "ids": list(paketkelas_list),
    }).scalars().all())

    return [p for p in paketkelas_list if p not in terdaftar]


def _mentor_has_conflict(conn, id_mentor, slot, exclude_ids):
    """Cek mentor punya jadwal aktif lain yang beririsan dengan slot."""

    stmt = text(f"""
        SELECT 1
        FROM jadwal_kelas j
        WHERE j.id_mentor = :id_mentor
          AND j.status = 1
          AND j.id_jadwal NOT IN :exclude
          AND {EFF_TANGGAL} = :tanggal
          AND {EFF_MULAI} < :waktu_selesai
          AND :waktu_mulai < {EFF_SELESAI}
        LIMIT 1
    """).bindparams(bindparam("exclude", expanding=True))

    return bool(conn.execute(stmt, {
        "id_mentor": id_mentor,
        "exclude": list(exclude_ids) or [0],
        "tanggal": slot["tanggal"],
        "waktu_mulai": slot["waktu_mulai"],
        "waktu_selesai": slot["waktu_selesai"],
    }).fetchone())


def _validate_pair(conn, asal, tujuan, now, exclude_request=None, check_pending=True):
    """Validasi aturan bisnis. Raise TukarError jika gagal."""

    if asal["id_mentor"] == tujuan["id_mentor"]:
        raise TukarError("Tidak dapat menukar jadwal dengan mentor yang sama", 400)

    for label, grup in (("asal", asal), ("tujuan", tujuan)):
        mulai = datetime.combine(grup["tanggal"], grup["waktu_mulai"])
        if mulai <= now:
            raise TukarError(f"Grup jadwal {label} sudah dimulai atau sudah lewat", 409, expire=True)

    all_ids = asal["id_jadwal_list"] + tujuan["id_jadwal_list"]

    if _ids_have_absensi(conn, all_ids):
        raise TukarError("Terdapat jadwal yang sudah memiliki absensi", 409, expire=True)

    missing = _mentor_missing_kelas(conn, tujuan["id_mentor"], asal["paketkelas_list"])
    if missing:
        raise TukarError(
            f"Mentor {tujuan.get('nama_mentor') or tujuan['id_mentor']} tidak terdaftar pada kelas grup asal",
            403,
        )

    missing = _mentor_missing_kelas(conn, asal["id_mentor"], tujuan["paketkelas_list"])
    if missing:
        raise TukarError(
            f"Mentor {asal.get('nama_mentor') or asal['id_mentor']} tidak terdaftar pada kelas grup tujuan",
            403,
        )

    # Mentor tujuan akan mengajar di slot asal; abaikan jadwal miliknya yang ikut ditukar
    if _mentor_has_conflict(conn, tujuan["id_mentor"], asal, tujuan["id_jadwal_list"]):
        raise TukarError("Mentor tujuan memiliki jadwal lain yang bentrok dengan grup asal", 409, expire=True)

    if _mentor_has_conflict(conn, asal["id_mentor"], tujuan, asal["id_jadwal_list"]):
        raise TukarError("Mentor pengaju memiliki jadwal lain yang bentrok dengan grup tujuan", 409, expire=True)

    if check_pending and _ids_in_pending(conn, all_ids, exclude_request):
        raise TukarError("Salah satu jadwal sudah ada di request tukar lain yang masih PENDING", 409)


def _get_request_row(conn, id_request, lock=False):
    row = conn.execute(text(f"""
        SELECT
            r.*,
            up.nama AS nama_pengaju,
            ut.nama AS nama_tujuan
        FROM jadwal_tukar_request r
        JOIN users up ON up.id_user = r.id_mentor_pengaju
        JOIN users ut ON ut.id_user = r.id_mentor_tujuan
        WHERE r.id_request = :id_request
        {"FOR UPDATE OF r" if lock else ""}
    """), {"id_request": id_request}).mappings().fetchone()

    return dict(row) if row else None


def _get_request_detail_ids(conn, id_request):
    rows = conn.execute(text("""
        SELECT id_jadwal, sisi
        FROM jadwal_tukar_request_detail
        WHERE id_request = :id_request
        ORDER BY id_jadwal
    """), {"id_request": id_request}).mappings().all()

    asal = [r["id_jadwal"] for r in rows if r["sisi"] == SISI_ASAL]
    tujuan = [r["id_jadwal"] for r in rows if r["sisi"] == SISI_TUJUAN]
    return asal, tujuan


def _format_request(row, id_user_login=None):
    data = {
        "id_request": row["id_request"],
        "status": row["status"],
        "mentor_pengaju": {"id_mentor": row["id_mentor_pengaju"], "nama": row["nama_pengaju"]},
        "mentor_tujuan": {"id_mentor": row["id_mentor_tujuan"], "nama": row["nama_tujuan"]},
        "grup_asal": {
            "tanggal": row["tanggal_asal"].isoformat(),
            "waktu_mulai": _fmt_time(row["waktu_mulai_asal"]),
            "waktu_selesai": _fmt_time(row["waktu_selesai_asal"]),
        },
        "grup_tujuan": {
            "tanggal": row["tanggal_tujuan"].isoformat(),
            "waktu_mulai": _fmt_time(row["waktu_mulai_tujuan"]),
            "waktu_selesai": _fmt_time(row["waktu_selesai_tujuan"]),
        },
        "alasan": row["alasan"],
        "catatan_respon": row["catatan_respon"],
        "responded_at": serialize_value(row["responded_at"]),
        "created_at": serialize_value(row["created_at"]),
        "updated_at": serialize_value(row["updated_at"]),
    }

    if "total_asal" in row:
        data["grup_asal"]["total_jadwal"] = row["total_asal"]
        data["grup_tujuan"]["total_jadwal"] = row["total_tujuan"]

    if id_user_login is not None:
        if row["id_mentor_pengaju"] == id_user_login:
            data["arah"] = "keluar"
        elif row["id_mentor_tujuan"] == id_user_login:
            data["arah"] = "masuk"

    return data


def _get_jadwal_detail_list(conn, ids):
    if not ids:
        return []

    stmt = text(f"""
        SELECT
            j.id_jadwal,
            j.id_mentor,
            u.nama AS nama_mentor,
            j.id_paketkelas,
            pk.nama_kelas,
            j.id_kelompok,
            kb.nama_kelompok,
            CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
            j.topik,
            j.catatan,
            j.type_pertemuan,
            j.status,
            {EFF_TANGGAL} AS tanggal_efektif,
            {EFF_MULAI} AS waktu_mulai_efektif,
            {EFF_SELESAI} AS waktu_selesai_efektif
        FROM jadwal_kelas j
        LEFT JOIN users u ON u.id_user = j.id_mentor
        LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
        LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
        WHERE j.id_jadwal IN :ids
        ORDER BY j.id_jadwal
    """).bindparams(bindparam("ids", expanding=True))

    return [serialize_value(dict(r)) for r in conn.execute(stmt, {"ids": list(ids)}).mappings().all()]


def _get_logs(conn, id_request):
    rows = conn.execute(text("""
        SELECT
            l.id_log, l.aksi, l.status_lama, l.status_baru,
            l.id_user, u.nama AS nama_user,
            l.keterangan, l.created_at
        FROM jadwal_tukar_log l
        LEFT JOIN users u ON u.id_user = l.id_user
        WHERE l.id_request = :id_request
        ORDER BY l.created_at, l.id_log
    """), {"id_request": id_request}).mappings().all()

    return [
        {
            "id_log": r["id_log"],
            "aksi": r["aksi"],
            "status_lama": r["status_lama"],
            "status_baru": r["status_baru"],
            "pelaku": {"id_user": r["id_user"], "nama": r["nama_user"]} if r["id_user"] else None,
            "keterangan": r["keterangan"],
            "created_at": serialize_value(r["created_at"]),
        }
        for r in rows
    ]


def _paginate_meta(page, per_page, total):
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if per_page else 0,
    }


# ============================================================================ #
#                                  KANDIDAT                                    #
# ============================================================================ #

def _validate_asal_only(conn, asal, now):
    """Validasi yang hanya bergantung pada grup asal (dipakai di kandidat)."""

    mulai = datetime.combine(asal["tanggal"], asal["waktu_mulai"])
    if mulai <= now:
        raise TukarError("Grup jadwal Anda sudah dimulai atau sudah lewat", 409)

    if _ids_have_absensi(conn, asal["id_jadwal_list"]):
        raise TukarError("Grup jadwal Anda sudah memiliki absensi", 409)

    if _ids_in_pending(conn, asal["id_jadwal_list"]):
        raise TukarError("Grup jadwal Anda sudah ada di request tukar yang masih PENDING", 409)


def get_kandidat_tukar(id_mentor, id_jadwal, tanggal=None, filter_mentor=None, search=None):
    """
    Return dict {grup_asal, kandidat, periode} atau raise TukarError.
    Semua aturan pada kandidat dicek dalam satu query (set-based).
    Tanpa filter tanggal, kandidat diambil dari hari ini s.d. 14 hari ke depan.
    """

    engine = get_connection()
    now = get_wib()

    with engine.connect() as conn:
        asal = _get_group_by_jadwal(conn, id_jadwal)

        if not asal:
            raise TukarError("Jadwal tidak ditemukan", 404)

        if asal["id_mentor"] != id_mentor:
            raise TukarError("Jadwal bukan milik Anda", 403)

        _validate_asal_only(conn, asal, now)

        if tanggal:
            start_date = end_date = tanggal
        else:
            start_date = now.date()
            end_date = start_date + timedelta(days=14)

        params = {
            "me": id_mentor,
            "start_date": start_date,
            "end_date": end_date,
            "now": now,
            "pending": STATUS_PENDING,
            "ids_asal": asal["id_jadwal_list"],
            "pks_asal": asal["paketkelas_list"],
            "n_pks_asal": len(asal["paketkelas_list"]),
            "tgl_asal": asal["tanggal"],
            "mulai_asal": asal["waktu_mulai"],
            "selesai_asal": asal["waktu_selesai"],
        }

        filter_sql = ""
        if filter_mentor:
            filter_sql += " AND j.id_mentor = :filter_mentor"
            params["filter_mentor"] = filter_mentor

        having_sql = ""
        if search and search.strip():
            having_sql = """
                HAVING bool_or(
                    u.nama ILIKE :search
                    OR pk.nama_kelas ILIKE :search
                    OR kb.nama_kelompok ILIKE :search
                )
            """
            params["search"] = f"%{search.strip()}%"

        X_TGL = "COALESCE(x.tanggal_reschedule, x.tanggal)"
        X_MULAI = "COALESCE(x.waktu_mulai_reschedule, x.waktu_mulai)"
        X_SELESAI = "COALESCE(x.waktu_selesai_reschedule, x.waktu_selesai)"

        groups = conn.execute(text(f"""
            WITH g AS (
                SELECT
                    j.id_mentor,
                    u.nama AS nama_mentor,
                    {EFF_TANGGAL} AS tanggal,
                    {EFF_MULAI} AS waktu_mulai,
                    {EFF_SELESAI} AS waktu_selesai,
                    array_agg(j.id_jadwal ORDER BY j.id_jadwal) AS ids,
                    COALESCE(
                        array_agg(DISTINCT j.id_paketkelas)
                            FILTER (WHERE j.id_paketkelas IS NOT NULL),
                        '{{}}'::integer[]
                    ) AS pks
                FROM jadwal_kelas j
                JOIN users u ON u.id_user = j.id_mentor
                LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
                LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
                WHERE j.status = 1
                  AND j.id_mentor <> :me
                  AND {EFF_TANGGAL} BETWEEN :start_date AND :end_date
                  {filter_sql}
                GROUP BY j.id_mentor, u.nama, 3, 4, 5
                {having_sql}
            )
            SELECT g.*
            FROM g
            WHERE (g.tanggal + g.waktu_mulai) > :now

              -- belum ada absensi
              AND NOT EXISTS (
                  SELECT 1 FROM absensi_mentor am
                  WHERE am.id_jadwal = ANY(g.ids) AND am.status = 1
              )
              AND NOT EXISTS (
                  SELECT 1 FROM absensi_peserta ap
                  WHERE ap.id_jadwal = ANY(g.ids) AND ap.status = 1
              )

              -- tidak ada di request PENDING
              AND NOT EXISTS (
                  SELECT 1
                  FROM jadwal_tukar_request_detail d
                  JOIN jadwal_tukar_request r ON r.id_request = d.id_request
                  WHERE r.status = :pending AND d.id_jadwal = ANY(g.ids)
              )

              -- mentor kandidat terdaftar di semua kelas grup asal
              AND (
                  SELECT COUNT(DISTINCT mk.id_paketkelas)
                  FROM mentorkelas mk
                  WHERE mk.id_user = g.id_mentor
                    AND mk.status = 1
                    AND mk.id_paketkelas = ANY(CAST(:pks_asal AS integer[]))
              ) = :n_pks_asal

              -- mentor asal terdaftar di semua kelas grup kandidat
              AND NOT EXISTS (
                  SELECT 1 FROM unnest(g.pks) AS p(id_paketkelas)
                  WHERE NOT EXISTS (
                      SELECT 1 FROM mentorkelas mk
                      WHERE mk.id_user = :me
                        AND mk.status = 1
                        AND mk.id_paketkelas = p.id_paketkelas
                  )
              )

              -- mentor kandidat tidak bentrok di slot asal
              AND NOT EXISTS (
                  SELECT 1 FROM jadwal_kelas x
                  WHERE x.id_mentor = g.id_mentor
                    AND x.status = 1
                    AND NOT (x.id_jadwal = ANY(g.ids))
                    AND {X_TGL} = :tgl_asal
                    AND {X_MULAI} < :selesai_asal
                    AND :mulai_asal < {X_SELESAI}
              )

              -- mentor asal tidak bentrok di slot kandidat
              AND NOT EXISTS (
                  SELECT 1 FROM jadwal_kelas x
                  WHERE x.id_mentor = :me
                    AND x.status = 1
                    AND NOT (x.id_jadwal = ANY(CAST(:ids_asal AS integer[])))
                    AND {X_TGL} = g.tanggal
                    AND {X_MULAI} < g.waktu_selesai
                    AND g.waktu_mulai < {X_SELESAI}
              )
            ORDER BY g.tanggal, g.waktu_mulai, g.nama_mentor
        """), params).mappings().all()

        all_ids = [i for g in groups for i in g["ids"]]
        detail_map = {}
        for d in _get_jadwal_detail_list(conn, all_ids):
            detail_map[d["id_jadwal"]] = {
                "id_jadwal": d["id_jadwal"],
                "nama_kelas": d["nama_kelas"],
                "nama_kelompok": d["nama_kelompok"],
                "topik": d["topik"],
                "type_pertemuan": d["type_pertemuan"],
            }

        kandidat = []
        for g in groups:
            item = _group_summary({
                "id_mentor": g["id_mentor"],
                "nama_mentor": g["nama_mentor"],
                "tanggal": g["tanggal"],
                "waktu_mulai": g["waktu_mulai"],
                "waktu_selesai": g["waktu_selesai"],
                "id_jadwal_list": list(g["ids"]),
            })
            item["jadwal"] = [detail_map[i] for i in g["ids"] if i in detail_map]
            kandidat.append(item)

        grup_asal = _group_summary(asal)
        grup_asal["jadwal"] = _get_jadwal_detail_list(conn, asal["id_jadwal_list"])

        return {
            "grup_asal": grup_asal,
            "kandidat": kandidat,
            "periode": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        }


# ============================================================================ #
#                                AJUKAN REQUEST                                #
# ============================================================================ #

def create_tukar_request(id_mentor, id_jadwal_asal, id_jadwal_tujuan, alasan=None):
    engine = get_connection()
    now = get_wib()

    with engine.begin() as conn:
        asal = _get_group_by_jadwal(conn, id_jadwal_asal, lock=True)
        tujuan = _get_group_by_jadwal(conn, id_jadwal_tujuan, lock=True)

        if not asal or not tujuan:
            raise TukarError("Jadwal tidak ditemukan atau tidak aktif", 404)

        if asal["id_mentor"] != id_mentor:
            raise TukarError("Jadwal asal bukan milik Anda", 403)

        _validate_pair(conn, asal, tujuan, now)

        id_request = conn.execute(text("""
            INSERT INTO jadwal_tukar_request (
                id_mentor_pengaju, id_mentor_tujuan,
                tanggal_asal, waktu_mulai_asal, waktu_selesai_asal,
                tanggal_tujuan, waktu_mulai_tujuan, waktu_selesai_tujuan,
                alasan, status, created_at, updated_at
            ) VALUES (
                :pengaju, :tujuan,
                :tgl_asal, :mulai_asal, :selesai_asal,
                :tgl_tujuan, :mulai_tujuan, :selesai_tujuan,
                :alasan, :status, :now, :now
            )
            RETURNING id_request
        """), {
            "pengaju": asal["id_mentor"],
            "tujuan": tujuan["id_mentor"],
            "tgl_asal": asal["tanggal"],
            "mulai_asal": asal["waktu_mulai"],
            "selesai_asal": asal["waktu_selesai"],
            "tgl_tujuan": tujuan["tanggal"],
            "mulai_tujuan": tujuan["waktu_mulai"],
            "selesai_tujuan": tujuan["waktu_selesai"],
            "alasan": alasan,
            "status": STATUS_PENDING,
            "now": now,
        }).scalar()

        detail_rows = (
            [{"id_request": id_request, "id_jadwal": i, "sisi": SISI_ASAL} for i in asal["id_jadwal_list"]]
            + [{"id_request": id_request, "id_jadwal": i, "sisi": SISI_TUJUAN} for i in tujuan["id_jadwal_list"]]
        )

        conn.execute(text("""
            INSERT INTO jadwal_tukar_request_detail (id_request, id_jadwal, sisi)
            VALUES (:id_request, :id_jadwal, :sisi)
        """), detail_rows)

        _insert_log(conn, id_request, AKSI_DIAJUKAN, None, STATUS_PENDING, id_mentor, alasan, now)

        return {
            "id_request": id_request,
            "status": STATUS_PENDING,
            "mentor_pengaju": {"id_mentor": asal["id_mentor"], "nama": asal["nama_mentor"]},
            "mentor_tujuan": {"id_mentor": tujuan["id_mentor"], "nama": tujuan["nama_mentor"]},
            "grup_asal": _group_summary(asal),
            "grup_tujuan": _group_summary(tujuan),
        }


# ============================================================================ #
#                                LIST & DETAIL                                 #
# ============================================================================ #

def get_tukar_requests(id_user, role, tipe="semua", status=None, id_mentor=None, page=1, per_page=20):
    engine = get_connection()

    with engine.begin() as conn:
        expire_pending_lewat(conn)

        where = "WHERE 1 = 1"
        params = {}

        if role == "mentor":
            if tipe == "masuk":
                where += " AND r.id_mentor_tujuan = :me"
            elif tipe == "keluar":
                where += " AND r.id_mentor_pengaju = :me"
            else:
                where += " AND (r.id_mentor_pengaju = :me OR r.id_mentor_tujuan = :me)"
            params["me"] = id_user

        elif id_mentor:
            where += " AND (r.id_mentor_pengaju = :id_mentor OR r.id_mentor_tujuan = :id_mentor)"
            params["id_mentor"] = id_mentor

        if status:
            where += " AND r.status = :status"
            params["status"] = status

        total = conn.execute(text(f"""
            SELECT COUNT(*) FROM jadwal_tukar_request r {where}
        """), params).scalar() or 0

        rows = conn.execute(text(f"""
            SELECT
                r.*,
                up.nama AS nama_pengaju,
                ut.nama AS nama_tujuan,
                (SELECT COUNT(*) FROM jadwal_tukar_request_detail d
                  WHERE d.id_request = r.id_request AND d.sisi = 'ASAL') AS total_asal,
                (SELECT COUNT(*) FROM jadwal_tukar_request_detail d
                  WHERE d.id_request = r.id_request AND d.sisi = 'TUJUAN') AS total_tujuan
            FROM jadwal_tukar_request r
            JOIN users up ON up.id_user = r.id_mentor_pengaju
            JOIN users ut ON ut.id_user = r.id_mentor_tujuan
            {where}
            ORDER BY r.created_at DESC, r.id_request DESC
            LIMIT :limit OFFSET :offset
        """), {**params, "limit": per_page, "offset": (page - 1) * per_page}).mappings().all()

        return {
            "data": [_format_request(dict(r), id_user if role == "mentor" else None) for r in rows],
            "meta": _paginate_meta(page, per_page, total),
        }


def get_tukar_request_detail(id_request, id_user, role):
    engine = get_connection()

    with engine.begin() as conn:
        expire_pending_lewat(conn)

        row = _get_request_row(conn, id_request)

        if not row:
            return None

        if role == "mentor" and id_user not in (row["id_mentor_pengaju"], row["id_mentor_tujuan"]):
            return None

        ids_asal, ids_tujuan = _get_request_detail_ids(conn, id_request)

        data = _format_request(row, id_user if role == "mentor" else None)
        data["grup_asal"]["total_jadwal"] = len(ids_asal)
        data["grup_tujuan"]["total_jadwal"] = len(ids_tujuan)
        data["grup_asal"]["jadwal"] = _get_jadwal_detail_list(conn, ids_asal)
        data["grup_tujuan"]["jadwal"] = _get_jadwal_detail_list(conn, ids_tujuan)

        if role == "admin":
            data["log"] = _get_logs(conn, id_request)

        return data


# ============================================================================ #
#                           TERIMA / TOLAK / BATAL                             #
# ============================================================================ #

def _load_pending_for(conn, id_request, id_user, field, label):
    row = _get_request_row(conn, id_request, lock=True)

    if not row:
        raise TukarError("Request tukar jadwal tidak ditemukan", 404)

    if row[field] != id_user:
        raise TukarError(f"Hanya {label} yang dapat melakukan aksi ini", 403)

    if row["status"] != STATUS_PENDING:
        raise TukarError(f"Request sudah berstatus {row['status']}", 409)

    return row


def accept_tukar_request(id_request, id_user, catatan_respon=None):
    """
    Return dict hasil, atau raise TukarError.
    Jika gagal karena kondisi jadwal berubah, request di-set KADALUARSA
    (perubahan status tetap di-commit) lalu TukarError dilempar ulang.
    """

    engine = get_connection()
    now = get_wib()
    error = None

    with engine.begin() as conn:
        row = _load_pending_for(conn, id_request, id_user, "id_mentor_tujuan", "mentor tujuan")
        snap_asal, snap_tujuan = _get_request_detail_ids(conn, id_request)

        asal_rows = _fetch_group_rows(
            conn, row["id_mentor_pengaju"], row["tanggal_asal"],
            row["waktu_mulai_asal"], row["waktu_selesai_asal"], lock=True
        )
        tujuan_rows = _fetch_group_rows(
            conn, row["id_mentor_tujuan"], row["tanggal_tujuan"],
            row["waktu_mulai_tujuan"], row["waktu_selesai_tujuan"], lock=True
        )

        asal = _build_group(conn, asal_rows)
        tujuan = _build_group(conn, tujuan_rows)

        try:
            if (
                not asal or not tujuan
                or asal["id_jadwal_list"] != snap_asal
                or tujuan["id_jadwal_list"] != snap_tujuan
            ):
                raise TukarError(
                    "Isi grup jadwal sudah berubah sejak request diajukan, silakan ajukan ulang",
                    409, expire=True
                )

            _validate_pair(conn, asal, tujuan, now, exclude_request=id_request)

        except TukarError as e:
            if e.expire:
                _set_status(conn, id_request, STATUS_PENDING, STATUS_KADALUARSA, None, e.message, now)
            error = e

        if error is None:
            update = text("""
                UPDATE jadwal_kelas
                SET id_mentor = :id_mentor,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal IN :ids
            """).bindparams(bindparam("ids", expanding=True))

            conn.execute(update, {
                "id_mentor": row["id_mentor_tujuan"],
                "updated_by": id_user,
                "now": now,
                "ids": snap_asal,
            })
            conn.execute(update, {
                "id_mentor": row["id_mentor_pengaju"],
                "updated_by": id_user,
                "now": now,
                "ids": snap_tujuan,
            })

            _set_status(
                conn, id_request, STATUS_PENDING, STATUS_DITERIMA, id_user,
                catatan_respon, now, catatan_respon=catatan_respon, responded=True
            )

            # Request PENDING lain yang memuat jadwal yang sama tidak lagi valid
            stmt = text("""
                SELECT r.id_request
                FROM jadwal_tukar_request r
                WHERE r.status = :pending
                  AND r.id_request <> :id_request
                  AND EXISTS (
                      SELECT 1 FROM jadwal_tukar_request_detail d
                      WHERE d.id_request = r.id_request
                        AND d.id_jadwal IN :ids
                  )
                FOR UPDATE OF r
            """).bindparams(bindparam("ids", expanding=True))

            others = conn.execute(stmt, {
                "pending": STATUS_PENDING,
                "id_request": id_request,
                "ids": snap_asal + snap_tujuan,
            }).scalars().all()

            for other in others:
                _set_status(
                    conn, other, STATUS_PENDING, STATUS_KADALUARSA, None,
                    f"Jadwal sudah ditukar melalui request #{id_request}", now
                )

    if error is not None:
        raise error

    return {
        "id_request": id_request,
        "status": STATUS_DITERIMA,
        "jadwal_ke_mentor_tujuan": snap_asal,
        "jadwal_ke_mentor_pengaju": snap_tujuan,
    }


def reject_tukar_request(id_request, id_user, catatan_respon=None):
    engine = get_connection()
    now = get_wib()

    with engine.begin() as conn:
        _load_pending_for(conn, id_request, id_user, "id_mentor_tujuan", "mentor tujuan")
        _set_status(
            conn, id_request, STATUS_PENDING, STATUS_DITOLAK, id_user,
            catatan_respon, now, catatan_respon=catatan_respon, responded=True
        )

    return {"id_request": id_request, "status": STATUS_DITOLAK}


def cancel_tukar_request(id_request, id_user):
    engine = get_connection()
    now = get_wib()

    with engine.begin() as conn:
        _load_pending_for(conn, id_request, id_user, "id_mentor_pengaju", "mentor pengaju")
        _set_status(conn, id_request, STATUS_PENDING, STATUS_DIBATALKAN, id_user, None, now)

    return {"id_request": id_request, "status": STATUS_DIBATALKAN}


# ============================================================================ #
#                                  LOG (ADMIN)                                 #
# ============================================================================ #

def get_tukar_logs(id_request=None, id_mentor=None, aksi=None, start_date=None, end_date=None, page=1, per_page=20):
    engine = get_connection()

    with engine.begin() as conn:
        expire_pending_lewat(conn)

        where = "WHERE 1 = 1"
        params = {}

        if id_request:
            where += " AND l.id_request = :id_request"
            params["id_request"] = id_request

        if id_mentor:
            where += " AND (r.id_mentor_pengaju = :id_mentor OR r.id_mentor_tujuan = :id_mentor)"
            params["id_mentor"] = id_mentor

        if aksi:
            where += " AND l.aksi = :aksi"
            params["aksi"] = aksi

        if start_date:
            where += " AND l.created_at >= :start_date"
            params["start_date"] = start_date

        if end_date:
            where += " AND l.created_at < :end_date"
            params["end_date"] = end_date + timedelta(days=1)

        base = f"""
            FROM jadwal_tukar_log l
            JOIN jadwal_tukar_request r ON r.id_request = l.id_request
            {where}
        """

        total = conn.execute(text(f"SELECT COUNT(*) {base}"), params).scalar() or 0

        rows = conn.execute(text(f"""
            SELECT
                l.id_log, l.id_request, l.aksi, l.status_lama, l.status_baru,
                l.id_user, ul.nama AS nama_user,
                r.id_mentor_pengaju, up.nama AS nama_pengaju,
                r.id_mentor_tujuan, ut.nama AS nama_tujuan,
                l.keterangan, l.created_at
            FROM jadwal_tukar_log l
            JOIN jadwal_tukar_request r ON r.id_request = l.id_request
            LEFT JOIN users ul ON ul.id_user = l.id_user
            JOIN users up ON up.id_user = r.id_mentor_pengaju
            JOIN users ut ON ut.id_user = r.id_mentor_tujuan
            {where}
            ORDER BY l.created_at DESC, l.id_log DESC
            LIMIT :limit OFFSET :offset
        """), {**params, "limit": per_page, "offset": (page - 1) * per_page}).mappings().all()

        data = [
            {
                "id_log": r["id_log"],
                "id_request": r["id_request"],
                "aksi": r["aksi"],
                "status_lama": r["status_lama"],
                "status_baru": r["status_baru"],
                "pelaku": {"id_user": r["id_user"], "nama": r["nama_user"]} if r["id_user"] else None,
                "mentor_pengaju": {"id_mentor": r["id_mentor_pengaju"], "nama": r["nama_pengaju"]},
                "mentor_tujuan": {"id_mentor": r["id_mentor_tujuan"], "nama": r["nama_tujuan"]},
                "keterangan": r["keterangan"],
                "created_at": serialize_value(r["created_at"]),
            }
            for r in rows
        ]

        return {"data": data, "meta": _paginate_meta(page, per_page, total)}
