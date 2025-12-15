from pyrogram import Client, filters
from plugins.utils.admin_checker import co_owner
from plugins.utils.helpers import START_MESSAGE, start_replymarkup, resolve_chat_id
from connections.mongo_db import get_tournament, tournaments_col, get_user, add_user, get_player, add_player, players_col, remove_player, teams_col
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, ReplyKeyboardMarkup
import asyncio
import asyncio
from pyrogram import Client, filters
from connections.mongo_db import (
    tournaments_col,
    players_col,
    teams_col,
    users_col,
    bids_col,
    admins_collection,
    get_tournament
)


@Client.on_message(filters.command(commands="start", prefixes=["/", "!", "."]))
async def view_activity(bot, message):

    if len(message.command) > 1:
        if message.command[1].startswith("reg_"):
            try:
                chat_id = int(message.command[1].split("_", 1)[1])
            except ValueError:
                return await message.reply("❌ Invalid tournament reference.")

            result = await register_user_in_tournament(bot, message.from_user, chat_id)
            return await message.reply(result)
        if message.command[1] == 'register':
            return await show_tournaments(bot,message)
    
    gif_id = "assets/start_vid.mp4"
    # await message.react(emoji="👍")
    await message.reply_video(
        video = gif_id,
        caption = START_MESSAGE,
        reply_markup = start_replymarkup
    )

@Client.on_message(filters.command("start_tour") & filters.group)
@co_owner
async def start_tour(bot, message):
    chat = message.chat
    user = message.from_user

    # Check if tournament already exists for this group
    existing = get_tournament(chat.id)
    if existing:
        return await message.reply("⚠️ Tournament already exists for this group.")

    try:
        # Ask for tournament name
        response_name = await bot.ask(
            chat_id=chat.id,
            text="🎯 Please enter the Tournament Name (e.g., CPLS2):",
            user_id=user.id,
            filters=filters.text,
            timeout=60
        )
        tour_name = response_name.text.strip()

        # Ask for team purse
        response_purse = await bot.ask(
            chat_id=chat.id,
            text="💰 Please enter team purse (number only):",
            user_id=user.id,
            filters=filters.text,
            timeout=60
        )
        purse = int(response_purse.text.strip())

        # Create new tournament in DB
        new_tour = {
            "chat_id": chat.id,
            "title": tour_name,
            "created_by": user.id,
            "purse": purse,
            "is_active": True
        }
        tournaments_col.insert_one(new_tour)

        # Invite link
        invite_link = f"https://t.me/{bot.me.username}?start=reg_{chat.id}"

        # Success message
        await message.reply_text(
            f"✦✧✦ 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗦𝘁𝗮𝗿𝘁𝗲𝗱! ✦✧✦\n\n"
            f"🏆 Tournament: **{tour_name}**\n"
            f"✅ Live for **{chat.title}**\n"
            f"💰 Team Purse: {purse} ⓜ\n"
            f"🎮 Players can join here: {invite_link}\n\n"
            f"⚡ Get ready to bid, compete, and win!"
        )

    except ValueError:
        await message.reply("❌ Invalid input! Team purse must be a number.")
    except asyncio.TimeoutError:
        await message.reply("⏰ Timeout! You did not respond in time.")
    except Exception as e:
        await message.reply(f"❌ An error occurred:\n`{str(e)}`")

@Client.on_message(filters.command("del_tour") & filters.group)
@co_owner
async def del_tour(bot, message):
    chat = message.chat
    user = message.from_user

    tournament = get_tournament(chat.id)
    if not tournament:
        return await message.reply(
            "⚠️ No active tournament found in this group."
        )

    try:
        # Confirmation step
        confirm = await bot.ask(
            chat_id=chat.id,
            text=(
                "🚨 **Tournament Deletion Warning** 🚨\n\n"
                f"🏆 Tournament: **{tournament['title']}**\n\n"
                "This will permanently delete:\n"
                "• Tournament data\n"
                "• Teams\n"
                "• Players\n"
                "• Auction history\n\n"
                "Type **DELETE** to confirm.\n"
                "Type anything else to cancel."
            ),
            user_id=user.id,
            filters=filters.text,
            timeout=60
        )

        if confirm.text.strip().upper() != "DELETE":
            return await message.reply("❎ Tournament deletion cancelled.")

        # Delete tournament
        tournaments_col.delete_one({"chat_id": chat.id})

        # Optional: clean related data
        teams_col.delete_many({"chat_id": chat.id})
        players_col.delete_many({"chat_id": chat.id})

        await message.reply_text(
            "🗑 **Tournament Deleted Successfully**\n\n"
            "All related data has been removed.\n"
            "You may now start a fresh tournament anytime."
        )

    except asyncio.TimeoutError:
        await message.reply("⏰ Timeout! Deletion confirmation not received.")
    except Exception as e:
        await message.reply(f"❌ An error occurred:\n`{str(e)}`")


