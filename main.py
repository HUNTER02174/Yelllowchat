from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters

ADMIN_ID = 6447881580          # آیدی عددی مدیر
CHANNEL_USERNAME = "@wilililill" # یوزرنیم کانال شما با @

# حافظه ربات
user_states = {}
user_code_map = {}
all_users = set()
blocked_users = {}            # {گیرنده: [لیست فرستنده‌های بلاک شده]}
inbox_messages = {ADMIN_ID: []}
total_messages_count = 0

def get_user_code(user_id: int) -> str:
    s = str(user_id)
    code = s[-8:] if len(s) >= 8 else s.zfill(8)
    user_code_map[code] = user_id
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sender_code = get_user_code(user_id)
    args = context.args

    if user_id != ADMIN_ID and not await check_membership(user_id, context):
        keyboard = [
            [InlineKeyboardButton("عضویت در کانال 📢", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton("عضو شدم ✅", callback_data="check_join")]
        ]
        await update.message.reply_text(
            "⚠️ برای استفاده از ربات یلو چت، ابتدا باید در کانال ما عضو شوید:",
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
            await update.message.reply_text("✍️ پیام ناشناس خود را بنویسید و بفرستید:")
            return

    await send_main_menu(update, context)

async def send_main_menu(update_or_query, context):
    user_id = update_or_query.effective_user.id
    sender_code = get_user_code(user_id)

    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📥 صندوق پیام‌ها", callback_data="open_inbox")],
            [InlineKeyboardButton("📊 آمار ربات", callback_data="admin_stats"), InlineKeyboardButton("📢 پیام همگانی", callback_data="start_broadcast")]
        ]
        text = f"👑 **پنل مدیریت یلو چت**\n\nتعداد کاربران تا این لحظه: {len(all_users)}"
    else:
        keyboard = [
            [InlineKeyboardButton("🔗 لینک ناشناس من", callback_data="get_link")],
            [InlineKeyboardButton("🚫 کاربران بلاک‌شده", callback_data="show_blocked"), InlineKeyboardButton("📩 پشتیبانی", callback_data="support_mode")]
        ]
        text = f"💛 **به ربات یلو چت خوش آمدید!**\n\nکد اختصاصی شما: `{sender_code}`"

    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update_or_query, 'message') and update_or_query.message:
        await update_or_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update_or_query.callback_query.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    sender_code = get_user_code(user_id)

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
        msg = f"📌 **لینک ناشناس شما در یلو چت:**\n\n{personal_link}\n\nاین لینک را در بیو یا شبکه‌های اجتماعی بگذارید تا دیگران بدون نام به شما پیام بفرستند!"
        await query.message.reply_text(msg, parse_mode="Markdown")

    elif query.data == "show_blocked":
        user_blocks = blocked_users.get(user_id, [])
        if not user_blocks:
            await query.answer("لیست مسدودی‌های شما خالی است!", show_alert=True)
        else:
            await query.message.reply_text("🚫 لیست کاربران بلاک‌شده توسط شما:", parse_mode="Markdown")
            for b_code in user_blocks:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ آنبلاک کد {b_code}", callback_data=f"unblock_{b_code}")]])
                await query.message.reply_text(f"👤 کاربر با کد: `{b_code}`", reply_markup=btn, parse_mode="Markdown")

    elif query.data.startswith("unblock_"):
        target_code_to_unblock = query.data.split("_")[1]
        if user_id in blocked_users and target_code_to_unblock in blocked_users[user_id]:
            blocked_users[user_id].remove(target_code_to_unblock)
            await query.answer("کاربر با موفقیت آنبلاک شد ✅", show_alert=True)
            await query.message.edit_text(f"✅ کاربر با کد `{target_code_to_unblock}` از مسدودی خارج شد.", parse_mode="Markdown")

    elif query.data == "open_inbox":
        messages = inbox_messages.get(ADMIN_ID, [])
        if not messages:
            await query.answer("📭 صندوق پیام‌های شما خالی است!", show_alert=True)
        else:
            await query.message.reply_text(f"📬 شما {len(messages)} پیام در صندوق دارید:")
            for msg in messages:
                await query.message.reply_text(msg['text'], parse_mode="Markdown", reply_markup=msg['reply_markup'])
            inbox_messages[ADMIN_ID] = []

    elif query.data == "admin_stats":
        stats_msg = (
            f"📊 **آمار کلی ربات یلو چت:**\n\n"
            f"👥 کل کاربران: {len(all_users)} نفر\n"
            f"💬 کل پیام‌های منتقل‌شده: {total_messages_count} پیام"
        )
        await query.message.reply_text(stats_msg, parse_mode="Markdown")

    elif query.data == "start_broadcast":
        user_states[user_id] = {'action': 'awaiting_broadcast'}
        await query.message.reply_text("✍️ پیام عمومی خود را بنویسید تا به تمام کاربران ارسال شود:")

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
        await query.message.reply_text("✍️ پاسخ خود را بنویسید تا ارسال شود:")

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
        await query.message.reply_text("✍️ پیام خود را برای پشتیبانی بنویسید:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_messages_count
    user_id = update.effective_user.id
    sender_code = get_user_code(user_id)
    user_text = update.message.text
    state = user_states.get(user_id, {})

    # ۱. ارسال پیام همگانی
    if user_id == ADMIN_ID and state.get('action') == 'awaiting_broadcast':
        user_states.pop(user_id, None)
        success, failed = 0, 0
        await update.message.reply_text("⏳ در حال ارسال پیام به تمام کاربران...")
        for uid in list(all_users):
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 **پیام عمومی از طرف مدیریت:**\n\n{user_text}", parse_mode="Markdown")
                success += 1
            except:
                failed += 1
        await update.message.reply_text(f"✅ پیام همگانی ارسال شد!\n\nموفق: {success}\nناموفق: {failed}", parse_mode="Markdown")
        return

    # ۲. پاسخ ادمین
    if user_id == ADMIN_ID and state.get('action') == 'admin_reply':
        target_code = state.get('target_code')
        target_id = user_code_map.get(target_code)
        if target_id:
            try:
                await context.bot.send_message(chat_id=target_id, text=f"📩 **پاسخ پشتیبانی یلو چت:**\n\n{user_text}", parse_mode="Markdown")
                await update.message.reply_text(f"پاسخ با موفقیت به کاربر `{target_code}` ارسال شد! ✅", parse_mode="Markdown")
            except:
                await update.message.reply_text("❌ خطا در ارسال پیام به کاربر.")
        user_states.pop(user_id, None)
        return

    # ۳. ارسال پیام ناشناس بین کاربران
    if state.get('action') in ['sending_anonymous', 'replying']:
        target_code = state.get('target_code')
        target_id = user_code_map.get(target_code)

        if target_id and sender_code in blocked_users.get(target_id, []):
            await update.message.reply_text("❌ این کاربر شما را مسدود کرده است.")
            user_states.pop(user_id, None)
            return

        keyboard = [
            [InlineKeyboardButton("💬 پاسخ", callback_data=f"reply_{sender_code}"),
             InlineKeyboardButton("❤️ ری‌اکشن", callback_data=f"react_{sender_code}")],
            [InlineKeyboardButton("🚫 بلاک این فرستنده", callback_data=f"block_{sender_code}")]
        ]

        if target_id:
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📩 **پیام ناشناس جدید:**\n\n{user_text}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                total_messages_count += 1
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
        admin_msg_text = (
            f"📩 **پیام جدید به پشتیبانی**\n\n"
            f"👤 کد کاربر: `{sender_code}`\n"
            f"🆔 آیدی واقعی: `{user_id}`\n\n"
            f"📝 متن:\n{user_text}"
        )

        inbox_messages[ADMIN_ID].append({
            'text': admin_msg_text,
            'reply_markup': admin_keyboard
        })

        await context.bot.send_message(chat_id=ADMIN_ID, text="🔔 یک پیام جدید در صندوق پشتیبانی دارید!")
        await update.message.reply_text("پیام شما به پشتیبانی ارسال شد ✅")
        user_states.pop(user_id, None)

    else:
        if user_id == ADMIN_ID:
            await send_main_menu(update, context)
        else:
            await update.message.reply_text("برای شروع دستور /start را بزنید.")

if __name__ == '__main__':
    TOKEN = "8785381801:AAF2k7OtrCvTQLzhUi6jHSdMHmdz-FltehI"

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("ربات یلو چت (Yellow Chat) با موفقیت روشن شد...")
    application.run_polling()
