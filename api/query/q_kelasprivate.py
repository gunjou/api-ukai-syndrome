from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita



def get_user_selection(role, search=None):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            base_query = """
                FROM users u
                WHERE u.status = 1
                  AND u.role = :role
            """

            params = {"role": role}

            # 🔍 SEARCH
            if search:
                base_query += " AND u.nama ILIKE :search"
                params["search"] = f"%{search}%"

            query = text(f"""
                SELECT 
                    u.id_user,
                    u.nama
                {base_query}
                ORDER BY u.nama ASC
            """)

            result = conn.execute(query, params).mappings().fetchall()

            return [serialize_row(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_user_selection] Error: {e}")
        return []
    
    

# ======================================================================
# QUERY KELAS PRIVATE (ADMIN)
# ======================================================================
def get_all_mentorship(page=1, limit=20, search=None):
    engine = get_connection()
    offset = (page - 1) * limit

    try:
        with engine.connect() as conn:

            base_query = """
                FROM mentorship m
                JOIN users mentor 
                    ON mentor.id_user = m.id_mentor 
                   AND mentor.status = 1
                JOIN users peserta 
                    ON peserta.id_user = m.id_peserta 
                   AND peserta.status = 1
                WHERE m.status = 1
            """

            params = {}

            # 🔍 SEARCH (opsional)
            if search:
                base_query += """
                AND (
                    mentor.nama ILIKE :search OR
                    peserta.nama ILIKE :search OR
                    m.nama_mentorship ILIKE :search
                )
                """
                params["search"] = f"%{search}%"

            # 🔹 DATA QUERY
            data_query = text(f"""
                SELECT 
                    m.id_mentorship,
                    m.nama_mentorship,
                    m.created_at,

                    mentor.id_user AS id_mentor,
                    mentor.nama AS nama_mentor,

                    peserta.id_user AS id_peserta,
                    peserta.nama AS nama_peserta,
                    peserta.email AS email_peserta,

                    -- 🔥 COUNT MATERI
                    (
                        SELECT COUNT(*)
                        FROM materi_private mp
                        WHERE mp.id_mentorship = m.id_mentorship
                        AND mp.status = 1
                    ) AS total_materi

                {base_query}
                ORDER BY m.created_at DESC
                LIMIT :limit OFFSET :offset
            """)

            params.update({
                "limit": limit,
                "offset": offset
            })

            data = conn.execute(data_query, params).mappings().fetchall()

            # 🔹 COUNT
            count_query = text(f"""
                SELECT COUNT(m.id_mentorship)
                {base_query}
            """)

            total = conn.execute(count_query, params).scalar()

            return {
                "data": [serialize_row(row) for row in data],
                "total": total,
                "page": page,
                "limit": limit
            }

    except SQLAlchemyError as e:
        print(f"[get_all_mentorship] Error: {e}")
        return None


def create_mentorship(id_mentor, id_peserta, nama_mentorship=None):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            # 🔒 VALIDASI: mentor harus role mentor
            mentor = conn.execute(text("""
                SELECT id_user FROM users
                WHERE id_user = :id_mentor 
                  AND role = 'mentor'
                  AND status = 1
            """), {"id_mentor": id_mentor}).fetchone()

            if not mentor:
                return {"error": "Mentor tidak valid"}

            # 🔒 VALIDASI: peserta harus role peserta
            peserta = conn.execute(text("""
                SELECT id_user FROM users
                WHERE id_user = :id_peserta 
                  AND role = 'peserta'
                  AND status = 1
            """), {"id_peserta": id_peserta}).fetchone()

            if not peserta:
                return {"error": "Peserta tidak valid"}

            # 🔒 VALIDASI: tidak boleh duplicate mentorship
            existing = conn.execute(text("""
                SELECT 1 FROM mentorship
                WHERE id_mentor = :id_mentor
                  AND id_peserta = :id_peserta
                  AND status = 1
            """), {
                "id_mentor": id_mentor,
                "id_peserta": id_peserta
            }).fetchone()

            if existing:
                return {"error": "Mentorship sudah ada"}

            # 🚀 INSERT
            result = conn.execute(text("""
                INSERT INTO mentorship (id_mentor, id_peserta, nama_mentorship, created_at, updated_at)
                VALUES (:id_mentor, :id_peserta, :nama_mentorship, :now, :now)
                RETURNING id_mentorship
            """), {
                "id_mentor": id_mentor,
                "id_peserta": id_peserta,
                "nama_mentorship": nama_mentorship,
                "now": get_wita()
            })

            new_id = result.scalar()

            return {
                "id_mentorship": new_id
            }

    except SQLAlchemyError as e:
        print(f"[create_mentorship] Error: {e}")
        return None


def get_mentorship_by_id(id_mentorship):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    m.id_mentorship,
                    m.nama_mentorship,
                    m.created_at,
                    m.updated_at,

                    mentor.id_user AS id_mentor,
                    mentor.nama AS nama_mentor,

                    peserta.id_user AS id_peserta,
                    peserta.nama AS nama_peserta

                FROM mentorship m
                JOIN users mentor 
                    ON mentor.id_user = m.id_mentor 
                   AND mentor.status = 1
                JOIN users peserta 
                    ON peserta.id_user = m.id_peserta 
                   AND peserta.status = 1
                WHERE m.id_mentorship = :id_mentorship
                  AND m.status = 1
            """), {"id_mentorship": id_mentorship}).mappings().fetchone()

            return serialize_row(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_mentorship_by_id] Error: {e}")
        return None


def update_mentorship(id_mentorship, nama_mentorship=None):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            existing = conn.execute(text("""
                SELECT 1 FROM mentorship
                WHERE id_mentorship = :id
                  AND status = 1
            """), {"id": id_mentorship}).fetchone()

            if not existing:
                return {"error": "Mentorship tidak ditemukan"}

            conn.execute(text("""
                UPDATE mentorship
                SET nama_mentorship = COALESCE(:nama_mentorship, nama_mentorship),
                    updated_at = :now
                WHERE id_mentorship = :id
            """), {
                "id": id_mentorship,
                "nama_mentorship": nama_mentorship,
                "now": get_wita()
            })

            return {"id_mentorship": id_mentorship}

    except SQLAlchemyError as e:
        print(f"[update_mentorship] Error: {e}")
        return None


def delete_mentorship(id_mentorship):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            existing = conn.execute(text("""
                SELECT 1 FROM mentorship
                WHERE id_mentorship = :id
                  AND status = 1
            """), {"id": id_mentorship}).fetchone()

            if not existing:
                return {"error": "Mentorship tidak ditemukan"}

            conn.execute(text("""
                UPDATE mentorship
                SET status = 0,
                    updated_at = :now
                WHERE id_mentorship = :id
            """), {
                "id": id_mentorship,
                "now": get_wita()
            })

            return {"id_mentorship": id_mentorship}

    except SQLAlchemyError as e:
        print(f"[delete_mentorship] Error: {e}")
        return None



# ======================================================================
# QUERY MATERI PRIVATE (ADMIN)
# ======================================================================
def create_materi_private(
    id_mentorship,
    tipe_materi,
    judul,
    url_file,
    id_owner,
    visibility="hold",
    is_downloadable=0,
    viewer_only=True
):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            # 🔒 VALIDASI mentorship ada
            mentorship = conn.execute(text("""
                SELECT id_mentorship 
                FROM mentorship
                WHERE id_mentorship = :id
                  AND status = 1
            """), {"id": id_mentorship}).fetchone()

            if not mentorship:
                return {"error": "Mentorship tidak ditemukan"}

            result = conn.execute(text("""
                INSERT INTO materi_private (
                    id_mentorship,
                    tipe_materi,
                    judul,
                    url_file,
                    viewer_only,
                    is_downloadable,
                    id_owner,
                    visibility,
                    created_at,
                    updated_at
                )
                VALUES (
                    :id_mentorship,
                    :tipe_materi,
                    :judul,
                    :url_file,
                    :viewer_only,
                    :is_downloadable,
                    :id_owner,
                    :visibility,
                    :now,
                    :now
                )
                RETURNING id_materi_private
            """), {
                "id_mentorship": id_mentorship,
                "tipe_materi": tipe_materi,
                "judul": judul,
                "url_file": url_file,
                "viewer_only": viewer_only,
                "is_downloadable": is_downloadable,
                "id_owner": id_owner,
                "visibility": visibility,
                "now": get_wita()
            })

            new_id = result.scalar()

            return {"id_materi_private": new_id}

    except SQLAlchemyError as e:
        print(f"[create_materi_private] Error: {e}")
        return None


def get_materi_by_mentorship(id_mentorship):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            result = conn.execute(text("""
                SELECT 
                    mp.id_materi_private,
                    mp.judul,
                    mp.tipe_materi,
                    mp.url_file,
                    mp.visibility,
                    mp.is_downloadable,
                    mp.viewer_only,
                    mp.created_at,

                    u.id_user AS id_owner,
                    u.nama AS nama_owner

                FROM materi_private mp
                LEFT JOIN users u 
                    ON u.id_user = mp.id_owner
                WHERE mp.id_mentorship = :id_mentorship
                  AND mp.status = 1
                ORDER BY mp.created_at DESC
            """), {"id_mentorship": id_mentorship}).mappings().fetchall()

            return [serialize_row(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_materi_by_mentorship] Error: {e}")
        return []


def get_materi_private_by_id(id_materi_private):
    engine = get_connection()

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    mp.id_materi_private,
                    mp.id_mentorship,
                    mp.judul,
                    mp.tipe_materi,
                    mp.url_file,
                    mp.visibility,
                    mp.is_downloadable,
                    mp.viewer_only,
                    mp.created_at,
                    mp.updated_at,

                    u.id_user AS id_owner,
                    u.nama AS nama_owner

                FROM materi_private mp
                LEFT JOIN users u 
                    ON u.id_user = mp.id_owner
                WHERE mp.id_materi_private = :id
                  AND mp.status = 1
            """), {"id": id_materi_private}).mappings().fetchone()

            return serialize_row(result) if result else None

    except SQLAlchemyError as e:
        print(f"[get_materi_private_by_id] Error: {e}")
        return None


