from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_value
from ..utils.config import get_connection, get_wib


# ============================================================================ #
#                                    HELPER                                    #
# ============================================================================ #

def is_valid_paketkelas(id_paketkelas):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_paketkelas FROM paketkelas WHERE id_paketkelas = :id_paketkelas AND status = 1
            """), {
                "id_paketkelas": id_paketkelas
            }).scalar()

            return result is not None

    except SQLAlchemyError as e:
        print(f"[is_valid_paketkelas] Error: {e}")
        return False


def is_valid_mentor(id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text(""" 
                SELECT id_user FROM users WHERE id_user = :id_mentor AND role = 'mentor' AND status = 1
            """), {
                "id_mentor": id_mentor
            }).scalar()

            return result is not None

    except SQLAlchemyError as e:
        print(f"[is_valid_mentor] Error: {e}")
        return False


def is_mentor_of_kelas(id_mentor, id_paketkelas):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1 FROM mentorkelas WHERE id_user = :id_mentor AND id_paketkelas = :id_paketkelas AND status = 1
            """), {
                "id_mentor": id_mentor,
                "id_paketkelas": id_paketkelas
            }).fetchone()

            return bool(result)

    except SQLAlchemyError as e:
        print(f"[is_mentor_of_kelas] Error: {e}")
        return False


def is_wali_kelas(id_mentor, id_paketkelas):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1 FROM paketkelas WHERE id_paketkelas = :id_paketkelas AND id_user = :id_mentor AND status = 1
            """), {
                "id_paketkelas": id_paketkelas,
                "id_mentor": id_mentor
            }).fetchone()

            return bool(result)

    except SQLAlchemyError as e:
        print(f"[is_wali_kelas] Error: {e}")
        return False


def is_valid_kelompok(id_kelompok):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id_kelompok FROM kelompok_belajar WHERE id_kelompok = :id_kelompok AND status = 1
            """), {
                "id_kelompok": id_kelompok
            }).scalar()

            return result is not None

    except SQLAlchemyError as e:
        print(f"[is_valid_kelompok] Error: {e}")
        return False


def is_jadwal_has_absensi(id_jadwal):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 1
                WHERE EXISTS (
                    SELECT 1 FROM absensi_mentor WHERE id_jadwal = :id_jadwal AND status = 1
                )
                OR EXISTS (
                    SELECT 1 FROM absensi_peserta WHERE id_jadwal = :id_jadwal AND status = 1
                )
            """), {
                "id_jadwal": id_jadwal
            }).fetchone()

            return bool(result)

    except SQLAlchemyError as e:
        print(f"[is_jadwal_has_absensi] Error: {e}")
        return False


def get_mentor_dropdown(id_paketkelas=None):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            if id_paketkelas is not None:
                query = text("""
                    SELECT u.id_user, u.nama, u.nickname
                    FROM users u
                    INNER JOIN mentorkelas mk
                        ON mk.id_user = u.id_user
                       AND mk.status = 1
                       AND mk.id_paketkelas = :id_paketkelas
                    WHERE u.role = 'mentor'
                      AND u.status = 1
                    ORDER BY u.nama ASC
                """)

                params = {
                    "id_paketkelas": id_paketkelas
                }

            else:
                query = text("""
                    SELECT u.id_user, u.nama, u.nickname
                    FROM users u
                    WHERE u.role = 'mentor'
                      AND u.status = 1
                    ORDER BY u.nama ASC
                """)

                params = {}

            result = conn.execute(
                query,
                params
            ).mappings().fetchall()

            return [
                serialize_value(row)
                for row in result
            ]

    except SQLAlchemyError as e:
        print(f"[get_mentor_dropdown] Error: {e}")
        return []


# ============================================================================ #
#                          MANAJEMEN JADWAL BY - ADMIN                         #
# ============================================================================ #

def insert_jadwal(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO jadwal_kelas (
                    id_paketkelas, id_kelompok, id_mentor, topik, catatan, tanggal, waktu_mulai, waktu_selesai, type_pertemuan, 
                    status, created_by, created_at, updated_by, updated_at
                )
                VALUES (
                    :id_paketkelas, :id_kelompok, :id_mentor, :topik, :catatan, :tanggal, :waktu_mulai, :waktu_selesai, :type_pertemuan, 
                    1, :created_by, :now, :updated_by, :now
                )
                RETURNING
                    id_jadwal, id_paketkelas, id_kelompok, id_mentor, topik, catatan, tanggal, waktu_mulai, waktu_selesai, type_pertemuan,
                    status, created_by, created_at, updated_by, updated_at
            """), {
                **payload,
                "now": get_wib()
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[insert_jadwal] Error: {e}")
        return None


def get_all_jadwal(
    id_mentor=None,
    id_paketkelas=None,
    search=None,
    id_kelompok=None,
    start_date=None,
    end_date=None,
    page=1,
    per_page=50,
    type_pertemuan=None
):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            where_clause = "WHERE j.status = 1"
            params = {}

            if start_date is not None:
                where_clause += """
                    AND COALESCE(j.tanggal_reschedule, j.tanggal) >= :start_date
                """
                params["start_date"] = start_date

            if end_date is not None:
                where_clause += """
                    AND COALESCE(j.tanggal_reschedule, j.tanggal) <= :end_date
                """
                params["end_date"] = end_date

            if id_mentor is not None:
                where_clause += " AND j.id_mentor = :id_mentor"
                params["id_mentor"] = id_mentor

            if id_paketkelas is not None:
                where_clause += " AND j.id_paketkelas = :id_paketkelas"
                params["id_paketkelas"] = id_paketkelas

            if id_kelompok is not None:
                where_clause += " AND j.id_kelompok = :id_kelompok"
                params["id_kelompok"] = id_kelompok

            if type_pertemuan:
                where_clause += " AND j.type_pertemuan = :type_pertemuan"
                params["type_pertemuan"] = type_pertemuan

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
                        OR kb.nama_kelompok ILIKE :search
                        OR j.topik ILIKE :search
                        OR j.catatan ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            count_result = conn.execute(
                text(f"""
                    SELECT COUNT(*)
                    FROM jadwal_kelas j
                    LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
                    LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
                    LEFT JOIN users u ON u.id_user = j.id_mentor
                    {where_clause}
                """),
                params
            ).scalar()

            total = count_result or 0
            offset = (page - 1) * per_page

            params["limit"] = per_page
            params["offset"] = offset

            result = conn.execute(
                text(f"""
                    SELECT
                        j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                        CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
                        j.id_mentor, u.nama AS nama_mentor,
                        u.nickname AS nickname_mentor,j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                        j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                        COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                        COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                        j.type_pertemuan, j.status, j.created_by, j.created_at, j.updated_by, j.updated_at
                    FROM jadwal_kelas j
                    LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
                    LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
                    LEFT JOIN users u ON u.id_user = j.id_mentor
                    {where_clause}
                    ORDER BY
                        COALESCE(j.tanggal_reschedule, j.tanggal) ASC,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) ASC,
                        j.id_jadwal ASC
                    LIMIT :limit
                    OFFSET :offset
                """),
                params
            ).mappings().fetchall()

            data = [serialize_value(row) for row in result]

            total_pages = (total + per_page - 1) // per_page if total > 0 else 0

            return {
                "data": data,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages
            }

    except SQLAlchemyError as e:
        print(f"[get_all_jadwal] Error: {e}")
        raise


def get_jadwal_by_id(id_jadwal):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
                    j.id_mentor, u.nama AS nama_mentor,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                    j.type_pertemuan, j.status, j.created_by, j.created_at, j.updated_by, j.updated_at

                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                LEFT JOIN users u
                    ON u.id_user = j.id_mentor
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
            """), {
                "id_jadwal": id_jadwal
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_by_id] Error: {e}")
        return None


def update_jadwal(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    id_paketkelas = :id_paketkelas,
                    id_kelompok = :id_kelompok,
                    id_mentor = :id_mentor,
                    topik = :topik,
                    catatan = :catatan,
                    tanggal = :tanggal,
                    waktu_mulai = :waktu_mulai,
                    waktu_selesai = :waktu_selesai,
                    type_pertemuan = :type_pertemuan,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                RETURNING id_jadwal
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_jadwal_by_id(result)

    except SQLAlchemyError as e:
        print(f"[update_jadwal] Error: {e}")
        return None


def switch_mentor_jadwal(id_jadwal_1, id_jadwal_2, id_user, role):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            jadwal_1 = conn.execute(text("""
                SELECT id_jadwal, id_mentor
                FROM jadwal_kelas
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                FOR UPDATE
            """), {
                "id_jadwal": id_jadwal_1
            }).mappings().fetchone()

            jadwal_2 = conn.execute(text("""
                SELECT id_jadwal, id_mentor
                FROM jadwal_kelas
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                FOR UPDATE
            """), {
                "id_jadwal": id_jadwal_2
            }).mappings().fetchone()

            if not jadwal_1 or not jadwal_2:
                return None

            if role == "mentor":
                if (
                    jadwal_1["id_mentor"] != id_user
                    and jadwal_2["id_mentor"] != id_user
                ):
                    return None

            mentor_1 = jadwal_1["id_mentor"]
            mentor_2 = jadwal_2["id_mentor"]
            now = get_wib()

            conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    id_mentor = :id_mentor,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
            """), {
                "id_jadwal": id_jadwal_1,
                "id_mentor": mentor_2,
                "updated_by": id_user,
                "now": now
            })

            conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    id_mentor = :id_mentor,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
            """), {
                "id_jadwal": id_jadwal_2,
                "id_mentor": mentor_1,
                "updated_by": id_user,
                "now": now
            })

            return {
                "id_jadwal_1": id_jadwal_1,
                "id_mentor_1": mentor_2,
                "id_jadwal_2": id_jadwal_2,
                "id_mentor_2": mentor_1
            }

    except SQLAlchemyError as e:
        print(f"[switch_mentor_jadwal] Error: {e}")
        return None


def reschedule_jadwal(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    tanggal_reschedule = :tanggal_reschedule,
                    waktu_mulai_reschedule = :waktu_mulai_reschedule,
                    waktu_selesai_reschedule = :waktu_selesai_reschedule,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                RETURNING id_jadwal
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_jadwal_by_id(result)

    except SQLAlchemyError as e:
        print(f"[reschedule_jadwal] Error: {e}")
        return None


def delete_jadwal(id_jadwal, id_user):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    status = 0,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                RETURNING id_jadwal
            """), {
                "id_jadwal": id_jadwal,
                "updated_by": id_user,
                "now": get_wib()
            }).scalar()

            return result is not None

    except SQLAlchemyError as e:
        print(f"[delete_jadwal] Error: {e}")
        return False



