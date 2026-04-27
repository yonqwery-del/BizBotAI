/**
 * WhatsApp сервис через whatsapp-web.js
 * Запускается отдельно: node whatsapp.js
 * 
 * Установка: npm install whatsapp-web.js qrcode-terminal express axios
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());

const PYTHON_BACKEND = process.env.PYTHON_BACKEND || 'http://localhost:8000';

// ─── WHATSAPP CLIENT ────────────────────────────────────────────────
const client = new Client({
    authStrategy: new LocalAuth(),  // Сохраняет сессию, не нужно каждый раз сканировать
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

// Показываем QR для первого входа
client.on('qr', (qr) => {
    console.log('\n📱 Отсканируй QR-код в WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('✅ WhatsApp подключён!');
});

client.on('auth_failure', (msg) => {
    console.error('❌ Ошибка авторизации WhatsApp:', msg);
});

// ─── ОБРАБОТКА ВХОДЯЩИХ СООБЩЕНИЙ ──────────────────────────────────
client.on('message', async (message) => {
    // Игнорируем групповые чаты и статусы
    if (message.from.includes('@g.us') || message.from === 'status@broadcast') {
        return;
    }
    
    // Игнорируем исходящие
    if (message.fromMe) return;
    
    const phone = message.from.replace('@c.us', '');
    const text = message.body;
    const contact = await message.getContact();
    const pushName = contact.pushname || 'Клиент';
    
    console.log(`📨 WhatsApp от ${pushName} (${phone}): ${text}`);
    
    try {
        // Отправляем в Python бэкенд
        const response = await axios.post(`${PYTHON_BACKEND}/webhook/whatsapp`, {
            from: message.from,
            body: text,
            pushname: pushName,
            timestamp: message.timestamp
        }, { timeout: 15000 });
        
        const reply = response.data?.reply;
        
        if (reply) {
            await message.reply(reply);
        }
        
    } catch (error) {
        console.error('Ошибка отправки в бэкенд:', error.message);
        // Фолбэк — сообщаем клиенту
        await message.reply('Извините, временные неполадки. Мы свяжемся с вами в ближайшее время.');
    }
});

// ─── HTTP API ДЛЯ ОТПРАВКИ СООБЩЕНИЙ ───────────────────────────────
// Используется Python бэкендом для отправки напоминаний и ответов менеджера

app.post('/send', async (req, res) => {
    const { phone, text } = req.body;
    
    if (!phone || !text) {
        return res.status(400).json({ error: 'phone and text required' });
    }
    
    try {
        const chatId = phone.includes('@c.us') ? phone : ${phone}@c.us;
        await client.sendMessage(chatId, text);
        res.json({ ok: true });
    } catch (error) {
        console.error('Send error:', error);
        res.status(500).json({ error: error.message });
    }
});

app.get('/status', (req, res) => {
    res.json({
        ready: client.info ? true : false,
        phone: client.info?.wid?.user || null
    });
});

// ─── ЗАПУСК ─────────────────────────────────────────────────────────
const PORT = process.env.WA_PORT || 3001;
app.listen(PORT, () => {
    console.log(`WhatsApp сервис запущен на порту ${PORT}`);
});

client.initialize();