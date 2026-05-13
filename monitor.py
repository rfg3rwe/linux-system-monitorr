#!/usr/bin/env python3
"""
Linux System Monitor — SysMon v3.0.
Полноценный GUI-монитор с вкладками, графиками и кнопками.
Авторы: Лива, Настя, Максим
"""

import psutil
import time
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import yaml

# --------------------------- Конфигурация ---------------------------
DEFAULT_CONFIG = {
    'thresholds': {'low': 50, 'medium': 80},
    'interval': 1.0,
    'history_size': 60,
    'log_file': 'system_log.txt',
    'log_max_entries': 1000,
}

def load_config():
    if Path('config.yaml').exists():
        with open('config.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG

config = load_config()
THRESHOLDS = config['thresholds']
INTERVAL = config['interval']
HISTORY_SIZE = config['history_size']

# --------------------------- Сбор метрик ---------------------------
class SystemStats:
    def __init__(self):
        self.cpu_history = deque(maxlen=HISTORY_SIZE)
        self.ram_history = deque(maxlen=HISTORY_SIZE)
        self.net_history = deque(maxlen=HISTORY_SIZE)
        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.time()
        psutil.cpu_percent(interval=None)

    def get_all(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        now = time.time()

        # Скорость сети
        elapsed = now - self.prev_time
        download_speed = (net.bytes_recv - self.prev_net.bytes_recv) / elapsed
        upload_speed = (net.bytes_sent - self.prev_net.bytes_sent) / elapsed
        self.prev_net = net
        self.prev_time = now

        # Температура
        temp = None
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            temp = temps['coretemp'][0].current

        # История
        self.cpu_history.append(cpu)
        self.ram_history.append(ram.percent)

        return {
            'cpu': cpu,
            'ram_percent': ram.percent,
            'ram_used_gb': round(ram.used / (1024**3), 1),
            'ram_total_gb': round(ram.total / (1024**3), 1),
            'disk_percent': disk.percent,
            'disk_used_gb': round(disk.used / (1024**3), 1),
            'disk_total_gb': round(disk.total / (1024**3), 1),
            'download': download_speed,
            'upload': upload_speed,
            'temp': temp,
            'processes': len(psutil.pids()),
        }

# --------------------------- Цвета ---------------------------
def get_color(value):
    if value < THRESHOLDS['low']:
        return '#00cc66'
    elif value < THRESHOLDS['medium']:
        return '#ffaa00'
    else:
        return '#ff3333'

def format_speed(bytes_per_sec):
    if bytes_per_sec < 1024:
        return f'{bytes_per_sec:.0f} B/s'
    elif bytes_per_sec < 1024**2:
        return f'{bytes_per_sec/1024:.1f} KB/s'
    else:
        return f'{bytes_per_sec/(1024**2):.1f} MB/s'

# --------------------------- График на Canvas ---------------------------
class MiniGraph(tk.Canvas):
    def __init__(self, parent, width=300, height=60, color='#00cc66'):
        super().__init__(parent, width=width, height=height, bg='#1e1e1e', highlightthickness=0)
        self.width = width
        self.height = height
        self.color = color
        self.data = deque(maxlen=60)

    def add_value(self, value):
        self.data.append(value)
        self.draw()

    def draw(self):
        self.delete('all')
        if len(self.data) < 2:
            return

        max_val = max(self.data) if max(self.data) > 0 else 1
        step_x = self.width / (len(self.data) - 1)

        points = []
        for i, val in enumerate(self.data):
            x = i * step_x
            y = self.height - (val / max_val) * (self.height - 10) - 5
            points.extend([x, y])

        self.create_line(points, fill=self.color, width=2, smooth=True)

# --------------------------- Главное окно ---------------------------
class SysMonApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Linux System Monitor')
        self.root.geometry('750x550')
        self.root.configure(bg='#2b2b2b')
        self.root.resizable(True, True)
        self.stats = SystemStats()
        self.running = True

        self.setup_ui()
        self.update_loop()

    def setup_ui(self):
        # Заголовок
        title_frame = tk.Frame(self.root, bg='#1a1a1a', height=50)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        title = tk.Label(
            title_frame,
            text='🖥️  LINUX SYSTEM MONITOR',
            font=('Segoe UI', 16, 'bold'),
            bg='#1a1a1a',
            fg='#ffffff'
        )
        title.pack(pady=10)

        # Блок кнопок
        btn_frame = tk.Frame(self.root, bg='#2b2b2b')
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text='🔄 Обновить', command=self.manual_refresh).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='📋 Логи', command=self.show_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text='ℹ️ О программе', command=self.show_about).pack(side=tk.LEFT, padx=5)

        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            btn_frame,
            text='Автообновление',
            variable=self.auto_refresh_var
        ).pack(side=tk.LEFT, padx=20)

        ttk.Label(btn_frame, text=f'Интервал: {INTERVAL}с').pack(side=tk.RIGHT, padx=10)

        # Вкладки
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Вкладка 1: Обзор
        overview_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(overview_frame, text='📊 Обзор')
        self.setup_overview_tab(overview_frame)

        # Вкладка 2: Графики
        graphs_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(graphs_frame, text='📈 Графики')
        self.setup_graphs_tab(graphs_frame)

        # Вкладка 3: Диск
        disk_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(disk_frame, text='💾 Диск')
        self.setup_disk_tab(disk_frame)

        # Строка состояния
        self.status_bar = tk.Label(
            self.root,
            text='Готов',
            bg='#1a1a1a',
            fg='#888888',
            anchor=tk.W,
            padx=10
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def setup_overview_tab(self, parent):
        # Левая колонка
        left = tk.Frame(parent, bg='#2b2b2b')
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.cpu_bar = self.create_progress_block(left, 'Процессор (CPU)', 'cpu')
        self.ram_bar = self.create_progress_block(left, 'Память (RAM)', 'ram')
        self.temp_label = self.create_info_label(left, 'Температура: -- °C')

        # Правая колонка
        right = tk.Frame(parent, bg='#2b2b2b')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.disk_bar = self.create_progress_block(right, 'Диск (/)', 'disk')
        self.download_label = self.create_info_label(right, 'Загрузка: --')
        self.upload_label = self.create_info_label(right, 'Отправка: --')
        self.proc_label = self.create_info_label(right, 'Процессов: --')

    def create_progress_block(self, parent, title, tag):
        frame = tk.Frame(parent, bg='#333333', relief=tk.RIDGE, bd=1)
        frame.pack(fill=tk.X, pady=5)

        header = tk.Frame(frame, bg='#333333')
        header.pack(fill=tk.X, padx=10, pady=(10, 0))

        tk.Label(
            header, text=title,
            font=('Segoe UI', 12, 'bold'),
            bg='#333333', fg='#ffffff'
        ).pack(side=tk.LEFT)

        value_label = tk.Label(
            header, text='0%',
            font=('Segoe UI', 12, 'bold'),
            bg='#333333', fg='#00cc66'
        )
        value_label.pack(side=tk.RIGHT)

        canvas = tk.Canvas(frame, height=25, bg='#1e1e1e', highlightthickness=0)
        canvas.pack(fill=tk.X, padx=10, pady=(5, 10))

        setattr(self, f'{tag}_canvas', canvas)
        setattr(self, f'{tag}_value_label', value_label)

        return frame

    def create_info_label(self, parent, text):
        label = tk.Label(
            parent,
            text=text,
            font=('Segoe UI', 11),
            bg='#333333',
            fg='#ffffff',
            anchor=tk.W,
            padx=15,
            pady=10,
            relief=tk.RIDGE,
            bd=1
        )
        label.pack(fill=tk.X, pady=5)
        return label

    def setup_graphs_tab(self, parent):
        parent.configure(bg='#2b2b2b')

        frame = tk.Frame(parent, bg='#2b2b2b')
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(
            frame, text='Загрузка CPU (история)',
            font=('Segoe UI', 11, 'bold'),
            bg='#2b2b2b', fg='#ffffff'
        ).pack(anchor=tk.W)

        self.cpu_graph = MiniGraph(frame, width=680, height=80, color='#00cc66')
        self.cpu_graph.pack(fill=tk.X, pady=(5, 20))

        tk.Label(
            frame, text='Использование RAM (история)',
            font=('Segoe UI', 11, 'bold'),
            bg='#2b2b2b', fg='#ffffff'
        ).pack(anchor=tk.W)

        self.ram_graph = MiniGraph(frame, width=680, height=80, color='#ffaa00')
        self.ram_graph.pack(fill=tk.X, pady=5)

    def setup_disk_tab(self, parent):
        parent.configure(bg='#2b2b2b')

        frame = tk.Frame(parent, bg='#2b2b2b')
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(
            frame, text='💾 Информация о диске /',
            font=('Segoe UI', 14, 'bold'),
            bg='#2b2b2b', fg='#ffffff'
        ).pack(pady=(0, 20))

        self.disk_total_label = tk.Label(
            frame, text='Всего: -- GB',
            font=('Segoe UI', 12),
            bg='#333333', fg='#ffffff',
            relief=tk.RIDGE, bd=1,
            padx=20, pady=10
        )
        self.disk_total_label.pack(fill=tk.X, pady=5)

        self.disk_used_label = tk.Label(
            frame, text='Занято: -- GB',
            font=('Segoe UI', 12),
            bg='#333333', fg='#ffffff',
            relief=tk.RIDGE, bd=1,
            padx=20, pady=10
        )
        self.disk_used_label.pack(fill=tk.X, pady=5)

        self.disk_free_label = tk.Label(
            frame, text='Свободно: -- GB',
            font=('Segoe UI', 12),
            bg='#333333', fg='#ffffff',
            relief=tk.RIDGE, bd=1,
            padx=20, pady=10
        )
        self.disk_free_label.pack(fill=tk.X, pady=5)

        self.disk_canvas = tk.Canvas(frame, height=30, bg='#1e1e1e', highlightthickness=0)
        self.disk_canvas.pack(fill=tk.X, pady=(20, 0))

    def update_progress(self, canvas, value, max_width=None):
        canvas.delete('all')
        if max_width is None:
            max_width = canvas.winfo_width()
        if max_width < 10:
            max_width = 300
        fill_width = int((value / 100) * max_width)
        color = get_color(value)
        canvas.create_rectangle(0, 0, fill_width, 25, fill=color, outline='')
        canvas.create_text(
            max_width / 2, 12,
            text=f'{value:.1f}%',
            fill='#ffffff',
            font=('Segoe UI', 10, 'bold')
        )

    def manual_refresh(self):
        data = self.stats.get_all()
        self.update_display(data)
        self.status_bar.config(text=f'Обновлено вручную | {datetime.now().strftime("%H:%M:%S")}')

    def update_display(self, data):
        # CPU
        max_w = self.cpu_bar.winfo_width() if hasattr(self, 'cpu_bar') else 300
        self.update_progress(self.cpu_canvas, data['cpu'], max_w - 20)
        self.cpu_value_label.config(
            text=f'{data["cpu"]:.1f}%',
            fg=get_color(data['cpu'])
        )

        # RAM
        max_w = self.ram_bar.winfo_width() if hasattr(self, 'ram_bar') else 300
        self.update_progress(self.ram_canvas, data['ram_percent'], max_w - 20)
        self.ram_value_label.config(
            text=f'{data["ram_percent"]:.1f}%',
            fg=get_color(data['ram_percent'])
        )
        self.ram_bar_label_text = f'Занято: {data["ram_used_gb"]} GB / {data["ram_total_gb"]} GB'
        self.ram_value_label.config(text=f'{data["ram_percent"]:.1f}%')

        # Disk
        self.update_progress(self.disk_canvas, data['disk_percent'], 680)
        self.disk_value_label.config(
            text=f'{data["disk_percent"]:.1f}%',
            fg=get_color(data['disk_percent'])
        )

        # Disk tab
        self.disk_total_label.config(text=f'Всего: {data["disk_total_gb"]} GB')
        self.disk_used_label.config(text=f'Занято: {data["disk_used_gb"]} GB')
        disk_free = data['disk_total_gb'] - data['disk_used_gb']
        self.disk_free_label.config(text=f'Свободно: {disk_free:.1f} GB')

        # Temperature
        temp_text = f'Температура: {data["temp"]}°C' if data['temp'] else 'Температура: -- °C'
        self.temp_label.config(text=temp_text)

        # Network
        self.download_label.config(text=f'Загрузка: {format_speed(data["download"])}')
        self.upload_label.config(text=f'Отправка: {format_speed(data["upload"])}')

        # Processes
        self.proc_label.config(text=f'Процессов: {data["processes"]}')

        # Graphs
        self.cpu_graph.add_value(data['cpu'])
        self.ram_graph.add_value(data['ram_percent'])

    def update_loop(self):
        if self.running:
            data = self.stats.get_all()
            self.update_display(data)
            self.status_bar.config(
                text=f'Обновлено: {datetime.now().strftime("%H:%M:%S")} | '
                     f'CPU: {data["cpu"]:.0f}% | RAM: {data["ram_percent"]:.0f}%'
            )

            if self.auto_refresh_var.get():
                self.root.after(int(INTERVAL * 1000), self.update_loop)
            else:
                self.status_bar.config(text='Автообновление отключено')

    def show_logs(self):
        log_window = tk.Toplevel(self.root)
        log_window.title('Логи системы')
        log_window.geometry('600x400')
        log_window.configure(bg='#2b2b2b')

        text = scrolledtext.ScrolledText(
            log_window,
            bg='#1e1e1e',
            fg='#00ff66',
            font=('Courier New', 10),
            insertbackground='#00ff66'
        )
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        log_path = config.get('log_file', 'system_log.txt')
        if Path(log_path).exists():
            text.insert(tk.END, Path(log_path).read_text(encoding='utf-8'))
        else:
            text.insert(tk.END, 'Лог-файл отсутствует.')

        text.config(state=tk.DISABLED)

    def show_about(self):
        messagebox.showinfo(
            'О программе',
            'Linux System Monitor v3.0\n\n'
            'Мониторинг ресурсов Linux в реальном времени.\n'
            'CPU, RAM, диск, сеть, температура.\n\n'
            'Авторы: Лива, Настя, Максим\n'
            '© 2025'
        )

    def on_close(self):
        self.running = False
        self.root.destroy()

# --------------------------- Запуск ---------------------------
def main():
    root = tk.Tk()
    app = SysMonApp(root)
    root.protocol('WM_DELETE_WINDOW', app.on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
