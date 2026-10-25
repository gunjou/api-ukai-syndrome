from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.config import get_connection, get_wib
from ..utils.helper import serialize_value


# ============================================================================ #
#                     #ANCHOR - ROSTER JADWAL (KELAS / KELOMPOK)                #
# ============================================================================ #
# CTE daftar peserta yang seharusnya hadir pada satu jadwal (:id_jadwal):
# - jadwal kelas    -> peserta aktif pada kelas tsb
# - jadwal kelompok -> anggota aktif pada kelompok tsb
# Dipakai bersama oleh query roster, absensi, dan check-in peserta.

ROSTER_JADWAL_CTE = """
    WITH roster AS (
        SELECT pks.id_user AS id_peserta
        FROM jadwal_kelas jr
        INNER JOIN paketkelas pkr
            ON pkr.id_paketkelas = jr.id_paketkelas
           AND pkr.status = 1
        INNER JOIN pesertakelas pks
            ON pks.id_paketkelas = jr.id_paketkelas
           AND pks.status = 1
        WHERE jr.id_jadwal = :id_jadwal
          AND jr.status = 1

        UNION

        SELECT kbp.id_peserta
        FROM jadwal_kelas jr
        INNER JOIN kelompok_belajar kbr
            ON kbr.id_kelompok = jr.id_kelompok
           AND kbr.status = 1
        INNER JOIN kelompok_belajar_peserta kbp
            ON kbp.id_kelompok = jr.id_kelompok
           AND kbp.status = 1
        WHERE jr.id_jadwal = :id_jadwal
          AND jr.status = 1
    )
"""


# ============================================================================ #
#                   #ANCHOR - SHARED HELPER (ABSENSI PESERTA)                  #
# ============================================================================ #

