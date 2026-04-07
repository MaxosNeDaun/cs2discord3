import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os
import sqlite3

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN")
# ID канала для статуса и регистраций
CHANNEL_ID = 1482982357882507436 
# Интервал обновления статуса (в секундах)
UPDATE_INTERVAL = 60
# IP и Port твоего сервера
SERVER_IP = ("194.93.2.207", 27077)

# Путь к базе данных (для Railway Volume)
DB_PATH = "/app/data/registration.db" if os.path.exists("/app/data") else "registration.db"

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    if "/" in DB_PATH:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS participants 
                      (message_id TEXT, user_name TEXT, PRIMARY KEY (message_id, user_name))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS message_settings 
                      (message_id TEXT PRIMARY KEY, description TEXT, image_url TEXT)''')
    conn.commit()
    conn.close()

def fix_missing_participants(msg_id):
    """Добавление твоего списка игроков в базу"""
    participants = [
        "!hiro", "Et1cZ", "Ferlisia", "JDH", "KFC bo$$", "POPIROS", 
        "SKOP", "^_TynGla_^", "an1mesten", "darbojiy", "dinobombino", 
        "noemoti", "onivey", "the owner", "Джек вора бей", "Садик", 
        "гадёныш", "леквимоле", "лох", "мега найт"
    ]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for name in participants:
        try:
            cursor.execute("INSERT OR IGNORE INTO participants VALUES (?, ?)", (str(msg_id), name))
        except: pass
    conn.commit()
    conn.close()

def save_msg_settings(msg_id, desc, img):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO message_settings VALUES (?, ?, ?)", (str(msg_id), desc, img))
    conn.commit()
    conn.close()

def get_msg_settings(msg_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT description, image_url FROM message_settings WHERE message_id = ?", (str(msg_id),))
    res = cursor.fetchone()
    conn.close()
    return res if res else ("Без описания", None)

def add_user(msg_id, user_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO participants VALUES (?, ?)", (str(msg_id), user_name))
        conn.commit()
    except: pass
    finally: conn.close()

def remove_user(msg_id, user_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM participants WHERE message_id = ? AND user_name = ?", (str(msg_id), user_name))
    conn.commit()
    conn.close()

def get_users(msg_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_name FROM participants WHERE message_id = ?", (str(msg_id),))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# --- ИНТЕРФЕЙС РЕГИСТРАЦИИ ---
class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_embed(self, msg_id):
        desc, img = get_msg_settings(msg_id)
        users = get_users(msg_id)
        user_list = "\n".join([f"• {u}" for u in users]) if users else "Пока никого нет"
        
        embed = discord.Embed(title="🎮 Регистрация на турнир", description=desc, color=discord.Color.blue())
        embed.add_field(name=f"Участники ({len(users)}):", value=f"```\n{user_list}\n```", inline=False)
        if img: embed.set_image(url=img)
        return embed

    @discord.ui.button(label="Участвую", style=discord.ButtonStyle.success, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        add_user(interaction.message.id, interaction.user.display_name)
        await interaction.response.edit_message(embed=await self.create_embed(interaction.message.id))

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.danger, custom_id="unreg_btn")
    async def unregister(self, interaction: discord.Interaction, button: discord.ui.Button):
        remove_user(interaction.message.id, interaction.user.display_name)
        await interaction.response.edit_message(embed=await self.create_embed(interaction.message.id))

# --- МОНИТОРИНГ CS2 ---
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return

    try:
        # Получаем данные от сервера (в отдельном потоке, чтобы не вешать бота)
        info = await asyncio.to_thread(a2s.info, SERVER_IP)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        
        player_names = "\n".join([p.name for p in players if p.name.strip()]) or "На сервере пусто"
        if len(player_names) > 1000: player_names = player_names[:997] + "..."
        
        embed = discord.Embed(title="📊 Статус сервера CS2", color=discord.Color.green())
        embed.add_field(name="IP Адрес", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Карта", value=f"{info.map_name}", inline=True)
        embed.add_field(name="Список игроков:", value=f"```\n{player_names}\n```", inline=False)
        embed.set_footer(text="Обновляется автоматически")

        # Поиск существующего сообщения со статусом в истории канала
        status_msg = None
        async for msg in channel.history(limit=20):
            if msg.author == bot.user and msg.embeds and "Статус сервера CS2" in msg.embeds[0].title:
                status_msg = msg
                break
        
        if status_msg:
            await status_msg.edit(embed=embed)
        else:
            await channel.send(embed=embed)

        # Обновление активности самого бота
        await bot.change_presence(activity=discord.Game(name=f"{info.player_count}/{info.max_players} на {info.map_name}"))

    except Exception as e:
        print(f"Ошибка CS2: {e}")
        # Если сервер не отвечает
        offline_embed = discord.Embed(title="📊 Статус сервера CS2", color=discord.Color.red())
        offline_embed.add_field(name="Состояние", value="🔴 Сервер не отвечает (Offline)", inline=False)
        
        async for msg in channel.history(limit=10):
            if msg.author == bot.user and msg.embeds and "Статус сервера CS2" in msg.embeds[0].title:
                await msg.edit(embed=offline_embed)
                break

# --- КОМАНДЫ ---
@bot.command()
async def reg(ctx, *, description: str):
    img = ctx.message.attachments[0].url if ctx.message.attachments else None
    view = RegistrationView()
    msg = await ctx.send(embed=discord.Embed(title="Создание регистрации...", color=discord.Color.light_grey()), view=view)
    
    save_msg_settings(msg.id, description, img)
    # Раскомментируй строку ниже ОДИН РАЗ, если хочешь добавить свой список в новую регистрацию:
    # fix_missing_participants(msg.id)
    
    await msg.edit(embed=await view.create_embed(msg.id))

@bot.event
async def on_ready():
    init_db()
    bot.add_view(RegistrationView())
    print(f"✅ Бот запущен: {bot.user}")
    if not update_status_message.is_running():
        update_status_message.start()

bot.run(TOKEN)
