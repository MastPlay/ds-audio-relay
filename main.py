import discord
from discord.ext import commands
import asyncio
import base64
import json
import os
import sys
import logging
from aiohttp import web

# Настройка логирования (вывод в stdout Render)
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN')
WEBSOCKET_PORT = int(os.environ.get('PORT', 8080))  # Render сам подставляет PORT

# --- 1. Создаём объект бота (ВАЖНО: до всех декораторов) ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

connections = {}          # активные подключения к голосовым каналам
listener_websockets = set()  # все активные веб-сокеты слушателей

# --- 2. События и команды бота ---
@bot.event
async def on_ready():
    logger.info(f'✅ Бот {bot.user} запущен')
    logger.info(f'Discord.py версия: {discord.__version__}')
    
    # Проверка загрузки Opus
    if discord.opus.is_loaded():
        logger.info("Opus loaded successfully")
    else:
        logger.error("Opus NOT loaded! Voice will not work.")
        # Попробуем загрузить вручную
        try:
            discord.opus.load_opus('libopus.so.0')
            logger.info("Opus manually loaded")
        except Exception as e:
            logger.error(f"Failed to load opus manually: {e}")
    
    # Проверим наличие метода listen у VoiceClient
    vc_class = discord.VoiceClient
    has_listen = hasattr(vc_class, 'listen')
    logger.info(f"Есть ли метод listen у VoiceClient? {has_listen}")
    if has_listen:
        logger.info("Метод listen существует.")
    else:
        logger.warning("Метод listen НЕ найден в VoiceClient!")
    
    logger.info(f'Подключен к гильдиям: {[g.name for g in bot.guilds]}')

@bot.event
async def on_command_error(ctx, error):
    logger.error(f'Ошибка команды: {error}')
    await ctx.send(f"❌ Ошибка: {error}")

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

@bot.command(name='join')
async def join(ctx):
    logger.info(f"Команда join от {ctx.author} в канале {ctx.channel}")
    if not ctx.author.voice:
        logger.warning("Пользователь не в голосовом канале")
        await ctx.send("❌ Ты не в голосовом канале!")
        return

    channel = ctx.author.voice.channel
    logger.info(f"Попытка подключиться к каналу {channel.name} (ID: {channel.id})")

    try:
        vc = await channel.connect()
        connections[ctx.guild.id] = vc
        logger.info(f"✅ Подключился к каналу {channel.name}")

        # Проверяем, есть ли метод listen (должен быть в discord.py 2.x)
        if not hasattr(vc, 'listen'):
            await ctx.send("❌ Метод listen не найден. Убедитесь, что discord.py[voice]==2.3.2 установлен и голосовая поддержка работает.")
            return

        # Колбэк для аудиопакетов
        def audio_callback(data):
            packet = data.packet
            logger.debug(f"Получен аудиопакет от {data.user} размером {len(packet)} байт")
            b64 = base64.b64encode(packet).decode()
            msg = json.dumps({"type": "audio", "data": b64})
            asyncio.create_task(send_to_listeners(msg))

        vc.listen(audio_callback)
        logger.info("🎤 Начато прослушивание голосового канала")
        await ctx.send(f"🎤 Трансляция из {channel.name} начата (в реальном времени)")

    except Exception as e:
        logger.exception("Ошибка при подключении к голосовому каналу")
        await ctx.send(f"❌ Не удалось подключиться: {e}")

@bot.command(name='stop')
async def stop(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_listening()
        await vc.disconnect()
        del connections[ctx.guild.id]
        logger.info(f"🛑 Трансляция остановлена в гильдии {ctx.guild.id}")
        await ctx.send("🛑 Трансляция остановлена")
    else:
        await ctx.send("❌ Я сейчас не транслирую")

# --- 3. Веб-сервер для слушателей ---
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    listener_websockets.add(ws)
    logger.info(f"Новый слушатель подключился, всего: {len(listener_websockets)}")
    try:
        async for msg in ws:
            # от клиента ничего не ждём
            pass
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
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