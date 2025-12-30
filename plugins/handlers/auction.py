import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional
from pyrogram.types import InputMediaPhoto

from pyrogram import Client, filters
from plugins.utils.admin_checker import co_owner
from connections.mongo_db import players_col, teams_col, get_tournament, get_player, get_user
from plugins.utils.helpers import resolve_user, send_sold_message, resolve_chat_id
from plugins.utils.templates import generate_card
from config import Config

# ===============================
# Auction State
# ===============================
@dataclass
class Auction:
    chat_id: int
    player_id: int
    base_price: int
    current_bid: int
    leading_team: Optional[str] = None
    leading_owner_id: Optional[int] = None
    last_bid_time: float = field(default_factory=time.time)
    active: bool = True
    message_id: Optional[int] = None        # auction announcement
    bid_history: list = field(default_factory=list)  # (user_id, team_name, bid, timestamp)
    end_time: Optional[float] = None
    timer_task: Optional[asyncio.Task] = None
    team_cooldowns: dict = field(default_factory=dict)  # {team_name: timestamp}


auction_state = {}  # {chat_id: Auction}


# ===============================
# Helper: Calculate next bid increment
# ===============================
def get_increment(amount: int) -> int:
    if amount < 1000:
        return 50
    elif amount < 5000:
        return 100
    else:
        return 250


# ===============================
# Auction Countdown Coroutine
# ===============================
async def auction_countdown(bot, chat_id: int):
    auction = auction_state.get(chat_id)
    if not auction:
        return

    while True:
        remaining = int(auction.end_time - time.time())
        if remaining <= 0:
            print("[DEBUG] Countdown finished, finalizing auction...")
            await finalize_auction(bot, chat_id)
            return

        if remaining in [15, 10]:
            await bot.send_message(chat_id, f"⚠️ Auction ending in {remaining} seconds...")

        if 1 <= remaining <= 5 :
            await bot.send_message(chat_id, f"⚠️ Auction ending in {remaining} seconds...")

        await asyncio.sleep(1)

PFP_CACHE = {}  # global cache

@Client.on_message(filters.command("auctionstart", prefixes=["/", ".", "!"]) & filters.group)
async def auctionstart(bot, message):
    owner_id = 7736589272
    if message.from_user.id != owner_id:
        return await message.reply("❌ Only the owner can start an auction.")

    chat_id = resolve_chat_id(message.chat.id)
    args = message.text.split()

    tournament = get_tournament(chat_id)
    if not tournament:
        return await message.reply("⚠️ No active tournament in this group.")

    if chat_id in auction_state and auction_state[chat_id].active:
        return await message.reply("⚠️ An auction is already running!")

    # ── Parse user & base price ──
    if len(args) >= 3:
        user = await resolve_user(bot, args[1])
        if not user:
            return await message.reply("❌ Could not resolve player.")
        try:
            base_price = int(args[2])
        except ValueError:
            return await message.reply("❌ Invalid base price.")
    elif len(args) == 2 and message.reply_to_message:
        user = message.reply_to_message.from_user
        try:
            base_price = int(args[1])
        except ValueError:
            return await message.reply("❌ Invalid base price.")
    else:
        return await message.reply(
            "⚠️ Usage:\n"
            "• `/auctionstart user base_price`\n"
            "• Reply `/auctionstart base_price`"
        )

    # ── Register player ──
    players_col.update_one(
        {"user_id": user.id, "chat_id": chat_id},
        {"$setOnInsert": {
            "user_id": user.id,
            "chat_id": chat_id,
            "fullname": user.first_name or "",
            "username": user.username,
            "status": "unsold",
            "base_price": 0
        }},
        upsert=True
    )

    if get_player(user.id, chat_id).get("status") != "unsold":
        return await message.reply("⚠️ Player already sold or in auction.")

    players_col.update_one(
        {"user_id": user.id, "chat_id": chat_id},
        {"$set": {"base_price": base_price}}
    )

    # ── Create auction state ──
    auction = Auction(chat_id, user.id, base_price, base_price)
    auction.end_time = time.time() + Config.WAITTIME
    auction_state[chat_id] = auction

    # ── Caption FIRST (instant) ──
    caption = (
        f"🎈 **Auction Started!**\n\n"
        f"🏆 Tournament: **{tournament['title']}**\n\n"
        f"👤 Player: {user.mention}\n"
        f"🆔 ID: `{user.id}`\n"
        f"💸 Base Price: ©{base_price}\n\n"
        f"⏳ Preparing auction card..."
    )

    msg = await bot.send_message(chat_id, caption)

    # ── Background work ──
    async def build_and_edit():
        # Profile pic cache
        pfp_path = PFP_CACHE.get(user.id)
        if not pfp_path and user.photo:
            try:
                pfp_path = await bot.download_media(
                    user.photo.big_file_id,
                    file_name=f"{user.id}.jpg"
                )
                PFP_CACHE[user.id] = pfp_path
            except:
                pfp_path = None

        # Heavy image generation (non-blocking)
        card = await asyncio.to_thread(
            generate_card, "auctionstart", user_pfp=pfp_path
        )

        # Edit message → attach photo
        await bot.edit_message_media(
            chat_id=chat_id,
            message_id=msg.id,
            media=InputMediaPhoto(
                card,
                caption=caption.replace("⏳ Preparing auction card...", "➡ Use /bid to place your bid")
            )
        )

        # Pin safely
        try:
            chat = await bot.get_chat(chat_id)
            if not chat.pinned_message or chat.pinned_message.id != msg.id:
                await bot.pin_chat_message(chat_id, msg.id, disable_notification=True)
        except:
            pass

    asyncio.create_task(build_and_edit())

    auction.timer_task = asyncio.create_task(
        auction_countdown(bot, chat_id)
    )

