import discord
from discord.ext import commands
import aiohttp
import asyncio
import base64
import json
import os
from aiohttp import web

TOKEN = os.environ.get('BOT_TOKEN')
WEBSOCKET_PORT = int(os.environ.get('PORT', 8080))  # Render даёт PORT

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)
connections = {}
listener_websockets = set()

# --- Discord часть ---
@bot.event
async def on_ready():
    print(f'Бот {bot.user} запущен')

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Ты не в голосовом канале!")
        return
    channel = ctx.author.voice.channel
    vc = await channel.connect()
    vc.start_recording(
        discord.sinks.WaveSink(),
        once_done,
        ctx.channel
    )
    connections[ctx.guild.id] = vc
    await ctx.send(f"🎤 Начинаю трансляцию из {channel.name}")

async def once_done(sink, channel, *args):
    for user_id, audio in sink.audio_data.items():
        pcm_data = audio.file.read()
        # Отправляем всем слушателям
        b64 = base64.b64encode(pcm_data).decode()
        msg = json.dumps({"type": "audio", "data": b64})
        for ws in listener_websockets.copy():
            if ws.closed:
                listener_websockets.remove(ws)
            else:
                await ws.send_str(msg)
    await channel.send("⏹ Трансляция завершена")

@bot.command()
async def stop(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        await vc.disconnect()
        del connections[ctx.guild.id]
        await ctx.send("🛑 Остановил трансляцию и отключился")
    else:
        await ctx.send("❌ Я сейчас не записываю")

# --- Веб-сервер часть ---
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    listener_websockets.add(ws)
    try:
        async for msg in ws:
            # Если бот пришлёт что-то, но обычно слушатели ничего не шлют
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
    print(f"Web server started on port {WEBSOCKET_PORT}")

async def main():
    # Запускаем оба сервиса конкурентно
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == '__main__':
    asyncio.run(main())