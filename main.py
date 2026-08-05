from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

ADMIN_ID = 6447881580          # آیدی عددی ادمین
CHANNEL_USERNAME = "@wilililill" # یوزرنیم کانال

# حافظه ربات
user_states = {}
user_code_map = {}             # {code: user_id}
user_info_map = {}             # {user_id: {'username': str, 'first_name': str}}
all_users = set()
blocked_users = {}            # {گیرنده: [لیست فرستنده‌های بلاک شده]}
total_messages_count = 0

# ذخیره تمام پیام‌های عبوری برای پیگیری ادمین: {target_code: [{'sender_code': str, 'msg_type': str}]}
admin_inbox_history = {}

def get_user_code(user: object) -> str:
    user_id = user.id
    s = str(user_id)
    code = s[-8:] if len(s) >= 8 else s.zfill(8)
    user_code_map[code] = user_id
    user_info_map[user_id] = {
        'username': user.username if user.username else "ندارد",
        'first_name': user.first_name if user.first_name else "نامشخص"
    }
    all_users.add(user_id)
    return code

async def check_membership(user_id, context):
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except:
        pass
    return False

# تنظیم دکمه‌های منوی رسمی تلگرام
async def post_init(application):
    commands = [
        BotCommand("start", "🚀 شروع و منوی اصلی"),
        BotCommand("help", "❓ راهنمای استفاده از ربات")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    sender_code = get_user_code(user)
    args = context.args

    if user_id != ADMIN_ID and not await check_membership(user_id, context):
        keyboard = [
            [InlineKeyboardButton("عضویت در کانال 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("عضو شدم ✅", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات یـلو چت، ابتدا باید در کانال ما عضو شوید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if args and args[0]:
        target_code = args[0]
        if target_code == sender_code:
            await update.message.reply_text("❌ نمی‌توانید به خودتان پیام ناشناس بفرستید!")
        else:
            target_id = user_code_map.get(target_code)
            if target_id and sender_code in blocked_users.get(target_id, []):
                await update.message.reply_text("❌ متاسفانه این کاربر شما را مسدود (بلاک) کرده است.")
                return

            user_states[user_id] = {'action': 'sending_anonymous', 'target_code': target_code}
            await update.message.reply_text("✍️ پیام، عکس، ویس، گیف یا استیکر ناشناس خود را بفرستید:")
            return

    await send_main_menu(update, context)

# دستور جدید اختصاصی ادمین برای استعلام هویت واقعی کاربر با کد
async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ لطفاً کد کاربر را وارد کنید.\nمثال:\n`/info 12345678`", parse_mode="Markdown")
        return

    target_code = context.args[0]
    target_id = user_code_map.get(target_code)

    if not target_id:
        await update.message.reply_text("❌ کاربری با این کد یافت نشد.")
        return

    info = user_info_map.get(target_id, {})
    uname = f"@{info.get('username')}" if info.get('username') != "ندارد" else "ندارد"
    fname = info.get('first_name', 'نامشخص')

    res = (
        f"🔍 **اطلاعات واقعی کاربر با کد `{target_code}`:**\n\n"
        f"👤 **نام واقعی:** {fname}\n"
        f"🆔 **یوزرنیم تلگرام:** {uname}\n"
        f"🔢 **آیدی عددی:** `{target_id}`"
    )
    await update.message.reply_text(res, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ **راهنمای استفاده از یـلو چت:**\n\n"
        "1️⃣ لینک اختصاصی خود را از منوی اصلی دریافت کنید.\n"
        "2️⃣ لینک را در بیو تلگرام یا شبکه‌های اجتماعی بگذارید.\n"
        "3️⃣ هرکس روی لینک بزند، می‌تواند به شما پیام، ویس، عکس، گیف یا استیکر ناشناس بفرستد!\n"
        "4️⃣ می‌توانید به پیام‌های دریافتی پاسخ دهید یا فرستنده مزاحم را بلاک کنید."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def send_main_menu(update_or_query, context):
    user = update_or_query.effective_user
    user_id = user.id
    sender_code = get_user_code(user)

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📥 صندوق پیام‌ها و پیگیری کُدها", callback_data="open_inbox")],
            [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats"), InlineKeyboardButton("📢 پیام همگانی", callback_data="start_broadcast")]
        ]
        text = f"👑 پنل مدیریت یـلو چت\n\nتعداد کاربران تا این لحظه: {len(all_users)}\n\n💡 *برای استعلام هویت از دستور `/info کد` استفاده کنید.*"
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
    sender_code = get_user_code(user)

    if query.data == "check_join":
        if await check_membership(user_id, context):
            await query.message.delete()
            await query.message.reply_text("عضویت شما تایید شد! 🎉")
            await send_main_menu(update, context)
        else:
            await query.answer("هنوز در کانال عضو نشده‌اید!", show_alert=True)

    elif query.data == "get_link":
        bot_info = await context.bot.get_me()
        personal_link = f"https://t.me/{bot_info.username}?start={sender_code}"
        msg = f"📌 لینک ناشناس شما:\n\n{personal_link}\n\nاین لینک را در بیو قرار دهید تا دیگران به شما پیام ناشناس بفرستند!"
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif query.data == "show_blocked":
        user_blocks = blocked_users.get(user_id, [])
        if not user_blocks:
            await query.answer("لیست مسدودی‌های شما خالی است!", show_alert=True)
        else:
            await query.message.reply_text("🚫 لیست کاربران بلاک‌شده توسط شما:", parse_mode="Markdown")
            for b_code in user_blocks:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ آنبلاک کد {b_code}", callback_data=f"unblock_{b_code}")]])
                await query.message.reply_text(f"👤 کاربر با کد: {b_code}", reply_markup=btn, parse_mode="Markdown")

    elif query.data.startswith("unblock_"):
        target_code_to_unblock = query.data.split("_")[1]
        if user_id in blocked_users and target_code_to_unblock in blocked_users[user_id]:
            blocked_users[user_id].remove(target_code_to_unblock)
            await query.answer("کاربر با موفقیت آنبلاک شد ✅", show_alert=True)
            await query.message.edit_text(f"✅ کاربر با کد {target_code_to_unblock} از مسدودی خارج شد.", parse_mode="Markdown")

    elif query.data == "open_inbox":
        if not admin_inbox_history:
            await query.answer("📭 هیچ پیامی در سیستم ثبت نشده است!", show_alert=True)
        else:
            await query.message.reply_text("📥 **گزارش کلی تمام پیام‌های عبوری ربات:**", parse_mode="Markdown")
            for code, msgs in admin_inbox_history.items():
                inbox_text = (
                    f"🎯 **گیرنده (کد):** `{code}`\n"
                    f"🔢 **تعداد پیام دریافت شده:** {len(msgs)} پیام\n"
                    f"💬 **آخرین فرستنده:** `{msgs[-1]['sender_code']}` ({msgs[-1]['msg_type']})"
                )
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"🔍 استعلام گیرنده ({code})", callback_data=f"checkuser_{code}"), InlineKeyboardButton(f"🔍 استعلام آخرین فرستنده ({msgs[-1]['sender_code']})", callback_data=f"checkuser_{msgs[-1]['sender_code']}")]])
                await query.message.reply_text(inbox_text, parse_mode="Markdown", reply_markup=btn)

    elif query.data.startswith("checkuser_"):
        code_to_check = query.data.split("_")[1]
        target_id = user_code_map.get(code_to_check)
        if target_id:
            info = user_info_map.get(target_id, {})
            uname = f"@{info.get('username')}" if info.get('username') != "ندارد" else "ندارد"
            fname = info.get('first_name', 'نامشخص')
            await query.message.reply_text(f"👤 **کد:** `{code_to_check}`\n**نام:** {fname}\n**آیدی:** {uname}\n**آیدی عددی:** `{target_id}`", parse_mode="Markdown")
        else:
            await query.message.reply_text("اطلاعات یافت نشد.")

    elif query.data == "admin_stats":
        stats_msg = (
            f"📊 آمار کلی ربات یـلو چت:\n\n"
            f"👥 کل کاربران: {len(all_users)} نفر\n"
            f"💬 کل پیام‌های منتقل‌شده: {total_messages_count} پیام"
        )
        await query.message.reply_text(stats_msg, parse_mode="Markdown")

    elif query.data == "start_broadcast":
        user_states[user_id] = {'action': 'awaiting_broadcast'}
        await query.message.reply_text("✍️ پیام، گیف، استیکر یا فایل عمومی خود را بفرستید تا به تمام کاربران ارسال شود:")

    elif query.data.startswith("block_"):
        target_code_to_block = query.data.split("_")[1]
        if user_id not in blocked_users:
            blocked_users[user_id] = []
        if target_code_to_block not in blocked_users[user_id]:
            blocked_users[user_id].append(target_code_to_block)
        await query.answer("کاربر مسدود شد 🚫", show_alert=True)
        await query.message.edit_text(query.message.text + "\n\n❌ *(این کاربر توسط شما مسدود شد)*")

    elif query.data.startswith("replyto_"):
        target_code = query.data.split("_")[1]
        user_states[user_id] = {'action': 'admin_reply', 'target_code': target_code}
        await query.message.reply_text(f"✍️ پاسخ خود را برای کاربر با کد `{target_code}` بنویسید:", parse_mode="Markdown")

    elif query.data.startswith("reply_"):
        target_code = query.data.split("_")[1]
        user_states[user_id] = {'action': 'replying', 'target_code': target_code}
        await query.message.reply_text("✍️ پاسخ خود (متن، استیکر، گیف، ویس و...) را بفرستید:")

    elif query.data.startswith("react_"):
        target_code = query.data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("❤️", callback_data=f"sendreact_❤️_{target_code}"),
             InlineKeyboardButton("😂", callback_data=f"sendreact_😂_{target_code}"),
             InlineKeyboardButton("🔥", callback_data=f"sendreact_🔥_{target_code}"),
             InlineKeyboardButton("👍", callback_data=f"sendreact_👍_{target_code}")]
        ]
        await query.message.reply_text("یک ری‌اکشن انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("sendreact_"):
        _, emoji, target_code = query.data.split("_")
        target_id = user_code_map.get(target_code)
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text=f"طرف مقابل به پیام شما این ری‌اکشن را نشان داد: {emoji}")
            except:
                pass
        await query.message.edit_text(f"ری‌اکشن {emoji} ارسال شد!")

    elif query.data == "support_mode":
        user_states[user_id] = {'action': 'support'}
        await query.message.reply_text("✍️ پیام خود را برای پشتیبانی بفرستید:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_messages_count
    user = update.effective_user
    user_id = user.id
    sender_code = get_user_code(user)
    state = user_states.get(user_id, {})

    # ۱. ارسال پیام همگانی
    if user_id == ADMIN_ID and state.get('action') == 'awaiting_broadcast':
        user_states.pop(user_id, None)
        success, failed = 0, 0
        await update.message.reply_text("⏳ در حال ارسال به تمام کاربران...")
        for uid in list(all_users):
            try:
                await update.message.copy(chat_id=uid)
                success += 1
            except:
                failed += 1
        await update.message.reply_text(f"✅ پیام همگانی ارسال شد!\n\nموفق: {success}\nناموفق: {failed}")
        return

    # ۲. پاسخ مستقیم ادمین
    if user_id == ADMIN_ID and state.get('action') == 'admin_reply':
        target_code = state.get('target_code')
        target_id = user_code_map.get(target_code)
        if target_id:
            try:
                await update.message.copy(chat_id=target_id)
                await update.message.reply_text(f"پاسخ با موفقیت به کاربر `{target_code}` ارسال شد! ✅", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ خطا در ارسال پیام به کاربر.")
        user_states.pop(user_id, None)
        return

    # ۳. ارسال پیام ناشناس / پاسخ بین کاربران
    if state.get('action') in ['sending_anonymous', 'replying']:
        target_code = state.get('target_code')
        target_id = user_code_map.get(target_code)

        if target_id and sender_code in blocked_users.get(target_id, []):
            await update.message.reply_text("❌ این کاربر شما را مسدود کرده است.")
            user_states.pop(user_id, None)
            return

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 پاسخ", callback_data=f"reply_{sender_code}"),
             InlineKeyboardButton("❤️ ری‌اکشن", callback_data=f"react_{sender_code}")],
            [InlineKeyboardButton("🚫 بلاک این فرستنده", callback_data=f"block_{sender_code}")]
        ])

        if target_id:
            try:
                # ذکر کد فرستنده برای تفکیک پیام‌ها توسط گیرنده
                await context.bot.send_message(
                    chat_id=target_id, 
                    text=f"📩 **پیام ناشناس جدید از طرف کاربر (کد: `{sender_code}`):**", 
                    parse_mode="Markdown"
                )
                await update.message.copy(chat_id=target_id, reply_markup=keyboard)
                total_messages_count += 1

                # ثبت تمام پیام‌های ردوبدل شده در سیستم جهت نظارت و پیگیری ادمین
                msg_preview = update.message.text if update.message.text else "رسانه"
                if target_code not in admin_inbox_history:
                    admin_inbox_history[target_code] = []
                admin_inbox_history[target_code].append({'sender_code': sender_code, 'msg_type': msg_preview})

                await update.message.reply_text("پیام شما به صورت ناشناس ارسال شد! ✅")
            except:
                await update.message.reply_text("❌ خطا در ارسال پیام.")
        else:
            await update.message.reply_text("❌ کاربر مورد نظر پیدا نشد.")

        user_states.pop(user_id, None)

    # ۴. پشتیبانی
    elif state.get('action') == 'support':
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 پاسخ به این پیام", callback_data=f"replyto_{sender_code}")]
        ])
        admin_msg_text = f"📩 پیام جدید به پشتیبانی از طرف کاربر با کد: `{sender_code}`"

        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg_text, reply_markup=admin_keyboard, parse_mode="Markdown")
        await update.message.copy(chat_id=ADMIN_ID)
        await update.message.reply_text("پیام شما به پشتیبانی ارسال شد ✅")
        user_states.pop(user_id, None)

    else:
        if user_id == ADMIN_ID:
            await send_main_menu(update, context)
        else:
            await update.message.reply_text("برای شروع دستور /start را بزنید.")

if __name__ == '__main__':
    TOKEN = "8785381801:AAF2k7OtrCvTQLzhUi6jHSdMHmdz-FltehI"

    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", user_info_command)) # دستور جدید استعلام هویت
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_message))

    print("ربات یـلو چت روشن شد...")
    application.run_polling()