def get_user_nickname(id_user):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    id_user,
                    nama,
                    nickname,
                    role,
                    status
                FROM users
                WHERE id_user = :id_user
                  AND status = 1
            """), {
                "id_user": id_user
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_user_nickname] Error: {e}")
        return None


def update_absensi_peserta(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE absensi_peserta
                SET
                    status_kehadiran = :status_kehadiran,
                    updated_at = :now
                WHERE id_absensi_peserta = :id_absensi_peserta
                  AND status = 1
                RETURNING id_absensi_peserta
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_absensi_peserta_by_id(result)

    except SQLAlchemyError as e:
        print(f"[update_absensi_peserta] Error: {e}")
        return None



# ============================================================================ #
#                    #ANCHOR - ABSENSI MENTOR (LIST & DETAIL)                  #
# ============================================================================ #

def get_all_absensi_mentor():
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_jadwal,
                    j.id_paketkelas, pk.nama_kelas,
                    j.id_kelompok, kb.nama_kelompok,
                    am.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor, j.topik, j.catatan,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai,
                    
                    j.type_pertemuan,
                    am.check_in_at, am.check_in_latitude, am.check_in_longitude, am.check_in_accuracy, am.evidence_checkin_url,
                    am.check_out_at, am.check_out_latitude, am.check_out_longitude, am.check_out_accuracy, am.evidence_checkout_url,
                    am.status, am.created_at, am.updated_at

                FROM absensi_mentor am
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = am.id_jadwal
                   AND j.status = 1
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = am.id_mentor
                   AND u.status = 1
                WHERE am.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                ORDER BY
                    COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) DESC,
                    COALESCE(
                        j.waktu_mulai_reschedule,
                        j.waktu_mulai
                    ) DESC,
                    am.id_absensi_mentor DESC
            """)).mappings().fetchall()

            return [serialize_value(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_all_absensi_mentor] Error: {e}")
        return []


def get_absensi_mentor_by_id(id_absensi):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok, am.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai, j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    
                    j.type_pertemuan,
                    am.check_in_at, am.check_in_latitude, am.check_in_longitude, am.check_in_accuracy, am.evidence_checkin_url,
                    am.check_out_at, am.check_out_latitude, am.check_out_longitude, am.check_out_accuracy, am.evidence_checkout_url,
                    am.status, am.created_at, am.updated_at

                FROM absensi_mentor am
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = am.id_jadwal
                   AND j.status = 1
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = am.id_mentor
                   AND u.status = 1
                WHERE am.id_absensi_mentor = :id_absensi
                  AND am.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
            """), {
                "id_absensi": id_absensi
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_absensi_mentor_by_id] Error: {e}")
        return None


def get_status_absensi_mentor_by_jadwal(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal,
                    j.id_paketkelas,
                    pk.nama_kelas,
                    j.id_kelompok,
                    kb.nama_kelompok,
                    j.id_mentor,
                    u.nama AS nama_mentor,
                    j.topik, 
                    j.catatan,
                    j.tanggal,
                    j.waktu_mulai,
                    j.waktu_selesai,
                    j.type_pertemuan,
                    am.id_absensi_mentor,
                    am.check_in_at,
                    am.check_out_at,
                    CASE
                        WHEN am.id_absensi_mentor IS NULL
                            THEN 'BELUM_CHECK_IN'
                        WHEN am.check_in_at IS NOT NULL
                            AND am.check_out_at IS NULL
                            THEN 'CHECK_IN'
                        WHEN am.check_in_at IS NOT NULL
                            AND am.check_out_at IS NOT NULL
                            THEN 'SELESAI'
                    END AS status_absensi
                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                    AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                    AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = j.id_mentor
                    AND u.status = 1
                LEFT JOIN absensi_mentor am
                    ON am.id_jadwal = j.id_jadwal
                    AND am.id_mentor = j.id_mentor
                    AND am.status = 1
                WHERE
                    j.id_jadwal = :id_jadwal
                    AND j.id_mentor = :id_mentor
                    AND j.status = 1
                    AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                LIMIT 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_status_absensi_mentor_by_jadwal] Error: {e}")
        return None


# ============================================================================ #
#                      #ANCHOR - ABSENSI MENTOR (CHECK-IN)                     #
# ============================================================================ #

def get_jadwal_absensi_mentor(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, j.id_kelompok, j.id_mentor, j.topik, j.catatan,
                    j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    j.type_pertemuan,

                    CASE
                        WHEN am.id_absensi_mentor IS NOT NULL
                        THEN TRUE
                        ELSE FALSE
                    END AS sudah_check_in

                FROM jadwal_kelas j
                LEFT JOIN absensi_mentor am
                    ON am.id_jadwal = j.id_jadwal
                   AND am.status = 1
                WHERE j.id_jadwal = :id_jadwal
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_absensi_mentor] Error: {e}")
        return None


def insert_absensi_mentor_checkin(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO absensi_mentor (
                    id_jadwal, id_mentor, check_in_at, check_in_latitude, check_in_longitude, check_in_accuracy, 
                    evidence_checkin_url, status, created_at, updated_at
                )
                VALUES (
                    :id_jadwal, :id_mentor, :now, :latitude, :longitude, :accuracy, :evidence_url, 1, :now, :now
                )
                RETURNING id_absensi_mentor
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            result_data = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_jadwal, am.id_mentor, am.check_in_at, am.check_in_latitude, am.check_in_longitude, 
                    am.check_in_accuracy, am.evidence_checkin_url, am.check_out_at, am.status, am.created_at, am.updated_at
                FROM absensi_mentor am
                WHERE am.id_absensi_mentor = :id_absensi
            """), {
                "id_absensi": result
            }).mappings().fetchone()

            return serialize_value(result_data)

    except SQLAlchemyError as e:
        print(f"[insert_absensi_mentor_checkin] Error: {e}")
        return None



# ============================================================================ #
#                      #ANCHOR - ABSENSI MENTOR (CHECK-OUT)                    #
# ============================================================================ #

