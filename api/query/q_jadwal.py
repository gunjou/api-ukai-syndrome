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
                    id_paketkelas, id_mentor, topik, catatan, tanggal, waktu_mulai, waktu_selesai, type_pertemuan, 
                    status, created_by, created_at, updated_by, updated_at
                )
                VALUES (
                    :id_paketkelas, :id_mentor, :topik, :catatan, :tanggal, :waktu_mulai, :waktu_selesai, :type_pertemuan, 
                    1, :created_by, :now, :updated_by, :now
                )
                RETURNING
                    id_jadwal, id_paketkelas, id_mentor, topik, catatan, tanggal, waktu_mulai, waktu_selesai, type_pertemuan,
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
    start_date=None,
    end_date=None,
    page=1,
    per_page=50
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

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
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
                        j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_mentor, u.nama AS nama_mentor, 
                        u.nickname AS nickname_mentor,j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                        j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                        COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                        COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                        COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,
                        j.type_pertemuan, j.status, j.created_by, j.created_at, j.updated_by, j.updated_at
                    FROM jadwal_kelas j
                    LEFT JOIN paketkelas pk ON pk.id_paketkelas = j.id_paketkelas
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
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_mentor, u.nama AS nama_mentor,
                    j.topik, j.catatan, j.tanggal, j.waktu_mulai, j.waktu_selesai,
                    j.tanggal_reschedule, j.waktu_mulai_reschedule, j.waktu_selesai_reschedule,
                
                    COALESCE(j.tanggal_reschedule, j.tanggal) AS tanggal_efektif,
                    COALESCE(j.waktu_mulai_reschedule, j.waktu_mulai) AS waktu_mulai_efektif,
                    COALESCE(j.waktu_selesai_reschedule, j.waktu_selesai) AS waktu_selesai_efektif,

                    j.type_pertemuan, j.status, j.created_by, j.created_at, j.updated_by, j.updated_at

                FROM jadwal_kelas j
                LEFT JOIN paketkelas pk
                    ON pk.id_paketkelas = j.id_paketkelas
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
    end_date=None
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

            if search and search.strip():
                where_clause += """
                    AND (
                        u.nama ILIKE :search
                        OR pk.nama_kelas ILIKE :search
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
                    j.id_jadwal, j.id_paketkelas, pk.nama_kelas, j.id_mentor, u.nama AS nama_mentor, u.nickname AS nickname_mentor,
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