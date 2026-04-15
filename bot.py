import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1482982357882507436  # Убедись, что ID верный
UPDATE_INTERVAL = 30
SERVER_IP = ("194.93.2.207", 27077)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- МОНИТОРИНГ CS2 ---
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: 
        return
    
    try:
        # Получаем данные от сервера через A2S
        info = await asyncio.to_thread(a2s.info, SERVER_IP)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        
        # Формируем список игроков
        player_names = "\n".join([p.name for p in players if p.name.strip()]) or "На сервере пусто"
        
        # Создаем Embed
        embed = discord.Embed(
            title="📊 Статус сервера CS2", 
            color=discord.Color.green(),
            description=f"Последнее обновление: <t:{int(asyncio.get_event_loop().time())}:R>"
        )
        embed.add_field(name="IP Адрес", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Карта", value=f"{info.map_name}", inline=True)
        embed.add_field(name="Список игроков:", value=f"```\n{player_names}\n```", inline=False)
        
        # Ищем старое сообщение бота, чтобы обновить его, а не спамить новыми
        status_msg = None
        async for msg in channel.history(limit=10):
            if msg.author == bot.user and msg.embeds and "Статус сервера CS2" in msg.embeds[0].title:
                status_msg = msg
                break
        
        if status_msg: 
            await status_msg.edit(embed=embed)
        else: 
            await channel.send(embed=embed)

        # Обновляем статус бота (Activity)
        await bot.change_presence(
            activity=discord.Game(name=f"{info.player_count}/{info.max_players} на {info.map_name}")
        )
    except Exception as e:
        print(f"Ошибка при обновлении статуса: {e}")

@bot.event
async def on_ready():
    print(f"✅ Бот-мониторинг онлайн: {bot.user}")
    if not update_status_message.is_running():
        update_status_message.start()

bot.run(TOKEN)
