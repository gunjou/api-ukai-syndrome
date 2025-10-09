from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..utils.helper import serialize_row
from ..utils.config import get_connection, get_wita


""" #=== Endpoint Thread ===# """

def get_all_forum_thread(id_batch=None, id_materi=None, search=None):
    """
    Mengambil semua thread forum dengan opsi filter:
    - id_batch (untuk membatasi batch tertentu)
    - id_materi (untuk materi tertentu)
    - search (mencari berdasarkan judul/isi thread)
    """
    engine = get_connection()
    try:
        with engine.connect() as connection:
            # Base SQL
            query = """
                SELECT 
                    ft.id_thread, ft.judul AS thread_subject, ft.isi, ft.is_solved, ft.status, ft.created_at, ft.updated_at,
                    ft.id_materi, m.judul, ft.id_paketkelas, pk.nama_kelas, ft.id_batch, b.nama_batch,
                    u.id_user, u.nama AS nama_user,
                    COALESCE(COUNT(fc.id_comment), 0) AS total_komentar
                FROM forum_thread ft
                JOIN users u ON u.id_user = ft.id_user
                LEFT JOIN materi m ON m.id_materi = ft.id_materi
                LEFT JOIN paketkelas pk ON pk.id_paketkelas = ft.id_paketkelas
                LEFT JOIN batch b ON b.id_batch = ft.id_batch
                LEFT JOIN forum_comment fc ON fc.id_thread = ft.id_thread
                WHERE ft.status = 1
            """
            # Tambah filter dinamis
            params = {}
            if id_batch:
                query += " AND ft.id_batch = :id_batch"
                params['id_batch'] = id_batch
            if id_materi:
                query += " AND ft.id_materi = :id_materi"
                params['id_materi'] = id_materi
            if search:
                query += " AND (ft.judul AS thread_subject ILIKE :search OR ft.isi ILIKE :search)"
                params['search'] = f"%{search}%"

            query += """
                GROUP BY ft.id_thread, m.judul, pk.nama_kelas, b.nama_batch, u.id_user
                ORDER BY ft.created_at DESC;
            """

            result = connection.execute(text(query), params).mappings().fetchall()
            threads = [serialize_row(row) for row in result]

            return threads
    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return []


