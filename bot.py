import discord
from discord.ext import commands, tasks
import a2s
import asyncio
import os
import sqlite3

# --- КОНФИГУРАЦИЯ ---
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 1482982357882507436))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", 60))
SERVER_IP = ("194.93.2.207", 27077)

# --- RELAY КОНФИГУРАЦИЯ ---
# ID канала откуда копировать сообщения
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID",1127290770571931739))
# ID канала куда копировать сообщения
DESTINATION_CHANNEL_ID = int(os.getenv("DESTINATION_CHANNEL_ID",1359230337602949391))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- ОБНОВЛЕННАЯ БАЗА ДАННЫХ ---
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_settings (
            message_id TEXT PRIMARY KEY,
            description TEXT,
            image_url TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_msg_settings(msg_id, desc, img):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO message_settings VALUES (?, ?, ?)", (str(msg_id), desc, img))
    conn.commit()
    conn.close()

def get_msg_settings(msg_id):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    cursor.execute("SELECT description, image_url FROM message_settings WHERE message_id = ?", (str(msg_id),))
    res = cursor.fetchone()
    conn.close()
    return res if res else ("Без описания", None)

def add_user(msg_id, user_name):
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO participants VALUES (?, ?)", (str(msg_id), user_name))
        conn.commit()
    except: pass
    finally: conn.close()

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

# --- ИНТЕРФЕЙС ---
class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_embed(self, msg_id):
        desc, img = get_msg_settings(msg_id)
        users = get_users(msg_id)
        
        user_list = "\n".join([f"• {u}" for u in users]) if users else "Пока никого нет"
        if len(user_list) > 1000: user_list = user_list[:997] + "..."

        embed = discord.Embed(title="🎮 Регистрация на событие", description=desc, color=discord.Color.blue())
        embed.add_field(name="Список участников:", value=f"```\n{user_list}\n```", inline=False)
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

# --- CS2 МОНИТОРИНГ ---
async def get_server_info():
    try:
        info = await asyncio.wait_for(asyncio.to_thread(a2s.info, SERVER_IP), timeout=5.0)
        players = await asyncio.to_thread(a2s.players, SERVER_IP)
        all_names = [p.name.strip() for p in players if p.name.strip()]
        diff = info.player_count - len(all_names)
        if diff > 0:
            for _ in range(diff): all_names.append("Игрок...")
        player_list = "\n".join(all_names)
        if len(player_list) > 1000: player_list = player_list[:997] + "..."
        if not player_list: player_list = "На сервере никого нет"

        embed = discord.Embed(title="📊 Статус CS2", color=discord.Color.green())
        embed.add_field(name="IP Сервера", value=f"`{SERVER_IP[0]}:{SERVER_IP[1]}`", inline=False)
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

# --- RELAY: копирование сообщений ---
@bot.event
async def on_message(message):
    # Не копируем сообщения самого бота
    if message.author == bot.user:
        await bot.process_commands(message)
        return

    # Проверяем что relay настроен и сообщение из нужного канала
    if SOURCE_CHANNEL_ID and DESTINATION_CHANNEL_ID:
        if message.channel.id == SOURCE_CHANNEL_ID:
            dest = bot.get_channel(DESTINATION_CHANNEL_ID)
            if dest:
                # Формируем embed с оригинальным сообщением
                embed = discord.Embed(
                    description=message.content or "",
                    color=discord.Color.blurple(),
                    timestamp=message.created_at
                )
                embed.set_author(
                    name=message.author.display_name,
                    icon_url=message.author.display_avatar.url
                )
                embed.set_footer(text=f"#{message.channel.name}")

                # Если есть картинка — прикрепляем
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)

                await dest.send(embed=embed)

                # Если несколько вложений — отправляем остальные отдельно
                for attachment in message.attachments[1:]:
                    await dest.send(attachment.url)

    await bot.process_commands(message)

# --- КОМАНДЫ ---
@bot.command()
async def reg(ctx, *, description: str):
    image_url = ctx.message.attachments[0].url if ctx.message.attachments else None
    view = RegistrationView()
    temp_embed = discord.Embed(title="Создание регистрации...", color=discord.Color.light_grey())
    message = await ctx.send(embed=temp_embed, view=view)
    save_msg_settings(message.id, description, image_url)
    await message.edit(embed=await view.create_embed(message.id))

@bot.event
async def on_ready():
    init_db()
    bot.add_view(RegistrationView())
    print(f"✅ Бот онлайн: {bot.user}")
    if SOURCE_CHANNEL_ID and DESTINATION_CHANNEL_ID:
        print(f"🔁 Relay активен: {SOURCE_CHANNEL_ID} → {DESTINATION_CHANNEL_ID}")
    else:
        print("⚠️ Relay не настроен (SOURCE_CHANNEL_ID / DESTINATION_CHANNEL_ID не заданы)")
    if not update_status_message.is_running():
        update_status_message.start()

bot.run(TOKEN)