def get_absensi_mentor_for_checkout(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_jadwal, am.id_mentor, am.check_in_at,
                    am.check_in_latitude, am.check_in_longitude, am.check_in_accuracy, am.check_out_at, 
                    j.type_pertemuan
                FROM absensi_mentor am
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = am.id_jadwal
                   AND j.status = 1
                WHERE am.id_jadwal = :id_jadwal
                  AND am.id_mentor = :id_mentor
                  AND am.status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(
            f"[get_absensi_mentor_for_checkout] "
            f"Error: {e}"
        )
        return None


def update_absensi_mentor_checkout(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE absensi_mentor
                SET
                    check_out_at = :now,
                    check_out_latitude = :latitude,
                    check_out_longitude = :longitude,
                    check_out_accuracy = :accuracy,
                    evidence_checkout_url = :evidence_url,
                    updated_at = :now
                WHERE id_absensi_mentor = :id_absensi_mentor
                  AND status = 1
                  AND check_out_at IS NULL
                RETURNING id_absensi_mentor
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            result_data = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_jadwal, am.id_mentor,
                    am.check_in_at, am.check_in_latitude, am.check_in_longitude, am.check_in_accuracy, am.evidence_checkin_url,
                    am.check_out_at, am.check_out_latitude, am.check_out_longitude, am.check_out_accuracy, am.evidence_checkout_url,
                    am.status, am.created_at, am.updated_at
                FROM absensi_mentor am
                WHERE am.id_absensi_mentor = :id_absensi
            """), {
                "id_absensi": result
            }).mappings().fetchone()

            return serialize_value(result_data)

    except SQLAlchemyError as e:
        print(
            f"[update_absensi_mentor_checkout] "
            f"Error: {e}"
        )
        return None



# ============================================================================ #
#                   #ANCHOR - ABSENSI PESERTA (LIST & DETAIL)                  #
# ============================================================================ #

def get_all_absensi_peserta():
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    ap.id_absensi_peserta, ap.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    ap.id_peserta, u.nama AS nama_peserta, u.nickname AS nickname_peserta, j.topik, j.catatan,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai,
                    
                    j.type_pertemuan, ap.status_kehadiran, ap.check_in_at, ap.latitude, ap.longitude, ap.location_accuracy,
                    ap.status, ap.created_at, ap.updated_at

                FROM absensi_peserta ap
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = ap.id_jadwal
                   AND j.status = 1
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = ap.id_peserta
                   AND u.status = 1
                WHERE ap.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                ORDER BY
                    COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) DESC,
                    COALESCE(
                        j.waktu_mulai_reschedule,
                        j.waktu_mulai
                    ) DESC,
                    ap.id_absensi_peserta DESC
            """)).mappings().fetchall()

            return [serialize_value(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_all_absensi_peserta] Error: {e}")
        return []


def get_absensi_peserta_by_id(id_absensi):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    ap.id_absensi_peserta, ap.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    ap.id_peserta, u.nama AS nama_peserta, u.nickname AS nickname_peserta,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    
                    j.type_pertemuan, ap.status_kehadiran, ap.check_in_at, ap.latitude, ap.longitude, ap.location_accuracy,
                    ap.status, ap.created_at, ap.updated_at
                    
                FROM absensi_peserta ap
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = ap.id_jadwal
                   AND j.status = 1
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = ap.id_peserta
                   AND u.status = 1
                WHERE ap.id_absensi_peserta = :id_absensi
                  AND ap.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
            """), {
                "id_absensi": id_absensi
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_absensi_peserta_by_id] Error: {e}")
        return None



# ============================================================================ #
#                 #ANCHOR - ABSENSI PESERTA (BERDASARKAN MENTOR)               #
# ============================================================================ #

def get_all_absensi_peserta_by_mentor(id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    ap.id_absensi_peserta, ap.id_jadwal,
                    j.id_paketkelas, pk.nama_kelas,
                    j.id_kelompok, kb.nama_kelompok,
                    ap.id_peserta, u.nama AS nama_peserta, u.nickname AS nickname_peserta, j.topik, j.catatan,
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai,
                    j.type_pertemuan,
                    ap.status_kehadiran, ap.check_in_at,
                    ap.latitude, ap.longitude, ap.location_accuracy,
                    ap.status, ap.created_at, ap.updated_at
                FROM absensi_peserta ap
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = ap.id_jadwal
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = ap.id_peserta
                WHERE ap.status = 1
                  AND j.status = 1
                  AND j.id_mentor = :id_mentor
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                  AND u.status = 1
                ORDER BY
                    COALESCE(j.tanggal_reschedule, j.tanggal) DESC,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) DESC,
                    ap.id_absensi_peserta DESC
            """), {
                "id_mentor": id_mentor
            }).mappings().fetchall()

            return [
                serialize_value(row)
                for row in result
            ]

    except SQLAlchemyError as e:
        print(
            f"[get_all_absensi_peserta_by_mentor] "
            f"Error: {e}"
        )
        return []