async def register_user_in_tournament(bot, user, chat_id: int):
    """
    Core registration logic (used by both /start and callback).
    Returns a string message to send back to the user.
    Also notifies the main group after successful registration.
    """
    tournament = get_tournament(chat_id)
    if not tournament:
        return "⚠️ Tournament not found or inactive."

    tour_name = tournament.get("title", "Unknown Tournament")

    # Ensure global user record
    db_user = get_user(user.id)
    if not db_user:
        add_user(user.id, user.username, user.first_name)

    # Check if player exists in this tournament
    player = get_player(user.id, chat_id)
    if player and player.get("base_price"):
        return (
            f"✅ You are already registered in **{tour_name}**\n\n"
            "🗑 If you want to deregister, use: /deregister"
        )

    # Keyboard options for base price (only preset)
    keyboard = ReplyKeyboardMarkup(
        [["©100", "©500", "©1000"]],
        one_time_keyboard=True,
        resize_keyboard=True
    )

    try:
        prompt = (
            f"✨✦✧ 𝗖𝗵𝗼𝗼𝘀𝗲 𝗬𝗼𝘂𝗿 𝗕𝗮𝘀𝗲 𝗣𝗿𝗶𝗰𝗲 ✧✦✨\n\n"
            f"💰 Tap a button to select your base price for **{tour_name}**:\n"
            "• ©100  • ©500  • ©1000\n\n"
            "🎨 Designed by @Nini_arhi"
        )
        resp = await bot.ask(
            user.id,
            prompt,
            timeout=60,
            reply_markup=keyboard
        )
        choice = resp.text.strip()
    except asyncio.TimeoutError:
        try:
            await bot.send_message(user.id, "⌛ Registration timed out.", reply_markup=ReplyKeyboardRemove())
        except:
            pass
        return "❌ Registration failed (timeout). Please try /register again."

    # Validate selection
    if choice not in ("©100", "©500", "©1000"):
        try:
            await bot.send_message(user.id, "❌ Invalid selection. Please use the buttons.", reply_markup=ReplyKeyboardRemove())
        except:
            pass
        return "❌ Registration failed (invalid selection). Please try /register again."

    base_price = int(choice.replace("©", ""))

    # Save player record
    if not player:
        add_player(user.id, chat_id, base_price=base_price)
    else:
        players_col.update_one(
            {"user_id": user.id, "chat_id": chat_id},
            {"$set": {"base_price": base_price, "status": "unsold"}}
        )

    # Remove keyboard & confirm with styled text
    try:
        await bot.send_message(
            user.id,
            f"✦✧✦ 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱! ✦✧✦\n\n"
            f"🎉 Welcome **{user.first_name}** to **{tour_name}**!\n"
            f"💰 Base Price: ©{base_price}\n\n"
            f"🎨 Designed by @Nini_arhi",
            reply_markup=ReplyKeyboardRemove()
        )
    except:
        pass

    # Notify main group that user registered
    try:
        await bot.send_message(
            -1003149414375,
            f"💫 New Registration Alert 💫\n\n"
            f"👤 **{user.first_name}** has registered in **{tour_name}**!\n"
            f"💰 Base Price: ©{base_price}\n"
            f"🎨 Designed by @Nini_arhi"
        )
    except:
        pass

    return (
        f"✦✧✦ 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱! ✦✧✦\n\n"
        f"🎉 Welcome **{user.first_name}** to **{tour_name}**\n"
        f"💰 Base Price: **©{base_price}**\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# -------------------- GROUP COMMAND: REGISTER --------------------
@Client.on_message(filters.command("register") & filters.group)
async def group_reg(bot, message):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📩 𝗚𝗼 𝘁𝗼 𝗠𝘆 𝗗𝗠", url=f"https://t.me/{bot.me.username}?start=register")]]
    )
    await message.reply(
        "✨ 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿 𝗳𝗼𝗿 𝘁𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁𝘀 𝗶𝗻 𝗣𝗥𝗜𝗩𝗔𝗧𝗘 𝗗𝗠 ✨\n\n"
        "Click the button below to continue your registration 👇",
        reply_markup=keyboard
    )

