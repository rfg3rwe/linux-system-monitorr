<p align="center">
  <img src="https://img.shields.io/badge/platform-Linux-blue" alt="Платформа"/>
  <img src="https://img.shields.io/badge/python-3.8%2B-green" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="Лицензия"/>
  <img src="https://img.shields.io/badge/version-2.0-orange" alt="Версия"/>
</p>

<h1 align="center">🐧 Linux System Monitor</h1>

<p align="center">
  <b>SysMon</b> – стильный консольный и графический монитор ресурсов Linux<br>
  Отображает загрузку CPU, память, диск, сеть, температуру и ведёт журнал.
</p>

---

## 📦 Возможности

- **CPU** – загрузка (%), температура, количество процессов
- **RAM** – использование (%), занято / всего
- **Диск** – заполнение корневого раздела
- **Сеть** – отправленный и принятый трафик
- **Логирование** – запись метрик в файл с автоматической ротацией
- **Графики истории** – цветные прогресс-бары за последние N секунд
- **Цветовые пороги** – зелёный / жёлтый / красный, настраиваются в `config.yaml`
- **Три режима** – консольный (Rich), графический (Tkinter) и демон (фоновый лог)

---

## 🛠 Установка и запуск

```bash
git clone https://github.com/rfg3rwe/linux-system-monitorr.git
cd linux-system-monitorr
sudo apt update
sudo apt install python3-pip python3-tk
pip install -r requirements.txt
python3 monitor.py
