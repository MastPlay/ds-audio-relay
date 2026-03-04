import discord
from discord.ext import commands, voice_recv
import asyncio
import base64
import json
import os
import sys
import logging
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    logger.info(f'✅ Бот {bot.user} запущен')
    logger.info(f'Discord.py версия: {discord.__version__}')
    logger.info(f'Подключен к гильдиям: {[g.name for g in bot.guilds]}')

async def send_to_listeners(msg):
    """Отправить сообщение всем слушателям."""
    to_remove = []
    for ws in listener_websockets:
        if ws.closed:
            to_remove.append(ws)
        else:
            try:
                await ws.send_str(msg)
            except Exception as e:
                logger.error(f"Ошибка отправки слушателю: {e}")
                to_remove.append(ws)
    for ws in to_remove:
        listener_websockets.discard(ws)

# Функция, которая будет вызываться для каждого аудиопакета
def audio_callback(user, data):
    # data — это байты PCM (или Opus, но BasicSink отдаёт PCM)
    # Отправляем слушателям
    b64 = base64.b64encode(data).decode()
    msg = json.dumps({"type": "audio", "data": b64})
    asyncio.create_task(send_to_listeners(msg))

@bot.command(name='join')
async def join(ctx):
    logger.info(f"Команда join от {ctx.author}")
    if not ctx.author.voice:
        await ctx.send("❌ Ты не в голосовом канале!")
        return

    channel = ctx.author.voice.channel
    logger.info(f"Попытка подключиться к каналу {channel.name}")

    try:
        # Подключаемся с использованием VoiceRecvClient
        vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
        connections[ctx.guild.id] = vc

        # Создаём синк, который вызывает нашу функцию при получении данных
        sink = voice_recv.BasicSink(audio_callback)
        vc.listen(sink)

        await ctx.send(f"🎤 Трансляция из {channel.name} начата (в реальном времени)")
        logger.info(f"Трансляция начата в канале {channel.name}")

    except Exception as e:
        logger.exception("Ошибка в join")
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command(name='stop')
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
    logger.info(f"Новый слушатель, всего: {len(listener_websockets)}")
    try:
        async for msg in ws:
            pass
    finally:
        listener_websockets.discard(ws)
        logger.info(f"Слушатель отключился, осталось: {len(listener_websockets)}")
    return ws

async def index_handler(request):
    return web.FileResponse('./index.html')

async def health_handler(request):
    return web.Response(text="ok")

app = web.Application()
app.router.add_get('/', index_handler)
app.router.add_get('/ws', websocket_handler)
app.router.add_get('/health', health_handler)

async def start_bot():
    await bot.start(TOKEN)

async def start_web():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', WEBSOCKET_PORT)
    await site.start()
    logger.info(f"🌐 Веб-сервер запущен на порту {WEBSOCKET_PORT}")

async def main():
    await asyncio.gather(
        start_bot(),
        start_web()
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановка по Ctrl+C")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")