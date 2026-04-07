import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os
import sqlite3

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = 1482982357882507436 
UPDATE_INTERVAL = 60
SERVER_IP = ("194.93.2.207", 27077)

# ПУТЬ К БАЗЕ ДАННЫХ (Для Railway Volume используем /app/data/)
DB_PATH = "/app/data/registration.db" if os.path.exists("/app/data") else "registration.db"

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- БАЗА ДАННЫХ ---
def init_db():
    if "/" in DB_PATH:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            message_id TEXT,
            user_name TEXT,
            PRIMARY KEY (message_id, user_name)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_settings (
            message_id TEXT PRIMARY KEY,
            description TEXT,
            image_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def fix_missing_participants(msg_id):
    """Добавление списка игроков, которых ты прислал"""
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

# --- СТАТУС CS2 ---
@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    try:
        info = await asyncio.to_thread(a2s.info, SERVER_IP)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        player_names = "\n".join([p.name for p in players if p.name]) or "Никто не играет"
        
        embed = discord.Embed(title="📊 Статус сервера CS2", color=discord.Color.green())
        embed.add_field(name="IP Адрес", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="Карта", value=info.map_name, inline=True)
        embed.add_field(name="Список игроков:", value=f"```\n{player_names}\n```", inline=False)
        
        if not hasattr(bot, "status_message") or bot.status_message is None:
            async for msg in channel.history(limit=10):
                if msg.author == bot.user and msg.embeds and "Статус сервера CS2" in msg.embeds[0].title:
                    bot.status_message = msg
                    break
            if not bot.status_message:
                bot.status_message = await channel.send(embed=embed)
        
        await bot.status_message.edit(embed=embed)
    except: pass

# --- КОМАНДЫ ---
@bot.command()
async def reg(ctx, *, description: str):
    img = ctx.message.attachments[0].url if ctx.message.attachments else None
    view = RegistrationView()
    msg = await ctx.send(embed=discord.Embed(title="Создание..."), view=view)
    save_msg_settings(msg.id, description, img)
    # Если хочешь сразу добавить тех 20 человек в новую регистрацию, раскомментируй строку ниже:
    # fix_missing_participants(msg.id)
    await msg.edit(embed=await view.create_embed(msg.id))

@bot.event
async def on_ready():
    init_db()
    bot.add_view(RegistrationView())
    print(f"✅ Бот запущен как {bot.user}")
    if not update_status_message.is_running():
        update_status_message.start()

bot.run(TOKEN)