# -------------------- PRIVATE COMMAND: SHOW TOURNAMENTS --------------------
@Client.on_message(filters.command("register") & filters.private)
async def show_tournaments(bot, message):
    tournaments = list(tournaments_col.find({"is_active": True}))

    if not tournaments:
        return await message.reply(
            "⚠️ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝘁𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁𝘀 𝗿𝗶𝗴𝗵𝘁 𝗻𝗼𝘄.\n"
            "⏳ Please check back later!"
        )

    buttons = [[InlineKeyboardButton(text=t["title"], callback_data=f"reg_{t['chat_id']}")] for t in tournaments]

    await message.reply_photo(
        photo="assets/register.jpeg",
        caption=(
            "🏆 ✦✧✦ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ 🏆\n\n"
            "Tap a tournament below to register:\n\n"
            "🎨 Designed by @Nini_arhi"
        ),
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# -------------------- CALLBACK: REGISTER --------------------
@Client.on_callback_query(filters.regex(r"^reg_"))
async def handle_register_callback(bot, query):
    try:
        chat_id = int(query.data.split("_", 1)[1])
    except ValueError:
        return await query.answer("❌ Invalid tournament reference.", show_alert=True)

    result = await register_user_in_tournament(bot, query.from_user, chat_id)
    await query.message.reply(result)
    await query.answer("✅ Registration processed!")

# -------------------- PRIVATE COMMAND: DEREGISTER --------------------
@Client.on_message(filters.command("deregister") & filters.private)
async def show_deregister_options(bot, message):
    user = message.from_user

    player_entries = list(players_col.find({"user_id": user.id}))
    if not player_entries:
        return await message.reply(
            "⚠️ 𝗬𝗼𝘂 𝗮𝗿𝗲 𝗻𝗼𝘁 𝗿𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 𝗶𝗻 𝗮𝗻𝘆 𝘁𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁𝘀."
        )

    buttons = []
    for p in player_entries:
        tournament = get_tournament(p["chat_id"])
        if tournament:
            buttons.append([InlineKeyboardButton(
                text=f"{tournament['title']} (©{p['base_price']})",
                callback_data=f"dereg_{p['chat_id']}"
            )])

    await message.reply(
        "🗑 ✦✧✦ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗮 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝘁𝗼 𝗱𝗲𝗿𝗲𝗴𝗶𝘀𝘁𝗲𝗿 ✦✧✦ 🗑",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# -------------------- CALLBACK: DEREGISTER --------------------
@Client.on_callback_query(filters.regex(r"^dereg_"))
async def handle_deregister_callback(bot, query):
    try:
        chat_id = int(query.data.split("_", 1)[1])
    except ValueError:
        return await query.answer("❌ Invalid tournament reference.", show_alert=True)

    user = query.from_user
    player = players_col.find_one({"user_id": user.id, "chat_id": chat_id})
    if not player:
        return await query.answer("⚠️ You are not registered here.", show_alert=True)

    remove_player(user.id, chat_id)
    tournament = get_tournament(chat_id)

    # DM confirmation showing only tournament name
    await query.message.reply(
        f"🗑 ✦✧✦ 𝗗𝗲𝗿𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 ✦✧✦ 🗑\n\n"
        f"You have been removed from **{tournament['title']}**.\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    await query.answer("✅ Deregistered successfully!")

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# -------------------- STOP TOURNAMENT COMMAND --------------------
@Client.on_message(filters.command("stop_tour") & filters.group)
@co_owner
async def stop_tour(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)

    if not tournament:
        return await message.reply(
            "⚠️ 𝗡𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝘁𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗳𝗼𝘂𝗻𝗱 𝗶𝗻 𝘁𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽."
        )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 𝗬𝗲𝘀, 𝗦𝘁𝗼𝗽", callback_data=f"confirm_stop_{chat_id}")],
        [InlineKeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="cancel_action")]
    ])

    await message.reply(
        "🛑 ✦✧✦ 𝗦𝘁𝗼𝗽 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ 🛑\n\n"
        "⚠️ Are you sure you want to **stop this tournament**?\n"
        "This action will permanently remove it from the database.\n\n"
        "🎨 Designed by @Nini_arhi",
        reply_markup=buttons
    )