def get_forum_thread_detail(id_thread):
    """
    Mengambil detail satu thread beserta komentar-komentarnya (nested)
    """
    engine = get_connection()
    try:
        with engine.connect() as connection:
            # Ambil data thread utama
            thread_query = text("""
                SELECT 
                    ft.id_thread, ft.judul as thread_subject, ft.isi, ft.is_solved, ft.status, ft.created_at, ft.updated_at,
                    ft.id_materi, m.judul, ft.id_paketkelas, pk.nama_kelas, ft.id_batch, b.nama_batch,
                    u.id_user, u.nama AS nama_user
                FROM forum_thread ft
                JOIN users u ON u.id_user = ft.id_user AND u.status = 1
                LEFT JOIN materi m ON m.id_materi = ft.id_materi AND m.status = 1
                LEFT JOIN paketkelas pk ON pk.id_paketkelas = ft.id_paketkelas AND pk.status = 1
                LEFT JOIN batch b ON b.id_batch = ft.id_batch AND b.status = 1
                WHERE ft.status = 1 AND ft.id_thread = :id_thread
                LIMIT 1;
            """)
            thread_result = connection.execute(thread_query, {'id_thread': id_thread}).mappings().fetchone()

            if not thread_result:
                return None

            thread_data = serialize_row(thread_result)

            # Ambil semua komentar untuk thread ini
            comment_query = text("""
                SELECT 
                    fc.id_comment, fc.parent_id, fc.id_user, u.nama AS nama_user,
                    fc.isi, fc.is_solved_answer, fc.is_deleted, fc.deleted_by_mentor,
                    fc.created_at, fc.updated_at,
                    COALESCE(SUM(fv.vote_type), 0) AS total_vote
                FROM forum_comment fc
                JOIN users u ON u.id_user = fc.id_user AND u.status = 1
                LEFT JOIN forum_vote fv ON fv.id_comment = fc.id_comment
                WHERE fc.id_thread = :id_thread
                GROUP BY fc.id_comment, u.nama
                ORDER BY fc.created_at ASC;
            """)
            comment_result = connection.execute(comment_query, {'id_thread': id_thread}).mappings().fetchall()
            comments = [serialize_row(row) for row in comment_result]

            # Bentuk komentar nested
            comment_dict = {c['id_comment']: c for c in comments}
            for c in comment_dict.values():
                c['replies'] = []

            root_comments = []
            for c in comments:
                parent_id = c['parent_id']
                if parent_id and parent_id in comment_dict:
                    comment_dict[parent_id]['replies'].append(c)
                else:
                    root_comments.append(c)

            thread_data['comments'] = root_comments
            thread_data['total_comments'] = len(comments)

            return thread_data

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def create_forum_thread(id_user, judul, isi, id_materi=None, id_paketkelas=None, id_batch=None):
    """
    Membuat thread baru di forum
    """
    engine = get_connection()
    wita = get_wita()
    try:
        with engine.begin() as connection:
            query = text("""
                INSERT INTO forum_thread (
                    id_user, judul, isi, id_materi, id_paketkelas, id_batch,
                    is_solved, status, created_at, updated_at
                )
                VALUES (
                    :id_user, :judul, :isi, :id_materi, :id_paketkelas, :id_batch,
                    FALSE, 1, :created_at, :updated_at
                )
                RETURNING id_thread, judul, isi, created_at;
            """)
            params = {
                'id_user': id_user,
                'judul': judul,
                'isi': isi,
                'id_materi': id_materi,
                'id_paketkelas': id_paketkelas,
                'id_batch': id_batch,
                'created_at': wita,
                'updated_at': wita
            }

            result = connection.execute(query, params).mappings().fetchone()
            return serialize_row(result) if result else None

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def update_forum_thread(id_thread, id_user, judul=None, isi=None):
    """
    Mengupdate thread (judul atau isi)
    - Hanya pembuat thread atau admin yang boleh mengedit
    - Jika field dikirim null, maka nilai sebelumnya akan dipertahankan
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek apakah thread ada dan milik user ini
            check = connection.execute(text("""
                SELECT id_thread, id_user, judul, isi
                FROM forum_thread
                WHERE id_thread = :id_thread AND status = 1
            """), {'id_thread': id_thread}).mappings().first()

            if not check:
                return 'not_found'

            # Cek kepemilikan atau role admin
            if int(check['id_user']) != int(id_user):
                role_check = connection.execute(text("""
                    SELECT role FROM users WHERE id_user = :id_user
                """), {'id_user': id_user}).scalar()
                if role_check != 'admin':
                    return 'forbidden'

            # Gunakan nilai lama jika input null
            new_judul = judul if judul is not None else check['judul']
            new_isi = isi if isi is not None else check['isi']

            # Cek jika keduanya sama seperti sebelumnya (tidak ada perubahan)
            if new_judul == check['judul'] and new_isi == check['isi']:
                return 'no_changes'

            # Jalankan update
            update_query = """
                UPDATE forum_thread
                SET judul = :judul,
                    isi = :isi,
                    updated_at = NOW()
                WHERE id_thread = :id_thread
                RETURNING id_thread, judul, isi, updated_at;
            """
            params = {
                'id_thread': id_thread,
                'judul': new_judul,
                'isi': new_isi
            }

            updated = connection.execute(text(update_query), params).mappings().first()
            return serialize_row(updated) if updated else None

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def delete_forum_thread(id_thread, id_user):
    """
    Menghapus thread (soft delete)
    - Hanya pembuat thread atau admin yang boleh menghapus
    - Tidak benar-benar menghapus data, hanya ubah status menjadi 0
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek apakah thread ada
            check = connection.execute(text("""
                SELECT id_thread, id_user FROM forum_thread
                WHERE id_thread = :id_thread AND status = 1
            """), {'id_thread': id_thread}).mappings().first()

            if not check:
                return 'not_found'

            # Validasi kepemilikan atau admin
            if int(check['id_user']) != int(id_user):
                role_check = connection.execute(text("""
                    SELECT role FROM users WHERE id_user = :id_user
                """), {'id_user': id_user}).scalar()

                if role_check != 'admin':
                    return 'forbidden'

            # Soft delete
            connection.execute(text("""
                UPDATE forum_thread
                SET status = 0, updated_at = :now
                WHERE id_thread = :id_thread
            """), {'id_thread': id_thread, "now": get_wita()})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


""" #=== Endpoint Comment ===# """

