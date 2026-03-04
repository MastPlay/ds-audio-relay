import discord
from discord.ext import commands
import aiohttp
import asyncio
import base64
import json
import os
from aiohttp import web

TOKEN = os.environ.get('BOT_TOKEN')
WEBSOCKET_PORT = int(os.environ.get('PORT', 8080))  # Render подставляет PORT

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
connections = {}
listener_websockets = set()  # все активные веб‑сокеты слушателей

# ----- Discord часть -----
@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен')

async def send_to_listeners(msg):
    """Отправить сообщение всем подключённым слушателям."""
    for ws in listener_websockets.copy():
        if ws.closed:
            listener_websockets.remove(ws)
        else:
            try:
                await ws.send_str(msg)
            except:
                listener_websockets.remove(ws)

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Ты не в голосовом канале!")
        return
    channel = ctx.author.voice.channel
    vc = await channel.connect()
    connections[ctx.guild.id] = vc

    # Колбэк, вызываемый на каждый аудиопакет от любого говорящего
    def audio_callback(user, data):
        # data — сырые байты аудио (обычно Opus)
        b64 = base64.b64encode(data).decode()
        msg = json.dumps({"type": "audio", "data": b64})
        asyncio.create_task(send_to_listeners(msg))

    # Начинаем слушать
    vc.listen(audio_callback)

    await ctx.send(f"🎤 Трансляция из {channel.name} начата (в реальном времени)")

@bot.command()
async def stop(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_listening()          # останавливаем прослушивание
        await vc.disconnect()
        del connections[ctx.guild.id]
        await ctx.send("🛑 Трансляция остановлена")
    else:
        await ctx.send("❌ Я сейчас не транслирую")

# ----- Веб‑сервер часть -----
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    listener_websockets.add(ws)
    try:
        async for msg in ws:
            # слушатели обычно ничего не отправляют
            pass
    finally:
        listener_websockets.remove(ws)
    return ws

async def index_handler(request):
    return web.FileResponse('./index.html')

app = web.Application()
app.router.add_get('/', index_handler)
app.router.add_get('/ws', websocket_handler)

async def start_bot():
    await bot.start(TOKEN)

async def start_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEBSOCKET_PORT)
    await site.start()
    print(f"Веб‑сервер запущен на порту {WEBSOCKET_PORT}")

async def main():
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == '__main__':
    asyncio.run(main())