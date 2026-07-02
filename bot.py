# -*- coding: utf-8 -*-

import logging
import random
import string
import os
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    filters,
    CallbackQueryHandler,
)

from config import BOT_TOKEN, REFERRAL_REWARD, PROMO_PRICES, BOT_USERNAME, REQUIRED_CHANNELS, ADMIN_ID
from database import (
    init_database,
    add_user,
    get_user,
    get_top_referrals,
    get_top_coins,
    update_user_coins,
    get_referral_count,
    get_db_connection,
)
from buttons import (
    get_main_keyboard,
    get_promo_keyboard,
    get_referral_keyboard,
    get_referral_link_keyboard,
    get_admin_keyboard,
    get_admin_coin_keyboard,
)

# 24/7 uchun keep_alive
try:
    from keep_alive import keep_alive
except ImportError:
    keep_alive = None
    print("⚠️ keep_alive moduli topilmadi, 24/7 ishlamasligi mumkin")

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============ ADMIN TEKSHIRISH ============

def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshirish"""
    return user_id == ADMIN_ID


# ============ Helper Functions ============

def extract_referral_id(text: str) -> Optional[int]:
    """Extract referral ID from start parameter"""
    if not text or not text.startswith("start="):
        return None
    try:
        return int(text.split("=")[1])
    except (ValueError, IndexError):
        return None


async def get_or_create_user(update: Update, context: CallbackContext) -> Optional[dict]:
    """Get user from database or create new one if not exists"""
    user = update.effective_user
    if not user:
        return None

    db_user = get_user(user.id)
    if db_user:
        return db_user

    invited_by = None
    if context.args and len(context.args) > 0:
        invited_by = extract_referral_id(context.args[0])
        if invited_by == user.id:
            invited_by = None

    username = user.username or ""
    first_name = user.first_name or ""

    success = add_user(user.id, username, first_name, invited_by)
    if not success:
        logger.error(f"Failed to add user {user.id}")
        return None

    return get_user(user.id)


async def check_subscription(user_id: int, context: CallbackContext) -> bool:
    """Check if user is subscribed to all required channels"""
    if not REQUIRED_CHANNELS:
        return True

    try:
        for channel_name, channel_username in REQUIRED_CHANNELS.items():
            channel_username = channel_username.replace('@', '')

            try:
                chat_member = await context.bot.get_chat_member(
                    chat_id=f"@{channel_username}",
                    user_id=user_id
                )

                if chat_member.status not in ['member', 'administrator', 'creator']:
                    logger.info(f"❌ User {user_id} NOT subscribed to {channel_name}")
                    return False
                else:
                    logger.info(f"✅ User {user_id} subscribed to {channel_name}")

            except Exception as e:
                logger.error(f"Error checking channel {channel_name}: {e}")
                return False

        logger.info(f"✅ All checks passed for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Error in check_subscription: {e}")
        return False


async def get_subscription_keyboard(user_id: int, context: CallbackContext):
    """Get subscription keyboard - only shows unsubscribed channels"""
    keyboard = []
    not_subscribed = []

    for channel_name, channel_username in REQUIRED_CHANNELS.items():
        channel_username = channel_username.replace('@', '')

        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=f"@{channel_username}",
                user_id=user_id
            )

            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append((channel_name, channel_username))

        except Exception as e:
            logger.error(f"Error checking channel {channel_name}: {e}")
            not_subscribed.append((channel_name, channel_username))

    if not not_subscribed:
        return None

    for channel_name, channel_username in not_subscribed:
        keyboard.append([
            InlineKeyboardButton(
                f"📢 {channel_name}",
                url=f"https://t.me/{channel_username}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription")
    ])

    return InlineKeyboardMarkup(keyboard)


# ============ Command Handlers ============

async def start_command(update: Update, context: CallbackContext):
    """/start command handler"""
    try:
        user = update.effective_user
        user_id = user.id

        # Check subscription
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)

            if keyboard is None:
                # User subscribed to all
                db_user = await get_or_create_user(update, context)
                if not db_user:
                    await update.message.reply_text("❌ Xatolik yuz berdi.")
                    return

                welcome_text = (
                    f"👋 Assalomu alaykum, {user.first_name}!\n"
                    f"📱 Telegram Referral Botga xush kelibsiz!\n\n"
                    f"💡 Botdan foydalanish uchun quyidagi tugmalardan foydalaning:"
                )

                if is_admin(user_id):
                    await update.message.reply_text(
                        welcome_text,
                        reply_markup=get_admin_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        welcome_text,
                        reply_markup=get_main_keyboard()
                    )
            else:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
                text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return

        # User is subscribed
        db_user = await get_or_create_user(update, context)
        if not db_user:
            await update.message.reply_text("❌ Xatolik yuz berdi.")
            return

        referral_message = ""
        if db_user.get("invited_by"):
            referrer = get_user(db_user["invited_by"])
            if referrer:
                referral_message = f"\n\n👤 Siz {referrer.get('first_name', '')} tomonidan taklif qilindingiz!"

        welcome_text = (
            f"👋 Assalomu alaykum, {user.first_name}!\n"
            f"📱 Telegram Referral Botga xush kelibsiz!{referral_message}\n\n"
            f"💡 Botdan foydalanish uchun quyidagi tugmalardan foydalaning:"
        )

        if is_admin(user_id):
            await update.message.reply_text(
                welcome_text,
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                welcome_text,
                reply_markup=get_main_keyboard()
            )

        logger.info(f"User {user.id} started the bot")

    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def subscription_callback(update: Update, context: CallbackContext):
    """Handle subscription check callback"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Check subscription
    if await check_subscription(user_id, context):
        # User is subscribed
        db_user = get_user(user_id)
        if not db_user:
            user = query.from_user
            username = user.username or ""
            first_name = user.first_name or ""
            add_user(user_id, username, first_name, None)

        if is_admin(user_id):
            await query.edit_message_text(
                "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n"
                "📱 Botdan foydalanishni boshlang.",
                parse_mode="HTML",
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text(
                "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n"
                "📱 Botdan foydalanishni boshlang.",
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )

        logger.info(f"✅ User {user_id} subscribed to all channels")
    else:
        # User not subscribed
        keyboard = await get_subscription_keyboard(user_id, context)

        if keyboard is None:
            # All subscribed
            db_user = get_user(user_id)
            if not db_user:
                user = query.from_user
                username = user.username or ""
                first_name = user.first_name or ""
                add_user(user_id, username, first_name, None)

            if is_admin(user_id):
                await query.edit_message_text(
                    "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n"
                    "📱 Botdan foydalanishni boshlang.",
                    parse_mode="HTML",
                    reply_markup=get_admin_keyboard()
                )
            else:
                await query.edit_message_text(
                    "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n"
                    "📱 Botdan foydalanishni boshlang.",
                    parse_mode="HTML",
                    reply_markup=get_main_keyboard()
                )
        else:
            text = "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmagansiz!</b>\n\n"
            text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=keyboard
            )