def update_materi_private(
    id_materi_private,
    judul=None,
    tipe_materi=None,
    url_file=None,
    visibility=None,
    is_downloadable=None,
    viewer_only=None
):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            existing = conn.execute(text("""
                SELECT 1 FROM materi_private
                WHERE id_materi_private = :id
                  AND status = 1
            """), {"id": id_materi_private}).fetchone()

            if not existing:
                return {"error": "Materi tidak ditemukan"}

            conn.execute(text("""
                UPDATE materi_private
                SET 
                    judul = COALESCE(:judul, judul),
                    tipe_materi = COALESCE(:tipe_materi, tipe_materi),
                    url_file = COALESCE(:url_file, url_file),
                    visibility = COALESCE(:visibility, visibility),
                    is_downloadable = COALESCE(:is_downloadable, is_downloadable),
                    viewer_only = COALESCE(:viewer_only, viewer_only),
                    updated_at = :now
                WHERE id_materi_private = :id
            """), {
                "id": id_materi_private,
                "judul": judul,
                "tipe_materi": tipe_materi,
                "url_file": url_file,
                "visibility": visibility,
                "is_downloadable": is_downloadable,
                "viewer_only": viewer_only,
                "now": get_wita()
            })

            return {"id_materi_private": id_materi_private}

    except SQLAlchemyError as e:
        print(f"[update_materi_private] Error: {e}")
        return None


