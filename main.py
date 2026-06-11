import discord
import os
import json
import re
from discord.ext import commands, tasks
from mcstatus import JavaServer
from flask import Flask
from threading import Thread
from python_aternos import Client

# --- НАСТРОЙКА ВЕБ-СЕРВЕРА ДЛЯ РЕЖИМА 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "Бот активен и работает 24/7! Подключите этот URL к cron-job.org."

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- НАСТРОЙКА БОТА ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Переменные окружения и настройки сервера
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ADDRESS = "TempersSMP-nd4T.aternos.me:58427"
DATA_FILE = "kills_stats.json"

# === ВАЖНО: ЗАМЕНИ ЭТИ ID НА СВОИ ЦИФРАМИ ===
MINECRAFT_CHAT_CHANNEL_ID = 123456789012345678  # ID канала, куда DiscordSRV пишет чат и смерти
LEADERBOARD_CHANNEL_ID = 876543210987654321     # ID канала, где бот будет автоматически обновлять топ

# Шаблон для поиска убийств из DiscordSRV на английском языке
KILL_PATTERN = re.compile(r"([\w_]+) was slain by ([\w_]+)")

# --- РАБОТА С БАЗОЙ ДАННЫХ (JSON) ---
def load_stats():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_stats(stats):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=4)

kills_db = load_stats()

@bot.event
async def on_ready():
    print(f'Бот {bot.user} успешно запущен!')
    check_server.start()
    update_leaderboard_job.start()

# --- АВТОМАТИЧЕСКИЙ ПЕРЕХВАТ КИЛЛОВ ИЗ DISCORDSRV ---
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id == MINECRAFT_CHAT_CHANNEL_ID:
        content = message.content
        if message.embeds:
            for embed in message.embeds:
                if embed.description:
                    content += " " + embed.description

        match = KILL_PATTERN.search(content)
        if match:
            victim, attacker = match.groups()
            kills_db[attacker] = kills_db.get(attacker, 0) + 1
            save_stats(kills_db)
            print(f"[Килл] {attacker} уничтожил {victim}. Всего: {kills_db[attacker]}")

    await bot.process_commands(message)

# --- АВТО-ОБНОВЛЕНИЕ ТАБЛИЦЫ ЛИДЕРОВ РАЗ В 5 МИНУТ ---
@tasks.loop(minutes=5.0)
async def update_leaderboard_job():
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    if not kills_db:
        leaderboard_text = "🏆 **Топ убийц сервера:**\nПока никто никого не убил."
    else:
        sorted_kills = sorted(kills_db.items(), key=lambda x: x[1], reverse=True)
        leaderboard_text = "🏆 **Официальный топ убийц сервера:**\n"
        for place, (player, count) in enumerate(sorted_kills, 1):
            leaderboard_text += f"{place}. `{player}` — **{count}** ⚔️\n"

    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.edit(content=leaderboard_text)
            return
            
    await channel.send(leaderboard_text)

# --- КОМАНДЫ БОТА ---

@bot.command()
async def on(ctx):
    """Включает сервер через твинк-аккаунт Атерноса"""
    await ctx.send("🔍 Проверяю текущий статус сервера...")
    
    try:
        server_dns = JavaServer.lookup(SERVER_ADDRESS)
        server_dns.status()
        await ctx.send("🟢 Сервер уже работает! Можешь заходить.")
        return
    except:
        pass

    await ctx.send("⏳ Подключаюсь к панели Aternos, подожди...")

    at_user = os.getenv('ATERNOS_USER')
    at_pass = os.getenv('ATERNOS_PASSWORD')

    if not at_user or not at_pass:
        await ctx.send("❌ Ошибка: В настройках Render не указаны ATERNOS_USER или ATERNOS_PASSWORD.")
        return

    try:
        aternos = Client.from_credentials(at_user, at_pass)
        servers = aternos.list_servers()
        
        if not servers:
            await ctx.send("❌ Не удалось найти сервер. Проверь права доступа для твинка.")
            return
            
        my_server = servers[0]
        status_code = my_server.status_num
        
        if status_code == 1:
            await ctx.send("🟢 Сервер уже запущен!")
        elif status_code in [2, 3, 4]:
            await ctx.send("⏳ Сервер уже включается. Заходи через пару минут!")
        elif status_code == 6:
            await ctx.send("⏳ Сервер стоит в очереди на запуск.")
        else:
            my_server.start()
            await ctx.send("🚀 Команда отправлена! Сервер запускается. Подожди 2-3 минуты.")
            
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        await ctx.send("❌ Не удалось запустить сервер. Возможно, Атернос обновил защиту.")

