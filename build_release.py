import os
import sys
import zipfile

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

VERSION = "1.0.0"
ARCHIVE_NAME = f"StorageScanner-v{VERSION}.zip"

# Файлы, упаковываемые в релизный ZIP-архив
RELEASE_FILES = [
    "run_scanner.bat",
    "disk_scanner.py",
    "disk_scanner.pyw",
    "requirements.txt",
    "README.md"
]

def make_zip_release():
    print(f"📦 Создание релизного архива: {ARCHIVE_NAME}...")
    with zipfile.ZipFile(ARCHIVE_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in RELEASE_FILES:
            if os.path.exists(fname):
                zf.write(fname, arcname=fname)
                print(f"  + добавлен {fname}")
            else:
                print(f"  - пропущен (не найден) {fname}")
                
    print(f"\n✅ Готово! Архив создан: {os.path.abspath(ARCHIVE_NAME)}")
    print("👉 Загрузите этот ZIP-архив в раздел GitHub Releases.")
    print("   Пользователи просто распакуют архив и сразу запустят run_scanner.bat!")

if __name__ == "__main__":
    make_zip_release()
