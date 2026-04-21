import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os
import time

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1482982357882507436  
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
        # Получаем данные через a2s (в отдельном потоке, чтобы не вешать бота)
        info = await asyncio.to_thread(a2s.info, SERVER_IP)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        
        # Формируем список игроков
        names_list = [p.name for p in players if p.name.strip()]
        player_names = "\n".join(names_list) or "На сервере пусто"
        
        # Защита от слишком длинного списка (лимит Embed Field - 1024 символа)
        if len(player_names) > 1000:
            player_names = player_names[:997] + "..."

        # Создаем Embed
        embed = discord.Embed(
            title="📊 Статус сервера CS2", 
            color=discord.Color.green(),
            # Используем реальное время Unix
            description=f"Последнее обновление: <t:{int(time.time())}:R>"
        )
        embed.add_field(name="IP Адрес", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Игроки", value=f"👥 {info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Карта", value=f"🗺️ {info.map_name}", inline=True)
        embed.add_field(name="Список игроков:", value=f"```\n{player_names}\n```", inline=False)
        
        # Поиск и редактирование сообщения
        status_msg = None
        async for msg in channel.history(limit=5):
            if msg.author == bot.user and msg.embeds and "Статус сервера CS2" in msg.embeds[0].title:
                status_msg = msg
                break
        
        if status_msg: 
            await status_msg.edit(embed=embed)
        else: 
            await channel.send(embed=embed)

        # Статус бота
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