@Client.on_message(filters.command("bid") & filters.group)
async def place_bid(bot, message):
    """
    /bid [amount]
    - no amount: auto-increment according to slab
    - with amount: direct bid (must be > current bid). If it's a large/direct jump, team cooldown = 15s else 8s.
    - prevents same team bidding twice in a row
    - enforces team purse
    - extends auction.end_time to Config.WAITTIME seconds after accepted bid
    """
    chat_id = resolve_chat_id(message.chat.id) if "resolve_chat_id" in globals() else message.chat.id
    user = message.from_user

    auction = auction_state.get(chat_id)
    if not auction or not auction.active:
        return await message.reply("⚠️ No active auction right now.")

    # Find bidder's team (must be registered in this tournament)
    team = teams_col.find_one({"chat_id": chat_id, "bidder_list": user.id})
    if not team:
        return await message.reply("⚠️ You are not a registered bidder for any team.")

    team_name = team["team_name"]

    players_count = len(team.get("sold_players", []))
    if players_count > 10 :
        return await message.reply(f"❌ {team_name} have bought maximum playeres. You can't bid anymore.")

    # Prevent same team consecutive bids
    if auction.leading_team == team_name:
        return await message.reply("⚠️ Your team already has the highest bid. Wait for another team to overbid.")

    # Parse bid amount (if any)
    args = message.text.split()
    direct_bid = None
    if len(args) == 2:
        try:
            direct_bid = int(args[1])
        except ValueError:
            return await message.reply("❌ Invalid bid amount. Use a number.")

    # Compute next minimum increment
    next_min = auction.current_bid + get_increment(auction.current_bid)

    # Determine bid_amount and cooldown to apply to the team
    if direct_bid is not None:
        # Direct bid: must be strictly greater than current
        if direct_bid <= auction.current_bid:
            return await message.reply("⚠️ Bid must be higher than the current bid.")
        
        
        if direct_bid % 100 != 0:
            return await message.reply(f"⚠️ For large jumps bid must increase in multiples of 100.")
        cooldown = 15

        bid_amount = direct_bid
    else:
        bid_amount = next_min
        cooldown = 8

    # Team cooldown check
    last_bid_time = auction.team_cooldowns.get(team_name, 0)
    elapsed = time.time() - last_bid_time
    if elapsed < cooldown:
        wait_left = int(cooldown - elapsed)
        return await message.reply(f"⏳ Your team must wait {wait_left}s before bidding again.")

    # Purse check
    if bid_amount > team.get("purse", 0):
        return await message.reply("❌ Your team doesn't have enough purse for this bid.")

    # Accept bid: update auction state (no cancelling timer)
    auction.current_bid = bid_amount
    auction.leading_team = team_name
    auction.leading_owner_id = user.id
    auction.last_bid_time = time.time()
    auction.bid_history.append({
        "user_id": user.id,
        "team_name": team_name,
        "bid": bid_amount,
        "ts": auction.last_bid_time
    })
    auction.team_cooldowns[team_name] = time.time()

    # Debug/log
    print(f"[DEBUG] New leading team: {team_name}, bid: {bid_amount} (by {user.id})")

    # Extend auto-end timer: always use configured WAITTIME seconds after last valid bid
    auction.end_time = time.time() + getattr(Config, "WAITTIME", 10)

    # Ensure countdown task is running; if it's finished or missing, start it
    if not auction.timer_task or auction.timer_task.done():
        auction.timer_task = asyncio.create_task(auction_countdown(bot, chat_id))

    # Announce bid in chat (reply keeps auction lively)
    await message.reply(
        f"💰 Bid placed: {bid_amount}\n"
        f"🧧 Team: {team_name} ({user.mention})"
    )


# ===============================
# Command: /finalbid (Admin Override)
# ===============================
@Client.on_message(filters.command("finalbid") & filters.group)
@co_owner
async def finalbid(bot, message):
    chat_id = resolve_chat_id(message.chat.id)
    await finalize_auction(bot, chat_id)


# ===============================
# Finalize Auction
# ===============================
async def finalize_auction(bot, chat_id: int):
    auction = auction_state.get(chat_id)
    if not auction or not auction.active:
        print("Gaya BC")
        return

    auction.active = False

    try:
        player = get_player(auction.player_id, chat_id)
        if not player:
            print("Player not found")
            return
        pusr = await bot.get_users(int(auction.player_id))
        pname = pusr.first_name

        if not auction.leading_team:
            players_col.update_one(
                {"user_id": auction.player_id, "chat_id": chat_id},
                {"$set": {"status": "unsold"}}
            )
            return await bot.send_message(chat_id, "❌ No bids received. Player remains unsold.")

        # DB updates
        teams_col.update_one(
            {"chat_id": chat_id, "team_name": auction.leading_team},
            {
                "$inc": {"purse": -auction.current_bid},
                "$push": {
                    "sold_players": {
                        "player_id": auction.player_id,
                        "player_name": pname,
                        "sold_price": auction.current_bid
                    }
                }
            }
        )

        players_col.update_one(
            {"user_id": auction.player_id, "chat_id": chat_id},
            {
                "$set": {
                    "status": "sold",
                    "sold_to": auction.leading_team,
                    "sold_price": auction.current_bid
                }
            }
        )

        # ✅ SOLD message
        await send_sold_message(bot, chat_id, auction)

    except Exception as e:
        print(f"[ERROR] finalize_auction failed: {e}")
