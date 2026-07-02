# -*- coding: utf-8 -*-

import os
from dotenv import load_dotenv

load_dotenv()

# ============ BOT SOZLAMALARI ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "8901157648:AAER_bR0ntOjcaxDflrtCfFyRXd55qxl5to")
BOT_USERNAME = "toxicbullpromo_bot"

# ============ MAJBURIY KANALLAR ============
REQUIRED_CHANNELS = {
    "Kanal 1": "@frezybulldrop",
    "Kanal 2": "@fendi_bulldrop",
}

# ============ DATABASE ============
DATABASE_FILE = "users.db"

# ============ REFERRAL SOZLAMALARI ============
REFERRAL_REWARD = 1

# ============ PROMO NARXLAR ============
PROMO_PRICES = {
    "69 promo": 10,
    "99 promo": 15,
    "299 promo": 25,
}

# ============ ADMIN ============
# ✏️ O'Z TELEGRAM ID NIGIZNI YOZING!
ADMIN_ID = 8632521282  # ← SHU YERGA O'Z ID NIGIZNI YOZING
