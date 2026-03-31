import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os
import sqlite3

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID",1127290770571931739)) 
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))
SERVER_IP = ("194.93.2.207", 27077)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            message_id TEXT,
            user_name TEXT,
            PRIMARY KEY (message_id, user_name)
        )
    ''')
    conn.commit()
    conn.close()

def add_user(msg_id, user_name):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO participants (message_id, user_name) VALUES (?, ?)", (str(msg_id), user_name))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def remove_user(msg_id, user_name):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM participants WHERE message_id = ? AND user_name = ?", (str(msg_id), user_name))
    conn.commit()
    conn.close()

def get_users(msg_id):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_name FROM participants WHERE message_id = ?", (str(msg_id),))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

# --- ИНТЕРФЕЙС РЕГИСТРАЦИИ ---
class RegistrationView(discord.ui.View):
    def __init__(self, description="", image_url=None):
        super().__init__(timeout=None)
        self.description = description
        self.image_url = image_url

    def create_embed(self, registered_users):
        user_list_str = "\n".join([f"• {user}" for user in registered_users]) if registered_users else "Пока никого нет"
        embed = discord.Embed(
            title="Регистрация на 5х5", 
            description=self.description, 
            color=discord.Color.blue()
        )
        embed.add_field(name="Список участников:", value=f"```\n{user_list_str}\n```", inline=False)
        
        # Если есть ссылка на фото (из вложения), добавляем её в эмбед
        if self.image_url:
            embed.set_image(url=self.image_url)
        return embed

    @discord.ui.button(label="Участвую", style=discord.ButtonStyle.success, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        add_user(interaction.message.id, interaction.user.display_name)
        users = get_users(interaction.message.id)
        await interaction.response.edit_message(embed=self.create_embed(users))

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.danger, custom_id="unreg_btn")
    async def unregister(self, interaction: discord.Interaction, button: discord.ui.Button):
        remove_user(interaction.message.id, interaction.user.display_name)
        users = get_users(interaction.message.id)
        await interaction.response.edit_message(embed=self.create_embed(users))

# --- МОНИТОРИНГ CS2 ---
async def get_server_info():
    try:
        info = await asyncio.wait_for(asyncio.to_thread(a2s.info, SERVER_IP), timeout=5.0)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        player_names = [p.name for p in players[:15]]
        player_list = "\n".join(player_names) if player_names else "Пусто"

        embed = discord.Embed(title="📊 Статус CS2", color=discord.Color.green())
        embed.add_field(name="Сервер", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
        embed.add_field(name="Карта", value=info.map_name, inline=True)
        embed.add_field(name="Игроки", value=f"{info.player_count}/{info.max_players}", inline=True)
        embed.add_field(name="В сети:", value=f"```\n{player_list}\n```", inline=False)
        return embed
    except:
        return discord.Embed(title="🔴 Сервер оффлайн", color=discord.Color.red())

@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_status_message():
    channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
    if not channel: return
    embed = await get_server_info()
    if not hasattr(bot, "status_message") or bot.status_message is None:
        bot.status_message = await channel.send(embed=embed)
    else:
        try: await bot.status_message.edit(embed=embed)
        except: bot.status_message = await channel.send(embed=embed)

# --- НОВАЯ КОМАНДА РЕГИСТРАЦИИ ---
@bot.command()
async def reg(ctx, *, description: str):
    image_url = None
    
    # Если к сообщению прикреплен файл, берем его URL
    if ctx.message.attachments:
        image_url = ctx.message.attachments[0].url
    
    view = RegistrationView(description, image_url)
    await ctx.send(embed=view.create_embed([]), view=view)

@bot.event
async def on_ready():
    init_db()
    bot.add_view(RegistrationView()) 
    print(f"✅ Бот запущен как {bot.user}")
    if not update_status_message.is_running():
        update_status_message.start()

bot.run(TOKEN)
