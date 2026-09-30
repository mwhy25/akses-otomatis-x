"""
Backend API untuk posting ke X dari website abc.com.
Dibungkus dengan Flask, menggunakan twifork sebagai client X.

MODE PAKAI:
    python server.py           -> jalankan server Flask
    python server.py --test    -> test posting langsung (hardcode)
    python server.py --test-image -> test posting dengan gambar (hardcode)
"""

import os
import sys
import asyncio
import tempfile
from pathlib import Path
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from twifork import Client

# ============================================================
# KONFIGURASI
# ============================================================

load_dotenv()

AUTH_TOKEN = os.environ.get("X_AUTH_TOKEN", "")
CT0 = os.environ.get("X_CT0", "")

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "https://abc.com,https://www.abc.com,http://localhost:3000,http://localhost:5173"
).split(",")

MAX_FILE_SIZE = 5 * 1024 * 1024

# ============================================================
# TEKS HARDCODE UNTUK TESTING
# ============================================================
TEKS_TEST = "Test dari server.py — kalau muncul, berarti backend siap dipakai! 🚀"

# Path gambar untuk test (kosongkan kalau tidak ada)
GAMBAR_TEST = "test.jpg"  # ganti dengan nama file gambar Anda, atau biarkan kalau belum ada

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
CORS(app, origins=ALLOWED_ORIGINS)


# ============================================================
# HELPER
# ============================================================

def validasi_env():
    if not AUTH_TOKEN or not CT0:
        return False, "Environment variable X_AUTH_TOKEN / X_CT0 belum di-set."
    return True, None


def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def buat_client() -> Client:
    client = Client("en-US")
    client.set_cookies({"auth_token": AUTH_TOKEN, "ct0": CT0})
    return client


# ============================================================
# MODE TEST (jalankan dengan: python server.py --test)
# ============================================================

async def test_post_teks():
    """Test posting teks hardcode."""
    print("=" * 60)
    print("  TEST: POSTING TEKS")
    print("=" * 60)

    ok, err = validasi_env()
    if not ok:
        print(f"[✗] {err}")
        return

    print(f"[+] Cookie terkonfigurasi: auth_token={AUTH_TOKEN[:8]}..., ct0={CT0[:8]}...")
    print(f"[+] Teks: {TEKS_TEST}")
    print("[...] Mengirim tweet...")

    try:
        client = buat_client()
        result = await client.create_tweet(text=TEKS_TEST)
        print("[✓] BERHASIL! Tweet terkirim.")
        print(f"    Response: {result}")
    except Exception as e:
        print(f"[✗] GAGAL: {e}")


async def test_post_gambar():
    """Test posting teks + gambar hardcode."""
    print("=" * 60)
    print("  TEST: POSTING TEKS + GAMBAR")
    print("=" * 60)

    ok, err = validasi_env()
    if not ok:
        print(f"[✗] {err}")
        return

    if not os.path.exists(GAMBAR_TEST):
        print(f"[✗] File gambar '{GAMBAR_TEST}' tidak ditemukan.")
        print(f"    Taruh file gambar di folder yang sama dengan server.py,")
        print(f"    atau ubah variabel GAMBAR_TEST di atas.")
        return

    print(f"[+] Cookie terkonfigurasi: auth_token={AUTH_TOKEN[:8]}..., ct0={CT0[:8]}...")
    print(f"[+] Gambar: {GAMBAR_TEST} ({os.path.getsize(GAMBAR_TEST) / 1024:.1f} KB)")
    print(f"[+] Teks: {TEKS_TEST}")
    print("[...] Mengupload gambar...")

    try:
        client = buat_client()

        # Upload gambar
        media_id = await client.upload_media(GAMBAR_TEST)
        print(f"[+] Gambar terupload. media_id: {media_id}")

        # Kirim tweet
        print("[...] Mengirim tweet dengan gambar...")
        result = await client.create_tweet(
            text=TEKS_TEST,
            media_ids=[media_id],
        )
        print("[✓] BERHASIL! Tweet dengan gambar terkirim.")
        print(f"    Response: {result}")
    except Exception as e:
        print(f"[✗] GAGAL: {e}")


