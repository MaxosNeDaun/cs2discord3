import discord
from discord.ext import tasks, commands
import a2s
import os

# Nastavení botu
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Načtení tokenu z prostředí (Railway/Render)
TOKEN = os.getenv("TOKEN")

# Nastavení tvého CS2 serveru
IP = "127.0.0.1"  # Tady jsi měl svou IP
PORT = 27015      # Tady jsi měl svůj port

@tasks.loop(seconds=30)
async def update_status():
    try:
        # Dotaz na CS2 server
        info = a2s.info((IP, PORT))
        
        # Nastavení statusu: "X/Y hráčů"
        status_text = f"{info.player_count}/{info.max_players} hráčů"
        await bot.change_presence(activity=discord.Game(name=status_text))
        print(f"Aktualizováno: {status_text}")
        
    except Exception as e:
        print(f"Chyba při spojení se serverem: {e}")
        await bot.change_presence(activity=discord.Game(name="Server Offline"))

@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} je online!')
    if not update_status.is_running():
        update_status.start()

if TOKEN:
    bot.run(TOKEN)
else:
    print("TOKEN ne nalezen! Pridejte ho do Environment Variables.")