# -------------------- CALLBACK: CONFIRM STOP --------------------
@Client.on_callback_query(filters.regex(r"^confirm_stop_"))
async def confirm_stop_tour(bot, query):
    chat_id = int(query.data.split("_")[2])
    tournament = get_tournament(chat_id)

    if not tournament:
        await query.answer("⚠️ Tournament not found.", show_alert=True)
        return

    tournaments_col.delete_one({"chat_id": chat_id})

    # Edit message in chat with styled text
    await query.message.edit_text(
        f"🛑 ✦✧✦ 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗦𝘁𝗼𝗽𝗽𝗲𝗱 ✦✧✦ 🛑\n\n"
        f"✅ **{tournament['title']}** has been successfully stopped and removed from the database.\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    # Optional: send a log to main GC
    try:
        await bot.send_message(
            -1003149414375,
            f"⚡ 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗦𝘁𝗼𝗽𝗽𝗲𝗱 ⚡\n\n"
            f"🛑 **{tournament['title']}** has been stopped in the group.\n\n"
            f"🎨 Designed by @Nini_arhi"
        )
    except:
        pass

    await query.answer("✅ Tournament stopped successfully.", show_alert=True)


@Client.on_callback_query(filters.regex(r"^cancel_action$"))
async def cancel_action(bot, query):
    await query.message.edit_text("❌ Action cancelled.")
    await query.answer("Cancelled.")


from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# -------------------- CLEAR ALL TOURNAMENT DATA --------------------
@Client.on_message(filters.command("clear") & filters.group)
@co_owner
async def clear_all(bot, message):
    chat_id = resolve_chat_id(message.chat.id)

    player_count = players_col.count_documents({"chat_id": chat_id})
    team_count = teams_col.count_documents({"chat_id": chat_id})

    if player_count == 0 and team_count == 0:
        return await message.reply("⚠️ 𝗡𝗼 𝘁𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗱𝗮𝘁𝗮 𝗳𝗼𝘂𝗻𝗱 𝘁𝗼 𝗰𝗹𝗲𝗮𝗿 𝗶𝗻 𝘁𝗵𝗶𝘀 𝗴𝗿𝗼𝘂𝗽.")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 𝗬𝗲𝘀, 𝗖𝗹𝗲𝗮𝗿 𝗔𝗹𝗹", callback_data=f"confirm_clear_{chat_id}")],
        [InlineKeyboardButton("❌ 𝗖𝗮𝗻𝗰𝗲𝗹", callback_data="cancel_action")]
    ])

    await message.reply(
        f"🗑 ✦✧✦ 𝗖𝗹𝗲𝗮𝗿 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗗𝗮𝘁𝗮 ✦✧✦ 🗑\n\n"
        f"⚠️ Are you sure you want to clear ALL tournament data for this group?\n\n"
        f"👤 Players to remove: {player_count}\n"
        f"🏏 Teams to remove: {team_count}\n\n"
        f"🎨 Designed by @Nini_arhi",
        reply_markup=buttons
    )


# -------------------- CALLBACK: CONFIRM CLEAR --------------------
@Client.on_callback_query(filters.regex(r"^confirm_clear_"))
async def confirm_clear(bot, query):
    chat_id = int(query.data.split("_")[2])

    player_count = players_col.count_documents({"chat_id": chat_id})
    team_count = teams_col.count_documents({"chat_id": chat_id})

    players_col.delete_many({"chat_id": chat_id})
    teams_col.delete_many({"chat_id": chat_id})

    await query.message.edit_text(
        f"🗑 ✦✧✦ 𝗗𝗮𝘁𝗮 𝗖𝗹𝗲𝗮𝗿𝗲𝗱 ✦✧✦ 🗑\n\n"
        f"✅ Players removed: {player_count}\n"
        f"✅ Teams removed: {team_count}\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    # Optional: log to main GC
    try:
        await bot.send_message(
            -1003149414375,
            f"⚡ 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗗𝗮𝘁𝗮 𝗖𝗹𝗲𝗮𝗿 ⚡\n\n"
            f"🗑 All data cleared in group.\n"
            f"👤 Players removed: {player_count}\n"
            f"🏏 Teams removed: {team_count}\n\n"
            f"🎨 Designed by @Nini_arhi"
        )
    except:
        pass

    await query.answer("✅ Tournament data cleared.", show_alert=True)

from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

OWNER_ID = 7995262033  # Owner's user ID

# -------------------- CLEAR ALL DATA COMMAND --------------------
@Client.on_message(filters.command("clearall") & filters.private)
async def clear_all_data(bot, message):
    user = message.from_user
    if user.id != OWNER_ID:
        return await message.reply("❌ You are not authorized to use this command.")

    # Count total entries before clearing
    total_tournaments = tournaments_col.count_documents({})
    total_players = players_col.count_documents({})
    total_teams = teams_col.count_documents({})

    if total_tournaments == 0 and total_players == 0 and total_teams == 0:
        return await message.reply("⚠️ No tournament data found to clear.")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, clear all", callback_data="confirm_clearall")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
    ])

    await message.reply(
        f"🗑 ✦✧✦ 𝗖𝗹𝗲𝗮𝗿 𝗔𝗹𝗹 𝗕𝗼𝘁 𝗗𝗮𝘁𝗮 ✦✧✦ 🗑\n\n"
        f"⚠️ Are you sure you want to clear ALL tournament data on this bot?\n\n"
        f"📊 Tournaments: {total_tournaments}\n"
        f"👤 Players: {total_players}\n"
        f"🏏 Teams: {total_teams}\n\n"
        f"🎨 Designed by @Nini_arhi",
        reply_markup=buttons
    )


