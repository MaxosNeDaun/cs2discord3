import discord
from discord.ext import tasks, commands
import a2s
import os
from flask import Flask
from threading import Thread

# --- NASTAVENÍ WEBOVÉHO SERVERU PRO RENDER ---
app = Flask('')

@app.get('/')
def home():
    return "Bot is running!"

def run_flask():
    # Render vyžaduje port, který mu přidělí v proměnné PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- NASTAVENÍ DISCORD BOTA ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# NASTAVENÍ CS2 SERVERU (Můžeš změnit nebo dát do Environment Variables)
IP = os.getenv("CS2_IP", "127.0.0.1") # Sem dej IP serveru, pokud ji nemáš v ENV
PORT = int(os.getenv("CS2_PORT", 27015)) # Sem dej port serveru

@tasks.loop(seconds=30)
async def update_status():
    try:
        # Získání info o CS2 serveru přes a2s
        info = a2s.info((IP, PORT))
        players = a2s.players((IP, PORT))
        
        status_text = f"{info.player_count}/{info.max_players} hráčů na CS2"
        await bot.change_presence(activity=discord.Game(name=status_text))
        print(f"Status aktualizován: {status_text}")
    except Exception as e:
        print(f"Chyba při čtení CS2 serveru: {e}")
        await bot.change_presence(activity=discord.Game(name="Server Offline"))

@bot.event
async def on_ready():
    print(f'Bot přihlášen jako {bot.user.name}')
    update_status.start()

# --- SPUŠTĚNÍ ---
if __name__ == "__main__":
    # 1. Spustíme Flask webserver (pro Render)
    keep_alive()
    
    # 2. Načteme TOKEN
    TOKEN = os.getenv("TOKEN")
    
    if not TOKEN:
        # Tato hláška se objeví v logu Renderu, pokud zapomeneš přidat Environment Variable
        print("CHYBA: Proměnná 'TOKEN' nebyla nalezena v nastavení Renderu!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"Nepodařilo se spustit bota: {e}")
