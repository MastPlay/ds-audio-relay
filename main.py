import discord
from discord.ext import commands
import asyncio
import base64
import json
import os
from aiohttp import web

TOKEN = os.environ.get('BOT_TOKEN')
WEBSOCKET_PORT = int(os.environ.get('PORT', 8080))

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
connections = {}
listener_websockets = set()

# ----- Discord часть -----
@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен')

async def send_to_listeners(msg):
    """Отправить сообщение всем подключённым слушателям."""
    to_remove = []
    for ws in listener_websockets:
        if ws.closed:
            to_remove.append(ws)
        else:
            try:
                await ws.send_str(msg)
            except Exception:
                to_remove.append(ws)
    for ws in to_remove:
        listener_websockets.discard(ws)

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Ты не в голосовом канале!")
        return
    channel = ctx.author.voice.channel
    vc = await channel.connect()
    connections[ctx.guild.id] = vc

    # Правильный колбэк для VoiceClient.listen
    def audio_callback(data):
        # data — объект VoiceData с атрибутами user и packet
        packet = data.packet  # байты Opus
        b64 = base64.b64encode(packet).decode()
        msg = json.dumps({"type": "audio", "data": b64})
        asyncio.create_task(send_to_listeners(msg))

    vc.listen(audio_callback)
    await ctx.send(f"🎤 Трансляция из {channel.name} начата (в реальном времени)")

@bot.command()
async def stop(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_listening()
        await vc.disconnect()
        del connections[ctx.guild.id]
        await ctx.send("🛑 Трансляция остановлена")
    else:
        await ctx.send("❌ Я сейчас не транслирую")

# ----- Веб-сервер часть -----
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    listener_websockets.add(ws)
    try:
        async for msg in ws:
            pass
    finally:
        listener_websockets.discard(ws)
    return ws

async def index_handler(request):
    return web.FileResponse('./index.html')

async def health_handler(request):
    # Для пинга от cron-job
    return web.Response(text="ok")

app = web.Application()
app.router.add_get('/', index_handler)
app.router.add_get('/ws', websocket_handler)
app.router.add_get('/health', health_handler)  # добавили эндпоинт для пинга

async def start_bot():
    await bot.start(TOKEN)

async def start_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEBSOCKET_PORT)
    await site.start()
    print(f"Веб-сервер запущен на порту {WEBSOCKET_PORT}")

async def main():
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == '__main__':
    asyncio.run(main())