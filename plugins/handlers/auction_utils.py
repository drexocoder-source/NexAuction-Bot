from pyrogram import Client, filters
from plugins.utils.admin_checker import co_owner, group_admin
from connections.mongo_db import players_col, get_tournament, get_user, get_player, add_user, teams_col
from plugins.utils.helpers import resolve_user, resolve_chat_id
from config import Config

def split_message(text, limit=4000):
    """Split text into chunks under Telegram's message limit"""
    for i in range(0, len(text), limit):
        yield text[i:i+limit]
        
OWNER_ID = 7995262033

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

@Client.on_message(filters.command("list") & filters.group)
async def list_players(bot, message):
    if not is_owner(message.from_user.id):
        return await message.reply("🚫 This command is restricted to the bot owner.")

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

    text = (
        f"📋 ✦✧✦ 𝗣𝗹𝗮𝘆𝗲𝗿 𝗟𝗶𝘀𝘁 ✦✧✦ 📋\n\n"
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

        base_price = p.get("base_price", "N/A")
        status = p.get("status", "unsold").lower()

        if status == "sold":
            text += (
                f"✦ **{idx}. {name}** ║ ツ [ `{p['user_id']}` ]\n"
                f"└ 💰 Sold Price: ©{p.get('sold_price','N/A')}\n"
                f"└ 🏏 Team: **{p.get('sold_to','N/A')}**\n"
                f"└ ✅ Status: **Sold**\n\n"
            )
        else:
            text += (
                f"✦ **{idx}. {name}** ║ ツ [ `{p['user_id']}` ]\n"
                f"└ 💸 Base Price: ©{base_price}\n"
                f"└ ⏳ Status: **Unsold**\n\n"
            )

    text += "🎨 Designed by @Nini_arhi"

    for chunk in split_message(text):
        await message.reply(chunk)

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

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        if len(message.command) < 2:
            return await message.reply("⚠️ Usage: Reply with /add_team {team_name}")
        team_name = " ".join(message.command[1:])
    else:
        if len(message.command) < 3:
            return await message.reply("⚠️ Usage: /add_team {user_id/username} {team_name}")

        identifier = message.command[1]
        user = await resolve_user(bot, identifier)
        if not user:
            return await message.reply("❌ Could not resolve user.")
        team_name = " ".join(message.command[2:])

    existing = teams_col.find_one(
        {"chat_id": chat_id, "$or": [{"team_name": team_name}, {"owner_id": user.id}]}
    )
    if existing:
        return await message.reply("⚠️ A team with this name or owner already exists in this tournament.")

    new_team = {
        "chat_id": chat_id,
        "team_name": team_name,
        "owner_id": user.id,
        "bidder_list": [user.id],
        "purse": tournament["purse"],
        "sold_players": []
    }
    teams_col.insert_one(new_team)

    await message.reply(
        f"✨ 🎟 **Team Registered!** 🎟 ✨\n\n"
        f"🧩 Team Name: **{team_name}**\n"
        f"👤 Owner: {user.mention}\n"
        f"💰 Starting Purse: {tournament['purse']:,} ©\n"
        f"🎈 Have a great bidding! 🍷💓"
    )

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

# @Client.on_message(filters.private)
# async def contactrobot(bot, message):
#     await message.forward(Config.LOG_CHANNEL)