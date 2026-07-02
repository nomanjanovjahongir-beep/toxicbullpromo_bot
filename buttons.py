# -*- coding: utf-8 -*-

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup


def get_main_keyboard():
    """Asosiy tugmalar - oddiy foydalanuvchilar uchun"""
    buttons = [
        [KeyboardButton("👤 Profil"), KeyboardButton("🔗 Referral")],
        [KeyboardButton("💰 Promo"), KeyboardButton("🏆 Reyting")],
        [KeyboardButton("❓ Yordam")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_admin_keyboard():
    """Admin tugmalar - admin foydalanuvchi uchun"""
    buttons = [
        [KeyboardButton("📊 Statistika"), KeyboardButton("💰 Coin berish")],
        [KeyboardButton("📢 Xabar yuborish"), KeyboardButton("👥 Foydalanuvchilar")],
        [KeyboardButton("🔙 Asosiy menyu")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_back_keyboard():
    """Orqaga qaytish tugmasi"""
    buttons = [[KeyboardButton("🔙 Orqaga")]]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def get_promo_keyboard():
    """Promo almashtirish tugmalari - InlineKeyboardButton ko'rinishida"""
    from config import PROMO_PRICES
    
    keyboard = []
    
    # Har bir promo uchun alohida tugma
    for promo_name in PROMO_PRICES.keys():
        keyboard.append([
            InlineKeyboardButton(
                f"🎫 {promo_name}", 
                callback_data=f"promo_{promo_name}"
            )
        ])
    
    # Orqaga tugmasi
    keyboard.append([
        InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_referral_keyboard():
    """Referral link uchun tugma - linkni nusxalash"""
    keyboard = [
        [InlineKeyboardButton("📋 Linkni nusxalash", callback_data="copy_referral_link")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_referral_link_keyboard():
    """Faqat referral linkni ko'rsatish uchun - orqaga tugmasi bilan"""
    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_coin_keyboard():
    """Coin berish/olish uchun admin tugmalar - InlineKeyboardButton ko'rinishida"""
    keyboard = [
        [InlineKeyboardButton("➕ 10 coin", callback_data="add_10")],
        [InlineKeyboardButton("➕ 50 coin", callback_data="add_50")],
        [InlineKeyboardButton("➕ 100 coin", callback_data="add_100")],
        [InlineKeyboardButton("➖ 10 coin", callback_data="sub_10")],
        [InlineKeyboardButton("➖ 50 coin", callback_data="sub_50")],
        [InlineKeyboardButton("➖ 100 coin", callback_data="sub_100")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)