# ============================================================================ #
#                         MANAJEMEN JADWAL BY - MENTOR                         #
# ============================================================================ #
def get_all_jadwal_by_mentor(
    id_mentor,
    search=None,
    start_date=None,
    end_date=None,
    type_pertemuan=None
):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            where_clause = """
                WHERE j.id_mentor = :id_mentor
                  AND j.status = 1
            """

            params = {
                "id_mentor": id_mentor
            }

            if start_date is not None:
                where_clause += """
                    AND COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) >= :start_date
                """
                params["start_date"] = start_date

            if end_date is not None:
                where_clause += """
                    AND COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) <= :end_date
                """
                params["end_date"] = end_date

            if type_pertemuan:
                where_clause += " AND j.type_pertemuan = :type_pertemuan"
                params["type_pertemuan"] = type_pertemuan

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
                        OR kb.nama_kelompok ILIKE :search
                        OR j.topik ILIKE :search
                        OR j.catatan ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            result = conn.execute(
                text(f"""
                    SELECT
                        j.id_jadwal,
                        j.id_paketkelas,
                        pk.nama_kelas,
                        j.id_kelompok,
                        kb.nama_kelompok,
                        CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
                        j.id_mentor,
                        u.nama AS nama_mentor,
                        u.nickname AS nickname_mentor,
                        j.topik,
                        j.catatan,
                        j.tanggal,
                        j.waktu_mulai,
                        j.waktu_selesai,
                        j.tanggal_reschedule,
                        j.waktu_mulai_reschedule,
                        j.waktu_selesai_reschedule,

                        COALESCE(
                            j.tanggal_reschedule,
                            j.tanggal
                        ) AS tanggal_efektif,

                        COALESCE(
                            j.waktu_mulai_reschedule,
                            j.waktu_mulai
                        ) AS waktu_mulai_efektif,

                        COALESCE(
                            j.waktu_selesai_reschedule,
                            j.waktu_selesai
                        ) AS waktu_selesai_efektif,

                        j.type_pertemuan,
                        j.status,
                        j.created_by,
                        j.created_at,
                        j.updated_by,
                        j.updated_at

                    FROM jadwal_kelas j

                    LEFT JOIN paketkelas pk
                        ON pk.id_paketkelas = j.id_paketkelas
                       AND pk.status = 1

                    LEFT JOIN kelompok_belajar kb
                        ON kb.id_kelompok = j.id_kelompok
                       AND kb.status = 1

                    LEFT JOIN users u
                        ON u.id_user = j.id_mentor
                       AND u.status = 1

                    {where_clause}

                    ORDER BY
                        COALESCE(
                            j.tanggal_reschedule,
                            j.tanggal
                        ) ASC,

                        COALESCE(
                            j.waktu_mulai_reschedule,
                            j.waktu_mulai
                        ) ASC,

                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            return [
                serialize_value(row)
                for row in result
            ]

    except SQLAlchemyError as e:
        print(f"[get_all_jadwal_by_mentor] Error: {e}")
        raise


def get_jadwal_by_id_mentor(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                    CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
                    j.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                    j.type_pertemuan, j.status, j.created_by, j.created_at, j.updated_by, j.updated_at

                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1
                LEFT JOIN users u
                    ON u.id_user = j.id_mentor
                   AND u.status = 1
                WHERE j.id_jadwal = :id_jadwal
                  AND j.id_mentor = :id_mentor
                  AND j.status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            return serialize_value(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_by_id_mentor] Error: {e}")
        return None


def reschedule_jadwal_by_mentor(payload):
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    tanggal_reschedule = :tanggal_reschedule,
                    waktu_mulai_reschedule = :waktu_mulai_reschedule,
                    waktu_selesai_reschedule = :waktu_selesai_reschedule,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
                  AND id_mentor = :id_mentor
                  AND status = 1
                RETURNING id_jadwal
            """), {
                **payload,
                "now": get_wib()
            }).scalar()

            if not result:
                return None

            return get_jadwal_by_id_mentor(
                result,
                payload["id_mentor"]
            )

    except SQLAlchemyError as e:
        print(f"[reschedule_jadwal_by_mentor] Error: {e}")
        return None


