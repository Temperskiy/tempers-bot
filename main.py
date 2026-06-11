import discord
import os
import json
import re
import sys
from discord.ext import commands, tasks
from mcstatus import JavaServer
from flask import Flask
from threading import Thread

# --- НАСТРОЙКА ВЕБ-СЕРВЕРА ДЛЯ РЕЖИМА 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "Бот активен и работает 24/7!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- НАСТРОЙКА БОТА ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ADDRESS = "TempersSMP-nd4T.aternos.me:58427"
DATA_FILE = "kills_stats.json"

MINECRAFT_CHAT_CHANNEL_ID = 1514273059173961808  
LEADERBOARD_CHANNEL_ID = 1514272743795724340     

KILL_PATTERN = re.compile(r"([\w_]+) was slain by ([\w_]+)")

def load_stats():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ЛОГ] Ошибка чтения БД: {e}")
            return {}
    return {}

def save_stats(stats):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[ЛОГ] Ошибка сохранения БД: {e}")

kills_db = load_stats()

@bot.event
async def on_ready():
    print(f'Бот {bot.user} успешно запущен в Discord!')
    try:
        check_server.start()
        update_leaderboard_job.start()
    except Exception as e:
        print(f"[ЛОГ] Ошибка запуска задач: {e}")

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

    await bot.process_commands(message)

@tasks.loop(minutes=5.0)
async def update_leaderboard_job():
    try:
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
    except Exception as e:
        print(f"[ЛОГ] Ошибка топа: {e}")

# --- КОМАНДЫ БОТА ---

@bot.command()
async def on(ctx):
    """Инструкция по быстрому включению сервера"""
    try:
        server_dns = JavaServer.lookup(SERVER_ADDRESS)
        server_dns.status()
        await ctx.send("🟢 **Сервер уже запущен и работает!** Заходи играть.")
        return
    except:
        pass

    instructions = """
⏳ **Сервер сейчас выключен!** 
Вы можете включить его самостоятельно за 10 секунд:

1️⃣ Перейдите на сайт: https://aternos.org/server/
2️⃣ Нажмите зеленую кнопку **«Запустить»**.

💡 *Если у вас нет кнопки запуска, напишите админу сервера — он выдаст вашему Атернос-аккаунту доступ для включения (без доступа к файлам и консоли)!*
"""
    await ctx.send(instructions)

@bot.command()
async def players(ctx):
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
• `!on` — как включить сервер (если он оффлайн) 🚀
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

@tasks.loop(minutes=1.0)
async def check_server():
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        await bot.change_presence(activity=discord.Game(f"Онлайн: {status.players.online}"))
    except:
        await bot.change_presence(activity=discord.Game("Сервер оффлайн"))

if __name__ == "__main__":
    if not TOKEN:
        print("[ОШИБКА] DISCORD_TOKEN отсутствует в настройках!")
        sys.exit(1)
        
    keep_alive()
    try:
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("[ОШИБКА] Токен бота недействительный!")
        sys.exit(1)
    except Exception as e:
        print(f"[ОШИБКА] Сбой bot.run: {e}")
        sys.exit(1)
        