def get_absensi_peserta_by_id_mentor(id_absensi, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    ap.id_absensi_peserta, ap.id_jadwal,
                    j.id_paketkelas, pk.nama_kelas,
                    j.id_kelompok, kb.nama_kelompok,
                    ap.id_peserta, u.nama AS nama_peserta, u.nickname AS nickname_peserta,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    
                    j.type_pertemuan,
                    ap.status_kehadiran, ap.check_in_at,
                    ap.latitude, ap.longitude, ap.location_accuracy,
                    ap.status, ap.created_at, ap.updated_at
                FROM absensi_peserta ap
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = ap.id_jadwal
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = ap.id_peserta
                WHERE ap.id_absensi_peserta = :id_absensi
                  AND ap.status = 1
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                  AND u.status = 1
            """), {
                "id_absensi": id_absensi,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_absensi_peserta_by_id_mentor] Error: {e}")
        return None


def update_absensi_peserta_by_mentor(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE absensi_peserta ap
                SET
                    status_kehadiran = :status_kehadiran,
                    updated_at = :now
                FROM jadwal_kelas j
                WHERE ap.id_absensi_peserta = :id_absensi_peserta
                  AND ap.id_jadwal = j.id_jadwal
                  AND ap.status = 1
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
                RETURNING ap.id_absensi_peserta
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_absensi_peserta_by_id_mentor(
                result,
                payload["id_mentor"]
            )

    except SQLAlchemyError as e:
        print(f"[update_absensi_peserta_by_mentor] Error: {e}")
        return None


def delete_absensi_peserta_by_mentor(id_absensi, id_mentor):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE absensi_peserta ap
                SET
                    status = 0,
                    updated_at = :now
                FROM jadwal_kelas j
                WHERE ap.id_absensi_peserta = :id_absensi
                  AND ap.id_jadwal = j.id_jadwal
                  AND ap.status = 1
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
                RETURNING ap.id_absensi_peserta
            """), {
                "id_absensi": id_absensi,
                "id_mentor": id_mentor,
                "now": get_wib()
            }).scalar()

            return result is not None

    except SQLAlchemyError as e:
        print(f"[delete_absensi_peserta_by_mentor] Error: {e}")
        return False



# ============================================================================ #
#                 #ANCHOR - ABSENSI PESERTA (BERDASARKAN JADWAL)               #
# ============================================================================ #

def get_jadwal_absensi_peserta(id_jadwal):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    j.id_mentor, u.nama AS nama_mentor, j.topik, j.catatan,
                    j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    j.type_pertemuan, j.status
                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = j.id_mentor
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                  AND u.status = 1
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_absensi_peserta] Error: {e}")
        return None


def get_jadwal_absensi_peserta_by_mentor(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    j.id_mentor, u.nama AS nama_mentor, j.topik, j.catatan,
                    j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    j.type_pertemuan, j.status
                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users u
                    ON u.id_user = j.id_mentor
                WHERE j.id_jadwal = :id_jadwal
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
                  AND u.status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_absensi_peserta_by_mentor] Error: {e}")
        return None


