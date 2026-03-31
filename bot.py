import discord
from discord.ext import commands
import os
import sqlite3

# Настройки
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- РАБОТА С БАЗОЙ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("registration.db")
    cursor = conn.cursor()
    # Создаем таблицу, если её нет
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
        pass # Пользователь уже есть
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

# --- ИНТЕРФЕЙС КНОПОК ---
class RegistrationView(discord.ui.View):
    def __init__(self, description, image_url, msg_id=None):
        super().__init__(timeout=None)
        self.description = description
        self.image_url = image_url
        self.msg_id = msg_id

    def create_embed(self, registered_users):
        if not registered_users:
            user_list_str = "Пока никого нет"
        else:
            user_list_str = "\n".join([f"• {user}" for user in registered_users])

        embed = discord.Embed(
            title="📝 Регистрация на событие",
            description=self.description,
            color=discord.Color.green()
        )
        embed.add_field(name="Участники:", value=user_list_str, inline=False)
        if self.image_url:
            embed.set_image(url=self.image_url)
        return embed

    @discord.ui.button(label="Зарегистрироваться", style=discord.ButtonStyle.success, custom_id="reg_btn")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_name = interaction.user.display_name
        add_user(interaction.message.id, user_name)
        
        users = get_users(interaction.message.id)
        await interaction.response.edit_message(embed=self.create_embed(users), view=self)

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.danger, custom_id="unreg_btn")
    async def unregister(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_name = interaction.user.display_name
        remove_user(interaction.message.id, user_name)
        
        users = get_users(interaction.message.id)
        await interaction.response.edit_message(embed=self.create_embed(users), view=self)

# --- КОМАНДЫ ---
@bot.command()
async def reg(ctx, description: str, image_url: str = None):
    # Сначала отправляем сообщение, чтобы получить его ID для базы
    view = RegistrationView(description, image_url)
    embed = view.create_embed([])
    message = await ctx.send(embed=embed, view=view)
    # Можно использовать ID сообщения как уникальный ключ для разных регистраций

@bot.event
async def on_ready():
    init_db()
    # Чтобы кнопки работали после перезагрузки, их нужно "зарегистрировать" снова
    bot.add_view(RegistrationView("", "")) 
    print(f"✅ Бот запущен, БД готова. Вошел как {bot.user}")

bot.run(TOKEN)
