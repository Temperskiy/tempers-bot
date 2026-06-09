import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer

# --- НАСТРОЙКИ ---
# Вставь сюда свой токен бота
TOKEN = 'MTUxMzkzODkzMTAzNTU0MTcyNg.Gxy5G_.v9R-u4d4T0spcij-23HBz4bwgJcSef3xmOJMHs'
# Адрес твоего сервера
SERVER_ADDRESS = 'TempersSMP-nd4T.aternos.me:58427'
# Вставь сюда ID канала (только цифры)
CHANNEL_ID = 1505160265325482034 
# -----------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

was_online = False

@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен!')
    # Запускаем цикл проверки
    if not check_server.is_running():
        check_server.start()

@tasks.loop(minutes=1.0)
async def check_server():
    global was_online
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        server.status() # Проверка связи
        is_online = True
    except:
        is_online = False

    # Уведомление об изменении статуса
    if is_online != was_online:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            if is_online:
                await channel.send("🚀 Сервер TempersSMP запущен и доступен для игры!")
            else:
                await channel.send("🔌 Сервер TempersSMP выключен.")
            
    was_online = is_online

@bot.command()
async def status(ctx):
    try:
        server = JavaServer.lookup(SERVER_ADDRESS)
        status = server.status()
        embed = discord.Embed(title="📊 Статус TempersSMP", color=discord.Color.green())
        embed.add_field(name="Состояние", value="Онлайн ✅", inline=False)
        embed.add_field(name="Игроки", value=f"{status.players.online}/{status.players.max}", inline=True)
        embed.add_field(name="Пинг", value=f"{status.latency:.0f} мс", inline=True)
        embed.add_field(name="Версия", value=status.version.name, inline=False)
        await ctx.send(embed=embed)
    except:
        await ctx.send("❌ Сервер TempersSMP сейчас офлайн или недоступен.")

# Запуск бота
bot.run(TOKEN)