def get_absensi_peserta_by_jadwal(id_jadwal):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            # ==========================================
            # Roster mengikuti target jadwal:
            # kelas -> pesertakelas, kelompok -> anggota kelompok
            # ==========================================

            result = conn.execute(text(f"""
                {ROSTER_JADWAL_CTE}
                SELECT
                    u.id_user AS id_peserta, u.nama, u.nickname,
                    pk.id_paketkelas, pk.nama_kelas,
                    kb.id_kelompok, kb.nama_kelompok,
                    j.id_jadwal,
                    COALESCE(ap.status_kehadiran, 'ALPHA') AS status_kehadiran,
                    ap.id_absensi_peserta, ap.check_in_at,
                    ap.latitude, ap.longitude, ap.location_accuracy,
                    CASE
                        WHEN ap.id_absensi_peserta IS NULL THEN FALSE
                        ELSE TRUE
                    END AS sudah_absen
                FROM roster r
                INNER JOIN jadwal_kelas j
                    ON j.id_jadwal = :id_jadwal
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                INNER JOIN users u
                    ON u.id_user = r.id_peserta
                   AND u.role = 'peserta'
                   AND u.status = 1
                LEFT JOIN absensi_peserta ap
                    ON ap.id_jadwal = j.id_jadwal
                   AND ap.id_peserta = u.id_user
                   AND ap.status = 1
                ORDER BY u.nama ASC
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchall()

            return [
                serialize_value(row)
                for row in result
            ]

    except SQLAlchemyError as e:
        print(f"[get_absensi_peserta_by_jadwal] Error: {e}")
        return []


def get_absensi_by_jadwal(id_jadwal):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            jadwal = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    j.id_mentor, um.nama AS nama_mentor, um.nickname AS nickname_mentor,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                    j.type_pertemuan, j.status
                    
                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                INNER JOIN users um
                    ON um.id_user = j.id_mentor
                   AND um.status = 1
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
                  AND (pk.id_paketkelas IS NOT NULL OR kb.id_kelompok IS NOT NULL)
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchone()

            if not jadwal:
                return None

            mentor = conn.execute(text("""
                SELECT
                    am.id_absensi_mentor, am.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
                    am.check_in_at, am.check_in_latitude, am.check_in_longitude, am.check_in_accuracy, am.evidence_checkin_url,
                    am.check_out_at, am.check_out_latitude, am.check_out_longitude, am.check_out_accuracy, am.evidence_checkout_url,
                    am.status, am.created_at, am.updated_at
                FROM absensi_mentor am
                INNER JOIN users u
                    ON u.id_user = am.id_mentor
                   AND u.status = 1
                WHERE am.id_jadwal = :id_jadwal
                  AND am.status = 1
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchone()

            peserta = conn.execute(text(f"""
                {ROSTER_JADWAL_CTE}
                SELECT
                    u.id_user AS id_peserta, u.nama AS nama_peserta, u.nickname AS nickname_peserta,
                    ap.id_absensi_peserta, ap.status_kehadiran, ap.check_in_at, ap.latitude, ap.longitude, ap.location_accuracy, ap.status
                FROM roster r
                INNER JOIN users u
                    ON u.id_user = r.id_peserta
                   AND u.role = 'peserta'
                   AND u.status = 1
                LEFT JOIN absensi_peserta ap
                    ON ap.id_peserta = r.id_peserta
                   AND ap.id_jadwal = :id_jadwal
                   AND ap.status = 1
                ORDER BY u.nama ASC
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchall()

            peserta_data = []

            for row in peserta:
                data = dict(row)

                if data["id_absensi_peserta"] is None:
                    data["status_kehadiran"] = "BELUM ABSEN"

                peserta_data.append(
                    serialize_value(data)
                )

            return {
                "jadwal": serialize_value(jadwal),
                "mentor": serialize_value(mentor),
                "peserta": peserta_data
            }

    except SQLAlchemyError as e:
        print(f"[get_absensi_by_jadwal] Error: {e}")
        return None



# ============================================================================ #
#                       #ANCHOR - ABSENSI PESERTA (MANUAL)                     #
# ============================================================================ #

def get_jadwal_for_manual_attendance(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, j.id_kelompok, j.id_mentor, j.topik, j.catatan,
                    j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                    j.type_pertemuan
                FROM jadwal_kelas j
                WHERE j.id_jadwal = :id_jadwal
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_for_manual_attendance] Error: {e}")
        return None


def get_peserta_for_manual_attendance(id_peserta, id_paketkelas):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    u.id_user, u.nama, u.nickname
                FROM pesertakelas pks
                INNER JOIN users u
                    ON u.id_user = pks.id_user
                WHERE pks.id_user = :id_peserta
                  AND pks.id_paketkelas = :id_paketkelas
                  AND pks.status = 1
                  AND u.role = 'peserta'
                  AND u.status = 1
            """), {
                "id_peserta": id_peserta,
                "id_paketkelas": id_paketkelas
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_peserta_for_manual_attendance] Error: {e}")
        return None


def get_absensi_peserta_by_jadwal_peserta(id_jadwal, id_peserta):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    id_absensi_peserta, id_jadwal, id_peserta,
                    status_kehadiran, status
                FROM absensi_peserta
                WHERE id_jadwal = :id_jadwal
                  AND id_peserta = :id_peserta
                  AND status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_peserta": id_peserta
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_absensi_peserta_by_jadwal_peserta] Error: {e}")
        return None


def insert_absensi_peserta_manual(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO absensi_peserta (
                    id_jadwal, id_peserta, status_kehadiran, status, created_at, updated_at
                )
                VALUES (
                    :id_jadwal, :id_peserta, :status_kehadiran, 1, :now, :now
                )
                RETURNING id_absensi_peserta
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_absensi_peserta_by_id(result)

    except SQLAlchemyError as e:
        print(f"[insert_absensi_peserta_manual] Error: {e}")
        return None



# ============================================================================ #
#                     #ANCHOR - PESERTA (BERDASARKAN KELAS)                    #
# ============================================================================ #

def get_peserta_by_mentor(id_mentor, id_paketkelas):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    u.id_user AS id_peserta, u.nama, u.email
                FROM mentorkelas mk
                INNER JOIN paketkelas pk
                    ON pk.id_paketkelas = mk.id_paketkelas
                INNER JOIN pesertakelas pks
                    ON pks.id_paketkelas = pk.id_paketkelas
                INNER JOIN users u
                    ON u.id_user = pks.id_user
                WHERE mk.id_user = :id_mentor
                  AND mk.id_paketkelas = :id_paketkelas
                  AND mk.status = 1
                  AND pk.status = 1
                  AND pks.status = 1
                  AND u.role = 'peserta'
                  AND u.status = 1
                ORDER BY u.nama ASC
            """), {
                "id_mentor": id_mentor,
                "id_paketkelas": id_paketkelas
            }).mappings().fetchall()

            return [
                serialize_value(row)
                for row in result
            ]

    except SQLAlchemyError as e:
        print(f"[get_peserta_by_mentor] Error: {e}")
        return []



# ============================================================================ #
#                  #ANCHOR - PESERTA BERDASARKAN ROSTER JADWAL                 #
# ============================================================================ #

def get_peserta_roster_jadwal(id_jadwal, id_peserta):
    """Cek peserta termasuk roster jadwal (berlaku untuk jadwal kelas maupun kelompok)"""

    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                {ROSTER_JADWAL_CTE}
                SELECT u.id_user, u.nama, u.nickname
                FROM roster r
                INNER JOIN users u
                    ON u.id_user = r.id_peserta
                   AND u.role = 'peserta'
                   AND u.status = 1
                WHERE r.id_peserta = :id_peserta
            """), {
                "id_jadwal": id_jadwal,
                "id_peserta": id_peserta
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_peserta_roster_jadwal] Error: {e}")
        return None



# ============================================================================ #
#                       #ANCHOR - ABSENSI PESERTA (CHECK-IN)                   #
# ============================================================================ #

def get_jadwal_for_peserta_checkin(id_jadwal, id_peserta):
    """
    Data yang dibutuhkan untuk check-in mandiri peserta.
    Hanya mengembalikan jadwal jika peserta termasuk roster jadwal tsb.
    """

    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                {ROSTER_JADWAL_CTE}
                SELECT
                    j.id_jadwal, j.id_paketkelas, j.id_kelompok, j.id_mentor, j.type_pertemuan,

                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                    (COALESCE(j.tanggal_reschedule, j.tanggal) = :today) AS is_hari_ini,

                    am.id_absensi_mentor,
                    am.check_in_at AS mentor_check_in_at,
                    am.check_out_at AS mentor_check_out_at,
                    am.check_in_latitude AS mentor_latitude,
                    am.check_in_longitude AS mentor_longitude,

                    ap.id_absensi_peserta
                FROM jadwal_kelas j
                LEFT JOIN absensi_mentor am
                    ON am.id_jadwal = j.id_jadwal
                   AND am.status = 1
                LEFT JOIN absensi_peserta ap
                    ON ap.id_jadwal = j.id_jadwal
                   AND ap.id_peserta = :id_peserta
                   AND ap.status = 1
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
                  AND EXISTS (
                      SELECT 1 FROM roster r WHERE r.id_peserta = :id_peserta
                  )
            """), {
                "id_jadwal": id_jadwal,
                "id_peserta": id_peserta,
                "today": get_wib().date()
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_for_peserta_checkin] Error: {e}")
        return None


def insert_absensi_peserta_checkin(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO absensi_peserta (
                    id_jadwal, id_peserta, status_kehadiran, check_in_at,
                    latitude, longitude, location_accuracy, status, created_at, updated_at
                )
                VALUES (
                    :id_jadwal, :id_peserta, 'HADIR', :now,
                    :latitude, :longitude, :accuracy, 1, :now, :now
                )
                RETURNING id_absensi_peserta
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_absensi_peserta_by_id(result)

    except SQLAlchemyError as e:
        print(f"[insert_absensi_peserta_checkin] Error: {e}")
        return None
