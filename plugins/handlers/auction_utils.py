from pyrogram import Client, filters
from plugins.utils.admin_checker import co_owner, group_admin
from connections.mongo_db import players_col, get_tournament, get_user, get_player, add_user, teams_col, tournaments_col
from plugins.utils.helpers import resolve_user, resolve_chat_id
from config import Config
import time
TOP_COMMAND_COOLDOWN = {}
TOP_COOLDOWN_SECONDS = 180  # 3 minutes

def split_message(text, limit=4000):
    """Split text into chunks under Telegram's message limit"""
    for i in range(0, len(text), limit):
        yield text[i:i+limit]
        
OWNER_ID = 7995262033

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def build_compact_player_list(players, title):
    text = (
        f"📋 ✦✧✦ 𝗣𝗹𝗮𝘆𝗲𝗿 𝗟𝗶𝘀𝘁 ✦✧✦ 📋\n\n"
        f"🏆 **{title}**\n\n"
    )

    for idx, p in enumerate(players, start=1):
        user_info = get_user(p["user_id"])
        name = (
            user_info.get("full_name")
            if user_info and user_info.get("full_name")
            else user_info.get("username")
            if user_info and user_info.get("username")
            else "Unknown"
        )
        base_price = p.get("base_price", "N/A")

        text += (
            f"{idx}. **{name}**  [`{p['user_id']}`]\n"
            f"└ ©{base_price}\n\n"
        )

    text += "🎨 Designed by @Nini_arhi"
    return text

@Client.on_message(filters.command("list") & filters.group)
@co_owner
async def list_players_group(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)

    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    players = list(players_col.find({"chat_id": chat_id}))
    if not players:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗣𝗹𝗮𝘆𝗲𝗿𝘀 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 𝗬𝗲𝘁 ✦✧✦ ⚠️"
        )

    text = build_compact_player_list(players, tournament["title"])

    for chunk in split_message(text):
        await message.reply(chunk)
        
@Client.on_message(filters.command("list") & filters.private)
@co_owner
async def list_tournaments_dm(bot, message):
    tournaments = list(tournaments_col.find({}))

    if not tournaments:
        return await message.reply("⚠️ No tournaments found.")

    buttons = [
        [InlineKeyboardButton(
            text=t["title"],
            callback_data=f"list_{t['chat_id']}"
        )]
        for t in tournaments
    ]

    await message.reply(
        "🏆 ✦✧✦ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ 🏆\n\n"
        "Tap a tournament to view its player list:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex(r"^list_"))
@co_owner
async def list_players_callback(bot, query):
    chat_id = int(query.data.split("_", 1)[1])
    tournament = get_tournament(chat_id)

    if not tournament:
        return await query.answer("Tournament not found.", show_alert=True)

    players = list(players_col.find({"chat_id": chat_id}))
    if not players:
        return await query.message.reply(
            "⚠️ No players registered in this tournament."
        )

    text = build_compact_player_list(players, tournament["title"])

    for chunk in split_message(text):
        await query.message.reply(chunk)

    await query.answer()


@Client.on_message(filters.command("unsold") & filters.group)
async def unsold_players(bot, message):
    if not is_owner(message.from_user.id):
        return await message.reply("🚫 This command is restricted to the bot owner.")

    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)

    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    players = list(players_col.find({"chat_id": chat_id, "status": "unsold"}))
    if not players:
        return await message.reply(
            "🎉 ✦✧✦ 𝗡𝗼 𝗨𝗻𝘀𝗼𝗹𝗱 𝗣𝗹𝗮𝘆𝗲𝗿𝘀 𝗟𝗲𝗳𝘁 ✦✧✦ 🎉"
        )

    text = (
        f"❌ ✦✧✦ 𝗨𝗻𝘀𝗼𝗹𝗱 𝗣𝗹𝗮𝘆𝗲𝗿𝘀 ✦✧✦ ❌\n\n"
        f"🏆 **{tournament['title']}**\n\n"
    )

    for idx, p in enumerate(players, start=1):
        user_info = get_user(p["user_id"])
        name = (
            user_info.get("full_name")
            if user_info and user_info.get("full_name")
            else user_info.get("username")
            if user_info and user_info.get("username")
            else "Unknown Player"
        )

        text += (
            f"✦ **{idx}. {name}** ║ ツ [ `{p['user_id']}` ]\n"
            f"└ 💸 Base Price: ©{p.get('base_price','N/A')}\n"
            f"└ ⏳ Status: **Unsold**\n\n"
        )

    text += "🎨 Designed by @Nini_arhi"

    for chunk in split_message(text):
        await message.reply(chunk)

