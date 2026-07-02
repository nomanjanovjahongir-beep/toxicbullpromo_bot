# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8901157648:AAER_bR0ntOjcaxDflrtCfFyRXd55qxl5to")
BOT_USERNAME = "bullpromo_bot"

REQUIRED_CHANNELS = {
    "Kanal 1": "@frezybulldrop",
    "Kanal 2": "@fendi_bulldrop",
}

DATABASE_FILE = "users.db"
REFERRAL_REWARD = 1

PROMO_PRICES = {
    "69 promo": 10,
    "99 promo": 15,
    "299 promo": 25,
}

ADMIN_ID = 8632521282  # O'z ID niz yozing!
ADMIN ID = 8656034255