def create_forum_comment(id_user, id_thread, isi, parent_id=None):
    """
    Membuat komentar baru di thread forum
    - Bisa membuat komentar utama atau reply ke komentar lain
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek apakah thread ada dan aktif
            thread_check = connection.execute(text("""
                SELECT id_thread FROM forum_thread
                WHERE id_thread = :id_thread AND status = 1
            """), {'id_thread': id_thread}).mappings().first()

            if not thread_check:
                return 'not_found'

            # Jika parent_id diisi, pastikan komentar induk valid
            if parent_id:
                parent_check = connection.execute(text("""
                    SELECT id_comment FROM forum_comment
                    WHERE id_comment = :parent_id AND id_thread = :id_thread AND status = 1
                """), {'parent_id': parent_id, 'id_thread': id_thread}).mappings().first()

                if not parent_check:
                    raise ValueError("Komentar induk tidak ditemukan atau sudah dihapus")

            # Insert komentar baru
            insert_query = text("""
                INSERT INTO forum_comment (id_user, id_thread, isi, parent_id)
                VALUES (:id_user, :id_thread, :isi, :parent_id)
                RETURNING id_comment, id_user, id_thread, isi, parent_id, created_at;
            """)

            result = connection.execute(insert_query, {
                'id_user': id_user,
                'id_thread': id_thread,
                'isi': isi,
                'parent_id': parent_id
            }).mappings().first()

            return serialize_row(result) if result else None

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return None


def get_thread_comments(id_thread):
    """
    Ambil semua komentar dari sebuah thread dalam struktur nested (balasan bertingkat)
    """
    engine = get_connection()
    try:
        with engine.connect() as connection:
            # Pastikan thread valid
            thread_check = connection.execute(text("""
                SELECT id_thread FROM forum_thread
                WHERE id_thread = :id_thread AND status = 1
            """), {'id_thread': id_thread}).mappings().first()
            if not thread_check:
                return 'not_found'

            # Ambil semua komentar aktif pada thread ini
            query = text("""
                SELECT 
                    fc.id_comment,
                    fc.parent_id,
                    fc.id_user,
                    u.nama AS nama_user,
                    fc.isi,
                    fc.is_solved_answer,
                    fc.is_deleted,
                    fc.deleted_by_mentor,
                    fc.created_at,
                    fc.updated_at,
                    COALESCE(SUM(fv.vote_type), 0) AS total_vote
                FROM forum_comment fc
                JOIN users u ON u.id_user = fc.id_user
                LEFT JOIN forum_vote fv ON fv.id_comment = fc.id_comment
                WHERE fc.id_thread = :id_thread
                GROUP BY fc.id_comment, u.nama
                ORDER BY fc.created_at ASC
            """)

            comments = connection.execute(query, {'id_thread': id_thread}).mappings().fetchall()
            comments = [serialize_row(row) for row in comments]

            # Bangun struktur nested
            comment_dict = {c['id_comment']: c for c in comments}
            for c in comment_dict.values():
                c['replies'] = []

            root_comments = []
            for c in comments:
                if c['parent_id']:
                    parent = comment_dict.get(c['parent_id'])
                    if parent:
                        parent['replies'].append(c)
                else:
                    root_comments.append(c)

            return root_comments

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return []


def update_forum_comment(id_comment, id_user, isi=None):
    """
    Mengupdate komentar forum
    - Hanya pembuat komentar atau admin yang boleh mengedit
    - Jika isi None atau kosong, tidak ada perubahan
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Cek apakah komentar ada dan aktif
            check = connection.execute(text("""
                SELECT id_comment, id_user, isi
                FROM forum_comment
                WHERE id_comment = :id_comment AND is_deleted = FALSE
            """), {'id_comment': id_comment}).mappings().first()

            if not check:
                return 'not_found'

            # Cek kepemilikan atau role admin
            if int(check['id_user']) != int(id_user):
                role_check = connection.execute(text("""
                    SELECT role FROM users WHERE id_user = :id_user
                """), {'id_user': id_user}).scalar()
                if role_check != 'admin':
                    return 'forbidden'

            # Jika isi None → gunakan nilai lama
            if isi is None or isi.strip() == "":
                return 'empty_fields'

            # Update komentar
            update_query = text("""
                UPDATE forum_comment
                SET isi = :isi, updated_at = NOW()
                WHERE id_comment = :id_comment
                RETURNING id_comment, id_user, isi, updated_at;
            """)

            updated = connection.execute(update_query, {
                'id_comment': id_comment,
                'isi': isi.strip()
            }).mappings().first()

            return serialize_row(updated) if updated else None

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def soft_delete_forum_comment(id_comment, id_user):
    """
    Soft delete komentar:
    - Pemilik komentar boleh hapus sendiri
    - Mentor boleh hapus komentar di materi/kelas yang diampu
    - Admin boleh hapus semua
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Ambil data komentar dan thread terkait
            comment_data = connection.execute(text("""
                SELECT 
                    fc.id_comment, fc.id_user AS comment_owner, fc.is_deleted,
                    ft.id_materi, ft.id_paketkelas
                FROM forum_comment fc
                JOIN forum_thread ft ON ft.id_thread = fc.id_thread
                WHERE fc.id_comment = :id_comment
            """), {'id_comment': id_comment}).mappings().first()

            if not comment_data:
                return 'not_found'

            # Sudah dihapus sebelumnya
            if comment_data['is_deleted']:
                return True

            # Ambil role user
            user_role = connection.execute(text("""
                SELECT role FROM users WHERE id_user = :id_user
            """), {'id_user': id_user}).scalar()

            # Cek hak akses
            allowed = False
            deleted_by_mentor = False

            # Pemilik komentar
            if int(comment_data['comment_owner']) == int(id_user):
                allowed = True

            # Admin
            elif user_role == 'admin':
                allowed = True

            # Mentor (cek apakah mengampu materi / paketkelas)
            elif user_role == 'mentor':
                cek_mentor = connection.execute(text("""
                    SELECT 1 FROM mentorkelas
                    WHERE id_user = :id_user 
                    AND id_paketkelas = :id_paketkelas
                    AND status = 1
                    LIMIT 1;
                """), {
                    'id_user': id_user,
                    'id_paketkelas': comment_data['id_paketkelas']
                }).scalar()

                if cek_mentor:
                    allowed = True
                    deleted_by_mentor = True

            if not allowed:
                return 'forbidden'

            # Jalankan soft delete
            connection.execute(text("""
                UPDATE forum_comment
                SET is_deleted = TRUE,
                    deleted_by_mentor = :deleted_by_mentor,
                    updated_at = :now
                WHERE id_comment = :id_comment
            """), {
                'id_comment': id_comment,
                'deleted_by_mentor': deleted_by_mentor,
                "now": get_wita()
            })

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


""" #=== Query Vote ===# """

