#!/usr/bin/env python3
"""
Linux System Monitor — SysMon v2.0.
Консольный (Rich), графический (Tkinter) и демон-режим.
Авторы: Лива, Настя, Максим
"""

import psutil
import time
import sys
import argparse
import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich import box

try:
    import tkinter as tk
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

# --------------------------- Конфигурация ---------------------------
DEFAULT_CONFIG = {
    'thresholds': {'low': 50, 'medium': 80},
    'interval': 1.0,
    'history_size': 20,
    'log_file': 'system_log.txt',
    'log_max_entries': 1000,
}

def load_config(config_path='config.yaml'):
    if Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return DEFAULT_CONFIG

# --------------------------- Сбор метрик ---------------------------
class SystemStats:
    def __init__(self, history_size=20):
        self.history_size = history_size
        self.cpu_history = deque(maxlen=history_size)
        self.ram_history = deque(maxlen=history_size)
        psutil.cpu_percent(interval=None)

    def get_cpu(self):
        cpu = psutil.cpu_percent(interval=None)
        self.cpu_history.append(cpu)
        return cpu

    def get_ram(self):
        ram = psutil.virtual_memory()
        self.ram_history.append(ram.percent)
        return ram

    def get_disk(self):
        return psutil.disk_usage('/').percent

    def get_network(self):
        net = psutil.net_io_counters()
        return net.bytes_sent, net.bytes_recv

    def get_temperature(self):
        temps = psutil.sensors_temperatures()
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        return None

    def get_process_count(self):
        return len(psutil.pids())

# --------------------------- Логирование ---------------------------
def setup_logger(log_file, max_entries):
    logger = logging.getLogger('SysMon')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        log_file, maxBytes=max_entries * 100, backupCount=1, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s'))
    logger.addHandler(handler)
    return logger

# --------------------------- Цвета ---------------------------
def color_for_value(value, thresholds):
    if value < thresholds['low']:
        return 'green'
    elif value < thresholds['medium']:
        return 'yellow'
    else:
        return 'red'

# --------------------------- Rich-интерфейс ---------------------------
def build_layout(stats):
    cpu = stats.get_cpu()
    ram = stats.get_ram()
    disk = stats.get_disk()
    net_sent, net_recv = stats.get_network()
    temp = stats.get_temperature()
    procs = stats.get_process_count()
    thresholds = load_config().get('thresholds', DEFAULT_CONFIG['thresholds'])

    def make_bar(value):
        length = 20
        filled = int(value / 100 * length)
        return '█' * filled + '░' * (length - filled)

    cpu_history_bar = ' '.join([make_bar(v) for v in stats.cpu_history])
    ram_history_bar = ' '.join([make_bar(v) for v in stats.ram_history])

    cpu_panel = Panel(
        f'[bold {color_for_value(cpu, thresholds)}]{cpu}%[/]\nПроцессов: {procs}'
        + (f'\nТемпература: {temp}°C' if temp else ''),
        title='[bold cyan]CPU[/]', border_style='cyan', box=box.ROUNDED
    )

    ram_panel = Panel(
        f'[bold {color_for_value(ram.percent, thresholds)}]{ram.percent}%[/]\n'
        f'Занято: {ram.used // (1024**2)} / {ram.total // (1024**2)} MB',
        title='[bold magenta]RAM[/]', border_style='magenta', box=box.ROUNDED
    )

    disk_panel = Panel(
        f'[bold {color_for_value(disk, thresholds)}]{disk}%[/]',
        title='[bold yellow]DISK /[/]', border_style='yellow', box=box.ROUNDED
    )

    net_panel = Panel(
        f'↓ {net_recv // 1024} KB\n↑ {net_sent // 1024} KB',
        title='[bold green]NETWORK[/]', border_style='green', box=box.ROUNDED
    )

    history_panel = Panel(
        f'[cyan]CPU[/]: {cpu_history_bar}\n[magenta]RAM[/]: {ram_history_bar}',
        title='[bold]История[/]', border_style='white', box=box.ROUNDED
    )

    layout = Layout()
    layout.split_column(
        Layout(name='top', size=8),
        Layout(name='bottom')
    )
    layout['top'].split_row(
        Layout(cpu_panel, name='cpu'),
        Layout(ram_panel, name='ram'),
        Layout(disk_panel, name='disk'),
        Layout(net_panel, name='net')
    )
    layout['bottom'].update(history_panel)
    return layout