@Client.on_message(filters.command("add_player") & filters.group)
async def add_player_cmd(bot, message):
    # ── Owner check ──
    if not is_owner(message.from_user.id):
        return await message.reply("🚫 This command is restricted to the bot owner.")

    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    # ── Identify user & base price ──
    if message.reply_to_message:
        if len(message.command) < 2:
            return await message.reply("⚠️ Usage: Reply with `/add_player <base_price>`")
        try:
            base_price = int(message.command[1])
        except ValueError:
            return await message.reply("❌ Invalid base price.")
        user = message.reply_to_message.from_user
    else:
        if len(message.command) < 3:
            return await message.reply("⚠️ Usage: `/add_player <user_id/username> <base_price>`")
        identifier = message.command[1]
        try:
            base_price = int(message.command[2])
        except ValueError:
            return await message.reply("❌ Invalid base price.")
        user = await resolve_user(bot, identifier)
        if not user:
            return await message.reply("❌ Could not resolve user.")

    # ── Check if player already exists ──
    if get_player(user.id, chat_id):
        return await message.reply("⚠️ Player already registered in this tournament.")

    # ── Ensure global user ──
    if not get_user(user.id):
        add_user(user.id, user.username, user.first_name)

    # ── Insert player into tournament ──
    players_col.insert_one({
        "user_id": user.id,
        "chat_id": chat_id,
        "base_price": base_price,
        "status": "unsold",
        "sold_to": None,
        "sold_price": None
    })

    # ── Confirmation message ──
    await message.reply(
        f"✦✧✦ 𝗣𝗹𝗮𝘆𝗲𝗿 𝗔𝗱𝗱𝗲𝗱 ✦✧✦\n\n"
        f"👤 **{user.first_name}** ║ ツ [ `{user.id}` ]\n"
        f"└ 💸 Base Price: ©{base_price}\n"
        f"└ 🏆 Tournament: **{tournament['title']}**\n\n"
    )

    # ── Log to main GC ──
    try:
        await bot.send_message(
            -1003149414375,
            f"➕ **Player Added**\n\n"
            f"👤 {user.first_name} (`{user.id}`)\n"
            f"💸 Base Price: ©{base_price}\n"
            f"🏆 Tournament: **{tournament['title']}**\n"
        )
    except:
        pass