def add_or_update_vote(id_comment, id_user, vote_type):
    """
    Tambah atau ubah vote pada komentar.
    - Jika komentar tidak ada atau sudah dihapus → return 'not_found'
    - Jika user sudah vote dengan nilai sama → return 'no_change'
    - Jika belum → insert baru atau update vote_type
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Pastikan komentar valid & aktif
            comment_exists = connection.execute(text("""
                SELECT 1 FROM forum_comment
                WHERE id_comment = :id_comment AND is_deleted = FALSE
            """), {'id_comment': id_comment}).scalar()

            if not comment_exists:
                return 'not_found'

            # Cek apakah user sudah pernah vote
            existing_vote = connection.execute(text("""
                SELECT vote_type FROM forum_vote
                WHERE id_comment = :id_comment AND id_user = :id_user
            """), {'id_comment': id_comment, 'id_user': id_user}).mappings().first()

            if existing_vote:
                if existing_vote['vote_type'] == vote_type:
                    return 'no_change'
                else:
                    # Update vote
                    connection.execute(text("""
                        UPDATE forum_vote
                        SET vote_type = :vote_type, created_at = :now
                        WHERE id_comment = :id_comment AND id_user = :id_user
                    """), {'id_comment': id_comment, 'id_user': id_user, 'vote_type': vote_type, "now": get_wita()})
            else:
                # Insert vote baru
                connection.execute(text("""
                    INSERT INTO forum_vote (id_comment, id_user, vote_type)
                    VALUES (:id_comment, :id_user, :vote_type)
                """), {'id_comment': id_comment, 'id_user': id_user, 'vote_type': vote_type})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def delete_vote(id_comment, id_user):
    """
    Hapus vote milik user pada komentar.
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            vote_exists = connection.execute(text("""
                SELECT 1 FROM forum_vote
                WHERE id_comment = :id_comment AND id_user = :id_user
            """), {'id_comment': id_comment, 'id_user': id_user}).scalar()

            if not vote_exists:
                return 'not_found'

            connection.execute(text("""
                DELETE FROM forum_vote
                WHERE id_comment = :id_comment AND id_user = :id_user
            """), {'id_comment': id_comment, 'id_user': id_user})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


""" #=== Endpoint Solved ===# """

