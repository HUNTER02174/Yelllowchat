import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

ADMIN_ID = 6447881580          # آیدی عددی ادمین
REQUIRED_CHANNELS = ["@wilililill", "@Yelllowchat"] # لیست کانال‌ها

# --- تابع کمکی ساخت کد یکسان ---
def generate_user_code(user_id):
    s_id = str(user_id)
    return s_id[-8:] if len(s_id) >= 8 else s_id.zfill(8)

# --- بخش مدیریت دیتابیس SQLite ---
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        code TEXT,
                        username TEXT,
                        first_name TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS blocks (
                        blocker_id INTEGER,
                        blocked_code TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS stats (
                        id INTEGER PRIMARY KEY,
                        msg_count INTEGER)''')
    cursor.execute('INSERT OR IGNORE INTO stats (id, msg_count) VALUES (1, 0)')
    conn.commit()
    conn.close()

def save_or_update_user(user):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    code = generate_user_code(user.id)
    uname = user.username if user.username else "ندارد"
    fname = user.first_name if user.first_name else "نامشخص"
    
    cursor.execute('INSERT OR REPLACE INTO users (user_id, code, username, first_name) VALUES (?, ?, ?, ?)',
                   (user.id, code, uname, fname))
    conn.commit()
    conn.close()
    return code

def get_user_by_code(code):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users WHERE code = ?', (str(code),))
    res = cursor.fetchone()
    conn.close()
    return res

def is_blocked(blocker_id, sender_code):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM blocks WHERE blocker_id = ? AND blocked_code = ?', (blocker_id, str(sender_code)))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def add_block(blocker_id, blocked_code):
    if not is_blocked(blocker_id, blocked_code):
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO blocks (blocker_id, blocked_code) VALUES (?, ?)', (blocker_id, str(blocked_code)))
        conn.commit()
        conn.close()

def remove_block(blocker_id, blocked_code):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocks WHERE blocker_id = ? AND blocked_code = ?', (blocker_id, str(blocked_code)))
    conn.commit()
    conn.close()

def get_user_blocks(blocker_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT blocked_code FROM blocks WHERE blocker_id = ?', (blocker_id,))
    res = [row[0] for row in cursor.fetchall()]
    conn.close()
    return res

def increment_msg_count():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE stats SET msg_count = msg_count + 1 WHERE id = 1')
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT msg_count FROM stats WHERE id = 1')
    msg_count = cursor.fetchone()[0]
    conn.close()
    return total_users, msg_count

# --- منطق اصلی ربات ---
user_states = {}

async def check_all_memberships(user_id, context):
    if user_id == ADMIN_ID:
        return True
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

async def get_join_keyboard():
    keyboard = []
    for channel in REQUIRED_CHANNELS:
        ch_cleaned = channel.replace('@', '')
        keyboard.append([InlineKeyboardButton(f"عضویت در کانال {channel} 📢", url=f"https://t.me/{ch_cleaned}")])
    keyboard.append([InlineKeyboardButton("عضو شدم ✅", callback_data="check_join")])
    return InlineKeyboardMarkup(keyboard)

async def post_init(application):
    init_db()
    user_commands = [
        BotCommand("start", "🚀 شروع و منوی اصلی"),
        BotCommand("help", "❓ راهنمای استفاده از ربات")
    ]
    await application.bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())

    admin_commands = [
        BotCommand("start", "🚀 شروع و منوی اصلی"),
        BotCommand("help", "❓ راهنمای استفاده از ربات"),
        BotCommand("info", "🔍 استعلام هویت کاربر با کد")
    ]
    try:
        await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as e:
        print(f"تنظیم دستورات ادمین با خطا مواجه شد: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    sender_code = save_or_update_user(user)
    args = context.args

    if args and args[0]:
        target_code = args[0]
        if target_code != sender_code:
            user_states[user_id] = {'action': 'sending_anonymous', 'target_code': target_code}

    if not await check_all_memberships(user_id, context):
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات، ابتدا باید در تمام کانال‌های زیر عضو شوید:",
            reply_markup=await get_join_keyboard()
        )
        return

    state = user_states.get(user_id, {})
    if state.get('action') == 'sending_anonymous':
        target_code = state.get('target_code')
        target = get_user_by_code(target_code)
        
        if not target:
            await update.message.reply_text("❌ کاربر مورد نظر پیدا نشد یا کد اشتباه است.")
            user_states.pop(user_id, None)
            return

        if is_blocked(target[0], sender_code):
            await update.message.reply_text("❌ متاسفانه این کاربر شما را مسدود کرده است.")
            user_states.pop(user_id, None)
            return
        
        await update.message.reply_text("✍️ پیام، عکس، ویس، گیف یا استیکر ناشناس خود را بفرستید:")
        return

    await send_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ **راهنمای استفاده از یـلو چت:**\n\n"
        "1️⃣ لینک اختصاصی خود را از منوی اصلی دریافت کنید.\n"
        "2️⃣ لینک را در بیو تلگرام یا شبکه‌های اجتماعی بگذارید.\n"
        "3️⃣ هرکس روی لینک بزند، می‌تواند به شما پیام، ویس، عکس، گیف یا استیکر ناشناس بفرستد!\n"
        "4️⃣ می‌توانید به پیام‌های دریافتی پاسخ دهید، ری‌اکشن بفرستید یا فرستنده مزاحم را بلاک کنید."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ لطفاً کد کاربر را وارد کنید.\nمثال:\n`/info 12345678`", parse_mode="Markdown")
        return

    target_code = context.args[0]
    await show_user_info_by_code(update.message, target_code)

async def show_user_info_by_code(message_obj, target_code: str):
    target = get_user_by_code(target_code)
    if not target:
        await message_obj.reply_text(f"❌ کاربر با کد `{target_code}` در دیتابیس یافت نشد.", parse_mode="Markdown")
        return

    target_id, uname, fname = target
    uname_str = f"@{uname}" if uname != "ندارد" else "ندارد"

    res = (
        f"🔍 **اطلاعات واقعی کاربر با کد `{target_code}`:**\n\n"
        f"👤 **نام واقعی:** {fname}\n"
        f"🆔 **یوزرنیم:** {uname_str}\n"
        f"🔢 **آیدی عددی:** `{target_id}`"
    )
    await message_obj.reply_text(res, parse_mode="Markdown")

async def send_main_menu(update_or_query, context):
    user = update_or_query.effective_user
    user_id = user.id
    sender_code = save_or_update_user(user)
    total_users, _ = get_stats()

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🔗 لینک ناشناس من", callback_data="get_link")],
            [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats"), InlineKeyboardButton("📢 پیام همگانی", callback_data="start_broadcast")]
        ]
        text = f"👑 **پنل مدیریت یـلو چت**\n\nتعداد کاربران: {total_users}\nکد اختصاصی شما: `{sender_code}`"
    else:
        keyboard = [
            [InlineKeyboardButton("🔗 لینک ناشناس من", callback_data="get_link")],
            [InlineKeyboardButton("🚫 کاربران بلاک‌شده", callback_data="show_blocked"), InlineKeyboardButton("📩 پشتیبانی", callback_data="support_mode")]
        ]
        text = f"💛 به یــلو چت خوش آمدید!\n\nکد اختصاصی شما: `{sender_code}`"

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update_or_query, 'message') and update_or_query.message:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update_or_query.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    sender_code = save_or_update_user(user)

    if query.data == "check_join":
        if await check_all_memberships(user_id, context):
            try:
                await query.message.delete()
            except:
                pass
            
            state = user_states.get(user_id, {})
            if state.get('action') == 'sending_anonymous':
                await query.message.reply_text("✅ عضویت تایید شد!\n\n✍️ پیام ناشناس خود را بفرستید:")
            else:
                await send_main_menu(update, context)
        else:
            await query.answer("شما هنوز در همه کانال‌ها عضو نشده‌اید!", show_alert=True)

    elif query.data == "get_link":
        bot_info = await context.bot.get_me()
        personal_link = f"https://t.me/{bot_info.username}?start={sender_code}"
        await query.message.reply_text(f"📌 لینک ناشناس شما:\n\n{personal_link}", parse_mode="Markdown")

    elif query.data == "show_blocked":
        user_blocks = get_user_blocks(user_id)
        if not user_blocks:
            await query.message.reply_text("❕ لیست کاربران بلاک‌شده توسط شما خالی است.")
        else:
            await query.message.reply_text("🚫 **لیست کاربران بلاک‌شده توسط شما:**", parse_mode="Markdown")
            for b_code in user_blocks:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ آنبلاک کد {b_code}", callback_data=f"unblock_{b_code}")]])
                await query.message.reply_text(f"👤 کاربر با کد: `{b_code}`", reply_markup=btn, parse_mode="Markdown")

    elif query.data.startswith("unblock_"):
        target_code_to_unblock = query.data.split("unblock_")[1]
        remove_block(user_id, target_code_to_unblock)
        await query.answer("کاربر با موفقیت آنبلاک شد ✅", show_alert=True)
        try:
            await query.message.edit_text(f"✅ کاربر با کد `{target_code_to_unblock}` از مسدودی خارج شد.", parse_mode="Markdown")
        except:
            pass

    elif query.data.startswith("checkuser_"):
        if user_id == ADMIN_ID:
            code_to_check = query.data.split("checkuser_")[1]
            await show_user_info_by_code(query.message, code_to_check)
        else:
            await query.answer("این قابلیت فقط برای ادمین ربات است! ❌", show_alert=True)

    elif query.data == "admin_stats":
        if user_id == ADMIN_ID:
            tot, msgs = get_stats()
            await query.message.reply_text(f"📊 **آمار ربات:**\n\n👥 کاربران: {tot}\n💬 پیام‌ها: {msgs}", parse_mode="Markdown")

    elif query.data == "start_broadcast":
        if user_id == ADMIN_ID:
            user_states[user_id] = {'action': 'awaiting_broadcast'}
            await query.message.reply_text("✍️ پیام عمومی خود را بفرستید:")

    elif query.data.startswith("block_"):
        target_code_to_block = query.data.split("block_")[1]
        add_block(user_id, target_code_to_block)
        await query.answer("کاربر مسدود شد 🚫", show_alert=True)
        try:
            await query.message.edit_text(query.message.text + "\n\n❌ *(این کاربر توسط شما مسدود شد)*", parse_mode="Markdown")
        except:
            pass

    elif query.data.startswith("reply_"):
        if not await check_all_memberships(user_id, context):
            await query.message.reply_text("⚠️ برای ادامه باید در کانال‌ها عضو شوید:", reply_markup=await get_join_keyboard())
            return
        target_code = query.data.split("reply_")[1]
        user_states[user_id] = {'action': 'replying', 'target_code': target_code}
        await query.message.reply_text("✍️ پاسخ خود را بفرستید:")

    elif query.data.startswith("react_"):
        if not await check_all_memberships(user_id, context):
            await query.message.reply_text("⚠️ برای ادامه باید در کانال‌ها عضو شوید:", reply_markup=await get_join_keyboard())
            return
        target_code = query.data.split("react_")[1]
        keyboard = [
            [InlineKeyboardButton("❤️", callback_data=f"sendreact_❤️_{target_code}"),
             InlineKeyboardButton("😂", callback_data=f"sendreact_😂_{target_code}"),
             InlineKeyboardButton("🔥", callback_data=f"sendreact_🔥_{target_code}"),
             InlineKeyboardButton("👍", callback_data=f"sendreact_👍_{target_code}")]
        ]
        await query.message.reply_text("یک ری‌اکشن انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sendreact_"):
        parts = query.data.split("_")
        if len(parts) >= 3:
            emoji = parts[1]
            target_code = parts[2]
            target = get_user_by_code(target_code)
            if target:
                try:
                    await context.bot.send_message(chat_id=target[0], text=f"طرف مقابل به پیام شما این ری‌اکشن را نشان داد: {emoji}")
                except:
                    pass
            try:
                await query.message.edit_text(f"ری‌اکشن {emoji} ارسال شد!")
            except:
                await query.message.reply_text(f"ری‌اکشن {emoji} ارسال شد!")

    elif query.data == "support_mode":
        user_states[user_id] = {'action': 'support'}
        await query.message.reply_text("✍️ پیام خود را برای پشتیبانی بفرستید:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    sender_code = save_or_update_user(user)

    if not await check_all_memberships(user_id, context):
        await update.message.reply_text("❌ ابتدا باید در کانال‌ها عضو شوید:", reply_markup=await get_join_keyboard())
        return

    state = user_states.get(user_id, {})

    # ارسال همگانی
    if user_id == ADMIN_ID and state.get('action') == 'awaiting_broadcast':
        user_states.pop(user_id, None)
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        all_u = cursor.fetchall()
        conn.close()

        success = 0
        for u in all_u:
            try:
                await update.message.copy(chat_id=u[0])
                success += 1
            except:
                pass
        await update.message.reply_text(f"✅ پیام به {success} نفر ارسال شد.")
        return

    # ارسال پیام ناشناس و پاسخ
    if state.get('action') in ['sending_anonymous', 'replying']:
        target_code = state.get('target_code')
        target = get_user_by_code(target_code)

        if target:
            target_id = target[0]
            if is_blocked(target_id, sender_code):
                await update.message.reply_text("❌ شما توسط این کاربر بلاک شده‌اید.")
                user_states.pop(user_id, None)
                return

            user_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 پاسخ", callback_data=f"reply_{sender_code}"),
                 InlineKeyboardButton("❤️ ری‌اکشن", callback_data=f"react_{sender_code}")],
                [InlineKeyboardButton("🚫 بلاک این فرستنده", callback_data=f"block_{sender_code}")]
            ])

            admin_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 هویت فرستنده", callback_data=f"checkuser_{sender_code}"),
                 InlineKeyboardButton("🔍 هویت گیرنده", callback_data=f"checkuser_{target_code}")]
            ])

            try:
                await context.bot.send_message(chat_id=target_id, text=f"📩 **پیام ناشناس جدید از طرف کاربر (کد: `{sender_code}`):**", parse_mode="Markdown")
                await update.message.copy(chat_id=target_id, reply_markup=user_keyboard)

                if target_id != ADMIN_ID:
                    admin_header = (
                        f"👁‍🗨 **[مانیتورینگ ادمین]**\n\n"
                        f"👤 **فرستنده (کد):** `{sender_code}`\n"
                        f"🎯 **گیرنده (کد):** `{target_code}`\n"
                        f"👇 **پیام:**"
                    )
                    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_header, parse_mode="Markdown")
                    await update.message.copy(chat_id=ADMIN_ID, reply_markup=admin_keyboard)

                increment_msg_count()
                await update.message.reply_text("پیام شما ارسال شد! ✅")
            except:
                await update.message.reply_text("❌ خطا در ارسال پیام.")
        else:
            await update.message.reply_text("❌ کاربر مورد نظر پیدا نشد.")

        user_states.pop(user_id, None)

    elif state.get('action') == 'support':
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 پاسخ", callback_data=f"reply_{sender_code}"),
             InlineKeyboardButton("🔍 هویت فرستنده", callback_data=f"checkuser_{sender_code}")]
        ])
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"📩 **پیام جدید پشتیبانی از کد `{sender_code}`:**", reply_markup=admin_keyboard, parse_mode="Markdown")
        await update.message.copy(chat_id=ADMIN_ID)
        await update.message.reply_text("پیام شما به پشتیبانی ارسال شد ✅")
        user_states.pop(user_id, None)

    else:
        await send_main_menu(update, context)

if __name__ == '__main__':
    TOKEN = "8785381801:AAF2k7OtrCvTQLzhUi6jHSdMHmdz-FltehI"
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", user_info_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))

    print("ربات آنلاین شد...")
    application.run_polling()