async def profile_handler(update: Update, context: CallbackContext):
    """Show user profile with stats"""
    try:
        user_id = update.effective_user.id

        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
                text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return

        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        referral_count = get_referral_count(user_id)

        profile_text = (
            f"👤 <b>Profil</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"👤 Ism: {db_user.get('first_name', 'Noma\'lum')}\n"
            f"💰 Coin: {db_user.get('coins', 0)}\n"
            f"👥 Referral soni: {referral_count}\n"
            f"🔗 Taklif qilgan: {db_user.get('invited_by', 'Yo\'q')}"
        )

        if is_admin(user_id):
            await update.message.reply_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                profile_text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in profile_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def referral_handler(update: Update, context: CallbackContext):
    """Show referral info and link with button"""
    try:
        user_id = update.effective_user.id

        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
                text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return

        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        referral_count = get_referral_count(user_id)
        referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

        referral_text = (
            f"🔗 <b>Referral tizimi</b>\n\n"
            f"📊 Sizning referral soningiz: <b>{referral_count}</b>\n"
            f"💰 Har bir referral uchun: <b>{REFERRAL_REWARD} coin</b>\n"
            f"💰 Jami coin: <b>{db_user.get('coins', 0)}</b>\n\n"
            f"📋 Referral linkni olish uchun tugmani bosing:"
        )

        if is_admin(user_id):
            await update.message.reply_text(
                referral_text,
                parse_mode="HTML",
                reply_markup=get_referral_keyboard()
            )
        else:
            await update.message.reply_text(
                referral_text,
                parse_mode="HTML",
                reply_markup=get_referral_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in referral_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def referral_callback_handler(update: Update, context: CallbackContext):
    """Handle referral button callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Handle back to menu
    if data == "back_to_menu":
        if is_admin(user_id):
            await query.edit_message_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_main_keyboard()
            )
        return

    # Handle copy referral link
    if data == "copy_referral_link":
        referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

        await query.edit_message_text(
            f"📋 <b>Referral link</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"📤 Linkni nusxalab, do'stlaringizga ulashing!",
            parse_mode="HTML",
            reply_markup=get_referral_link_keyboard()
        )


async def promo_handler(update: Update, context: CallbackContext):
    """Show promo prices with inline buttons"""
    try:
        user_id = update.effective_user.id

        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
                text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return

        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        user_coins = db_user.get('coins', 0)

        promo_text = (
            f"💰 <b>Promo almashtirish</b>\n\n"
            f"💎 Sizda <b>{user_coins}</b> coin bor.\n\n"
            f"📌 Quyidagi promolardan birini tanlang:\n\n"
        )

        for name, coins_needed in PROMO_PRICES.items():
            promo_text += f"🎫 {name} — <b>{coins_needed} coin</b>\n"

        if is_admin(user_id):
            await update.message.reply_text(
                promo_text,
                parse_mode="HTML",
                reply_markup=get_promo_keyboard()
            )
        else:
            await update.message.reply_text(
                promo_text,
                parse_mode="HTML",
                reply_markup=get_promo_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in promo_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def promo_callback_handler(update: Update, context: CallbackContext):
    """Handle promo button callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Handle back to menu
    if data == "back_to_menu":
        if is_admin(user_id):
            await query.edit_message_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_main_keyboard()
            )
        return

    # Handle promo selection
    if data.startswith("promo_"):
        promo_name = data.replace("promo_", "")

        if promo_name not in PROMO_PRICES:
            await query.edit_message_text("❌ Noto'g'ri promo tanlandi.")
            return

        coins_needed = PROMO_PRICES[promo_name]

        db_user = get_user(user_id)
        if not db_user:
            await query.edit_message_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return

        user_coins = db_user.get('coins', 0)

        if user_coins < coins_needed:
            await query.edit_message_text(
                f"❌ Coinlaringiz yetarli emas!\n\n"
                f"💰 Sizda: {user_coins} coin\n"
                f"💰 Kerak: {coins_needed} coin\n"
                f"💰 Yetishmayapti: {coins_needed - user_coins} coin",
                reply_markup=get_promo_keyboard()
            )
            return

        new_coins = user_coins - coins_needed
        update_user_coins(user_id, new_coins)

        promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

        await query.edit_message_text(
            f"✅ <b>Promo muvaffaqiyatli almashtirildi!</b>\n\n"
            f"📌 Promo: {promo_name}\n"
            f"💰 Sarflangan coin: {coins_needed}\n"
            f"💎 Qolgan coin: {new_coins}\n\n"
            f"🎫 <b>Promo kodingiz:</b>\n"
            f"<code>{promo_code}</code>\n\n"
            f"📝 Promo kodni saqlab qo'ying!",
            parse_mode="HTML",
            reply_markup=get_promo_keyboard()
        )

        logger.info(f"User {user_id} exchanged {coins_needed} coins for {promo_name}")