@Client.on_message(filters.command("remove_player") & filters.group)
async def remove_player_cmd(bot, message):
    if not is_owner(message.from_user.id):
        return await message.reply("🚫 This command is restricted to the bot owner.")

    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    if message.reply_to_message:
        user = message.reply_to_message.from_user
    else:
        if len(message.command) < 2:
            return await message.reply("⚠️ Usage: `/remove_player <user_id/username>`")
        user = await resolve_user(bot, message.command[1])
        if not user:
            return await message.reply("❌ Could not resolve user.")

    player = get_player(user.id, chat_id)
    if not player:
        return await message.reply("⚠️ Player not found in this tournament.")

    players_col.delete_one({"user_id": user.id, "chat_id": chat_id})

    await message.reply(
        f"🗑 ✦✧✦ 𝗣𝗹𝗮𝘆𝗲𝗿 𝗥𝗲𝗺𝗼𝘃𝗲𝗱 ✦✧✦ 🗑\n\n"
        f"👤 **{user.first_name}** ║ ツ [ `{user.id}` ]\n"
        f"🏆 Tournament: **{tournament['title']}**\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    # ── Log to GC ──
    try:
        await bot.send_message(
            -1003149414375,
            f"➖ **Player Removed**\n\n"
            f"👤 {user.first_name} (`{user.id}`)\n"
            f"🏆 {tournament['title']}"
        )
    except:
        pass



@Client.on_message(filters.command("reset") & filters.group)
async def reset_player_cmd(bot, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("🚫 Owner only command.")

    chat_id = resolve_chat_id(message.chat.id)
    user = message.reply_to_message.from_user if message.reply_to_message else (
        await resolve_user(bot, message.command[1]) if len(message.command) > 1 else None
    )

    if not user:
        return await message.reply("⚠️ Reply to a user or use /reset <id>")

    player = get_player(user.id, chat_id)
    if not player or player.get("status") != "sold":
        return await message.reply("⚠️ Player not sold or not found.")

    team_name = player.get("sold_to")
    sold_price = player.get("sold_price", 0)

    # Refund and reset
    teams_col.update_one(
        {"chat_id": chat_id, "team_name": team_name},
        {"$inc": {"purse": sold_price}, "$pull": {"sold_players": {"player_id": user.id}}}
    )
    players_col.update_one(
        {"user_id": user.id, "chat_id": chat_id},
        {"$set": {"status": "unsold", "sold_to": None, "sold_price": None}}
    )

    await message.reply(
        f"🔄 **Reset Done**\n"
        f"👤 {user.first_name} marked **Unsold**\n"
        f"💰 Price refunded to **{team_name}**"
    )

@Client.on_message(filters.command("add_team") & filters.group)
@co_owner
async def add_team(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply("⚠️ No active tournament here.")

    user = None
    team_name = None
    purse = tournament["purse"]  # default purse

    def parse_team_and_purse(text: str):
        if "|" in text:
            name, purse_val = text.split("|", 1)
            return name.strip(), int(purse_val.strip())
        return text.strip(), purse

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        if len(message.command) < 2:
            return await message.reply(
                "⚠️ Usage:\nReply with `/add_team Team Name | purse`"
            )
        team_name, purse = parse_team_and_purse(
            " ".join(message.command[1:])
        )
    else:
        if len(message.command) < 3:
            return await message.reply(
                "⚠️ Usage:\n/add_team user_id/username Team Name | purse"
            )

        identifier = message.command[1]
        user = await resolve_user(bot, identifier)
        if not user:
            return await message.reply("❌ Could not resolve user.")

        team_name, purse = parse_team_and_purse(
            " ".join(message.command[2:])
        )

    if purse < 0:
        return await message.reply("⚠️ Purse amount must be a positive number.")

    existing = teams_col.find_one({
        "chat_id": chat_id,
        "$or": [
            {"team_name": team_name},
            {"owner_id": user.id}
        ]
    })
    if existing:
        return await message.reply(
            "⚠️ A team with this name or owner already exists."
        )

    new_team = {
        "chat_id": chat_id,
        "team_name": team_name,
        "owner_id": user.id,
        "bidder_list": [user.id],
        "purse": purse,
        "sold_players": []
    }
    teams_col.insert_one(new_team)

    await message.reply(
        f"✨ 🎟 **Team Registered Successfully!** 🎟 ✨\n\n"
        f"🧩 **Team:** {team_name}\n"
        f"👤 **Owner:** {user.mention}\n"
        f"💰 **Starting Purse:** {purse:,} ©\n\n"
        f"🏏 Ready for the auction floor!"
    )

@Client.on_message(filters.command("rm_team") & filters.group)
@co_owner
async def remove_team(bot, message):
    chat_id = resolve_chat_id(message.chat.id)

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        team = teams_col.find_one({
            "chat_id": chat_id,
            "owner_id": user.id
        })
        if not team:
            return await message.reply("❌ No team found for this owner.")
    else:
        if len(message.command) < 2:
            return await message.reply(
                "⚠️ Usage:\n"
                "`/rm_team Team Name`\n"
                "or reply to owner with `/rm_team`"
            )

        team_name = " ".join(message.command[1:])
        team = teams_col.find_one({
            "chat_id": chat_id,
            "team_name": team_name
        })
        if not team:
            return await message.reply("❌ Team not found.")

    # Optional safety: block removal if players already sold
    if team.get("sold_players"):
        return await message.reply(
            "🚫 This team already has sold players.\n"
            "Removal is blocked to protect auction integrity."
        )

    teams_col.delete_one({"_id": team["_id"]})

    await message.reply(
        f"🗑 **Team Removed Successfully**\n\n"
        f"🧩 **Team:** {team['team_name']}\n"
        f"👤 **Owner ID:** `{team['owner_id']}`\n\n"
        f"⚖️ Auction data remains safe."
    )


@Client.on_message(filters.command("edit") & filters.group)
@co_owner
async def edit_team(bot, message):
    chat_id = resolve_chat_id(message.chat.id)

    if len(message.command) < 3:
        return await message.reply(
            "⚠️ Usage:\n"
            "`/edit TeamName name NewName`\n"
            "`/edit TeamName purse Amount`\n"
            "`/edit TeamName name NewName | purse Amount`"
        )

    team_name = message.command[1]
    team = teams_col.find_one({"chat_id": chat_id, "team_name": team_name})
    if not team:
        return await message.reply("❌ Team not found.")

    update_data = {}
    raw_text = " ".join(message.command[2:])

    if "|" in raw_text:
        parts = [p.strip() for p in raw_text.split("|")]
    else:
        parts = [raw_text]

    for part in parts:
        tokens = part.split(maxsplit=1)
        if len(tokens) != 2:
            continue

        key, value = tokens
        key = key.lower()

        if key == "name":
            update_data["team_name"] = value.strip()
        elif key == "purse":
            if not value.isdigit():
                return await message.reply("⚠️ Purse must be a number.")
            update_data["purse"] = int(value)

    if not update_data:
        return await message.reply("⚠️ Nothing to update.")

    teams_col.update_one(
        {"_id": team["_id"]},
        {"$set": update_data}
    )

    text = "✏️ **Team Updated Successfully!**\n\n"
    if "team_name" in update_data:
        text += f"🧩 New Name: **{update_data['team_name']}**\n"
    if "purse" in update_data:
        text += f"💰 New Purse: **{update_data['purse']:,} ©**\n"

    await message.reply(text)

@Client.on_message(filters.command("team") & filters.group)
async def fetch_team_players(bot, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ Usage: /team <team_name>")

    team_name = " ".join(message.command[1:])
    chat_id = resolve_chat_id(message.chat.id)

    team_data = teams_col.find_one(
        {"chat_id": chat_id, "team_name": {"$regex": f".*{team_name}.*", "$options": "i"}},
        {"_id": 0}
    )

    if not team_data:
        return await message.reply(f"⚠️ Team '{team_name}' not found in this tournament!")

    # Bidders
    bidders_text = ""
    for uid in team_data.get("bidder_list", []):
        try:
            user = await bot.get_users(uid)
            bidders_text += f"🎟 {user.mention}\n"
        except:
            bidders_text += f"🎟 `{uid}`\n"
    if not bidders_text:
        bidders_text = "— None —"

    sold_players = team_data.get("sold_players", [])
    purse = team_data.get("purse", 0)
    total_cost = sum(p.get("sold_price", 0) for p in sold_players)

    # Header
    response = (
        f"🏏 ✦✧✦ **Team: {team_data['team_name']}** ✦✧✦ 🏏\n\n"
        f"👑 Owner: [`{team_data['owner_id']}`]\n"
        f"💰 Purse Left: ©{purse}\n"
        f"💸 Total Spent: ©{total_cost}\n"
        f"🎟 Bidders:\n{bidders_text}\n\n"
    )

    if sold_players:
        response += "📌 ✦ Sold Players ✦ 📌\n"
        for idx, player in enumerate(sold_players, start=1):
            response += (
                f"✦ {idx}. {player['player_name']} ║ ツ [ `{player['player_id']}` ]\n"
                f"└ 💰 Sold Price: ©{player.get('sold_price', 0)}\n"
                f"└ ⏳ Status: Sold\n\n"
            )
    else:
        response += "🎈 No players have been sold to this team yet.\n\n"

    response += "🎨 Designed by @Nini_arhi"

    # Send in chunks to avoid Telegram limits
    for chunk in split_message(response):
        await message.reply(chunk)

@Client.on_message(filters.command("add_bidder") & filters.group)
@co_owner
async def add_bidder(bot, message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply(
            "⚠️ Usage:\n"
            "📝 /add_bidder {user_id/username} {team_name}\n"
            "📝 Or reply to a user: /add_bidder {team_name}"
        )

    chat_id = resolve_chat_id(message.chat.id)

    # Get the target user
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        team_name = message.command[1]
    elif len(message.command) > 2:
        identifier = message.command[1]
        target_user = await resolve_user(bot, identifier)
        team_name = message.command[2]
    else:
        return await message.reply("⚠️ No user provided (reply or pass username/ID).")

    if not team_name:
        return await message.reply("⚠️ Please provide a team name.")
    if not target_user:
        return await message.reply("❌ Could not resolve user.")

    # Fetch team
    team = teams_col.find_one(
        {"chat_id": chat_id, "team_name": {"$regex": f".*{team_name}.*", "$options": "i"}}
    )
    if not team:
        return await message.reply(f"⚠️ Team '{team_name}' not found in this tournament.")

    # Already bidder?
    if target_user.id in team.get("bidder_list", []):
        return await message.reply(f"⚠️ {target_user.mention} is already a bidder for 🧧 **{team['team_name']}**.")

    # Add bidder
    teams_col.update_one(
        {"_id": team["_id"]},
        {"$push": {"bidder_list": target_user.id}}
    )

    await message.reply(
        f"✨ Added 🎟 {target_user.mention} as a bidder for 🧩 **{team['team_name']}**!"
    )


@Client.on_message(filters.command("rm_bidder") & filters.group)
@co_owner
async def remove_bidder(bot, message):
    """
    /rm_bidder {username/userid} {team_name}
    OR reply to a user: /rm_bidder {team_name}
    Removes a bidder from a team's bidder_list.
    """
    chat_id = resolve_chat_id(message.chat.id)
    args = message.text.split(maxsplit=2)

    # Reply to user
    if message.reply_to_message and len(args) >= 2:
        target_user = message.reply_to_message.from_user
        team_name = args[1]
    # /rm_bidder {username/userid} {team_name}
    elif len(args) >= 3:
        identifier = args[1]
        team_name = args[2]
        target_user = await resolve_user(bot, identifier)
        if not target_user:
            return await message.reply("❌ Could not resolve user.")
    else:
        return await message.reply(
            "⚠️ Usage:\n"
            "📝 /rm_bidder {username/userid} {team_name}\n"
            "📝 Or reply to a user: /rm_bidder {team_name}"
        )

    # Tournament check
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply("⚠️ No active tournament here.")

    # Fetch team
    team = teams_col.find_one(
        {"chat_id": chat_id, "team_name": {"$regex": f".*{team_name}.*", "$options": "i"}}
    )
    if not team:
        return await message.reply(f"⚠️ Team **{team_name}** not found in this tournament.")

    if target_user.id not in team.get("bidder_list", []):
        return await message.reply(f"⚠️ {target_user.mention} is not a bidder in team 🧧 **{team_name}**.")

    # Remove bidder
    teams_col.update_one(
        {"chat_id": chat_id, "team_name": {"$regex": f".*{team_name}.*", "$options": "i"}},
        {"$pull": {"bidder_list": target_user.id}}
    )

    await message.reply(
        f"🗑 Removed 🎟 {target_user.mention} from bidder list of 🧩 **{team_name}**!"
    )

@Client.on_message(filters.command("info") & filters.group)
@group_admin
async def get_player_info(bot, message):
    args = message.text.split()
    chat_id = resolve_chat_id(message.chat.id)

    # --- Identify target user ---
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
    elif len(args) == 2:
        target_user = await resolve_user(bot, args[1])
        if not target_user:
            return await message.reply("❌ Could not fetch user details.")
    else:
        return await message.reply(
            "⚠️ Usage:\n"
            "📝 Reply to a user with /info\n"
            "📝 Or use /info {userid/username}"
        )

    # --- Fetch player data for this tournament ---
    player = players_col.find_one({"user_id": target_user.id, "chat_id": chat_id})
    if not player:
        return await message.reply("⚠️ Player not found in this tournament database.")

    # --- Determine status ---
    status = player.get("status", "unsold").capitalize()
    sold_price = player.get("sold_price", "N/A")
    base_price = player.get("base_price", "N/A")

    # --- Get team name if sold ---
    team_name = "N/A"
    if player.get("sold_to"):
        team = teams_col.find_one({"chat_id": chat_id, "team_name": player["sold_to"]})
        if team:
            team_name = team.get("team_name", "N/A")

    # --- Build response with aesthetic emojis ---
    response = (
        f"🎟 ✦✧✦ 𝗣𝗹𝗮𝘆𝗲𝗿 𝗜𝗻𝗳𝗼 ✦✧✦ 🎟\n\n"
        f"💓 Name:  {target_user.mention}\n"
        f"♦ User ID:  `{target_user.id}`\n"
        f"🧧 Base Price:  ©{base_price}\n"
        f"⏳ Status:  **{status}**\n"
        f"💰 Sold Price:  ©{sold_price}\n"
        f"🎈 Team:  {team_name}\n\n"
        f"🌺 Designed by @Nini_arhi "
    )

    await message.reply(response)


@Client.on_message(filters.command("purse") & filters.group)
async def show_team_purses(bot, message):
    owner_id = 7995262033
    if message.from_user.id != owner_id:
        return await message.reply("❌ Only the owner can use this command.")

    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply("⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️")

    tour_name = tournament['title']  # Fix: get tournament name

    teams = list(teams_col.find({"chat_id": chat_id}))
    if not teams:
        return await message.reply("⚠️ ✦✧✦ 𝗡𝗼 𝗧𝗲𝗮𝗺𝘀 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 ✦✧✦ ⚠️")

    text = f"💼 ✦✧✦ 𝗧𝗲𝗮𝗺 𝗣𝘂𝗿𝘀𝗲𝘀 ✦✧✦ 💼\n\n🏆 **{tour_name}**\n\n"
    for idx, team in enumerate(teams, start=1):
        purse = team.get("purse", 0)
        players_count = len(team.get("sold_players", []))
        text += (
            f"✦ {idx}.  **{team['team_name']}**\n"
            f"└ 🧧 Purse Left:  {purse:,} ©\n"
            f"└ 👥 Players Bought:  {players_count}\n\n"
        )

    text += " Designed by @Nini_arhi 🧩"

    for chunk in split_message(text):
        await message.reply(chunk)

@Client.on_message(filters.command("top") & filters.group)
async def top_sales(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    user_id = message.from_user.id
    now = time.time()

    # ---- Cooldown Check ----
    key = (chat_id, user_id)
    last_used = TOP_COMMAND_COOLDOWN.get(key, 0)

    remaining = TOP_COOLDOWN_SECONDS - (now - last_used)
    if remaining > 0:
        return await message.reply(
            f"⏳ Please wait **{int(remaining)}s** before using /top again."
        )

    # Update cooldown
    TOP_COMMAND_COOLDOWN[key] = now

    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    # ---- Fetch Top 5 Sold Players ----
    top_players = list(
        players_col.find(
            {
                "chat_id": chat_id,
                "status": "sold",
                "sold_price": {"$ne": None}
            }
        )
        .sort("sold_price", -1)
        .limit(5)
    )

    if not top_players:
        return await message.reply(
            "⚠️ No players have been sold yet."
        )

    text = (
        "🏆 ✦✧✦ **TOP 5 MOST EXPENSIVE BUYS** ✦✧✦ 🏆\n\n"
        f"🏏 Tournament: **{tournament['title']}**\n\n"
    )

    for idx, p in enumerate(top_players, start=1):
        user_info = get_user(p["user_id"])
        name = (
            user_info.get("full_name")
            if user_info and user_info.get("full_name")
            else f"User {p['user_id']}"
        )

        team_name = p.get("sold_to", "N/A")
        price = p.get("sold_price", 0)

        text += (
            f"🥇 {idx}. **{name}**\n"
            f"└ 💰 Sold For: **©{price:,}**\n"
            f"└ 🏏 Team: **{team_name}**\n\n"
        )

    text += "🌺 Designed by @Nini_arhi"

    await message.reply(text)

@Client.on_message(filters.command("status") & filters.group)
@co_owner
async def tournament_status(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)

    if not tournament:
        return await message.reply(
            "⚠️ ✦✧✦ 𝗡𝗼 𝗔𝗰𝘁𝗶𝘃𝗲 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 ✦✧✦ ⚠️"
        )

    players_count = players_col.count_documents({"chat_id": chat_id})
    teams_count = teams_col.count_documents({"chat_id": chat_id})

    reg_status = (
        "🟢 OPEN" if tournament.get("registration_open", True) else "🔴 CLOSED"
    )

    text = (
        "📊 ✦✧✦ **𝗧𝗢𝗨𝗥𝗡𝗔𝗠𝗘𝗡𝗧 𝗦𝗧𝗔𝗧𝗨𝗦** ✦✧✦ 📊\n\n"
        f"🏆 Tournament: **{tournament['title']}**\n"
        f"📩 Registration: **{reg_status}**\n"
        f"👤 Players Registered: **{players_count}**\n"
        f"🏏 Teams Created: **{teams_count}**\n"
        f"💰 Team Purse: **©{tournament['purse']:,}**\n\n"
        f"🎨 Designed by @Nini_arhi"
    )

    await message.reply(text)

import csv
import os

@Client.on_message(filters.command("export") & filters.group)
@co_owner
async def export_data(bot, message):
    args = message.text.split(maxsplit=1)
    if len(args) != 2 or args[1].lower() not in ("players", "teams"):
        return await message.reply(
            "⚠️ Usage:\n"
            "`/export players`\n"
            "`/export teams`"
        )

    chat_id = resolve_chat_id(message.chat.id)
    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply("⚠️ No active tournament found.")

    export_type = args[1].lower()

    if export_type == "players":
        filename = f"players_{chat_id}.csv"
        fields = [
            "user_id", "base_price", "status",
            "sold_price", "sold_to"
        ]
        data = players_col.find({"chat_id": chat_id})

    else:  # teams
        filename = f"teams_{chat_id}.csv"
        fields = [
            "team_name", "owner_id",
            "purse", "sold_players"
        ]
        data = teams_col.find({"chat_id": chat_id})

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in data:
            row = {field: item.get(field, "") for field in fields}
            writer.writerow(row)

    await message.reply_document(
        document=filename,
        caption=(
            f"📤 ✦✧✦ **EXPORT READY** ✦✧✦ 📤\n\n"
            f"🏆 Tournament: **{tournament['title']}**\n"
            f"📁 Data: **{export_type.capitalize()}**\n\n"
            f"🎨 Designed by @Nini_arhi"
        )
    )

    try:
        os.remove(filename)
    except:
        pass

# @Client.on_message(filters.private)
# async def contactrobot(bot, message):
#     await message.forward(Config.LOG_CHANNEL)
