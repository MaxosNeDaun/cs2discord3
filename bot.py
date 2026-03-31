import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os

TOKEN = os.getenv("TOKEN")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 1127290770571931739)) # Убедитесь, что ID верный
SERVER_IP = ("194.93.2.207", 27077)

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# Переменная для хранения ID сообщения, чтобы бот не «забывал» его при перезапуске
status_msg_id = None

async def get_server_info():
    try:
        # Устанавливаем таймаут, чтобы бот не зависал, если сервер CS2 лежит
        info = await asyncio.wait_for(asyncio.to_thread(a2s.info, SERVER_IP), timeout=5.0)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        
        # Ограничиваем список игроков, чтобы не превысить лимит символов Discord Embed
        player_names = [p.name if p.name else "Игрок" for p in players]
        player_list = "\n".join(player_names[:20]) if player_names else "Пусто"
        if len(player_names) > 20:
            player_list += f"\n...и еще {len(player_names) - 20}"

        embed = discord.Embed(title="📊 Статус сервера CS2", color=discord.Color.green())
        embed.add_field(name="IP Адрес", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Карта", value=info.map_name, inline=True)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Список игроков", value=f"```\n{player_list}\n```", inline=False)
        return embed

    except Exception as e:
        print(f"Ошибка сервера: {e}")
        embed = discord.Embed(title="🔴 Сервер оффлайн", color=discord.Color.red())
        embed.add_field(name="IP:Port", value=f"{SERVER_IP[0]}:{SERVER_IP[1]}")
        return embed

@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    global status_msg_id
    try:
        # Используем fetch_channel вместо get_channel
        channel = await bot.fetch_channel(CHANNEL_ID)
        embed = await get_server_info()

        if status_msg_id is None:
            msg = await channel.send(embed=embed)
            status_msg_id = msg.id
        else:
            msg = await channel.fetch_message(status_msg_id)
            await msg.edit(embed=embed)
    except Exception as e:
        print(f"Ошибка в цикле обновления: {e}")
        # Если сообщение было удалено вручную, сбрасываем ID, чтобы создать новое
        status_msg_id = None

@bot.event
async def on_ready():
    print(f"✅ Бот {bot.user} успешно запущен!")
    if not update_status_message.is_running():
        update_status_message.start()

@bot.command()
async def test(ctx):
    await ctx.send("Бот работает и видит команды!")

@bot.command()
async def status(ctx):
    await ctx.send(embed=await get_server_info())

bot.run(TOKEN)