# =================================== GROUP ================================== #
_GROUP_EFEKTIF_TANGGAL = "COALESCE(j.tanggal_reschedule, j.tanggal)"
_GROUP_EFEKTIF_MULAI = "COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai)"
_GROUP_EFEKTIF_SELESAI = "COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai)"

_GROUP_SELECT_COLUMNS = f"""
    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
    j.id_mentorship, ms.nama_mentorship,
    CASE
        WHEN j.id_mentorship IS NOT NULL THEN 'PRIVATE'
        WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK'
        ELSE 'KELAS'
    END AS target_type,
    j.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
    j.topik, j.catatan,
    j.tanggal, j.waktu_mulai, j.waktu_selesai,
    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
    {_GROUP_EFEKTIF_TANGGAL} AS tanggal_efektif,
    {_GROUP_EFEKTIF_MULAI} AS waktu_mulai_efektif,
    {_GROUP_EFEKTIF_SELESAI} AS waktu_selesai_efektif,
    j.type_pertemuan, j.status
"""

_GROUP_JOINS = """
    LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
    LEFT JOIN kelompok_belajar kb ON kb.id_kelompok = j.id_kelompok
    LEFT JOIN mentorship ms ON ms.id_mentorship = j.id_mentorship
    LEFT JOIN users u ON u.id_user = j.id_mentor
"""


def _build_jadwal_groups(rows):
    """Kelompokkan baris jadwal per (mentor, type_pertemuan, tanggal, jam mulai, jam selesai) efektif.
    Data jadwal (topik, catatan, waktu, reschedule, dll) ada di level group;
    `classes` hanya berisi pembeda tiap jadwal: id_jadwal, kelas, kelompok, kelas private.
    Urutan baris input dipertahankan."""
    grouped = {}

    for row in rows:
        item = serialize_value(row)
        key = (
            item["id_mentor"],
            item["type_pertemuan"],
            item["tanggal_efektif"],
            item["waktu_mulai_efektif"],
            item["waktu_selesai_efektif"],
        )

        if key not in grouped:
            grouped[key] = {
                "id_jadwal": item["id_jadwal"],
                "id_mentor": item["id_mentor"],
                "nama_mentor": item["nama_mentor"],
                "nickname_mentor": item["nickname_mentor"],
                "type_pertemuan": item["type_pertemuan"],
                "target_type": item["target_type"],
                "topik": item["topik"],
                "catatan": item["catatan"],
                "tanggal": item["tanggal"],
                "waktu_mulai": item["waktu_mulai"],
                "waktu_selesai": item["waktu_selesai"],
                "tanggal_reschedule": item["tanggal_reschedule"],
                "waktu_mulai_reschedule": item["waktu_mulai_reschedule"],
                "waktu_selesai_reschedule": item["waktu_selesai_reschedule"],
                "tanggal_efektif": item["tanggal_efektif"],
                "waktu_mulai_efektif": item["waktu_mulai_efektif"],
                "waktu_selesai_efektif": item["waktu_selesai_efektif"],
                "status": item["status"],
                "is_selesai": item.get("is_selesai"),
                "count": 0,
                "classes": [],
            }

        group = grouped[key]

        # ID jadwal terkecil dipakai sebagai ID representatif group
        if item["id_jadwal"] < group["id_jadwal"]:
            group["id_jadwal"] = item["id_jadwal"]

        group["classes"].append({
            "id_jadwal": item["id_jadwal"],
            "id_paketkelas": item["id_paketkelas"],
            "nama_kelas": item["nama_kelas"],
            "id_kelompok": item["id_kelompok"],
            "nama_kelompok": item["nama_kelompok"],
            "id_mentorship": item["id_mentorship"],
            "nama_mentorship": item["nama_mentorship"],
        })
        group["count"] += 1

    return list(grouped.values())


