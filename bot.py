# -*- coding: utf-8 -*-

import logging
import random
import string
import asyncio
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

try:
    from keep_alive import keep_alive
except ImportError:
    keep_alive = None

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def extract_referral_id(text: str) -> Optional[int]:
    if not text or not text.startswith("start="):
        return None
    try:
        return int(text.split("=")[1])
    except (ValueError, IndexError):
        return None


async def get_or_create_user(update: Update, context: CallbackContext) -> Optional[dict]:
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
    if not REQUIRED_CHANNELS:
        return True
    
    for channel_name, channel_username in REQUIRED_CHANNELS.items():
        channel_username = channel_username.replace('@', '')
        try:
            chat_member = await context.bot.get_chat_member(
                chat_id=f"@{channel_username}",
                user_id=user_id
            )
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking channel {channel_name}: {e}")
            return False
    
    return True


async def get_subscription_keyboard(user_id: int, context: CallbackContext):
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
        keyboard.append([InlineKeyboardButton(f"📢 {channel_name}", url=f"https://t.me/{channel_username}")])
    
    keyboard.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: CallbackContext):
    try:
        user = update.effective_user
        user_id = user.id
        
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
                return
        
        db_user = await get_or_create_user(update, context)
        if not db_user:
            await update.message.reply_text("❌ Xatolik yuz berdi.")
            return
        
        referral_message = ""
        if db_user.get("invited_by"):
            referrer = get_user(db_user["invited_by"])
            if referrer:
                referral_message = f"\n\n👤 Siz {referrer.get('first_name', '')} tomonidan taklif qilindingiz!"
        
        welcome_text = f"👋 Assalomu alaykum, {user.first_name}!\n📱 Telegram Referral Botga xush kelibsiz!{referral_message}\n\n💡 Botdan foydalanish uchun quyidagi tugmalardan foydalaning:"
        
        if is_admin(user_id):
            await update.message.reply_text(welcome_text, reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
        
        logger.info(f"User {user.id} started the bot")
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def subscription_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if await check_subscription(user_id, context):
        user = query.from_user
        db_user = get_user(user_id)
        if not db_user:
            username = user.username or ""
            first_name = user.first_name or ""
            add_user(user_id, username, first_name, None)
        
        if is_admin(user_id):
            await query.edit_message_text(
                "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n📱 Botdan foydalanishni boshlang.", 
                parse_mode="HTML", 
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text(
                "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n📱 Botdan foydalanishni boshlang.", 
                parse_mode="HTML", 
                reply_markup=get_main_keyboard()
            )
    else:
        keyboard = await get_subscription_keyboard(user_id, context)
        if keyboard is None:
            if is_admin(user_id):
                await query.edit_message_text(
                    "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n📱 Botdan foydalanishni boshlang.", 
                    parse_mode="HTML", 
                    reply_markup=get_admin_keyboard()
                )
            else:
                await query.edit_message_text(
                    "✅ <b>Siz barcha kanallarga muvaffaqiyatli obuna bo'ldingiz!</b>\n\n📱 Botdan foydalanishni boshlang.", 
                    parse_mode="HTML", 
                    reply_markup=get_main_keyboard()
                )
        else:
            text = "❌ <b>Siz hali quyidagi kanallarga obuna bo'lmagansiz!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def profile_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
            return
        
        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return
        
        referral_count = get_referral_count(user_id)
        profile_text = f"👤 <b>Profil</b>\n\n🆔 ID: <code>{user_id}</code>\n👤 Ism: {db_user.get('first_name', 'Noma\'lum')}\n💰 Coin: {db_user.get('coins', 0)}\n👥 Referral soni: {referral_count}\n🔗 Taklif qilgan: {db_user.get('invited_by', 'Yo\'q')}"
        
        if is_admin(user_id):
            await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in profile_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def referral_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
            return
        
        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return
        
        referral_count = get_referral_count(user_id)
        referral_text = f"🔗 <b>Referral tizimi</b>\n\n📊 Sizning referral soningiz: <b>{referral_count}</b>\n💰 Har bir referral uchun: <b>{REFERRAL_REWARD} coin</b>\n💰 Jami coin: <b>{db_user.get('coins', 0)}</b>\n\n📋 Referral linkni olish uchun tugmani bosing:"
        
        await update.message.reply_text(referral_text, parse_mode="HTML", reply_markup=get_referral_keyboard())
    except Exception as e:
        logger.error(f"Error in referral_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def referral_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "back_to_menu":
        if is_admin(user_id):
            await query.edit_message_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_admin_keyboard())
        else:
            await query.edit_message_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_main_keyboard())
        return
    
    if data == "copy_referral_link":
        referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        await query.edit_message_text(
            f"📋 <b>Referral link</b>\n\n<code>{referral_link}</code>\n\n📤 Linkni nusxalab, do'stlaringizga ulashing!", 
            parse_mode="HTML", 
            reply_markup=get_referral_link_keyboard()
        )


async def promo_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
            return
        
        db_user = get_user(user_id)
        if not db_user:
            await update.message.reply_text("❌ Siz ro'yxatdan o'tmagansiz. /start bosing.")
            return
        
        user_coins = db_user.get('coins', 0)
        promo_text = f"💰 <b>Promo almashtirish</b>\n\n💎 Sizda <b>{user_coins}</b> coin bor.\n\n📌 Quyidagi promolardan birini tanlang:\n\n"
        
        for name, coins_needed in PROMO_PRICES.items():
            promo_text += f"🎫 {name} — <b>{coins_needed} coin</b>\n"
        
        await update.message.reply_text(promo_text, parse_mode="HTML", reply_markup=get_promo_keyboard())
    except Exception as e:
        logger.error(f"Error in promo_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def promo_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "back_to_menu":
        if is_admin(user_id):
            await query.edit_message_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_admin_keyboard())
        else:
            await query.edit_message_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_main_keyboard())
        return
    
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
                f"❌ Coinlaringiz yetarli emas!\n\n💰 Sizda: {user_coins} coin\n💰 Kerak: {coins_needed} coin\n💰 Yetishmayapti: {coins_needed - user_coins} coin", 
                reply_markup=get_promo_keyboard()
            )
            return
        
        new_coins = user_coins - coins_needed
        update_user_coins(user_id, new_coins)
        promo_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        await query.edit_message_text(
            f"✅ <b>Promo muvaffaqiyatli almashtirildi!</b>\n\n📌 Promo: {promo_name}\n💰 Sarflangan coin: {coins_needed}\n💎 Qolgan coin: {new_coins}\n\n🎫 <b>Promo kodingiz:</b>\n<code>{promo_code}</code>\n\n📝 Promo kodni saqlab qo'ying!", 
            parse_mode="HTML", 
            reply_markup=get_promo_keyboard()
        )
        logger.info(f"User {user_id} exchanged {coins_needed} coins for {promo_name}")


