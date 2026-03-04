const { Client, GatewayIntentBits, Events } = require('discord.js');
const { joinVoiceChannel, createAudioPlayer, createAudioResource, getVoiceConnection, AudioPlayerStatus, VoiceConnectionStatus, entersState } = require('@discordjs/voice');
const WebSocket = require('ws');
const express = require('express');
const http = require('http');
const { pipeline } = require('stream');
const prism = require('prism-media'); // для декодирования Opus

const TOKEN = process.env.BOT_TOKEN;
const WS_PORT = process.env.PORT || 8080;

// HTTP + WebSocket сервер
const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

let listeners = new Set();

// Discord клиент
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ]
});

client.once(Events.ClientReady, () => {
  console.log(`✅ Бот ${client.user.tag} запущен`);
});

client.on(Events.MessageCreate, async (message) => {
  if (!message.content.startsWith('!') || message.author.bot) return;
  const args = message.content.slice(1).split(' ');
  const command = args.shift().toLowerCase();

  if (command === 'join') {
    const voiceChannel = message.member?.voice.channel;
    if (!voiceChannel) {
      return message.reply('❌ Ты не в голосовом канале!');
    }

    try {
      const connection = joinVoiceChannel({
        channelId: voiceChannel.id,
        guildId: voiceChannel.guild.id,
        adapterCreator: voiceChannel.guild.voiceAdapterCreator,
      });

      await entersState(connection, VoiceConnectionStatus.Ready, 10_000);
      const receiver = connection.receiver;

      receiver.speaking.on('start', (userId) => {
        const user = client.users.cache.get(userId);
        console.log(`🔊 ${user?.tag || userId} начал говорить`);

        const opusStream = receiver.subscribe(userId, {
          end: { behavior: 'manual' },
        });

        // Декодируем Opus в PCM
        const decoder = new prism.opus.Decoder({ frameSize: 960, channels: 2, rate: 48000 });
        pipeline(opusStream, decoder, (err) => {
          if (err) console.error('Pipeline error:', err);
        });

        decoder.on('data', (chunk) => {
          const audioData = chunk.toString('base64');
          const msg = JSON.stringify({ type: 'audio', data: audioData });
          listeners.forEach(ws => {
            if (ws.readyState === WebSocket.OPEN) ws.send(msg);
          });
        });

        decoder.on('end', () => {
          console.log(`Поток от ${userId} завершён`);
        });
      });

      message.reply(`🎤 Начинаю трансляцию из ${voiceChannel.name}`);
    } catch (err) {
      console.error('Ошибка подключения:', err);
      message.reply('❌ Не удалось подключиться к голосовому каналу');
    }
  }

  if (command === 'stop') {
    const connection = getVoiceConnection(message.guild.id);
    if (connection) {
      connection.destroy();
      message.reply('🛑 Трансляция остановлена');
    } else {
      message.reply('❌ Бот не в голосовом канале');
    }
  }
});

// WebSocket для слушателей
wss.on('connection', (ws) => {
  listeners.add(ws);
  console.log('👂 Новый слушатель, всего:', listeners.size);
  ws.on('close', () => {
    listeners.delete(ws);
    console.log('👋 Слушатель отключился, осталось:', listeners.size);
  });
});

// Простой эндпоинт для проверки
app.get('/', (req, res) => res.send('Discord Audio Relay работает'));
app.get('/health', (req, res) => res.send('ok'));

server.listen(WS_PORT, () => {
  console.log(`🌐 Сервер запущен на порту ${WS_PORT}`);
});

client.login(TOKEN);