def get_group_all_jadwal_v2(
    id_mentor=None,
    id_paketkelas=None,
    id_kelompok=None,
    search=None,
    start_date=None,
    end_date=None,
    type_pertemuan=None,
    page=None,
    per_page=None,
    upcoming_first=False,
):
    """Daftar jadwal yang sudah di-group per mentor + type_pertemuan + tanggal + jam efektif.

    upcoming_first=True: group yang jam selesainya belum lewat tampil lebih dulu
    (terdekat -> terjauh), lalu group yang sudah selesai (terbaru -> terlama).
    Tidak ada data yang disembunyikan, hanya urutannya. False: kronologis naik.

    Filter (search, id_paketkelas, id_kelompok, tanggal) menentukan group mana yang
    tampil; isi `classes` tiap group tetap memuat SEMUA kelas/kelompok di slot tersebut.
    Pagination (jika page & per_page diisi) dihitung per group, bukan per baris jadwal.
    """
    engine = get_connection()

    try:
        with engine.connect() as conn:
            where_clause = "WHERE j.status = 1"
            params = {}

            if start_date is not None:
                where_clause += f" AND {_GROUP_EFEKTIF_TANGGAL} >= :start_date"
                params["start_date"] = start_date

            if end_date is not None:
                where_clause += f" AND {_GROUP_EFEKTIF_TANGGAL} <= :end_date"
                params["end_date"] = end_date

            if id_mentor is not None:
                where_clause += " AND j.id_mentor = :id_mentor"
                params["id_mentor"] = id_mentor

            if id_paketkelas is not None:
                where_clause += " AND j.id_paketkelas = :id_paketkelas"
                params["id_paketkelas"] = id_paketkelas

            if id_kelompok is not None:
                where_clause += " AND j.id_kelompok = :id_kelompok"
                params["id_kelompok"] = id_kelompok

            if type_pertemuan:
                where_clause += " AND j.type_pertemuan = :type_pertemuan"
                params["type_pertemuan"] = type_pertemuan

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
                        OR kb.nama_kelompok ILIKE :search
                        OR ms.nama_mentorship ILIKE :search
                        OR j.topik ILIKE :search
                        OR j.catatan ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            groups_cte = f"""
                groups AS (
                    SELECT
                        j.id_mentor,
                        j.type_pertemuan AS tipe,
                        {_GROUP_EFEKTIF_TANGGAL} AS tgl,
                        {_GROUP_EFEKTIF_MULAI} AS mulai,
                        {_GROUP_EFEKTIF_SELESAI} AS selesai
                    FROM jadwal_kelas j
                    {_GROUP_JOINS}
                    {where_clause}
                    GROUP BY 1, 2, 3, 4, 5
                )
            """

            params["now"] = get_wib()

            chrono = "tgl ASC, mulai ASC, selesai ASC, id_mentor ASC, tipe ASC"
            if upcoming_first:
                order_clause = f"""
                    is_selesai ASC,
                    CASE WHEN NOT is_selesai THEN tgl + mulai END ASC,
                    CASE WHEN is_selesai THEN tgl + mulai END DESC,
                    {chrono}
                """
            else:
                order_clause = chrono

            paginate = page is not None and per_page is not None
            total = None
            limit_clause = ""

            if paginate:
                total = conn.execute(
                    text(f"WITH {groups_cte} SELECT COUNT(*) FROM groups"),
                    params
                ).scalar() or 0
                limit_clause = "LIMIT :limit OFFSET :offset"
                params["limit"] = per_page
                params["offset"] = (page - 1) * per_page

            result = conn.execute(
                text(f"""
                    WITH {groups_cte},
                    flagged AS (
                        SELECT *, (tgl + selesai) < :now AS is_selesai
                        FROM groups
                    ),
                    paged AS (
                        SELECT
                            *,
                            ROW_NUMBER() OVER (ORDER BY {order_clause}) AS urut
                        FROM flagged
                        ORDER BY urut
                        {limit_clause}
                    )
                    SELECT {_GROUP_SELECT_COLUMNS}, g.is_selesai
                    FROM paged g
                    JOIN jadwal_kelas j
                        ON j.id_mentor = g.id_mentor
                       AND {_GROUP_EFEKTIF_TANGGAL} = g.tgl
                       AND {_GROUP_EFEKTIF_MULAI} = g.mulai
                       AND {_GROUP_EFEKTIF_SELESAI} = g.selesai
                       AND j.type_pertemuan = g.tipe
                       AND j.status = 1
                    {_GROUP_JOINS}
                    ORDER BY
                        g.urut ASC,
                        COALESCE(pk.nama_kelas, kb.nama_kelompok, ms.nama_mentorship) ASC,
                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            data = _build_jadwal_groups(result)

            if not paginate:
                return data

            return {
                "data": data,
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
            }

    except SQLAlchemyError as e:
        print(f"[get_group_all_jadwal_v2] Error: {e}")
        raise


def get_group_jadwal_by_id_v2(id_jadwal, id_mentor=None):
    """Detail 1 group jadwal: semua kelas/kelompok milik mentor yang sama
    pada tanggal + jam efektif yang sama dengan `id_jadwal`.
    Jika id_mentor diisi, jadwal referensi harus milik mentor tersebut."""
    engine = get_connection()

    try:
        with engine.connect() as conn:
            mentor_clause = " AND j.id_mentor = :id_mentor" if id_mentor is not None else ""
            params = {"id_jadwal": id_jadwal}
            if id_mentor is not None:
                params["id_mentor"] = id_mentor

            result = conn.execute(
                text(f"""
                    WITH ref AS (
                        SELECT
                            j.id_mentor,
                            j.type_pertemuan AS tipe,
                            {_GROUP_EFEKTIF_TANGGAL} AS tgl,
                            {_GROUP_EFEKTIF_MULAI} AS mulai,
                            {_GROUP_EFEKTIF_SELESAI} AS selesai
                        FROM jadwal_kelas j
                        WHERE j.id_jadwal = :id_jadwal
                          AND j.status = 1
                          {mentor_clause}
                    )
                    SELECT {_GROUP_SELECT_COLUMNS}
                    FROM ref g
                    JOIN jadwal_kelas j
                        ON j.id_mentor = g.id_mentor
                       AND {_GROUP_EFEKTIF_TANGGAL} = g.tgl
                       AND {_GROUP_EFEKTIF_MULAI} = g.mulai
                       AND {_GROUP_EFEKTIF_SELESAI} = g.selesai
                       AND j.type_pertemuan = g.tipe
                       AND j.status = 1
                    {_GROUP_JOINS}
                    ORDER BY
                        COALESCE(pk.nama_kelas, kb.nama_kelompok, ms.nama_mentorship) ASC,
                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            groups = _build_jadwal_groups(result)
            return groups[0] if groups else None

    except SQLAlchemyError as e:
        print(f"[get_group_jadwal_by_id_v2] Error: {e}")
        raise


# ============================================================================ #
#                  AKSI GROUP V2 (berlaku untuk semua jadwal 1 group)          #
# ============================================================================ #

def _get_group_members_v2(conn, id_jadwal, for_update=False):
    """Ambil semua jadwal aktif dalam group yang sama dengan `id_jadwal`
    (mentor + type_pertemuan + tanggal + jam mulai + jam selesai efektif)."""
    lock = "FOR UPDATE OF j" if for_update else ""

    return conn.execute(
        text(f"""
            WITH ref AS (
                SELECT
                    j.id_mentor,
                    j.type_pertemuan AS tipe,
                    {_GROUP_EFEKTIF_TANGGAL} AS tgl,
                    {_GROUP_EFEKTIF_MULAI} AS mulai,
                    {_GROUP_EFEKTIF_SELESAI} AS selesai
                FROM jadwal_kelas j
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
            )
            SELECT j.id_jadwal, j.id_paketkelas, j.id_kelompok, j.id_mentorship, j.id_mentor, j.type_pertemuan
            FROM jadwal_kelas j
            JOIN ref g
                ON j.id_mentor = g.id_mentor
               AND j.type_pertemuan = g.tipe
               AND {_GROUP_EFEKTIF_TANGGAL} = g.tgl
               AND {_GROUP_EFEKTIF_MULAI} = g.mulai
               AND {_GROUP_EFEKTIF_SELESAI} = g.selesai
            WHERE j.status = 1
            ORDER BY j.id_jadwal ASC
            {lock}
        """),
        {"id_jadwal": id_jadwal}
    ).mappings().fetchall()


def get_group_members_v2(id_jadwal):
    """Daftar jadwal (id_jadwal, id_paketkelas, id_kelompok, id_mentor, type_pertemuan)
    dalam group `id_jadwal`. List kosong jika jadwal tidak ditemukan."""
    engine = get_connection()

    try:
        with engine.connect() as conn:
            return [dict(row) for row in _get_group_members_v2(conn, id_jadwal)]

    except SQLAlchemyError as e:
        print(f"[get_group_members_v2] Error: {e}")
        raise


def update_group_jadwal_v2(id_jadwal, payload):
    """Ubah mentor, topik, catatan, tanggal & jam untuk SEMUA jadwal dalam group.
    Kelas/kelompok dan type_pertemuan tiap jadwal tidak diubah.
    Return list id_jadwal yang diubah, atau None jika group tidak ditemukan."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            members = _get_group_members_v2(conn, id_jadwal, for_update=True)
            if not members:
                return None

            ids = [row["id_jadwal"] for row in members]

            conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    id_mentor = :id_mentor,
                    topik = :topik,
                    catatan = :catatan,
                    tanggal = :tanggal,
                    waktu_mulai = :waktu_mulai,
                    waktu_selesai = :waktu_selesai,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = ANY(:ids)
                  AND status = 1
            """), {**payload, "ids": ids, "now": get_wib()})

            return ids

    except SQLAlchemyError as e:
        print(f"[update_group_jadwal_v2] Error: {e}")
        raise


