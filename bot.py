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

from config import BOT_TOKEN, REFERRAL_REWARD, PROMO_PRICES, BOT_USERNAME, REQUIRED_CHANNELS
from database import (
    init_database,
    add_user,
    get_user,
    get_top_referrals,
    get_top_coins,
    update_user_coins,
    get_referral_count,
)
from buttons import (
    get_main_keyboard, 
    get_promo_keyboard, 
    get_referral_keyboard,
    get_referral_link_keyboard
)

# 24/7 uchun keep_alive
from keep_alive import keep_alive

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
        await query.edit_message_text(
            "📱 Asosiy menyuga qaytdingiz",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Handle copy referral link
    if data == "copy_referral_link":
        referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        
        # Faqat linkni ko'rsatish - nusxalash uchun
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
        
        # Promo ro'yxati - ✅ belgisisiz
        for name, coins_needed in PROMO_PRICES.items():
            promo_text += f"🎫 {name} — <b>{coins_needed} coin</b>\n"
        
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
        
        # Deduct coins
        new_coins = user_coins - coins_needed
        update_user_coins(user_id, new_coins)
        
        # Generate promo code
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
        
        await update.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error in help_handler: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")


async def unknown_handler(update: Update, context: CallbackContext):
    """Handle unknown commands"""
    try:
        await update.message.reply_text(
            "❌ Noma'lum buyruq. Iltimos, tugmalardan foydalaning.",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in unknown_handler: {e}")


# ============ Main Function ============

def main():
    """Main function to run the bot"""
    try:
        # Database ni ishga tushirish
        init_database()
        logger.info("Database initialized")
        
        # ⭐ 24/7 uchun web server (Render da ishlaydi)
        keep_alive()
        logger.info("Keep-alive server started")
        
        # Application yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Command handlers
        application.add_handler(CommandHandler("start", start_command))
        
        # Callback query handlers
        application.add_handler(CallbackQueryHandler(subscription_callback, pattern="check_subscription"))
        application.add_handler(CallbackQueryHandler(referral_callback_handler, pattern="^(copy_referral_link|back_to_menu)"))
        application.add_handler(CallbackQueryHandler(promo_callback_handler, pattern="^(promo_|back_to_menu)"))
        
        # Message handlers
        application.add_handler(MessageHandler(filters.Regex("^👤 Profil$"), profile_handler))
        application.add_handler(MessageHandler(filters.Regex("^🔗 Referral$"), referral_handler))
        application.add_handler(MessageHandler(filters.Regex("^💰 Promo$"), promo_handler))
        application.add_handler(MessageHandler(filters.Regex("^🏆 Reyting$"), rating_handler))
        application.add_handler(MessageHandler(filters.Regex("^❓ Yordam$"), help_handler))
        
        # Unknown handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_handler))
        
        logger.info("Bot started...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    main()