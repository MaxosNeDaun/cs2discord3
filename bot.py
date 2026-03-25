import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os

# Получаем токен из environment (Shared Variables на Railway)
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("TOKEN не найден! Добавьте его в Shared Variables на Railway.")

# Можно сделать интервал обновления настраиваемым через переменную
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))  # по умолчанию 60 секунд

# ID канала Discord для сообщений
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 1127290770571931739))

# IP и порт сервера CS2
SERVER_IP = ("194.93.2.207", 27077)

# Настройка intents
intents = discord.Intents.default()
intents.message_content = True  # Нужно, если используешь команды
bot = commands.Bot(command_prefix="!", intents=intents)

# Функция получения информации с сервера
async def get_server_info():
    try:
        info = await asyncio.to_thread(a2s.info, SERVER_IP)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        player_list = "\n".join([p.name for p in players]) if players else "Пусто"

        embed = discord.Embed(
            title="Статус сервера",
            color=discord.Color.green()
        )
        embed.add_field(name="🟢 В сети", value=f"{SERVER_IP[0]}:{SERVER_IP[1]}", inline=False)
        embed.add_field(name="Карта", value=info.map_name, inline=True)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Список игроков", value=player_list, inline=False)
        return embed

    except Exception as e:
        print("Ошибка при запросе сервера:", e)
        embed = discord.Embed(title="🔴 Сервер оффлайн", color=discord.Color.red())
        embed.add_field(name="IP:Port", value=f"{SERVER_IP[0]}:{SERVER_IP[1]}", inline=True)
        return embed

# Задача для автообновления статуса
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Канал не найден!")
        return

    if not hasattr(bot, "status_message") or bot.status_message is None:
        bot.status_message = await channel.send(embed=await get_server_info())
    else:
        await bot.status_message.edit(embed=await get_server_info())

# Команда для ручного запроса статуса
@bot.command()
async def status(ctx):
    await ctx.send(embed=await get_server_info())

# Событие при запуске бота
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    update_status_message.start()

# Запуск бота
bot.run(TOKEN)