def reschedule_group_jadwal_v2(id_jadwal, payload):
    """Reschedule SEMUA jadwal dalam group. Return list id_jadwal atau None."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            members = _get_group_members_v2(conn, id_jadwal, for_update=True)
            if not members:
                return None

            ids = [row["id_jadwal"] for row in members]

            conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    tanggal_reschedule = :tanggal_reschedule,
                    waktu_mulai_reschedule = :waktu_mulai_reschedule,
                    waktu_selesai_reschedule = :waktu_selesai_reschedule,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = ANY(:ids)
                  AND status = 1
            """), {**payload, "ids": ids, "now": get_wib()})

            return ids

    except SQLAlchemyError as e:
        print(f"[reschedule_group_jadwal_v2] Error: {e}")
        raise


def delete_group_jadwal_v2(id_jadwal, id_user):
    """Soft delete SEMUA jadwal dalam group. Return list id_jadwal atau None."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            members = _get_group_members_v2(conn, id_jadwal, for_update=True)
            if not members:
                return None

            ids = [row["id_jadwal"] for row in members]

            conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    status = 0,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = ANY(:ids)
                  AND status = 1
            """), {"ids": ids, "updated_by": id_user, "now": get_wib()})

            return ids

    except SQLAlchemyError as e:
        print(f"[delete_group_jadwal_v2] Error: {e}")
        raise


def switch_mentor_group_jadwal_v2(id_jadwal_1, id_jadwal_2, id_user):
    """Tukar mentor antar 2 group: semua jadwal group 1 diberi mentor group 2
    dan sebaliknya. Return dict ringkasan, None jika salah satu group tidak
    ditemukan, atau "SAME_GROUP" jika kedua ID berada di group yang sama."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            group_1 = _get_group_members_v2(conn, id_jadwal_1, for_update=True)
            group_2 = _get_group_members_v2(conn, id_jadwal_2, for_update=True)

            if not group_1 or not group_2:
                return None

            ids_1 = [row["id_jadwal"] for row in group_1]
            ids_2 = [row["id_jadwal"] for row in group_2]

            if set(ids_1) & set(ids_2):
                return "SAME_GROUP"

            mentor_1 = group_1[0]["id_mentor"]
            mentor_2 = group_2[0]["id_mentor"]
            now = get_wib()

            update_sql = text("""
                UPDATE jadwal_kelas
                SET
                    id_mentor = :id_mentor,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = ANY(:ids)
                  AND status = 1
            """)

            conn.execute(update_sql, {"ids": ids_1, "id_mentor": mentor_2, "updated_by": id_user, "now": now})
            conn.execute(update_sql, {"ids": ids_2, "id_mentor": mentor_1, "updated_by": id_user, "now": now})

            return {
                "id_jadwal_1": ids_1,
                "id_mentor_1": mentor_2,
                "id_jadwal_2": ids_2,
                "id_mentor_2": mentor_1,
            }

    except SQLAlchemyError as e:
        print(f"[switch_mentor_group_jadwal_v2] Error: {e}")
        raise


# ============================================================================ #
#              JADWAL SATUAN V2 (mendukung kelas private / mentorship)         #
# ============================================================================ #

def get_mentorship_v2(id_mentorship):
    """Data kelas private aktif, atau None."""
    engine = get_connection()

    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id_mentorship, id_mentor, id_peserta, nama_mentorship
                FROM mentorship
                WHERE id_mentorship = :id_mentorship
                  AND status = 1
            """), {"id_mentorship": id_mentorship}).mappings().fetchone()

            return dict(row) if row else None

    except SQLAlchemyError as e:
        print(f"[get_mentorship_v2] Error: {e}")
        raise


