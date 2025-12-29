import requests
from .config import CDN_API_KEY, CDN_UPLOAD_URL

def upload_image_to_cdn(image_file, folder="tryout"):
    """
    Upload file ke CDN MGF
    Return: {success, url}
    """

    files = {
        "file": (
            image_file.filename,
            image_file.stream,
            image_file.mimetype
        )
    }

    headers = {
        "X-API-KEY": CDN_API_KEY
    }

    data = {
        "folder": folder
    }

    try:
        response = requests.post(
            f"{CDN_UPLOAD_URL}/tryout",
            headers=headers,
            files=files,
            data=data
        )

        if not response.ok:
            return {
                "success": False,
                "message": "Upload ke CDN gagal",
                "detail": response.text
            }

        res_json = response.json()

        if "url" not in res_json:
            return {
                "success": False,
                "message": "Response CDN tidak valid"
            }

        return {
            "success": True,
            "url": res_json["url"]
        }

    except requests.RequestException as e:
        print(f"[CDN ERROR] {e}")
        return {
            "success": False,
            "message": "Tidak dapat terhubung ke CDN"
        }