@bot.command()
async def players(ctx):
    """Показывает ники игроков онлайн"""
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        if status.players.sample:
            names = [player.name for player in status.players.sample]
            players_list = ", ".join(f"`{name}`" for name in names)
            await ctx.send(f"👥 **Сейчас на сервере ({status.players.online}/{status.players.max}):**\n{players_list}")
        else:
            await ctx.send("На сервере сейчас никого нет. Заходи! 🎮")
    except:
        await ctx.send("❌ Не удалось связаться с сервером. Возможно, он сейчас выключен.")

@bot.command()
async def top(ctx):
    """Показывает таблицу лидеров по запросу"""
    if not kills_db:
        await ctx.send("🏆 Таблица лидеров пока пуста.")
        return
    sorted_kills = sorted(kills_db.items(), key=lambda x: x[1], reverse=True)
    leaderboard = "**🏆 Топ игроков по киллам:**\n"
    for place, (player, kills) in enumerate(sorted_kills, 1):
        leaderboard += f"{place}. `{player}` — {kills} ⚔️\n"
    await ctx.send(leaderboard)

@bot.command()
async def eventrules(ctx):
    """Показывает правила текущего ивента"""
    rules_text = """
📜 **ПРАВИЛА ИВЕНТА** 📜
——————————————————
1️⃣ **Не набивать киллы** (запрещено просить друзей умирать ради статистики).
2️⃣ **Не создавать твинк-аккаунты** (играть можно только с одного основного аккаунта).
3️⃣ **Читы запрещены** (любые софты, чит-клиенты — бан).
——————————————————
*За нарушение любого из правил — дисквалификация с ивента и бан! Играйте честно.* 😊
"""
    await ctx.send(rules_text)

@bot.command()
async def github(ctx):
    """Выводит ссылку на GitHub разработчика"""
    await ctx.send("Бот в открытом доступе на github (by.temperskiy)")

@bot.command()
async def ip(ctx):
    await ctx.send(f"📍 IP нашего сервера: `{SERVER_ADDRESS}`")

@bot.command()
async def info(ctx):
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        await ctx.send(f"🟢 Сервер онлайн! Игроков: **{status.players.online}/{status.players.max}**")
    except:
        await ctx.send("🔴 Сервер сейчас оффлайн.")

@bot.command()
async def help(ctx):
    help_text = """
**Доступные команды:**
• `!on` — включить сервер (если он оффлайн) 🚀
• `!ip` — показать IP сервера
• `!info` — статус сервера и количество игроков
• `!players` — ники тех, кто сейчас играет онлайн
• `!top` — показать таблицу лидеров по киллам
• `!eventrules` — узнать правила текущего ивента 📜
• `!github` — исходный код бота 🛠️
• `!help` — это меню команд

---
📢 *Здесь могла быть ваша реклама! По вопросам размещения пишите админу сервера.*
"""
    await ctx.send(help_text)

# --- АВТО-ОБНОВЛЕНИЕ СТАТУСА БОТА (СТАТУС ИГРЫ) ---
@tasks.loop(minutes=1.0)
async def check_server():
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        await bot.change_presence(activity=discord.Game(f"Онлайн: {status.players.online}"))
    except:
        await bot.change_presence(activity=discord.Game("Сервер оффлайн"))

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
        