def run_cli(config):
    stats = SystemStats(config['history_size'])
    logger = setup_logger(config['log_file'], config['log_max_entries'])
    console = Console()

    with Live(console=console, refresh_per_second=1 / config['interval'], screen=True) as live:
        while True:
            try:
                cpu = stats.get_cpu()
                ram = stats.get_ram()
                disk = stats.get_disk()
                temp = stats.get_temperature()
                procs = stats.get_process_count()

                logger.info(
                    f'CPU:{cpu}% RAM:{ram.percent}% DISK:{disk}% '
                    f'PROCS:{procs} TEMP:{temp}'
                )

                layout = build_layout(stats)
                live.update(layout)
                time.sleep(config['interval'])
            except KeyboardInterrupt:
                console.print('\n[bold]Выход...[/]')
                break

# --------------------------- Режим демона (только логирование) ---------------------------
def run_daemon(config):
    stats = SystemStats(config['history_size'])
    logger = setup_logger(config['log_file'], config['log_max_entries'])
    print(f"Демон запущен. Лог: {config['log_file']} (Ctrl+C для остановки)")
    try:
        while True:
            cpu = stats.get_cpu()
            ram = stats.get_ram()
            disk = stats.get_disk()
            temp = stats.get_temperature()
            procs = stats.get_process_count()
            logger.info(
                f'CPU:{cpu}% RAM:{ram.percent}% DISK:{disk}% '
                f'PROCS:{procs} TEMP:{temp}'
            )
            time.sleep(config['interval'])
    except KeyboardInterrupt:
        print("Демон остановлен.")

# --------------------------- GUI ---------------------------
def gui_color(value, thresholds):
    if value < thresholds['low']:
        return 'green'
    elif value < thresholds['medium']:
        return 'orange'
    else:
        return 'red'

def run_gui(config):
    if not GUI_AVAILABLE:
        print('Ошибка: Tkinter не установлен. Установите python3-tk.')
        sys.exit(1)

    stats = SystemStats(config['history_size'])
    thresholds = config.get('thresholds', DEFAULT_CONFIG['thresholds'])

    root = tk.Tk()
    root.title('Linux System Monitor')
    root.geometry('400x320')
    root.resizable(False, False)

    tk.Label(root, text='LINUX SYSTEM MONITOR', font=('Arial', 16, 'bold')).pack(pady=10)

    cpu_label = tk.Label(root, text='CPU: 0%', font=('Arial', 14))
    cpu_label.pack(pady=5)

    ram_label = tk.Label(root, text='RAM: 0%', font=('Arial', 14))
    ram_label.pack(pady=5)

    disk_label = tk.Label(root, text='DISK: 0%', font=('Arial', 14))
    disk_label.pack(pady=5)

    net_label = tk.Label(root, text='NET: 0 KB', font=('Arial', 14))
    net_label.pack(pady=5)

    temp_label = tk.Label(root, text='TEMP: -- °C', font=('Arial', 14))
    temp_label.pack(pady=5)

    psutil.cpu_percent(interval=None)

    def update():
        cpu = stats.get_cpu()
        ram = stats.get_ram()
        disk = stats.get_disk()
        net = psutil.net_io_counters()
        temp = stats.get_temperature()

        cpu_label.config(text=f'CPU: {cpu}%', fg=gui_color(cpu, thresholds))
        ram_label.config(text=f'RAM: {ram.percent}%', fg=gui_color(ram.percent, thresholds))
        disk_label.config(text=f'DISK: {disk}%', fg=gui_color(disk, thresholds))
        net_label.config(
            text=f'NET: ↓{net.bytes_recv//1024} ↑{net.bytes_sent//1024} KB',
            fg='blue'
        )
        temp_label.config(
            text=f'TEMP: {temp}°C' if temp else 'TEMP: -- °C',
            fg='darkred' if temp and temp > 70 else 'black'
        )
        root.after(int(config['interval'] * 1000), update)

    update()
    root.mainloop()

# --------------------------- Точка входа ---------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Linux System Monitor — мониторинг ресурсов Linux'
    )
    parser.add_argument('--mode', choices=['cli', 'gui', 'daemon'], default='cli',
                        help='Режим: cli (консоль), gui (графика), daemon (фоновый лог)')
    parser.add_argument('--interval', type=float, default=None,
                        help='Интервал обновления в секундах')
    parser.add_argument('--config', default='config.yaml',
                        help='Путь к конфигурационному файлу')
    parser.add_argument('--log', action='store_true',
                        help='Показать лог и выйти')
    parser.add_argument('--version', action='version', version='SysMon 2.0')
    args = parser.parse_args()

    config = load_config(args.config)
    if args.interval is not None:
        config['interval'] = args.interval

    if args.log:
        log_path = config.get('log_file', 'system_log.txt')
        if Path(log_path).exists():
            print(Path(log_path).read_text(encoding='utf-8'))
        else:
            print('Лог-файл отсутствует.')
        return

    if args.mode == 'cli':
        run_cli(config)
    elif args.mode == 'gui':
        run_gui(config)
    elif args.mode == 'daemon':
        run_daemon(config)

if __name__ == '__main__':
    main()