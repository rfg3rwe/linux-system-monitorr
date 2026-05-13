#!/usr/bin/env python3
"""
Linux System Monitor - SysMon v3.0
Мониторинг ресурсов Linux: CPU, RAM, диск, сеть, температура.
Авторы: Лива, Настя, Максим
"""

import psutil
import time
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
        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.time()
        psutil.cpu_percent(interval=None)

    def get_all(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net = psutil.net_io_counters()
        now = time.time()

        elapsed = now - self.prev_time
        download_speed = (net.bytes_recv - self.prev_net.bytes_recv) / elapsed
        upload_speed = (net.bytes_sent - self.prev_net.bytes_sent) / elapsed
        self.prev_net = net
        self.prev_time = now

        temp = None
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            temp = temps['coretemp'][0].current

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
        return '#4CAF50'
    elif value < THRESHOLDS['medium']:
        return '#FF9800'
    else:
        return '#F44336'

def format_speed(bytes_per_sec):
    if bytes_per_sec < 1024:
        return f'{bytes_per_sec:.0f} B/s'
    elif bytes_per_sec < 1024**2:
        return f'{bytes_per_sec/1024:.1f} KB/s'
    else:
        return f'{bytes_per_sec/(1024**2):.1f} MB/s'

# --------------------------- График ---------------------------
class MiniGraph(tk.Canvas):
    def __init__(self, parent, width=300, height=60, color='#4CAF50'):
        super().__init__(parent, width=width, height=height, bg='#1a1a1a', highlightthickness=0)
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
        self.root.geometry('780x560')
        self.root.configure(bg='#1e1e1e')
        self.root.minsize(700, 500)
        self.stats = SystemStats()
        self.running = True

        self.setup_style()
        self.setup_ui()
        self.update_loop()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton',
            background='#333333',
            foreground='#ffffff',
            borderwidth=1,
            focuscolor='none',
            font=('Segoe UI', 9)
        )
        style.map('TButton',
            background=[('active', '#444444')]
        )
        style.configure('Exit.TButton',
            background='#333333',
            foreground='#F44336',
            borderwidth=1,
            focuscolor='none',
            font=('Segoe UI', 9, 'bold')
        )
        style.map('Exit.TButton',
            background=[('active', '#553333')]
        )
        style.configure('TNotebook',
            background='#1e1e1e',
            borderwidth=0
        )
        style.configure('TNotebook.Tab',
            background='#2a2a2a',
            foreground='#aaaaaa',
            padding=[15, 8],
            font=('Segoe UI', 10)
        )
        style.map('TNotebook.Tab',
            background=[('selected', '#333333')],
            foreground=[('selected', '#ffffff')]
        )

    def setup_ui(self):
        # Заголовок
        header = tk.Frame(self.root, bg='#141414', height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text='LINUX SYSTEM MONITOR',
            font=('Segoe UI', 15, 'bold'),
            bg='#141414',
            fg='#e0e0e0'
        ).pack(pady=11)

        # Панель управления
        toolbar = tk.Frame(self.root, bg='#252525')
        toolbar.pack(fill=tk.X, padx=12, pady=(8, 0))

        ttk.Button(toolbar, text='Refresh', command=self.manual_refresh).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text='Logs', command=self.show_logs).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text='About', command=self.show_about).pack(side=tk.LEFT, padx=3)

        separator = ttk.Separator(toolbar, orient=tk.VERTICAL)
        separator.pack(side=tk.LEFT, padx=15, fill=tk.Y, pady=4)

        self.auto_refresh_var = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(
            toolbar,
            text='Auto-refresh',
            variable=self.auto_refresh_var,
            command=self.on_auto_refresh_toggle
        )
        cb.pack(side=tk.LEFT, padx=3)

        self.interval_label = tk.Label(
            toolbar,
            text=f'Interval: {INTERVAL}s',
            bg='#252525',
            fg='#888888',
            font=('Segoe UI', 9)
        )
        self.interval_label.pack(side=tk.RIGHT, padx=10)

        ttk.Button(
            toolbar,
            text='Exit',
            command=self.on_close,
            style='Exit.TButton'
        ).pack(side=tk.RIGHT, padx=3)

        # Вкладки
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        tab_overview = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(tab_overview, text='Overview')
        self.setup_overview_tab(tab_overview)

        tab_graphs = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(tab_graphs, text='History')
        self.setup_graphs_tab(tab_graphs)

        tab_disk = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(tab_disk, text='Disk')
        self.setup_disk_tab(tab_disk)

        # Строка состояния
        self.status_bar = tk.Label(
            self.root,
            text='Ready',
            bg='#141414',
            fg='#777777',
            anchor=tk.W,
            padx=12,
            pady=4,
            font=('Segoe UI', 8)
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def setup_overview_tab(self, parent):
        left = tk.Frame(parent, bg='#1e1e1e')
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        right = tk.Frame(parent, bg='#1e1e1e')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        # Левая колонка
        self.cpu_frame = self.create_metric_card(left, 'CPU', 'cpu')
        self.ram_frame = self.create_metric_card(left, 'RAM', 'ram')
        self.temp_card = self.create_info_card(left, 'Temperature', '-- C')

        # Правая колонка
        self.disk_frame = self.create_metric_card(right, 'Disk /', 'disk')
        self.download_card = self.create_info_card(right, 'Download', '--')
        self.upload_card = self.create_info_card(right, 'Upload', '--')
        self.proc_card = self.create_info_card(right, 'Processes', '--')

    def create_metric_card(self, parent, title, tag):
        card = tk.Frame(parent, bg='#2a2a2a', relief=tk.FLAT, bd=0, padx=1, pady=1)
        card.pack(fill=tk.X, pady=4)

        inner = tk.Frame(card, bg='#252525')
        inner.pack(fill=tk.BOTH)

        header = tk.Frame(inner, bg='#252525')
        header.pack(fill=tk.X, padx=14, pady=(12, 4))

        tk.Label(
            header, text=title,
            font=('Segoe UI', 11, 'bold'),
            bg='#252525', fg='#cccccc'
        ).pack(side=tk.LEFT)

        value_label = tk.Label(
            header, text='0%',
            font=('Segoe UI', 13, 'bold'),
            bg='#252525', fg='#4CAF50'
        )
        value_label.pack(side=tk.RIGHT)

        canvas = tk.Canvas(inner, height=6, bg='#1a1a1a', highlightthickness=0)
        canvas.pack(fill=tk.X, padx=14, pady=(0, 12))

        setattr(self, f'{tag}_canvas', canvas)
        setattr(self, f'{tag}_value_label', value_label)
        return card

    def create_info_card(self, parent, title, default_text):
        card = tk.Frame(parent, bg='#2a2a2a', relief=tk.FLAT, bd=0, padx=1, pady=1)
        card.pack(fill=tk.X, pady=4)

        inner = tk.Frame(card, bg='#252525')
        inner.pack(fill=tk.BOTH)

        tk.Label(
            inner, text=title,
            font=('Segoe UI', 9),
            bg='#252525', fg='#888888',
            anchor=tk.W, padx=14, pady=(10, 0)
        ).pack(fill=tk.X)

        label = tk.Label(
            inner, text=default_text,
            font=('Segoe UI', 14, 'bold'),
            bg='#252525', fg='#e0e0e0',
            anchor=tk.W, padx=14, pady=(0, 10)
        )
        label.pack(fill=tk.X)
        return label

    def setup_graphs_tab(self, parent):
        container = tk.Frame(parent, bg='#1e1e1e')
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        card = tk.Frame(container, bg='#2a2a2a', relief=tk.FLAT, bd=0, padx=1, pady=1)
        card.pack(fill=tk.BOTH, expand=True, pady=4)

        inner = tk.Frame(card, bg='#252525')
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        tk.Label(
            inner, text='CPU History',
            font=('Segoe UI', 10, 'bold'),
            bg='#252525', fg='#cccccc'
        ).pack(anchor=tk.W)

        self.cpu_graph = MiniGraph(inner, width=700, height=80, color='#4CAF50')
        self.cpu_graph.pack(fill=tk.X, pady=(4, 16))

        tk.Label(
            inner, text='RAM History',
            font=('Segoe UI', 10, 'bold'),
            bg='#252525', fg='#cccccc'
        ).pack(anchor=tk.W)

        self.ram_graph = MiniGraph(inner, width=700, height=80, color='#FF9800')
        self.ram_graph.pack(fill=tk.X, pady=4)

    def setup_disk_tab(self, parent):
        container = tk.Frame(parent, bg='#1e1e1e')
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        card = tk.Frame(container, bg='#2a2a2a', relief=tk.FLAT, bd=0, padx=1, pady=1)
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card, bg='#252525')
        inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        tk.Label(
            inner, text='Disk /',
            font=('Segoe UI', 14, 'bold'),
            bg='#252525', fg='#e0e0e0'
        ).pack(pady=(0, 16))

        self.disk_total_label = self.create_info_row(inner, 'Total', '-- GB')
        self.disk_used_label = self.create_info_row(inner, 'Used', '-- GB')
        self.disk_free_label = self.create_info_row(inner, 'Free', '-- GB')

        self.disk_bar = tk.Canvas(inner, height=8, bg='#1a1a1a', highlightthickness=0)
        self.disk_bar.pack(fill=tk.X, pady=(16, 0))

    def create_info_row(self, parent, title, default_text):
        frame = tk.Frame(parent, bg='#252525')
        frame.pack(fill=tk.X, pady=3)

        tk.Label(
            frame, text=title,
            font=('Segoe UI', 10),
            bg='#252525', fg='#888888',
            width=8, anchor=tk.W
        ).pack(side=tk.LEFT)

        label = tk.Label(
            frame, text=default_text,
            font=('Segoe UI', 12, 'bold'),
            bg='#252525', fg='#e0e0e0'
        )
        label.pack(side=tk.LEFT, padx=(10, 0))
        return label

    def update_progress(self, canvas, value, max_width=None):
        canvas.delete('all')
        if max_width is None:
            max_width = canvas.winfo_width()
        if max_width < 4:
            max_width = 300
        fill_width = int((value / 100) * max_width)
        color = get_color(value)
        canvas.create_rectangle(0, 0, fill_width, 6, fill=color, outline='', tags='bar')

    def manual_refresh(self):
        data = self.stats.get_all()
        self.update_display(data)
        self.status_bar.config(text=f'Manual refresh | {datetime.now().strftime("%H:%M:%S")}')

    def on_auto_refresh_toggle(self):
        if self.auto_refresh_var.get():
            self.status_bar.config(text='Auto-refresh resumed')
            self.update_loop()

    def update_display(self, data):
        # CPU
        self.update_progress(self.cpu_canvas, data['cpu'])
        self.cpu_value_label.config(
            text=f'{data["cpu"]:.1f}%',
            fg=get_color(data['cpu'])
        )

        # RAM
        self.update_progress(self.ram_canvas, data['ram_percent'])
        self.ram_value_label.config(
            text=f'{data["ram_percent"]:.1f}%',
            fg=get_color(data['ram_percent'])
        )

        # Disk overview
        self.update_progress(self.disk_canvas, data['disk_percent'])
        self.disk_value_label.config(
            text=f'{data["disk_percent"]:.1f}%',
            fg=get_color(data['disk_percent'])
        )

        # Disk tab
        self.disk_total_label.config(text=f'{data["disk_total_gb"]} GB')
        self.disk_used_label.config(text=f'{data["disk_used_gb"]} GB')
        disk_free = data['disk_total_gb'] - data['disk_used_gb']
        self.disk_free_label.config(text=f'{disk_free:.1f} GB')

        disk_w = self.disk_bar.winfo_width()
        if disk_w > 4:
            fill_w = int((data['disk_percent'] / 100) * disk_w)
            self.disk_bar.delete('all')
            self.disk_bar.create_rectangle(
                0, 0, fill_w, 8,
                fill=get_color(data['disk_percent']),
                outline=''
            )

        # Temperature
        temp_text = f'{data["temp"]} C' if data['temp'] else '-- C'
        self.temp_card.config(text=temp_text)

        # Network
        self.download_card.config(text=format_speed(data['download']))
        self.upload_card.config(text=format_speed(data['upload']))

        # Processes
        self.proc_card.config(text=str(data['processes']))

        # Graphs
        self.cpu_graph.add_value(data['cpu'])
        self.ram_graph.add_value(data['ram_percent'])

    def update_loop(self):
        if self.running and self.auto_refresh_var.get():
            data = self.stats.get_all()
            self.update_display(data)
            self.status_bar.config(
                text=f'Updated: {datetime.now().strftime("%H:%M:%S")} | '
                     f'CPU {data["cpu"]:.0f}% | RAM {data["ram_percent"]:.0f}%'
            )
            self.root.after(int(INTERVAL * 1000), self.update_loop)

    def show_logs(self):
        log_window = tk.Toplevel(self.root)
        log_window.title('System Logs')
        log_window.geometry('650x420')
        log_window.configure(bg='#1e1e1e')
        log_window.minsize(400, 300)

        text = scrolledtext.ScrolledText(
            log_window,
            bg='#141414',
            fg='#aaaaaa',
            font=('Cascadia Code', 10),
            insertbackground='#aaaaaa',
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=12
        )
        text.pack(fill=tk.BOTH, expand=True)

        log_path = config.get('log_file', 'system_log.txt')
        if Path(log_path).exists():
            text.insert(tk.END, Path(log_path).read_text(encoding='utf-8'))
        else:
            text.insert(tk.END, 'Log file not found.')
        text.config(state=tk.DISABLED)

    def show_about(self):
        messagebox.showinfo(
            'About',
            'Linux System Monitor\n'
            'Version 3.0\n\n'
            'Real-time Linux resource monitoring.\n'
            'CPU, RAM, Disk, Network, Temperature.\n\n'
            'Authors: Liva, Nastya, Maxim\n'
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