def mark_comment_as_solved(id_comment, id_user):
    """
    Tandai komentar sebagai solusi.
    - Hanya pembuat thread yang bisa menandai.
    - Jika sudah ada komentar solved → tidak bisa menandai lagi.
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            # Ambil komentar beserta thread-nya
            comment = connection.execute(text("""
                SELECT c.id_comment, c.id_thread, c.id_user AS comment_user,
                       c.is_deleted, t.id_user AS thread_owner, t.is_solved
                FROM forum_comment c
                JOIN forum_thread t ON c.id_thread = t.id_thread
                WHERE c.id_comment = :id_comment
            """), {'id_comment': id_comment}).mappings().first()

            if not comment or comment['is_deleted']:
                return 'not_found'

            # Hanya pembuat thread yang boleh menandai
            if int(comment['thread_owner']) != int(id_user):
                return 'forbidden'

            # Cek apakah sudah ada komentar solved di thread
            already_solved = connection.execute(text("""
                SELECT 1 FROM forum_comment
                WHERE id_thread = :id_thread AND is_solved_answer = TRUE
            """), {'id_thread': comment['id_thread']}).scalar()

            if already_solved:
                return 'already_solved'

            # Tandai komentar dan update thread
            connection.execute(text("""
                UPDATE forum_comment
                SET is_solved_answer = TRUE, updated_at = :now
                WHERE id_comment = :id_comment
            """), {'id_comment': id_comment, "now": get_wita()})

            connection.execute(text("""
                UPDATE forum_thread
                SET is_solved = TRUE, updated_at = :now
                WHERE id_thread = :id_thread
            """), {'id_thread': comment['id_thread'], "now": get_wita()})

            # Notifikasi opsional
            connection.execute(text("""
                INSERT INTO forum_notification (id_user, id_thread, id_comment, tipe)
                VALUES (:id_user, :id_thread, :id_comment, 'solved')
            """), {
                'id_user': comment['comment_user'],
                'id_thread': comment['id_thread'],
                'id_comment': id_comment
            })

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def unmark_comment_as_solved(id_comment, id_user):
    """
    Batalkan tanda solusi.
    - Hanya pembuat thread yang bisa membatalkan.
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            comment = connection.execute(text("""
                SELECT c.id_comment, c.id_thread, c.is_solved_answer,
                       t.id_user AS thread_owner
                FROM forum_comment c
                JOIN forum_thread t ON c.id_thread = t.id_thread
                WHERE c.id_comment = :id_comment
            """), {'id_comment': id_comment}).mappings().first()

            if not comment:
                return 'not_found'

            # Hanya pembuat thread yang boleh membatalkan
            if int(comment['thread_owner']) != int(id_user):
                return 'forbidden'

            # Reset tanda solved
            connection.execute(text("""
                UPDATE forum_comment
                SET is_solved_answer = FALSE, updated_at = :now
                WHERE id_comment = :id_comment
            """), {'id_comment': id_comment, "now": get_wita()})

            connection.execute(text("""
                UPDATE forum_thread
                SET is_solved = FALSE, updated_at = :now
                WHERE id_thread = :id_thread
            """), {'id_thread': comment['id_thread'], "now": get_wita()})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


""" #=== Endpoint Notification ===# """

def get_forum_notifications(id_user):
    """
    Ambil semua notifikasi milik user (terbaru di atas).
    """
    engine = get_connection()
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT id_notification, id_thread, id_comment, tipe, is_read,
                       created_at
                FROM forum_notification
                WHERE id_user = :id_user
                ORDER BY created_at DESC
            """), {'id_user': id_user}).mappings().all()

            return [dict(row) for row in result]

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return []


def mark_forum_notification_as_read(id_notification, id_user):
    """
    Tandai notifikasi sebagai dibaca oleh user.
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            notif = connection.execute(text("""
                SELECT id_user FROM forum_notification
                WHERE id_notification = :id_notification
            """), {'id_notification': id_notification}).scalar()

            if not notif:
                return 'not_found'
            if int(notif) != int(id_user):
                return 'forbidden'

            connection.execute(text("""
                UPDATE forum_notification
                SET is_read = TRUE, updated_at = :now
                WHERE id_notification = :id_notification
            """), {'id_notification': id_notification, "now": get_wita()})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None


def delete_forum_notification(id_notification, id_user):
    """
    Hapus notifikasi milik user.
    """
    engine = get_connection()
    try:
        with engine.begin() as connection:
            notif = connection.execute(text("""
                SELECT id_user FROM forum_notification
                WHERE id_notification = :id_notification
            """), {'id_notification': id_notification}).scalar()

            if not notif:
                return 'not_found'
            if int(notif) != int(id_user):
                return 'forbidden'

            connection.execute(text("""
                DELETE FROM forum_notification
                WHERE id_notification = :id_notification
            """), {'id_notification': id_notification})

            return True

    except SQLAlchemyError as e:
        print(f"Database error: {str(e)}")
        return None
