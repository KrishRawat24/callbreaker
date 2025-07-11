import threading
import subprocess
import os

def run_dashboard():
    subprocess.run(["python3", "dashboard.py"])

def run_bot():
    subprocess.run(["python3", "bot.py"])

dashboard_thread = threading.Thread(target=run_dashboard)
bot_thread = threading.Thread(target=run_bot)

dashboard_thread.start()
bot_thread.start()

dashboard_thread.join()
bot_thread.join()
