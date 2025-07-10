import threading
import dashboard
import bot

if __name__ == '__main__':
    threading.Thread(target=lambda: dashboard.app.run(debug=True, port=8080)).start()
    bot.bot.run(os.getenv("DISCORD_BOT_TOKEN"))
