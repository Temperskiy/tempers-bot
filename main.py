import discord
import os
from discord.ext import commands, tasks
from mcstatus import JavaServer

# Настройка бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


# Твой токен из настроек Render
TOKEN = os.getenv('DISCORD_TOKEN')

# Укажи здесь IP своего сервера
SERVER_ADDRESS = "TempersSMP-nd4T.aternos.me:58427"

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')
    check_server.start()

# --- КОМАНДЫ ---

@bot.command()
async def ip(ctx):
    await ctx.send(f"IP нашего сервера: `{SERVER_ADDRESS}`")

@bot.command()
async def info(ctx):
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        await ctx.send(f"Сервер онлайн! Игроков: {status.players.online}/{status.players.max}")
    except:
        await ctx.send("Сервер сейчас недоступен.")

@bot.command()
async def help(ctx):
    help_text = """
**Доступные команды:**
!ip — показать IP сервера
!info — узнать текущий статус и количество игроков
!help — этот список команд
"""
    await ctx.send(help_text)

# --- АВТО-ОБНОВЛЕНИЕ СТАТУСА ---

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
    