async def rating_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        
        if not await check_subscription(user_id, context):
            keyboard = await get_subscription_keyboard(user_id, context)
            if keyboard:
                text = "🔒 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!</b>\n\n⬇️ Kanallarga obuna bo'ling va ✅ tugmasini bosing:\n"
                await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
            return
        
        top_referrals = get_top_referrals(10)
        top_coins = get_top_coins(10)
        
        rating_text = "🏆 <b>Reyting</b>\n\n<b>📊 Top 10 Referral:</b>\n"
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
            await update.message.reply_text(rating_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text(rating_text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in rating_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def help_handler(update: Update, context: CallbackContext):
    try:
        help_text = "❓ <b>Yordam</b>\n\n📌 <b>Bot haqida:</b>\nBu bot referral tizimi orqali do'stlaringizni taklif qilish va coin yig'ish uchun.\n\n🔗 <b>Referral link:</b>\nDo'stingizni taklif qilish uchun Referral tugmasini bosing.\n\n💰 <b>Coin:</b>\nHar bir taklif qilgan do'stingiz uchun coin olasiz.\n\n💎 <b>Promo almashtirish:</b>\nPromo tugmasini bosing va kerakli promoni tanlang.\n\n📊 <b>Reyting:</b>\nEng ko'p referral va coin yig'gan foydalanuvchilarni ko'rsatadi.\n\n👤 <b>Profil:</b>\nO'zingizning statistikingizni ko'rish uchun."
        
        user_id = update.effective_user.id
        if is_admin(user_id):
            await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text(help_text, parse_mode="HTML", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in help_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def back_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if is_admin(user_id):
            await update.message.reply_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("📱 Asosiy menyuga qaytdingiz", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in back_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_panel_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return
        
        text = "👑 <b>Admin Panel</b>\n\n📊 Statistika - Bot statistikasini ko'rish\n💰 Coin berish - Foydalanuvchilarga coin berish/olish\n📢 Xabar yuborish - Barcha foydalanuvchilarga xabar yuborish\n👥 Foydalanuvchilar - Foydalanuvchilar ro'yxati"
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Error in admin_panel_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_stats_handler(update: Update, context: CallbackContext):
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
            cursor.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = DATE('now')")
            today_users = cursor.fetchone()[0]
        
        text = f"📊 <b>Bot statistikasi</b>\n\n👥 Jami foydalanuvchilar: <b>{total_users}</b>\n💰 Jami coin: <b>{total_coins}</b>\n🔗 Jami referral: <b>{total_referrals}</b>\n📅 Bugun kelganlar: <b>{today_users}</b>"
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Error in admin_stats_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_coin_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return
        
        text = "💰 <b>Coin berish/olish</b>\n\nFoydalanuvchiga coin berish yoki olish uchun:\n<code>/coin 123456789 50</code> - coin berish\n<code>/coin 123456789 -50</code> - coin olish\n\nYoki quyidagi tugmalardan foydalaning:"
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_admin_coin_keyboard())
    except Exception as e:
        logger.error(f"Error in admin_coin_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_coin_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ Siz admin emassiz!")
        return
    
    data = query.data
    if data == "admin_back":
        await query.edit_message_text("👑 Admin panel", reply_markup=get_admin_keyboard())
        return
    
    coin_map = {"add_10": 10, "add_50": 50, "add_100": 100, "sub_10": -10, "sub_50": -50, "sub_100": -100}
    if data in coin_map:
        context.user_data['pending_coin'] = coin_map[data]
        await query.edit_message_text(
            f"💰 {coin_map[data]} coin {'berish' if coin_map[data] > 0 else 'olish'}\n\nFoydalanuvchi ID sini yozing:\n<code>/coin ID</code>\n\nMisol: <code>/coin 123456789</code>", 
            parse_mode="HTML", 
            reply_markup=get_admin_coin_keyboard()
        )


async def admin_coin_command_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Noto'g'ri format!\n<code>/coin 123456789 50</code> - coin berish\n<code>/coin 123456789 -50</code> - coin olish", 
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
            await update.message.reply_text(f"❌ Foydalanuvchida yetarli coin yo'q!\n💰 Joriy coin: {current_coins}")
            return
        
        update_user_coins(target_id, new_coins)
        
        try:
            await context.bot.send_message(
                chat_id=target_id, 
                text=f"{'✅' if amount > 0 else '❌'} Admin tomonidan {'berildi' if amount > 0 else 'olindi'}: <b>{abs(amount)} coin</b>\n💰 Joriy coin: <b>{new_coins}</b>", 
                parse_mode="HTML"
            )
        except:
            pass
        
        await update.message.reply_text(
            f"✅ {target_id} ID li foydalanuvchiga {amount} coin {'berildi' if amount > 0 else 'olindi'}!\n💰 Joriy coin: {new_coins}", 
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in admin_coin_command_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_broadcast_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return
        
        context.user_data['broadcast'] = True
        await update.message.reply_text(
            "📢 <b>Xabar yuborish</b>\n\nYubormoqchi bo'lgan xabaringizni yozing:\n💡 <i>Barcha foydalanuvchilarga yuboriladi</i>\n\n❌ Bekor qilish uchun /cancel deb yozing", 
            parse_mode="HTML", 
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in admin_broadcast_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_broadcast_send(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            return
        
        if not context.user_data.get('broadcast'):
            return
        
        text = update.message.text
        if text == "/cancel":
            context.user_data['broadcast'] = False
            await update.message.reply_text("❌ Xabar yuborish bekor qilindi", reply_markup=get_admin_keyboard())
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
        progress_msg = await update.message.reply_text(f"⏳ Xabar yuborilmoqda... 0/{len(users)}")
        
        for i, user in enumerate(users):
            try:
                await context.bot.send_message(chat_id=user['telegram_id'], text=text, parse_mode="HTML")
                sent += 1
            except:
                failed += 1
            
            if i % 10 == 0:
                await progress_msg.edit_text(f"⏳ Xabar yuborilmoqda... {i+1}/{len(users)}")
        
        await progress_msg.edit_text(
            f"✅ Xabar yuborildi!\n\n📤 Yuborildi: {sent}\n❌ Yuborilmadi: {failed}\n👥 Jami: {len(users)}", 
            reply_markup=get_admin_keyboard()
        )
        context.user_data['broadcast'] = False
    except Exception as e:
        logger.error(f"Error in admin_broadcast_send: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def admin_users_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if not is_admin(user_id):
            await update.message.reply_text("❌ Siz admin emassiz!")
            return
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_id, username, first_name, coins, referrals, created_at FROM users ORDER BY created_at DESC LIMIT 20")
            users = cursor.fetchall()
        
        if not users:
            await update.message.reply_text("❌ Hech qanday foydalanuvchi yo'q!")
            return
        
        text = "👥 <b>Oxirgi 20 foydalanuvchi</b>\n\n"
        for user in users:
            name = user.get('first_name', 'Noma\'lum')[:15]
            text += f"🆔 {user['telegram_id']}\n👤 {name}\n💰 {user['coins']} coin | 🔗 {user['referrals']} referral\n📅 {user['created_at'][:10]}\n{'─'*20}\n"
        
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"Error in admin_users_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def unknown_handler(update: Update, context: CallbackContext):
    try:
        user_id = update.effective_user.id
        if is_admin(user_id):
            await update.message.reply_text("❌ Noma'lum buyruq. Iltimos, tugmalardan foydalaning.", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("❌ Noma'lum buyruq. Iltimos, tugmalardan foydalaning.", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Error in unknown_handler: {e}")


# ============ MAIN ============
async def main():
    try:
        init_database()
        logger.info("Database initialized")
        
        if keep_alive:
            try:
                keep_alive()
                logger.info("Keep-alive server started")
            except Exception as e:
                logger.error(f"Keep-alive error: {e}")
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("coin", admin_coin_command_handler))
        
        application.add_handler(CallbackQueryHandler(subscription_callback, pattern="^check_subscription$"))
        application.add_handler(CallbackQueryHandler(referral_callback_handler, pattern="^(copy_referral_link|back_to_menu)$"))
        application.add_handler(CallbackQueryHandler(promo_callback_handler, pattern="^(promo_|back_to_menu)$"))
        application.add_handler(CallbackQueryHandler(admin_coin_callback_handler, pattern="^(add_|sub_|admin_back)$"))
        
        application.add_handler(MessageHandler(filters.Regex("^👤 Profil$"), profile_handler))
        application.add_handler(MessageHandler(filters.Regex("^🔗 Referral$"), referral_handler))
        application.add_handler(MessageHandler(filters.Regex("^💰 Promo$"), promo_handler))
        application.add_handler(MessageHandler(filters.Regex("^🏆 Reyting$"), rating_handler))
        application.add_handler(MessageHandler(filters.Regex("^❓ Yordam$"), help_handler))
        
        application.add_handler(MessageHandler(filters.Regex("^👑 Admin$"), admin_panel_handler))
        application.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"), admin_stats_handler))
        application.add_handler(MessageHandler(filters.Regex("^💰 Coin berish$"), admin_coin_handler))
        application.add_handler(MessageHandler(filters.Regex("^📢 Xabar yuborish$"), admin_broadcast_handler))
        application.add_handler(MessageHandler(filters.Regex("^👥 Foydalanuvchilar$"), admin_users_handler))
        application.add_handler(MessageHandler(filters.Regex("^🔙 Asosiy menyu$"), back_handler))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_send))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_handler))
        
        logger.info("Bot started...")
        await application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Botni ishga tushirishda xatolik: {e}")
