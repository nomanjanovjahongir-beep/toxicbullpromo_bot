# -*- coding: utf-8 -*-

from flask import Flask
from threading import Thread
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_web():
    """Web server ni ishga tushirish"""
    try:
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Web server error: {e}")

def keep_alive():
    """Botni 24/7 ushlab turish uchun web server"""
    try:
        thread = Thread(target=run_web)
        thread.daemon = True
        thread.start()
        logger.info("Keep-alive web server started")
    except Exception as e:
        logger.error(f"Keep-alive error: {e}")