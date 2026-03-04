import discord
import sys
import logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(f"Discord.py version: {discord.__version__}")

# ... (остальной код без изменений, но в команде join добавим отладку)

@bot.command(name='join')
async def join(ctx):
    logger.info(f"Команда join от {ctx.author}")
    if not ctx.author.voice:
        await ctx.send("❌ Ты не в голосовом канале!")
        return
    channel = ctx.author.voice.channel
    try:
        vc = await channel.connect()
        connections[ctx.guild.id] = vc
        logger.info(f"Тип vc: {type(vc)}")
        logger.info(f"Атрибуты vc: {dir(vc)}")  # посмотрим, есть ли listen

        # Проверим наличие listen
        if hasattr(vc, 'listen'):
            def audio_callback(data):
                packet = data.packet
                b64 = base64.b64encode(packet).decode()
                msg = json.dumps({"type": "audio", "data": b64})
                asyncio.create_task(send_to_listeners(msg))
            vc.listen(audio_callback)
            await ctx.send(f"🎤 Трансляция из {channel.name} начата")
        else:
            await ctx.send("❌ Метод listen не найден. Возможно, discord.py установлен без голосовой поддержки или версия устарела.")
    except Exception as e:
        logger.exception("Ошибка в join")
        await ctx.send(f"❌ Ошибка: {e}")