def get_jadwal_by_id_v2(id_jadwal):
    """Detail 1 jadwal aktif termasuk kelas private (id_mentorship, nama_mentorship)."""
    engine = get_connection()

    try:
        with engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT
                    {_GROUP_SELECT_COLUMNS},
                    j.created_by, j.created_at, j.updated_by, j.updated_at
                FROM jadwal_kelas j
                {_GROUP_JOINS}
                WHERE j.id_jadwal = :id_jadwal
                  AND j.status = 1
            """), {"id_jadwal": id_jadwal}).mappings().fetchone()

            return serialize_value(row) if row else None

    except SQLAlchemyError as e:
        print(f"[get_jadwal_by_id_v2] Error: {e}")
        raise


def update_jadwal_v2(payload):
    """Ubah 1 jadwal termasuk target kelas private. Return detail jadwal atau None."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                UPDATE jadwal_kelas
                SET
                    id_paketkelas = :id_paketkelas,
                    id_kelompok = :id_kelompok,
                    id_mentorship = :id_mentorship,
                    id_mentor = :id_mentor,
                    topik = :topik,
                    catatan = :catatan,
                    tanggal = :tanggal,
                    waktu_mulai = :waktu_mulai,
                    waktu_selesai = :waktu_selesai,
                    type_pertemuan = :type_pertemuan,
                    updated_by = :updated_by,
                    updated_at = :now
                WHERE id_jadwal = :id_jadwal
                  AND status = 1
                RETURNING id_jadwal
            """), {**payload, "now": get_wib()}).scalar()

        return get_jadwal_by_id_v2(result) if result else None

    except SQLAlchemyError as e:
        print(f"[update_jadwal_v2] Error: {e}")
        raise


def get_mentorship_dropdown_v2(search=None, id_mentor=None):
    """Dropdown kelas private (mentorship) aktif beserta mentor & peserta."""
    engine = get_connection()

    try:
        with engine.connect() as conn:
            where_clause = "WHERE m.status = 1"
            params = {}

            if id_mentor is not None:
                where_clause += " AND m.id_mentor = :id_mentor"
                params["id_mentor"] = id_mentor

            if search and search.strip():
                where_clause += """
                    AND (
                        m.nama_mentorship ILIKE :search
                        OR mentor.nama ILIKE :search
                        OR peserta.nama ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            rows = conn.execute(text(f"""
                SELECT
                    m.id_mentorship,
                    m.nama_mentorship,
                    m.id_mentor,
                    mentor.nama AS nama_mentor,
                    mentor.nickname AS nickname_mentor,
                    m.id_peserta,
                    peserta.nama AS nama_peserta
                FROM mentorship m
                INNER JOIN users mentor
                    ON mentor.id_user = m.id_mentor
                   AND mentor.status = 1
                INNER JOIN users peserta
                    ON peserta.id_user = m.id_peserta
                   AND peserta.status = 1
                {where_clause}
                ORDER BY m.nama_mentorship ASC NULLS LAST, peserta.nama ASC
            """), params).mappings().fetchall()

            return [serialize_value(row) for row in rows]

    except SQLAlchemyError as e:
        print(f"[get_mentorship_dropdown_v2] Error: {e}")
        raise


def insert_jadwal_v2(payload):
    """Buat 1 jadwal (kelas / kelompok / kelas private). Return detail jadwal atau None."""
    engine = get_connection()

    try:
        with engine.begin() as conn:
            id_jadwal = conn.execute(text("""
                INSERT INTO jadwal_kelas (
                    id_paketkelas, id_kelompok, id_mentorship, id_mentor,
                    topik, catatan, tanggal, waktu_mulai, waktu_selesai, type_pertemuan,
                    status, created_by, created_at, updated_by, updated_at
                )
                VALUES (
                    :id_paketkelas, :id_kelompok, :id_mentorship, :id_mentor,
                    :topik, :catatan, :tanggal, :waktu_mulai, :waktu_selesai, :type_pertemuan,
                    1, :created_by, :now, :updated_by, :now
                )
                RETURNING id_jadwal
            """), {**payload, "now": get_wib()}).scalar()

        return get_jadwal_by_id_v2(id_jadwal) if id_jadwal else None

    except SQLAlchemyError as e:
        print(f"[insert_jadwal_v2] Error: {e}")
        raise


def get_group_all_jadwal_by_mentor(
    id_mentor,
    search=None,
    start_date=None,
    end_date=None,
    type_pertemuan=None
):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            where_clause = """
                WHERE j.id_mentor = :id_mentor
                  AND j.status = 1
            """

            params = {
                "id_mentor": id_mentor
            }

            if start_date is not None:
                where_clause += """
                    AND COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) >= :start_date
                """
                params["start_date"] = start_date

            if end_date is not None:
                where_clause += """
                    AND COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) <= :end_date
                """
                params["end_date"] = end_date

            if type_pertemuan:
                where_clause += " AND j.type_pertemuan = :type_pertemuan"
                params["type_pertemuan"] = type_pertemuan

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
                        OR kb.nama_kelompok ILIKE :search
                        OR j.topik ILIKE :search
                        OR j.catatan ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            result = conn.execute(
                text(f"""
                    SELECT
                        j.id_jadwal,
                        j.id_paketkelas,
                        pk.nama_kelas,
                        j.id_kelompok,
                        kb.nama_kelompok,
                        CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,

                        j.id_mentor,
                        u.nama AS nama_mentor,
                        u.nickname AS nickname_mentor,

                        j.topik,
                        j.catatan,

                        j.tanggal,
                        j.waktu_mulai,
                        j.waktu_selesai,

                        j.tanggal_reschedule,
                        j.waktu_mulai_reschedule,
                        j.waktu_selesai_reschedule,

                        COALESCE(
                            j.tanggal_reschedule,
                            j.tanggal
                        ) AS tanggal_efektif,

                        COALESCE(
                            j.waktu_mulai_reschedule,
                            j.waktu_mulai
                        ) AS waktu_mulai_efektif,

                        COALESCE(
                            j.waktu_selesai_reschedule,
                            j.waktu_selesai
                        ) AS waktu_selesai_efektif,

                        j.type_pertemuan,
                        j.status,
                        j.created_by,
                        j.created_at,
                        j.updated_by,
                        j.updated_at

                    FROM jadwal_kelas j

                    LEFT JOIN paketkelas pk
                        ON pk.id_paketkelas = j.id_paketkelas
                       AND pk.status = 1

                    LEFT JOIN kelompok_belajar kb
                        ON kb.id_kelompok = j.id_kelompok
                       AND kb.status = 1

                    LEFT JOIN users u
                        ON u.id_user = j.id_mentor
                       AND u.status = 1

                    {where_clause}

                    ORDER BY
                        COALESCE(
                            j.tanggal_reschedule,
                            j.tanggal
                        ) ASC,

                        COALESCE(
                            j.waktu_mulai_reschedule,
                            j.waktu_mulai
                        ) ASC,

                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            # ==========================================
            # GROUP BY TANGGAL + JAM
            # ==========================================

            grouped = {}

            for row in result:
                item = serialize_value(row)

                group_key = (
                    item["tanggal_efektif"],
                    item["waktu_mulai_efektif"],
                    item["waktu_selesai_efektif"]
                )

                if group_key not in grouped:
                    grouped[group_key] = {
                        "tanggal": item["tanggal_efektif"],
                        "waktu_mulai": item["waktu_mulai_efektif"],
                        "waktu_selesai": item["waktu_selesai_efektif"],
                        "id_jadwal": item["id_jadwal"],
                        "count": 0,
                        "classes": []
                    }

                group = grouped[group_key]

                # ==========================================
                # Gunakan ID jadwal terkecil sebagai
                # representative ID group
                # ==========================================

                if item["id_jadwal"] < group["id_jadwal"]:
                    group["id_jadwal"] = item["id_jadwal"]

                # ==========================================
                # Tambahkan kelas
                # ==========================================

                group["classes"].append({
                    "id_jadwal": item["id_jadwal"],
                    "id_paketkelas": item["id_paketkelas"],
                    "nama_kelas": item["nama_kelas"],
                    "id_kelompok": item["id_kelompok"],
                    "nama_kelompok": item["nama_kelompok"],
                    "target_type": item["target_type"],
                    "topik": item["topik"],
                    "catatan": item["catatan"],
                    "type_pertemuan": item["type_pertemuan"],
                    "tanggal": item["tanggal"],
                    "waktu_mulai": item["waktu_mulai"],
                    "waktu_selesai": item["waktu_selesai"],
                    "tanggal_reschedule": item["tanggal_reschedule"],
                    "waktu_mulai_reschedule": item["waktu_mulai_reschedule"],
                    "waktu_selesai_reschedule": item["waktu_selesai_reschedule"],
                    "status": item["status"]
                })

                group["count"] += 1

            return list(grouped.values())

    except SQLAlchemyError as e:
        print(f"[get_all_jadwal_by_mentor] Error: {e}")
        raise


def get_group_jadwal_by_id_mentor(id_jadwal, id_mentor):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            # ==========================================
            # 1. Ambil jadwal referensi berdasarkan ID
            # ==========================================

            reference = conn.execute(text("""
                SELECT
                    COALESCE(
                        tanggal_reschedule,
                        tanggal
                    ) AS tanggal_efektif,

                    COALESCE(
                        waktu_mulai_reschedule,
                        waktu_mulai
                    ) AS waktu_mulai_efektif,

                    COALESCE(
                        waktu_selesai_reschedule,
                        waktu_selesai
                    ) AS waktu_selesai_efektif

                FROM jadwal_kelas

                WHERE id_jadwal = :id_jadwal
                  AND id_mentor = :id_mentor
                  AND status = 1
            """), {
                "id_jadwal": id_jadwal,
                "id_mentor": id_mentor
            }).mappings().fetchone()

            if not reference:
                return None

            # ==========================================
            # 2. Ambil semua jadwal yang identik
            #    tanggal + jam mulai + jam selesai
            # ==========================================

            result = conn.execute(text("""
                SELECT
                    j.id_jadwal,
                    j.id_paketkelas,
                    pk.nama_kelas,
                    j.id_kelompok,
                    kb.nama_kelompok,
                    CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,

                    j.id_mentor,
                    u.nama AS nama_mentor,
                    u.nickname AS nickname_mentor,

                    j.topik,
                    j.catatan,

                    j.tanggal,
                    j.waktu_mulai,
                    j.waktu_selesai,

                    j.tanggal_reschedule,
                    j.waktu_mulai_reschedule,
                    j.waktu_selesai_reschedule,

                    COALESCE(
                        j.tanggal_reschedule,
                        j.tanggal
                    ) AS tanggal_efektif,

                    COALESCE(
                        j.waktu_mulai_reschedule,
                        j.waktu_mulai
                    ) AS waktu_mulai_efektif,

                    COALESCE(
                        j.waktu_selesai_reschedule,
                        j.waktu_selesai
                    ) AS waktu_selesai_efektif,

                    j.type_pertemuan,
                    j.status,
                    j.created_by,
                    j.created_at,
                    j.updated_by,
                    j.updated_at

                FROM jadwal_kelas j

                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
                   AND pk.status = 1
                LEFT JOIN kelompok_belajar kb
                    ON kb.id_kelompok = j.id_kelompok
                   AND kb.status = 1

                LEFT JOIN users u
                    ON u.id_user = j.id_mentor
                   AND u.status = 1

                WHERE j.id_mentor = :id_mentor
                  AND j.status = 1

                  AND COALESCE(
                      j.tanggal_reschedule,
                      j.tanggal
                  ) = :tanggal_efektif

                  AND COALESCE(
                      j.waktu_mulai_reschedule,
                      j.waktu_mulai
                  ) = :waktu_mulai_efektif

                  AND COALESCE(
                      j.waktu_selesai_reschedule,
                      j.waktu_selesai
                  ) = :waktu_selesai_efektif

                ORDER BY
                    COALESCE(pk.nama_kelas, kb.nama_kelompok) ASC,
                    j.id_jadwal ASC
            """), {
                "id_mentor": id_mentor,
                "tanggal_efektif": reference["tanggal_efektif"],
                "waktu_mulai_efektif": reference["waktu_mulai_efektif"],
                "waktu_selesai_efektif": reference["waktu_selesai_efektif"]
            }).mappings().fetchall()

            if not result:
                return None

            rows = [
                serialize_value(row)
                for row in result
            ]

            # ==========================================
            # 3. Return grouped data
            # ==========================================

            return {
                "tanggal": rows[0]["tanggal_efektif"],
                "waktu_mulai": rows[0]["waktu_mulai_efektif"],
                "waktu_selesai": rows[0]["waktu_selesai_efektif"],
                "count": len(rows),

                "classes": [
                    {
                        "id_jadwal": row["id_jadwal"],
                        "id_paketkelas": row["id_paketkelas"],
                        "nama_kelas": row["nama_kelas"],
                        "id_kelompok": row["id_kelompok"],
                        "nama_kelompok": row["nama_kelompok"],
                        "target_type": row["target_type"],

                        "topik": row["topik"],
                        "catatan": row["catatan"],

                        "tanggal": row["tanggal"],
                        "waktu_mulai": row["waktu_mulai"],
                        "waktu_selesai": row["waktu_selesai"],

                        "tanggal_reschedule": (
                            row["tanggal_reschedule"]
                        ),
                        "waktu_mulai_reschedule": (
                            row["waktu_mulai_reschedule"]
                        ),
                        "waktu_selesai_reschedule": (
                            row["waktu_selesai_reschedule"]
                        ),

                        "tanggal_efektif": (
                            row["tanggal_efektif"]
                        ),
                        "waktu_mulai_efektif": (
                            row["waktu_mulai_efektif"]
                        ),
                        "waktu_selesai_efektif": (
                            row["waktu_selesai_efektif"]
                        ),

                        "type_pertemuan": row["type_pertemuan"],
                        "status": row["status"]
                    }
                    for row in rows
                ]
            }

    except SQLAlchemyError as e:
        print(f"[get_jadwal_by_id_mentor] Error: {e}")
        raise



# ============================================================================ #
#                         MANAJEMEN JADWAL BY - PESERTA                        #
# ============================================================================ #

def get_all_jadwal_by_peserta(id_peserta, start_date=None, end_date=None):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            where_clause = ""
            params = {
                "id_peserta": id_peserta
            }

            if start_date is not None:
                where_clause += """
                    AND COALESCE(j.tanggal_reschedule, j.tanggal) >= :start_date
                """
                params["start_date"] = start_date

            if end_date is not None:
                where_clause += """
                    AND COALESCE(j.tanggal_reschedule, j.tanggal) <= :end_date
                """
                params["end_date"] = end_date

            # ==========================================
            # Jadwal milik peserta:
            # - target kelas    -> peserta aktif di kelas tsb
            # - target kelompok -> peserta aktif di kelompok tsb
            # ==========================================

            result = conn.execute(
                text(f"""
                    SELECT
                        j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_kelompok, kb.nama_kelompok,
                        CASE WHEN j.id_kelompok IS NOT NULL THEN 'KELOMPOK' ELSE 'KELAS' END AS target_type,
                        j.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
                        j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                        j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,

                        COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                        COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                        j.type_pertemuan,

                        CASE
                            WHEN am.id_absensi_mentor IS NULL THEN 'BELUM_CHECK_IN'
                            WHEN am.check_out_at IS NULL THEN 'CHECK_IN'
                            ELSE 'SELESAI'
                        END AS status_absensi_mentor,

                        ap.id_absensi_peserta,
                        ap.status_kehadiran AS status_absensi_saya,
                        ap.check_in_at AS check_in_saya

                    FROM jadwal_kelas j
                    LEFT JOIN paketkelas pk
                        ON pk.id_paketkelas = j.id_paketkelas
                       AND pk.status = 1
                    LEFT JOIN kelompok_belajar kb
                        ON kb.id_kelompok = j.id_kelompok
                       AND kb.status = 1
                    LEFT JOIN users u
                        ON u.id_user = j.id_mentor
                       AND u.status = 1
                    LEFT JOIN absensi_mentor am
                        ON am.id_jadwal = j.id_jadwal
                       AND am.status = 1
                    LEFT JOIN absensi_peserta ap
                        ON ap.id_jadwal = j.id_jadwal
                       AND ap.id_peserta = :id_peserta
                       AND ap.status = 1
                    WHERE j.status = 1
                      AND (
                          (
                              pk.id_paketkelas IS NOT NULL
                              AND EXISTS (
                                  SELECT 1
                                  FROM pesertakelas pks
                                  WHERE pks.id_paketkelas = j.id_paketkelas
                                    AND pks.id_user = :id_peserta
                                    AND pks.status = 1
                              )
                          )
                          OR (
                              kb.id_kelompok IS NOT NULL
                              AND EXISTS (
                                  SELECT 1
                                  FROM kelompok_belajar_peserta kbp
                                  WHERE kbp.id_kelompok = j.id_kelompok
                                    AND kbp.id_peserta = :id_peserta
                                    AND kbp.status = 1
                              )
                          )
                      )
                      {where_clause}
                    ORDER BY
                        COALESCE(j.tanggal_reschedule, j.tanggal) ASC,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) ASC,
                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            return [serialize_value(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_all_jadwal_by_peserta] Error: {e}")
        raise


# ============================================================================ #
#                        MANAJEMEN JADWAL BY - WALI KELAS                      #
# ============================================================================ #

def get_all_jadwal_by_wali_kelas(
    id_wali_kelas,
    start_date,
    end_date,
    id_paketkelas=None,
    search=None
):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            # ==========================================
            # Hanya jadwal dari kelas yang wali kelasnya
            # adalah mentor yang sedang login
            # ==========================================

            where_clause = """
                WHERE pk.id_user = :id_wali_kelas
                  AND j.status = 1
                  AND COALESCE(j.tanggal_reschedule, j.tanggal) BETWEEN :start_date AND :end_date
            """

            params = {
                "id_wali_kelas": id_wali_kelas,
                "start_date": start_date,
                "end_date": end_date
            }

            if id_paketkelas is not None:
                where_clause += " AND j.id_paketkelas = :id_paketkelas"
                params["id_paketkelas"] = id_paketkelas

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR u.nickname ILIKE :search
                        OR pk.nama_kelas ILIKE :search
                        OR j.topik ILIKE :search
                        OR j.catatan ILIKE :search
                    )
                """
                params["search"] = f"%{search.strip()}%"

            result = conn.execute(
                text(f"""
                    SELECT
                        j.id_jadwal, j.id_paketkelas, pk.nama_kelas,
                        j.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
                        j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                        j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,

                        COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                        COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                        j.type_pertemuan,

                        CASE
                            WHEN am.id_absensi_mentor IS NULL THEN 'BELUM_CHECK_IN'
                            WHEN am.check_out_at IS NULL THEN 'CHECK_IN'
                            ELSE 'SELESAI'
                        END AS status_absensi_mentor,

                        j.status, j.created_by, j.created_at, j.updated_by, j.updated_at

                    FROM jadwal_kelas j
                    INNER JOIN paketkelas pk
                        ON pk.id_paketkelas = j.id_paketkelas
                       AND pk.status = 1
                    LEFT JOIN users u
                        ON u.id_user = j.id_mentor
                    LEFT JOIN absensi_mentor am
                        ON am.id_jadwal = j.id_jadwal
                       AND am.status = 1
                    {where_clause}
                    ORDER BY
                        COALESCE(j.tanggal_reschedule, j.tanggal) ASC,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) ASC,
                        pk.nama_kelas ASC,
                        j.id_jadwal ASC
                """),
                params
            ).mappings().fetchall()

            data = [serialize_value(row) for row in result]

            # ==========================================
            # META: jumlah jadwal & kelas per tanggal
            # ==========================================

            per_tanggal = {}

            for item in data:
                tanggal = item["tanggal_efektif"]

                if tanggal not in per_tanggal:
                    per_tanggal[tanggal] = {
                        "tanggal": tanggal,
                        "total_jadwal": 0,
                        "kelas": set()
                    }

                per_tanggal[tanggal]["total_jadwal"] += 1
                per_tanggal[tanggal]["kelas"].add(item["id_paketkelas"])

            meta_per_tanggal = [
                {
                    "tanggal": value["tanggal"],
                    "total_jadwal": value["total_jadwal"],
                    "total_kelas": len(value["kelas"])
                }
                for value in per_tanggal.values()
            ]

            return {
                "data": data,
                "per_tanggal": meta_per_tanggal,
                "total_kelas": len({item["id_paketkelas"] for item in data})
            }

    except SQLAlchemyError as e:
        print(f"[get_all_jadwal_by_wali_kelas] Error: {e}")
        raise