# -------------------- CALLBACK: CONFIRM CLEAR ALL --------------------
@Client.on_callback_query(filters.regex(r"^confirm_clearall"))
async def confirm_clear_all(bot, query):
    user = query.from_user
    if user.id != OWNER_ID:
        return await query.answer("❌ You are not authorized to perform this action.", show_alert=True)

    # Count before deletion for reporting
    total_tournaments = tournaments_col.count_documents({})
    total_players = players_col.count_documents({})
    total_teams = teams_col.count_documents({})

    # Delete all
    tournaments_col.delete_many({})
    players_col.delete_many({})
    teams_col.delete_many({})

    await query.message.edit_text(
        f"🗑 ✦✧✦ 𝗔𝗹𝗹 𝗕𝗼𝘁 𝗗𝗮𝘁𝗮 𝗖𝗹𝗲𝗮𝗿𝗲𝗱 ✦✧✦ 🗑\n\n"
        f"✅ Tournaments deleted: {total_tournaments}\n"
        f"✅ Players deleted: {total_players}\n"
        f"✅ Teams deleted: {total_teams}\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    # Log in main GC
    try:
        await bot.send_message(
            -1003149414375,
            f"⚡ 𝗕𝗼𝘁 𝗗𝗮𝘁𝗮 𝗖𝗹𝗲𝗮𝗿 ⚡\n\n"
            f"🗑 All tournaments, players, and teams have been cleared by the owner.\n\n"
            f"📊 Tournaments deleted: {total_tournaments}\n"
            f"👤 Players deleted: {total_players}\n"
            f"🏏 Teams deleted: {total_teams}\n\n"
            f"🎨 Designed by @Nini_arhi"
        )
    except:
        pass

    await query.answer("✅ All bot data cleared.", show_alert=True)


@Client.on_message(filters.command("stats") & filters.group)
@co_owner
async def bot_stats(bot, message):
    try:
        total_users = users_col.count_documents({})
        total_groups = tournaments_col.distinct("chat_id")
        total_tournaments = tournaments_col.count_documents({})
        active_tournaments = tournaments_col.count_documents({"is_active": True})
        total_teams = teams_col.count_documents({})
        total_players = players_col.count_documents({})
        total_bids = bids_col.count_documents({})

        text = (
            "📊 ✦✧✦ **Auction Bot Statistics** ✦✧✦ 📊\n\n"
            "👥 **Users & Groups**\n"
            f"├ 👤 Total Users: **{total_users}**\n"
            f"├ 🏘 Groups Served: **{len(total_groups)}**\n\n"
            "🏆 **Tournaments**\n"
            f"├ 📦 Total Tournaments: **{total_tournaments}**\n"
            f"├ 🔥 Active Tournaments: **{active_tournaments}**\n\n"
            "🧩 **Auction Data**\n"
            f"├ 🏏 Teams Created: **{total_teams}**\n"
            f"├ 🧍 Players Registered: **{total_players}**\n"
            f"├ 💸 Total Bids Placed: **{total_bids}**\n\n"
            "⚙️ Status: **Running Smoothly**"
        )

        await message.reply(text)

    except Exception as e:
        await message.reply(f"❌ Error fetching stats:\n`{str(e)}`")


@Client.on_message(filters.command("broad") & filters.group)
@co_owner
async def broadcast(bot, message):
    if not message.reply_to_message:
        return await message.reply(
            "⚠️ Please reply to a message to broadcast it."
        )

    sent_users = 0
    sent_groups = 0
    failed = 0

    status_msg = await message.reply("📣 Broadcasting message...")

    # Send to users
    for user in users_col.find({}, {"user_id": 1}):
        try:
            await message.reply_to_message.forward(user["user_id"])
            sent_users += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    # Send to groups (from tournaments)
    for tour in tournaments_col.find({}, {"chat_id": 1}):
        try:
            await message.reply_to_message.forward(tour["chat_id"])
            sent_groups += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await status_msg.edit_text(
        "✅ **Broadcast Completed**\n\n"
        f"👤 Users Reached: **{sent_users}**\n"
        f"🏘 Groups Reached: **{sent_groups}**\n"
        f"⚠️ Failed: **{failed}**"
    )

