import os
import sys
import time
import shutil
import string
import heapq
import tempfile
import threading
import subprocess
from pathlib import Path
from collections import defaultdict

# Предотвращаем предупреждения Matplotlib о временном каталоге
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())

# Настройка безопасной кодировки вывода в консоли Windows
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import matplotlib
matplotlib.use('Agg')  # Для CLI или до инициализации Tk
import matplotlib.pyplot as plt

# Настройка шрифтов для корректного отображения кириллицы
matplotlib.rcParams['font.sans-serif'] = ['Segoe UI', 'DejaVu Sans', 'Arial', 'sans-serif']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['axes.unicode_minus'] = False

WHOLE_COMPUTER_LABEL = "🖥️ Весь компьютер (Все диски)"

# Категории файлов и их расширения
FILE_CATEGORIES = {
    'Видео': {
        'extensions': {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.vob', '.3gp'},
        'color': '#E74C3C'  # Красный
    },
    'Изображения': {
        'extensions': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.ico', '.tiff', '.tif', '.raw', '.heic', '.psd', '.ai'},
        'color': '#1ABC9C'  # Бирюзовый
    },
    'Аудио': {
        'extensions': {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.alac', '.mid', '.midi'},
        'color': '#3498DB'  # Синий
    },
    'Архивы и образы': {
        'extensions': {'.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.img', '.bz2', '.xz', '.cab', '.dmg', '.tgz'},
        'color': '#E67E22'  # Оранжевый
    },
    'Документы': {
        'extensions': {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.txt', '.csv', '.rtf', '.odt', '.ods', '.odp', '.epub', '.fb2', '.djvu', '.md'},
        'color': '#2ECC71'  # Зеленый
    },
    'Программы и игры': {
        'extensions': {'.exe', '.msi', '.dll', '.sys', '.bat', '.cmd', '.ps1', '.apk', '.bin', '.appx'},
        'color': '#F1C40F'  # Желтый
    },
    'Код и проекты': {
        'extensions': {'.py', '.js', '.ts', '.html', '.css', '.cpp', '.c', '.h', '.hpp', '.java', '.cs', '.go', '.rs', '.php', '.json', '.xml', '.yaml', '.yml', '.sql'},
        'color': '#9B59B6'  # Фиолетовый
    },
    'Виртуализация и БД': {
        'extensions': {'.vmdk', '.vdi', '.vhdx', '.qcow2', '.db', '.sqlite', '.sqlite3', '.mdf', '.ldf'},
        'color': '#34495E'  # Темно-синий
    },
    'Другое / Прочее': {
        'extensions': set(),
        'color': '#95A5A6'  # Серый
    }
}

# Быстрое сопоставление расширение -> категория
EXT_TO_CATEGORY = {}
for cat_name, cat_data in FILE_CATEGORIES.items():
    for ext in cat_data['extensions']:
        EXT_TO_CATEGORY[ext.lower()] = cat_name


def format_size(size_bytes: int) -> str:
    """Форматирует байты в удобные человекочитаемые единицы (Б, КБ, МБ, ГБ, ТБ)."""
    if size_bytes < 0:
        return "0 Б"
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ', 'ПБ']:
        if abs(size_bytes) < 1024.0:
            if unit in ['Б', 'КБ']:
                return f"{size_bytes:,.0f} {unit}".replace(',', ' ')
            return f"{size_bytes:,.2f} {unit}".replace(',', ' ')
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} ЭБ"


def get_file_category(extension: str) -> str:
    """Определяет категорию по расширению файла."""
    ext = extension.lower()
    return EXT_TO_CATEGORY.get(ext, 'Другое / Прочее')


def get_available_drives():
    """Возвращает список доступных накопителей в системе Windows."""
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                usage = shutil.disk_usage(drive_path)
                drives.append({
                    'path': drive_path,
                    'name': f"Диск ({letter}:)",
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': (usage.used / usage.total) * 100 if usage.total > 0 else 0
                })
            except Exception:
                drives.append({
                    'path': drive_path,
                    'name': f"Диск ({letter}:)",
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'percent': 0
                })
    return drives


class ScanResult:
    """Хранилище результатов сканирования."""
    def __init__(self, target_label: str, is_whole_computer: bool = False):
        self.target_label = target_label
        self.is_whole_computer = is_whole_computer
        self.total_size = 0
        self.file_count = 0
        self.folder_count = 0
        self.error_count = 0
        self.elapsed_time = 0.0
        
        # Размеры по категориям файлов
        self.category_sizes = defaultdict(int)
        self.category_counts = defaultdict(int)
        
        # Топ-50 самых больших файлов: список кортежей (size, path, ext, category)
        self.largest_files = []
        
        # Размеры подкаталогов верхнего уровня
        self.subfolder_sizes = defaultdict(int)
        self.subfolder_file_counts = defaultdict(int)
        self.subfolder_full_paths = {}
        
        # Размеры по каждому диску (если сканируется весь ПК)
        self.drive_sizes = defaultdict(int)
        self.drive_file_counts = defaultdict(int)


def scan_storage(paths: list[str], target_label: str = None, progress_callback=None, stop_event=None) -> ScanResult:
    """
    Сканирование одного пути или нескольких накопителей (всего компьютера).
    Использует стек вместо рекурсии для предотвращения переполнения стека и быструю итерацию os.scandir.
    """
    is_multi = len(paths) > 1
    if not target_label:
        target_label = WHOLE_COMPUTER_LABEL if is_multi else paths[0]
        
    result = ScanResult(target_label, is_whole_computer=is_multi)
    start_time = time.time()
    
    heap_top_files = []
    max_top_files = 50
    
    last_callback_time = 0
    callback_interval = 0.1  # Обновление прогресса каждые 100 мс

    for root_dir in paths:
        if stop_event and stop_event.is_set():
            break
            
        root_path = os.path.abspath(root_dir)
        if not os.path.exists(root_path):
            continue
            
        drive_letter = os.path.splitdrive(root_path)[0].upper()
        stack = [root_path]

        while stack:
            if stop_event and stop_event.is_set():
                break
                
            current_dir = stack.pop()
            
            # Определяем подкаталог 1-го уровня для группировки
            try:
                rel_path = os.path.relpath(current_dir, root_path)
                if rel_path == '.':
                    if is_multi:
                        folder_key = f"{drive_letter}\\ [Файлы в корне]"
                        full_folder_path = root_path
                    else:
                        folder_key = '[Файлы в корневой папке]'
                        full_folder_path = root_path
                else:
                    first_part = rel_path.split(os.sep)[0]
                    if is_multi:
                        folder_key = f"{drive_letter}\\{first_part}"
                        full_folder_path = os.path.join(root_path, first_part)
                    else:
                        folder_key = first_part
                        full_folder_path = os.path.join(root_path, first_part)
            except ValueError:
                folder_key = f"{drive_letter}\\Другое" if is_multi else 'Другое'
                full_folder_path = current_dir

            result.subfolder_full_paths[folder_key] = full_folder_path

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        if stop_event and stop_event.is_set():
                            break
                            
                        try:
                            # Пропускаем символические ссылки во избежание зацикливания
                            if entry.is_symlink():
                                continue
                                
                            if entry.is_dir(follow_symlinks=False):
                                result.folder_count += 1
                                stack.append(entry.path)
                            elif entry.is_file(follow_symlinks=False):
                                size = entry.stat().st_size
                                result.total_size += size
                                result.file_count += 1
                                
                                # Учет по подпапке
                                result.subfolder_sizes[folder_key] += size
                                result.subfolder_file_counts[folder_key] += 1
                                
                                # Учет по диску
                                if is_multi:
                                    result.drive_sizes[drive_letter] += size
                                    result.drive_file_counts[drive_letter] += 1
                                
                                # Категория
                                ext = Path(entry.name).suffix.lower()
                                category = get_file_category(ext)
                                result.category_sizes[category] += size
                                result.category_counts[category] += 1
                                
                                # Отслеживание топ-файлов через мин-кучу
                                if len(heap_top_files) < max_top_files:
                                    heapq.heappush(heap_top_files, (size, entry.path, ext, category))
                                elif size > heap_top_files[0][0]:
                                    heapq.heapreplace(heap_top_files, (size, entry.path, ext, category))
                                    
                        except (PermissionError, FileNotFoundError, OSError):
                            result.error_count += 1
                            
            except (PermissionError, FileNotFoundError, OSError):
                result.error_count += 1

            # Обновление прогресса
            now = time.time()
            if progress_callback and (now - last_callback_time >= callback_interval):
                last_callback_time = now
                progress_callback(
                    current_dir=current_dir,
                    file_count=result.file_count,
                    total_size=result.total_size,
                    folder_count=result.folder_count
                )

    result.elapsed_time = time.time() - start_time
    result.largest_files = sorted(heap_top_files, key=lambda x: x[0], reverse=True)
    
    if progress_callback:
        progress_callback(
            current_dir="Сканирование завершено",
            file_count=result.file_count,
            total_size=result.total_size,
            folder_count=result.folder_count,
            finished=True
        )
        
    return result


def draw_charts_on_figure(fig, result: ScanResult):
    """Отрисовывает два информативных графика на переданном объекте Figure."""
    fig.clear()
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
    fig.subplots_adjust(wspace=0.38, top=0.88, bottom=0.12, left=0.08, right=0.95)
    
    total_scanned = result.total_size if result.total_size > 0 else 1
    
    # 1. Диаграмма категорий (Donut Chart)
    sorted_cats = sorted(
        [(cat, size) for cat, size in result.category_sizes.items() if size > 0],
        key=lambda x: x[1],
        reverse=True
    )
    
    if sorted_cats:
        labels = [cat for cat, size in sorted_cats]
        sizes = [size for cat, size in sorted_cats]
        colors = [FILE_CATEGORIES.get(cat, {}).get('color', '#95A5A6') for cat in labels]
        
        # Группируем очень мелкие категории (< 2%) в 'Другие'
        threshold = 0.02 * total_scanned
        grouped_labels = []
        grouped_sizes = []
        grouped_colors = []
        other_size = 0
        
        for lbl, sz, col in zip(labels, sizes, colors):
            if sz >= threshold or len(grouped_labels) < 4:
                grouped_labels.append(lbl)
                grouped_sizes.append(sz)
                grouped_colors.append(col)
            else:
                other_size += sz
                
        if other_size > 0:
            grouped_labels.append('Прочие (< 2%)')
            grouped_sizes.append(other_size)
            grouped_colors.append('#BDC3C7')
            
        wedges, texts, autotexts = ax1.pie(
            grouped_sizes,
            labels=grouped_labels,
            autopct=lambda pct: f'{pct:.1f}%' if pct >= 3.0 else '',
            pctdistance=0.75,
            startangle=140,
            colors=grouped_colors,
            wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2)
        )
        
        for t in texts:
            t.set_fontsize(9)
            t.set_color('#2C3E50')
        for at in autotexts:
            at.set_fontsize(8)
            at.set_weight('bold')
            at.set_color('#FFFFFF')
            
        center_title = "Файлов на ПК:\n" if result.is_whole_computer else "Файлов:\n"
        ax1.text(0, 0, f"{center_title}{format_size(result.total_size)}", 
                 ha='center', va='center', fontsize=10, weight='bold', color='#2C3E50')
        ax1.set_title("Распределение по типам файлов", fontsize=12, pad=15, weight='bold', color='#2C3E50')
    else:
        ax1.text(0.5, 0.5, "Нет данных о файлах", ha='center', va='center', color='#7F8C8D')
        ax1.set_title("Распределение по типам файлов", fontsize=12, pad=15, weight='bold', color='#2C3E50')
        ax1.axis('off')

    # 2. Столбчатая диаграмма Топ-10 папок
    sorted_folders = sorted(
        [(folder, size) for folder, size in result.subfolder_sizes.items() if size > 0],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    if sorted_folders:
        sorted_folders.reverse()
        folder_names = [f[0] if len(f[0]) <= 25 else f[0][:22] + '...' for f in sorted_folders]
        folder_sizes_bytes = [f[1] for f in sorted_folders]
        
        max_bytes = max(folder_sizes_bytes)
        if max_bytes >= 1024**3:
            unit_name = 'ГБ'
            divider = 1024**3
        elif max_bytes >= 1024**2:
            unit_name = 'МБ'
            divider = 1024**2
        else:
            unit_name = 'КБ'
            divider = 1024
            
        vals = [b / divider for b in folder_sizes_bytes]
        bars = ax2.barh(folder_names, vals, color='#3498DB', edgecolor='none', height=0.65)
        
        max_val = max(vals) if vals else 1
        for bar, b_size in zip(bars, folder_sizes_bytes):
            w = bar.get_width()
            ax2.text(w + (max_val * 0.02), bar.get_y() + bar.get_height() / 2,
                     format_size(b_size),
                     va='center', ha='left', fontsize=8, color='#34495E', weight='bold')
                     
        ax2.set_xlim(0, max_val * 1.28)
        ax2.set_xlabel(f"Размер ({unit_name})", fontsize=10, color='#2C3E50')
        chart_title = "Топ самых объёмных папок (все диски)" if result.is_whole_computer else "Топ самых объёмных папок"
        ax2.set_title(chart_title, fontsize=12, pad=15, weight='bold', color='#2C3E50')
        ax2.grid(axis='x', linestyle='--', alpha=0.5)
        ax2.set_axisbelow(True)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color('#BDC3C7')
        ax2.spines['bottom'].set_color('#BDC3C7')
        ax2.tick_params(colors='#2C3E50', labelsize=9)
    else:
        ax2.text(0.5, 0.5, "Нет подпапок для отображения", ha='center', va='center', color='#7F8C8D')
        ax2.set_title("Топ самых объёмных папок", fontsize=12, pad=15, weight='bold', color='#2C3E50')
        ax2.axis('off')


def create_charts_figure(result: ScanResult, figsize=(12, 6)):
    """Создает отдельную фигуру Matplotlib с графиками."""
    fig = plt.figure(figsize=figsize, facecolor='#F8F9FA')
    draw_charts_on_figure(fig, result)
    return fig


def run_cli_mode(target_paths: list[str], target_label: str = None, save_chart_path: str = "storage_report.png"):
    """Запуск сканера в консольном режиме с выводом информации и сохранением диаграммы."""
    print("=" * 68)
    print("        📊 СКАНЕР НАКОПИТЕЛЕЙ И АНАЛИЗАТОР ПАМЯТИ ПК")
    print("=" * 68)
    
    if len(target_paths) > 1 or target_label == WHOLE_COMPUTER_LABEL:
        print("🖥️  Режим: Сканирование всего компьютера (Все диски)")
        print(f"📂 Диски к сканированию: {', '.join(target_paths)}")
    else:
        print(f"📂 Сканируемый путь: {target_paths[0]}")
        
    print("⏳ Сканирование файлов... Пожалуйста, подождите...")
    
    def cli_progress(current_dir, file_count, total_size, folder_count, finished=False):
        if not finished:
            print(f"\r🔍 Файлов: {file_count:,} | Объём: {format_size(total_size)} | Папок: {folder_count:,}", end="", flush=True)

    result = scan_storage(target_paths, target_label=target_label, progress_callback=cli_progress)
    print("\n" + "-" * 68)
    print("✅ Сканирование завершено!")
    print(f"⏱️  Время выполнения: {result.elapsed_time:.2f} сек.")
    print(f"📁 Всего папок:      {result.folder_count:,}".replace(',', ' '))
    print(f"📄 Всего файлов:     {result.file_count:,}".replace(',', ' '))
    print(f"💾 Занято места:     {format_size(result.total_size)}")
    if result.error_count > 0:
        print(f"⚠️  Пропущено (ошибки доступа/системные): {result.error_count}")
    print("-" * 68)
    
    # Сводка по дискам (если сканировался весь компьютер)
    if result.is_whole_computer and result.drive_sizes:
        print("\n💾 ЗАНЯТОЕ МЕСТО ПО ДИСКАМ:")
        print(f"{'Диск':<10} | {'Занято файлов':<16} | {'Файлов'}")
        print("-" * 45)
        for drv, sz in sorted(result.drive_sizes.items()):
            cnt = result.drive_file_counts[drv]
            print(f"{drv:<10} | {format_size(sz):<16} | {cnt:,}".replace(',', ' '))

    # 1. Таблица по категориям
    print("\n📊 РАСПРЕДЕЛЕНИЕ ПО ТИПАМ ФАЙЛОВ:")
    print(f"{'Категория':<22} | {'Размер':<12} | {'Файлов':<10} | {'Доля (%)':<8}")
    print("-" * 58)
    sorted_cats = sorted(result.category_sizes.items(), key=lambda x: x[1], reverse=True)
    total_sz = result.total_size if result.total_size > 0 else 1
    for cat, sz in sorted_cats:
        count = result.category_counts[cat]
        pct = (sz / total_sz) * 100
        print(f"{cat:<22} | {format_size(sz):<12} | {count:<10,} | {pct:>6.2f}%")
        
    # 2. Топ папок
    print("\n📁 ТОП-10 САМЫХ БОЛЬШИХ ПАПОК:")
    print(f"{'Папка':<35} | {'Размер':<14} | {'Доля (%)':<8}")
    print("-" * 61)
    sorted_folders = sorted(result.subfolder_sizes.items(), key=lambda x: x[1], reverse=True)[:10]
    for folder, sz in sorted_folders:
        pct = (sz / total_sz) * 100
        short_name = folder if len(folder) <= 35 else folder[:32] + '...'
        print(f"{short_name:<35} | {format_size(sz):<14} | {pct:>6.2f}%")
        
    # 3. Топ-10 файлов
    print("\n📄 ТОП-10 САМЫХ БОЛЬШИХ ФАЙЛОВ:")
    print(f"{'Размер':<12} | {'Категория':<16} | {'Имя / Путь'}")
    print("-" * 68)
    for sz, filepath, ext, cat in result.largest_files[:10]:
        filename = os.path.basename(filepath)
        print(f"{format_size(sz):<12} | {cat:<16} | {filename} ({filepath})")

    # 4. Построение и сохранение диаграммы
    print("\n📈 Генерация наглядной диаграммы...")
    fig = create_charts_figure(result)
    fig.savefig(save_chart_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"🎉 Диаграмма успешно сохранена в файл: {os.path.abspath(save_chart_path)}")
    print("=" * 68)


def run_gui_mode():
    """Запуск графического интерфейса с поддержкой Tkinter и встроенным Matplotlib."""
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog

    class StorageScannerApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Анализатор дискового пространства и накопителей")
            self.root.geometry("1180x790")
            self.root.minsize(940, 620)

            # Переменные управления
            self.selected_path_var = tk.StringVar(value=WHOLE_COMPUTER_LABEL)
            self.status_var = tk.StringVar(value="Готов к сканированию. Выберите режим и нажмите «Начать сканирование».")
            self.stats_var = tk.StringVar(value="Файлов: 0 | Папок: 0 | Общий объём: 0 Б")
            self.drive_info_var = tk.StringVar(value="")
            self.file_search_var = tk.StringVar(value="")
            
            self.is_scanning = False
            self.stop_event = threading.Event()
            self.current_result = None

            # Хранение сырых данных для фильтрации и открытия
            self.cached_files = []
            self.folder_paths_map = {}

            self.setup_styles()
            self.create_widgets()
            self.update_drive_info()

        def setup_styles(self):
            style = ttk.Style()
            if 'clam' in style.theme_names():
                style.theme_use('clam')
                
            style.configure('.', font=('Segoe UI', 9))
            style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'), foreground='#2C3E50')
            style.configure('Title.TLabel', font=('Segoe UI', 13, 'bold'), foreground='#1A365D')
            style.configure('Status.TLabel', font=('Segoe UI', 9), foreground='#4A5568')
            
            style.configure('Accent.TButton', font=('Segoe UI', 9, 'bold'), background='#2B6CB0', foreground='white')
            style.map('Accent.TButton',
                      background=[('active', '#2C5282'), ('disabled', '#CBD5E0')])

            style.configure('AllComputer.TButton', font=('Segoe UI', 9, 'bold'), background='#2F855A', foreground='white')
            style.map('AllComputer.TButton',
                      background=[('active', '#276749'), ('disabled', '#CBD5E0')])
                      
            style.configure('Stop.TButton', font=('Segoe UI', 9, 'bold'), background='#E53E3E', foreground='white')
            style.map('Stop.TButton',
                      background=[('active', '#C53030'), ('disabled', '#CBD5E0')])

            style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'), background='#EDF2F7')
            style.configure("Treeview", rowheight=24, font=('Segoe UI', 9))

        def create_widgets(self):
            main_frame = ttk.Frame(self.root, padding="12")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Верхняя панель управления
            top_panel = ttk.LabelFrame(main_frame, text=" 💾 Выбор области сканирования ", padding="10")
            top_panel.pack(fill=tk.X, pady=(0, 10))

            # Ряд 1: Кнопки выбора (Весь компьютер + отдельные диски)
            drives_frame = ttk.Frame(top_panel)
            drives_frame.pack(fill=tk.X, pady=(0, 6))

            ttk.Label(drives_frame, text="Быстрый выбор:", font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 6))
            
            # Кнопка «Весь компьютер»
            btn_all = ttk.Button(
                drives_frame, 
                text="🖥️ Весь компьютер (Все диски)",
                style='AllComputer.TButton',
                command=self.select_whole_computer
            )
            btn_all.pack(side=tk.LEFT, padx=(0, 8))

            # Разделитель
            ttk.Separator(drives_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

            # Кнопки доступных накопителей
            drives = get_available_drives()
            for d in drives:
                btn = ttk.Button(
                    drives_frame, 
                    text=f"{d['name']} [{format_size(d['free'])} свободно]",
                    command=lambda p=d['path']: self.select_quick_drive(p)
                )
                btn.pack(side=tk.LEFT, padx=3)

            # Ряд 2: Ввод пути и кнопки действий
            path_row = ttk.Frame(top_panel)
            path_row.pack(fill=tk.X, pady=4)

            ttk.Label(path_row, text="Путь / Режим:").pack(side=tk.LEFT, padx=(0, 6))
            path_entry = ttk.Entry(path_row, textvariable=self.selected_path_var, font=('Segoe UI', 9))
            path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

            ttk.Button(path_row, text="Обзор папки...", command=self.browse_folder).pack(side=tk.LEFT, padx=3)
            
            self.scan_button = ttk.Button(
                path_row, 
                text="▶ Начать сканирование", 
                style='Accent.TButton',
                command=self.toggle_scan
            )
            self.scan_button.pack(side=tk.LEFT, padx=6)

            # Ряд 3: Информация о емкости диска или компьютера
            self.lbl_drive_info = ttk.Label(top_panel, textvariable=self.drive_info_var, style='Status.TLabel')
            self.lbl_drive_info.pack(anchor='w', pady=(4, 0))

            # Прогресс и статус
            status_panel = ttk.Frame(main_frame)
            status_panel.pack(fill=tk.X, pady=(0, 8))

            self.progress_bar = ttk.Progressbar(status_panel, mode='indeterminate')
            self.progress_bar.pack(fill=tk.X, pady=(0, 4))

            stats_row = ttk.Frame(status_panel)
            stats_row.pack(fill=tk.X)
            
            self.lbl_status = ttk.Label(stats_row, textvariable=self.status_var, style='Status.TLabel')
            self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.lbl_stats = ttk.Label(stats_row, textvariable=self.stats_var, font=('Segoe UI', 9, 'bold'), foreground='#2B6CB0')
            self.lbl_stats.pack(side=tk.RIGHT)

            # Вкладки
            self.notebook = ttk.Notebook(main_frame)
            self.notebook.pack(fill=tk.BOTH, expand=True)

            # Вкладка 1: Диаграммы
            self.tab_charts = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_charts, text=" 📊 Диаграммы ")
            self.setup_charts_tab()

            # Вкладка 2: Топ папок
            self.tab_folders = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_folders, text=" 📁 Топ папок ")
            self.setup_folders_tab()

            # Вкладка 3: Топ файлов
            self.tab_files = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_files, text=" 📄 Топ файлов ")
            self.setup_files_tab()

            # Вкладка 4: Категории
            self.tab_categories = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_categories, text=" 🏷️ Категории данных ")
            self.setup_categories_tab()

        def select_whole_computer(self):
            self.selected_path_var.set(WHOLE_COMPUTER_LABEL)
            self.update_drive_info()

        def select_quick_drive(self, path):
            self.selected_path_var.set(path)
            self.update_drive_info()

        def browse_folder(self):
            folder = filedialog.askdirectory()
            if folder:
                self.selected_path_var.set(folder)
                self.update_drive_info()

        def update_drive_info(self):
            path = self.selected_path_var.get().strip()
            drives = get_available_drives()
            
            if path == WHOLE_COMPUTER_LABEL or path.lower() in ['all', 'весь компьютер']:
                total_all = sum(d['total'] for d in drives)
                used_all = sum(d['used'] for d in drives)
                free_all = sum(d['free'] for d in drives)
                pct = (used_all / total_all) * 100 if total_all > 0 else 0
                drives_str = ", ".join(d['name'] for d in drives)
                self.drive_info_var.set(
                    f"🖥️ ВЕСЬ КОМПЬЮТЕР ({drives_str})  |  "
                    f"Всего памяти: {format_size(total_all)}  |  "
                    f"Занято: {format_size(used_all)} ({pct:.1f}%)  |  "
                    f"Свободно: {format_size(free_all)}"
                )
                return

            if not path:
                return

            try:
                drive_or_root = os.path.splitdrive(os.path.abspath(path))[0] + '\\'
                if os.path.exists(drive_or_root):
                    usage = shutil.disk_usage(drive_or_root)
                    pct = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                    self.drive_info_var.set(
                        f"Накопитель {drive_or_root}  |  Всего: {format_size(usage.total)}  |  "
                        f"Занято: {format_size(usage.used)} ({pct:.1f}%)  |  "
                        f"Свободно: {format_size(usage.free)}"
                    )
            except Exception:
                self.drive_info_var.set("")

        # --- ВКЛАДКА 1: ДИАГРАММЫ ---
        def setup_charts_tab(self):
            top_bar = ttk.Frame(self.tab_charts, padding="6 6 6 0")
            top_bar.pack(fill=tk.X)
            
            ttk.Label(
                top_bar, 
                text="Интерактивные диаграммы распределения памяти (типы файлов и топ папок):", 
                style='Header.TLabel'
            ).pack(side=tk.LEFT)

            self.btn_save_chart = ttk.Button(
                top_bar, 
                text="💾 Экспорт графика (PNG)...", 
                command=self.save_chart_as_image,
                state='disabled'
            )
            self.btn_save_chart.pack(side=tk.RIGHT)

            self.chart_container = ttk.Frame(self.tab_charts)
            self.chart_container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

            self.fig = plt.figure(figsize=(10, 5), facecolor='#F8F9FA')
            ax = self.fig.add_subplot(1, 1, 1)
            ax.text(0.5, 0.5, "Выберите режим сканирования (диск или весь компьютер) и запустите анализ",
                    ha='center', va='center', fontsize=12, color='#718096')
            ax.axis('off')
            
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_container)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        def save_chart_as_image(self):
            if not self.current_result:
                return
            default_name = "storage_report_all_pc.png" if self.current_result.is_whole_computer else "storage_report.png"
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG изображения", "*.png"), ("Все файлы", "*.*")],
                initialfile=default_name
            )
            if file_path:
                try:
                    fig = create_charts_figure(self.current_result)
                    fig.savefig(file_path, dpi=200, bbox_inches='tight')
                    plt.close(fig)
                    messagebox.showinfo("Успешно", f"Диаграмма сохранена в файл:\n{file_path}")
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")

        # --- ВКЛАДКА 2: ТОП ПАПОК ---
        def setup_folders_tab(self):
            top_bar = ttk.Frame(self.tab_folders, padding="6")
            top_bar.pack(fill=tk.X)
            
            ttk.Label(top_bar, text="Самые объёмные папки (нажмите дважды или используйте кнопку для открытия):", style='Header.TLabel').pack(side=tk.LEFT)
            
            btn_open = ttk.Button(top_bar, text="📂 Открыть папку в Проводнике", command=self.open_selected_folder)
            btn_open.pack(side=tk.RIGHT)

            cols = ('name', 'size', 'percent', 'files', 'path')
            self.folders_tree = ttk.Treeview(self.tab_folders, columns=cols, show='headings')
            
            self.folders_tree.heading('name', text='Имя папки')
            self.folders_tree.heading('size', text='Объём')
            self.folders_tree.heading('percent', text='Доля (%)')
            self.folders_tree.heading('files', text='Файлов')
            self.folders_tree.heading('path', text='Полный путь')

            self.folders_tree.column('name', width=220, anchor='w')
            self.folders_tree.column('size', width=120, anchor='e')
            self.folders_tree.column('percent', width=90, anchor='e')
            self.folders_tree.column('files', width=100, anchor='e')
            self.folders_tree.column('path', width=450, anchor='w')

            scrollbar = ttk.Scrollbar(self.tab_folders, orient=tk.VERTICAL, command=self.folders_tree.yview)
            self.folders_tree.configure(yscrollcommand=scrollbar.set)
            
            self.folders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)
            
            self.folders_tree.bind("<Double-1>", lambda event: self.open_selected_folder())

        # --- ВКЛАДКА 3: ТОП ФАЙЛОВ ---
        def setup_files_tab(self):
            top_bar = ttk.Frame(self.tab_files, padding="6")
            top_bar.pack(fill=tk.X)
            
            ttk.Label(top_bar, text="Топ самых больших файлов (основные кандидаты на очистку):", style='Header.TLabel').pack(side=tk.LEFT)
            
            btn_open_file = ttk.Button(top_bar, text="🔍 Показать файл в папке", command=self.open_selected_file)
            btn_open_file.pack(side=tk.RIGHT)

            filter_bar = ttk.Frame(self.tab_files, padding="6 0 6 6")
            filter_bar.pack(fill=tk.X)
            
            ttk.Label(filter_bar, text="Быстрый фильтр (расширение или имя):").pack(side=tk.LEFT, padx=(0, 6))
            search_entry = ttk.Entry(filter_bar, textvariable=self.file_search_var, width=30)
            search_entry.pack(side=tk.LEFT, padx=(0, 6))
            self.file_search_var.trace_add("write", lambda *args: self.filter_files_tree())

            cols = ('name', 'size', 'category', 'path')
            self.files_tree = ttk.Treeview(self.tab_files, columns=cols, show='headings')
            
            self.files_tree.heading('name', text='Имя файла')
            self.files_tree.heading('size', text='Размер')
            self.files_tree.heading('category', text='Категория')
            self.files_tree.heading('path', text='Путь к файлу')

            self.files_tree.column('name', width=260, anchor='w')
            self.files_tree.column('size', width=120, anchor='e')
            self.files_tree.column('category', width=150, anchor='w')
            self.files_tree.column('path', width=500, anchor='w')

            scrollbar = ttk.Scrollbar(self.tab_files, orient=tk.VERTICAL, command=self.files_tree.yview)
            self.files_tree.configure(yscrollcommand=scrollbar.set)
            
            self.files_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)

            self.files_tree.bind("<Double-1>", lambda event: self.open_selected_file())

        def filter_files_tree(self):
            query = self.file_search_var.get().strip().lower()
            for item in self.files_tree.get_children():
                self.files_tree.delete(item)

            for sz, filepath, ext, cat in self.cached_files:
                fname = os.path.basename(filepath)
                if not query or query in fname.lower() or query in cat.lower() or query in ext.lower():
                    self.files_tree.insert('', tk.END, values=(
                        fname,
                        format_size(sz),
                        cat,
                        filepath
                    ))

        # --- ВКЛАДКА 4: КАТЕГОРИИ ---
        def setup_categories_tab(self):
            top_bar = ttk.Frame(self.tab_categories, padding="6")
            top_bar.pack(fill=tk.X)
            
            ttk.Label(top_bar, text="Сводка по категориям контента (Видео, Игры, Документы и др.):", style='Header.TLabel').pack(side=tk.LEFT)

            cols = ('cat', 'size', 'percent', 'count')
            self.cat_tree = ttk.Treeview(self.tab_categories, columns=cols, show='headings')
            
            self.cat_tree.heading('cat', text='Категория')
            self.cat_tree.heading('size', text='Общий объём')
            self.cat_tree.heading('percent', text='Доля (%)')
            self.cat_tree.heading('count', text='Количество файлов')

            self.cat_tree.column('cat', width=220, anchor='w')
            self.cat_tree.column('size', width=140, anchor='e')
            self.cat_tree.column('percent', width=120, anchor='e')
            self.cat_tree.column('count', width=150, anchor='e')

            scrollbar = ttk.Scrollbar(self.tab_categories, orient=tk.VERTICAL, command=self.cat_tree.yview)
            self.cat_tree.configure(yscrollcommand=scrollbar.set)
            
            self.cat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=6)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 6), pady=6)

        # Открытие в Проводнике
        def open_selected_folder(self):
            selected = self.folders_tree.selection()
            if not selected:
                return
            item = self.folders_tree.item(selected[0])
            folder_path = item['values'][4]
            if os.path.exists(folder_path):
                try:
                    os.startfile(folder_path)
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{e}")
            else:
                messagebox.showwarning("Внимание", f"Папка не существует или недоступна:\n{folder_path}")

        def open_selected_file(self):
            selected = self.files_tree.selection()
            if not selected:
                return
            item = self.files_tree.item(selected[0])
            file_path = item['values'][3]
            if os.path.exists(file_path):
                try:
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(file_path)}"')
                except Exception as e:
                    messagebox.showerror("Ошибка", f"Не удалось выделить файл в проводнике:\n{e}")
            else:
                messagebox.showwarning("Внимание", "Файл не найден или был удалён.")

        # Сканирование
        def toggle_scan(self):
            if self.is_scanning:
                self.stop_event.set()
                self.status_var.set("Остановка сканирования...")
                self.scan_button.config(state='disabled')
            else:
                path_str = self.selected_path_var.get().strip()
                
                # Проверка: весь компьютер или конкретный путь
                is_all = (path_str == WHOLE_COMPUTER_LABEL or path_str.lower() in ['all', 'весь компьютер', 'компьютер'])
                
                if is_all:
                    drives = get_available_drives()
                    paths_to_scan = [d['path'] for d in drives if os.path.exists(d['path'])]
                    target_label = WHOLE_COMPUTER_LABEL
                else:
                    if not os.path.exists(path_str):
                        messagebox.showerror("Ошибка", f"Указанный путь не существует:\n{path_str}")
                        return
                    paths_to_scan = [path_str]
                    target_label = path_str

                self.is_scanning = True
                self.stop_event.clear()
                self.scan_button.config(text="⏹ Остановить сканирование", style='Stop.TButton')
                self.progress_bar.start(10)
                self.btn_save_chart.config(state='disabled')
                
                threading.Thread(target=self._worker_scan, args=(paths_to_scan, target_label), daemon=True).start()

        def _worker_scan(self, paths, target_label):
            def progress_cb(current_dir, file_count, total_size, folder_count, finished=False):
                self.root.after(0, self._update_gui_progress, current_dir, file_count, total_size, folder_count, finished)

            result = scan_storage(paths, target_label=target_label, progress_callback=progress_cb, stop_event=self.stop_event)
            self.root.after(0, self._on_scan_finished, result)

        def _update_gui_progress(self, current_dir, file_count, total_size, folder_count, finished):
            if not finished:
                display_dir = current_dir if len(current_dir) <= 60 else "..." + current_dir[-57:]
                self.status_var.set(f"Сканирование: {display_dir}")
                self.stats_var.set(f"Файлов: {file_count:,} | Папок: {folder_count:,} | Объём: {format_size(total_size)}".replace(',', ' '))

        def _on_scan_finished(self, result: ScanResult):
            self.is_scanning = False
            self.progress_bar.stop()
            self.scan_button.config(text="▶ Начать сканирование", style='Accent.TButton', state='normal')
            self.current_result = result
            self.btn_save_chart.config(state='normal')

            target_name = "всего компьютера" if result.is_whole_computer else "выбранного пути"
            if self.stop_event.is_set():
                self.status_var.set(f"Сканирование прервано пользователем. Найдено файлов: {result.file_count:,}".replace(',', ' '))
            else:
                self.status_var.set(
                    f"Анализ {target_name} завершен! Занято: {format_size(result.total_size)} | "
                    f"Файлов: {result.file_count:,} | Папок: {result.folder_count:,} | "
                    f"Время: {result.elapsed_time:.2f} сек.".replace(',', ' ')
                )

            self.render_all_data(result)

        def render_all_data(self, result: ScanResult):
            total_sz = result.total_size if result.total_size > 0 else 1
            self.cached_files = result.largest_files
            self.folder_paths_map = result.subfolder_full_paths

            # 1. Диаграммы
            draw_charts_on_figure(self.fig, result)
            self.canvas.draw()

            # 2. Папки
            for item in self.folders_tree.get_children():
                self.folders_tree.delete(item)
                
            sorted_folders = sorted(result.subfolder_sizes.items(), key=lambda x: x[1], reverse=True)
            for folder_name, sz in sorted_folders:
                pct = (sz / total_sz) * 100
                cnt = result.subfolder_file_counts.get(folder_name, 0)
                full_p = self.folder_paths_map.get(folder_name, folder_name)
                    
                self.folders_tree.insert('', tk.END, values=(
                    folder_name,
                    format_size(sz),
                    f"{pct:.2f} %",
                    f"{cnt:,}".replace(',', ' '),
                    full_p
                ))

            # 3. Файлы
            self.filter_files_tree()

            # 4. Категории
            for item in self.cat_tree.get_children():
                self.cat_tree.delete(item)

            sorted_cats = sorted(result.category_sizes.items(), key=lambda x: x[1], reverse=True)
            for cat, sz in sorted_cats:
                cnt = result.category_counts[cat]
                pct = (sz / total_sz) * 100
                self.cat_tree.insert('', tk.END, values=(
                    cat,
                    format_size(sz),
                    f"{pct:.2f} %",
                    f"{cnt:,}".replace(',', ' ')
                ))

    root = tk.Tk()
    app = StorageScannerApp(root)
    root.mainloop()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Анализатор дискового пространства и накопителей на Python")
    parser.add_argument("--cli", action="store_true", help="Запустить в консольном режиме (без GUI)")
    parser.add_argument("--all", action="store_true", help="Сканировать весь компьютер (все подключенные накопители)")
    parser.add_argument("--path", type=str, default=None, help="Путь для сканирования (папка или диск, например C:\\ или D:\\)")
    parser.add_argument("--output", type=str, default="storage_report.png", help="Имя файла для сохранения диаграммы в CLI-режиме")
    
    args = parser.parse_args()

    if args.cli:
        if args.all or (args.path and args.path.upper() in ["ALL", "ВЕСЬ", "ВСЕ"]):
            drives = get_available_drives()
            paths = [d['path'] for d in drives if os.path.exists(d['path'])]
            run_cli_mode(paths, target_label=WHOLE_COMPUTER_LABEL, save_chart_path=args.output)
        else:
            scan_target = args.path if args.path else "C:\\"
            run_cli_mode([scan_target], target_label=scan_target, save_chart_path=args.output)
    else:
        run_gui_mode()


if __name__ == "__main__":
    main()