async def rating_handler(update: Update, context: CallbackContext):
    """Show top 10 users by referrals and coins"""
    try:
        user_id = update.effective_user.id

        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n"
                text += "⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"

                await update.message.reply_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            return

        top_referrals = get_top_referrals(10)
        top_coins = get_top_coins(10)

        rating_text = "🏆 <b>Reyting</b>\n\n"

        rating_text += "<b>📊 Top 10 Referral:</b>\n"
        if top_referrals:
            for idx, user in enumerate(top_referrals, 1):
                name = user.get('first_name', 'Noma\'lum')
                referrals = user.get('referrals', 0)
                rating_text += f"{idx}. {name} — {referrals} ta\n"
        else:
            rating_text += "Hali referral yo'q\n"

        rating_text += "\n<b>💰 Top 10 Coin:</b>\n"
        if top_coins:
            for idx, user in enumerate(top_coins, 1):
                name = user.get('first_name', 'Noma\'lum')
                coins = user.get('coins', 0)
                rating_text += f"{idx}. {name} — {coins} coin\n"
        else:
            rating_text += "Hali coin yo'q\n"

        if is_admin(user_id):
            await update.message.reply_text(
                rating_text,
                parse_mode="HTML",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                rating_text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in rating_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def help_handler(update: Update, context: CallbackContext):
    """Show help information"""
    try:
        help_text = (
            "❓ <b>Yordam</b>\n\n"
            "📌 <b>Bot haqida:</b>\n"
            "Bu bot referral tizimi orqali do'stlaringizni taklif qilish va coin yig'ish uchun.\n\n"
            "🔗 <b>Referral link:</b>\n"
            "Do'stingizni taklif qilish uchun Referral tugmasini bosing.\n\n"
            "💰 <b>Coin:</b>\n"
            "Har bir taklif qilgan do'stingiz uchun coin olasiz.\n\n"
            "💎 <b>Promo almashtirish:</b>\n"
            "Promo tugmasini bosing va kerakli promoni tanlang.\n\n"
            "📊 <b>Reyting:</b>\n"
            "Eng ko'p referral va coin yig'gan foydalanuvchilarni ko'rsatadi.\n\n"
            "👤 <b>Profil:</b>\n"
            "O'zingizning statistikingizni ko'rish uchun."
        )

        user_id = update.effective_user.id
        if is_admin(user_id):
            await update.message.reply_text(
                help_text,
                parse_mode="HTML",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                help_text,
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )

    except Exception as e:
        logger.error(f"Error in help_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def back_handler(update: Update, context: CallbackContext):
    """Back to main menu"""
    try:
        user_id = update.effective_user.id
        if is_admin(user_id):
            await update.message.reply_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                "📱 Asosiy menyuga qaytdingiz",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in back_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


# ============ ADMIN HANDLERS ============

async def admin_panel_handler(update: Update, context: CallbackContext):
    """Admin panelni ko'rsatish"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return

        text = (
            "👑 <b>Admin Panel</b>\n\n"
            "📊 Statistika - Bot statistikasini ko'rish\n"
            "💰 Coin berish - Foydalanuvchilarga coin berish/olish\n"
            "📢 Xabar yuborish - Barcha foydalanuvchilarga xabar yuborish\n"
            "👥 Foydalanuvchilar - Foydalanuvchilar ro'yxati"
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in admin_panel_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_stats_handler(update: Update, context: CallbackContext):
    """Statistika ko'rsatish"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(coins) FROM users")
            total_coins = cursor.fetchone()[0] or 0

            cursor.execute("SELECT SUM(referrals) FROM users")
            total_referrals = cursor.fetchone()[0] or 0

            cursor.execute("""
                SELECT COUNT(*) FROM users 
                WHERE DATE(created_at) = DATE('now')
            """)
            today_users = cursor.fetchone()[0]

        text = (
            f"📊 <b>Bot statistikasi</b>\n\n"
            f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
            f"💰 Jami coin: <b>{total_coins}</b>\n"
            f"🔗 Jami referral: <b>{total_referrals}</b>\n"
            f"📅 Bugun kelganlar: <b>{today_users}</b>"
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in admin_stats_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_coin_handler(update: Update, context: CallbackContext):
    """Coin berish paneli"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return

        text = (
            "💰 <b>Coin berish/olish</b>\n\n"
            "Foydalanuvchiga coin berish yoki olish uchun:\n"
            "<code>/coin 123456789 50</code> - coin berish\n"
            "<code>/coin 123456789 -50</code> - coin olish\n\n"
            "Yoki quyidagi tugmalardan foydalaning:"
        )

        await update.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_coin_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in admin_coin_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_coin_callback_handler(update: Update, context: CallbackContext):
    """Coin tugmalarini boshqarish"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.edit_message_text("❌ Siz admin emassiz!")
        return

    data = query.data

    if data == "admin_back":
        await query.edit_message_text(
            "👑 Admin panel",
            reply_markup=get_admin_keyboard()
        )
        return

    coin_map = {
        "add_10": 10,
        "add_50": 50,
        "add_100": 100,
        "sub_10": -10,
        "sub_50": -50,
        "sub_100": -100
    }

    if data in coin_map:
        context.user_data['pending_coin'] = coin_map[data]
        await query.edit_message_text(
            f"💰 {coin_map[data]} coin {'berish' if coin_map[data] > 0 else 'olish'}\n\n"
            f"Foydalanuvchi ID sini yozing:\n"
            f"<code>/coin ID</code>\n\n"
            f"Misol: <code>/coin 123456789</code>",
            parse_mode="HTML",
            reply_markup=get_admin_coin_keyboard()
        )


async def admin_coin_command_handler(update: Update, context: CallbackContext):
    """/coin buyrug'i - coin berish/olish"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return

        args = context.args

        if len(args) < 2:
            await update.message.reply_text(
                "❌ Noto'g'ri format!\n"
                "<code>/coin 123456789 50</code> - coin berish\n"
                "<code>/coin 123456789 -50</code> - coin olish",
                parse_mode="HTML"
            )
            return

        target_id = int(args[0])
        amount = int(args[1])

        db_user = get_user(target_id)
        if not db_user:
            await update.message.reply_text(f"❌ {target_id} ID li foydalanuvchi topilmadi!")
            return

        current_coins = db_user.get('coins', 0)
        new_coins = current_coins + amount

        if new_coins < 0:
            await update.message.reply_text(
                f"❌ Foydalanuvchida yetarli coin yo'q!\n"
                f"💰 Joriy coin: {current_coins}"
            )
            return

        update_user_coins(target_id, new_coins)

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"{'✅' if amount > 0 else '❌'} Admin tomonidan "
                    f"{'berildi' if amount > 0 else 'olindi'}: <b>{abs(amount)} coin</b>\n"
                    f"💰 Joriy coin: <b>{new_coins}</b>"
                ),
                parse_mode="HTML"
            )
        except:
            pass

        await update.message.reply_text(
            f"✅ {target_id} ID li foydalanuvchiga {amount} coin {'berildi' if amount > 0 else 'olindi'}!\n"
            f"💰 Joriy coin: {new_coins}",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in admin_coin_command_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_broadcast_handler(update: Update, context: CallbackContext):
    """Xabar yuborish (broadcast)"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return

        context.user_data['broadcast'] = True
        await update.message.reply_text(
            "📢 <b>Xabar yuborish</b>\n\n"
            "Yubormoqchi bo'lgan xabaringizni yozing:\n"
            "💡 <i>Barcha foydalanuvchilarga yuboriladi</i>\n\n"
            "❌ Bekor qilish uchun /cancel deb yozing",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )

    except Exception as e:
        logger.error(f"Error in admin_broadcast_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_broadcast_send(update: Update, context: CallbackContext):
    """Xabarni yuborish"""
    try:
        user_id = update.effective_user.id

        if not is_admin(user_id):
            return

        if not context.user_data.get('broadcast'):
            return

        text = update.message.text

        if text == "/cancel":
            context.user_data['broadcast'] = False
            await update.message.reply_text(
                "❌ Xabar yuborish bekor qilindi",
                reply_markup=get_admin_keyboard()
            )
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id FROM users")
            users = cursor.fetchall()

        if not users:
            await update.message.reply_text("❌ Hech qanday foydalanuvchi yo'q!")
            return

        sent = 0
        failed = 0

        progress_msg = await update.message.reply_text(
            f"⏳ Xabar yuborilmoqda... 0/{len(users)}"
        )

        for i, user in enumerate(users):
            try:
                await context.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=text,
                    parse_mode="HTML"
                )
                sent += 1
            except:
                failed += 1

            if i % 10 == 0:
                await progress_msg.edit_text(
                    f"⏳ Xabar yuborilmoqda... {i+1}/{len(users)}"
                )

        await
