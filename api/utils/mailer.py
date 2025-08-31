from flask_mail import Message
from . import mail

def send_recovery_email(to_email, kode_pemulihan):
    try:
        msg = Message(
            subject="Kode Pemulihan Akun Ukai Syndrome",
            recipients=[to_email],
            body=f"""
Halo,

Berikut kode pemulihan akun kamu: {kode_pemulihan}

Masukkan kode ini di aplikasi Ukai Syndrome untuk melanjutkan registrasi.

Salam,  
Tim Ukai Syndrome
"""
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