def delete_materi_private(id_materi_private):
    engine = get_connection()

    try:
        with engine.begin() as conn:

            existing = conn.execute(text("""
                SELECT 1 FROM materi_private
                WHERE id_materi_private = :id
                  AND status = 1
            """), {"id": id_materi_private}).fetchone()

            if not existing:
                return {"error": "Materi tidak ditemukan"}

            conn.execute(text("""
                UPDATE materi_private
                SET status = 0,
                    updated_at = :now
                WHERE id_materi_private = :id
            """), {
                "id": id_materi_private,
                "now": get_wita()
            })

            return {"id_materi_private": id_materi_private}

    except SQLAlchemyError as e:
        print(f"[delete_materi_private] Error: {e}")
        return None



# ======================================================================
# QUERY MATERI PRIVATE (PESERTA)
# ======================================================================
def get_materi_private_by_user(id_user, tipe=None):
    engine = get_connection()

    try:
        with engine.connect() as conn:

            base_query = """
                FROM materi_private mp
                JOIN mentorship m 
                    ON m.id_mentorship = mp.id_mentorship
                   AND m.status = 1
                LEFT JOIN users u 
                    ON u.id_user = mp.id_owner

                WHERE m.id_peserta = :id_user
                  AND mp.status = 1
                  AND mp.visibility = 'open'
            """

            params = {"id_user": id_user}

            # 🔥 FILTER TIPE
            if tipe:
                if tipe == "document":
                    base_query += " AND mp.tipe_materi = 'document'"
                else:
                    base_query += " AND mp.tipe_materi = :tipe"
                    params["tipe"] = tipe

            query = text(f"""
                SELECT 
                    mp.id_materi_private,
                    mp.judul,
                    mp.tipe_materi,
                    mp.url_file,
                    mp.visibility,
                    mp.is_downloadable,
                    mp.viewer_only,
                    mp.created_at,

                    m.id_mentorship,
                    m.nama_mentorship,

                    u.id_user AS id_owner,
                    u.nama AS nama_owner

                {base_query}
                ORDER BY mp.created_at DESC
            """)

            result = conn.execute(query, params).mappings().fetchall()

            return [serialize_row(row) for row in result]

    except SQLAlchemyError as e:
        print(f"[get_materi_private_by_user] Error: {e}")
        return []