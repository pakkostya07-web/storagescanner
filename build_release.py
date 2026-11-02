import os
import sys
import zipfile
import shutil
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

VERSION = "1.0.0"
ARCHIVE_NAME = f"StorageScanner-v{VERSION}.zip"

# Файлы, включаемые в релиз
RELEASE_FILES = [
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
    print(f"\n✅ Архив успешно создан: {os.path.abspath(ARCHIVE_NAME)}")
    print("👉 Этот ZIP-файл можно сразу загружать в GitHub Releases!")

def try_build_exe():
    try:
        import PyInstaller
        print("\n🔨 Найден PyInstaller. Сборка автономного EXE...")
        cmd = [
            "pyinstaller",
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--name", "StorageScanner",
            "disk_scanner.py"
        ]
        subprocess.run(cmd, check=True)
        print("✅ EXE собран в папке dist/StorageScanner/")
    except ImportError:
        print("\n💡 Совет: чтобы собрать автономный .exe файл для релизов:")
        print("   pip install pyinstaller")
        print("   pyinstaller --onefile --windowed --name StorageScanner disk_scanner.py")

if __name__ == "__main__":
    make_zip_release()
    try_build_exe()
