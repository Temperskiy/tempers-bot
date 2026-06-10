import discord
import os
import json
import re
from discord.ext import commands, tasks
from mcstatus import JavaServer

# Настройка бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Основные настройки
TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ADDRESS = "TempersSMP-nd4T.aternos.me:58427"
DATA_FILE = "kills_stats.json"

# --- НАСТРОЙКА КАНАЛОВ (Вставь свои ID цифрами) ---
MINECRAFT_CHAT_CHANNEL_ID = 1514273059173961808  # Канал, куда DiscordSRV пишет логи игры
LEADERBOARD_CHANNEL_ID = 1514272743795724340     # Канал, где бот будет вешать топ

# Регулярное выражение для отслеживания убийств в английском Майнкрафте
# Пример: "Player1 was slain by Player2"
KILL_PATTERN = re.compile(r"([\w_]+) was slain by ([\w_]+)")

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
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

# --- ПАРСИНГ ЛОГОВ DISCORDSRV ---
@bot.event
async def on_message(message):
    # Игнорируем сообщения от самого себя
    if message.author == bot.user:
        return

    # Проверяем, что сообщение пришло из канала с чатом Майнкрафта
    if message.channel.id == MINECRAFT_CHAT_CHANNEL_ID:
        content = message.content
        
        # Если DiscordSRV отправляет эмбеды (красивые карточки), проверяем их текст
        if message.embeds:
            for embed in message.embeds:
                if embed.description:
                    content += " " + embed.description

        # Ищем совпадение по тексту убийства
        match = KILL_PATTERN.search(content)
        if match:
            victim, attacker = match.groups()
            
            # Начисляем килл убийце
            kills_db[attacker] = kills_db.get(attacker, 0) + 1
            save_stats(kills_db)
            print(f"[Килл зафиксирован] {attacker} убил {victim}")

    # Не забываем обрабатывать команды бота
    await bot.process_commands(message)

# --- АВТО-ОБНОВЛЕНИЕ ТАБЛИЦЫ ЛИДЕРОВ ---
@tasks.loop(minutes=5.0)
async def update_leaderboard_job():
    """Раз в 5 минут обновляет сообщение с топом в специальном канале"""
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

    # Ищем последнее сообщение бота в этом канале, чтобы отредактировать его, а не спамить новыми
    async for msg in channel.history(limit=10):
        if msg.author == bot.user:
            await msg.edit(content=leaderboard_text)
            return
            
    # Если сообщений бота нет, пишем новое
    await channel.send(leaderboard_text)

# --- КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ---

@bot.command()
async def players(ctx):
    """Показывает ники игроков, которые СЕЙЧАС в сети"""
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
        await ctx.send("❌ Не удалось связаться с сервером. Возможно, он выключен.")

@bot.command()
async def top(ctx):
    """Показать топ игроков по команде вручную"""
    if not kills_db:
        await ctx.send("🏆 Список убийц пока пуст.")
        return
    
    sorted_kills = sorted(kills_db.items(), key=lambda x: x[1], reverse=True)
    leaderboard = "**🏆 Топ игроков по киллам:**\n"
    for place, (player, kills) in enumerate(sorted_kills, 1):
        leaderboard += f"{place}. `{player}` — {kills} ⚔️\n"
    await ctx.send(leaderboard)

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
• `!ip` — показать IP сервера
• `!info` — статус сервера и количество игроков
• `!players` — ники тех, кто сейчас играет онлайн
• `!top` — показать таблицу лидеров по киллам
• `!help` — это меню команд
"""
    await ctx.send(help_text)

# --- АВТО-ОБНОВЛЕНИЕ СТАТУСА БОТА ---
@tasks.loop(minutes=1.0)
async def check_server():
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        await bot.change_presence(activity=discord.Game(f"Онлайн: {status.players.online}"))
    except:
        await bot.change_presence(activity=discord.Game("Сервер оффлайн"))

if __name__ == "__main__":
    bot.run(TOKEN)