# ============================================================
# ENDPOINT API (untuk dipanggil frontend)
# ============================================================

@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "status": "ok",
        "service": "abc-x-backend",
        "endpoints": ["/health", "/post", "/post-with-image"],
    })


@app.route("/health", methods=["GET"])
def health():
    ok, err = validasi_env()
    return jsonify({
        "status": "ok" if ok else "error",
        "cookie_configured": ok,
        "message": err or "Server siap menerima request.",
    }), (200 if ok else 500)


@app.route("/post", methods=["POST"])
@async_route
async def post_text():
    ok, err = validasi_env()
    if not ok:
        return jsonify({"success": False, "error": err}), 500

    data = request.get_json(silent=True) or {}
    teks = (data.get("text") or "").strip()

    if not teks:
        return jsonify({"success": False, "error": "Field 'text' wajib diisi."}), 400

    if len(teks) > 280:
        return jsonify({
            "success": False,
            "error": f"Teks terlalu panjang ({len(teks)} karakter, maks 280)."
        }), 400

    try:
        client = buat_client()
        result = await client.create_tweet(text=teks)
        return jsonify({
            "success": True,
            "message": "Tweet berhasil dikirim.",
            "result": str(result),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Gagal mengirim tweet: {e}",
        }), 500


@app.route("/post-with-image", methods=["POST"])
@async_route
async def post_with_image():
    ok, err = validasi_env()
    if not ok:
        return jsonify({"success": False, "error": err}), 500

    teks = (request.form.get("text") or "").strip()
    file = request.files.get("image")

    if not file or file.filename == "":
        return jsonify({"success": False, "error": "File 'image' wajib diupload."}), 400

    ext = Path(file.filename).suffix.lower()
    ext_diizinkan = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if ext not in ext_diizinkan:
        return jsonify({
            "success": False,
            "error": f"Format '{ext}' tidak didukung. Gunakan: {', '.join(ext_diizinkan)}",
        }), 400

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        client = buat_client()
        media_id = await client.upload_media(tmp_path)
        result = await client.create_tweet(
            text=teks if teks else None,
            media_ids=[media_id],
        )

        return jsonify({
            "success": True,
            "message": "Tweet dengan gambar berhasil dikirim.",
            "media_id": str(media_id),
            "result": str(result),
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Gagal mengirim tweet dengan gambar: {e}",
        }), 500

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ============================================================
# ERROR HANDLER
# ============================================================

@app.errorhandler(413)
def file_terlalu_besar(e):
    return jsonify({
        "success": False,
        "error": f"File terlalu besar. Maksimal {MAX_FILE_SIZE // (1024*1024)} MB.",
    }), 413


@app.errorhandler(404)
def tidak_ditemukan(e):
    return jsonify({"success": False, "error": "Endpoint tidak ditemukan."}), 404


@app.errorhandler(500)
def error_server(e):
    return jsonify({"success": False, "error": "Terjadi error di server."}), 500


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Mode test: langsung posting hardcode
    if "--test" in sys.argv:
        asyncio.run(test_post_teks())
        sys.exit(0)

    if "--test-image" in sys.argv:
        asyncio.run(test_post_gambar())
        sys.exit(0)

    # Mode default: jalankan server Flask
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print(f"  SERVER BERJALAN DI PORT {port}")
    print("=" * 60)
    print(f"  Cookie terkonfigurasi: {bool(AUTH_TOKEN and CT0)}")
    print(f"  Allowed origins: {ALLOWED_ORIGINS}")
    print()
    print("  Endpoint:")
    print(f"    GET  http://localhost:{port}/health")
    print(f"    POST http://localhost:{port}/post")
    print(f"    POST http://localhost:{port}/post-with-image")
    print()
    print("  Untuk test posting hardcode, jalankan:")
    print("    python server.py --test")
    print("    python server.py --test-image")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=True)