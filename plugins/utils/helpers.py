from pyrogram import Client, filters
from pyrogram.types import Message, ChatJoinRequest
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from plugins.utils.admin_checker import is_user_admin_cq
from pyrogram.enums import ParseMode
import asyncio
from plugins.utils.templates import generate_card
from connections.logger import group_logger
from connections.mongo_db import get_tournament
START_KEYBOARD_BUTTON = [
    [
        InlineKeyboardButton('➕ ᴊᴏɪɴ ᴏᴜʀ ɢʀᴏᴜᴘ ➕', url='https://t.me/CLG_fun_zone'),
    ],
    [
        InlineKeyboardButton('🌿 ʜᴇʟᴘ ᴍᴇɴᴜ 🌿', callback_data="DEVS")
    ]
]

BACK = [
    [
        InlineKeyboardButton('◀️ Bᴀᴄᴋ Tᴏ Mᴀɪɴ ◀️', callback_data="START")
    ]
]


CLOSE = [
    [
        InlineKeyboardButton('🌷 ᴄʟᴏsᴇ 🌷', callback_data='CLOSE')
    ]
]

ACLOSE = [
    [
        InlineKeyboardButton('🌷 ᴄʟᴏsᴇ 🌷', callback_data='ACLOSE')
    ]
]


start_replymarkup = InlineKeyboardMarkup(START_KEYBOARD_BUTTON)
back_replymarkup = InlineKeyboardMarkup(BACK)
close_replymarkup = InlineKeyboardMarkup(CLOSE)
aclose_replymarkup = InlineKeyboardMarkup(ACLOSE)

START_MESSAGE = '''
✦✧✦ Wᴇʟᴄᴏᴍᴇ ᴛᴏ 𝗔𝘂𝗰𝘁𝗶𝗼𝗻 𝗕𝗼𝘁 🤖 ✦✧✦

⚡ Dɪᴠᴇ ɪɴᴛᴏ ᴛʜᴇ ᴛʜʀɪʟʟ ᴏғ ʀᴇᴀʟ-ᴛɪᴍᴇ ᴀᴜᴄᴛɪᴏɴs!

🌟 Cʀᴇᴀᴛᴇ ᴀᴜᴄᴛɪᴏɴs ғᴏʀ ʏᴏᴜʀ ғʀɪᴇɴᴅs & ᴄᴏᴍᴍᴜɴɪᴛʏ  
💰 Pʟᴀᴄᴇ ʙɪᴅs • Mᴀɴᴀɢᴇ ᴏғғᴇʀs • Wɪɴ ʀᴇᴡᴀʀᴅs  
🏆 Cʟɪᴍʙ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ᴏғ ᴛᴏᴘ ʙɪᴅᴅᴇʀs

✨ Tʜᴇ ʜᴇᴀʀᴛ & sᴏᴜʟ ᴏғ ᴛʜᴇ ʙᴏᴛ: KING (@Nini_arhi)  

🔥 Lᴇᴛ ᴛʜᴇ ʙɪᴅᴅɪɴɢ ᴀᴅᴠᴇɴᴛᴜʀᴇ ʙᴇɢɪɴ!
'''
creator_names = '''
✦✧✦ 𝗔𝘂𝗰𝘁𝗶𝗼𝗻 𝗕𝗼𝘁 • 𝗛𝗲𝗹𝗽 𝗠𝗲𝗻𝘂 ✦✧✦

🏆 𝗧𝗼𝘂𝗿𝗻𝗮𝗺𝗲𝗻𝘁 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
/start_tour       - Start a tournament
/stop_tour        - Stop tournament
/clear            - Clear all players & teams

👥 𝗧𝗲𝗮𝗺 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
/add_team {user} {team_name} - Register team
/team {team_name}               - Team details

👤 𝗣𝗹𝗮𝘆𝗲𝗿 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
/register                    - Join tournament
/deregister                  - Leave tournament
/add_player {user} {base_price} - Add player
/remove_player {user}          - Remove player
/reset {user}                  - Reset player

⚡ 𝗔𝘂𝗰𝘁𝗶𝗼𝗻 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
/auctionstart {player} - Start auction
/bid [amount]          - Place bid
/finalbid               - Force finalize
/next                   - Next unsold player (coming soon)

ℹ️ 𝗜𝗻𝗳𝗼 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
/list           - All players
/unsold         - Unsold players
/info {user}    - Player info

✨ Created & Styled by @Nini_arhi
'''



@Client.on_message(filters.media & filters.private & filters.user(5930803951))
async def media_id_handler(client, message):
        media = getattr(message, message.media.value)
        await message.reply_text(
            f"<code> {media.file_id} </code>", parse_mode=ParseMode.HTML, quote=True
        )

@Client.on_callback_query(filters.regex(pattern="^(DEVS|START|CLOSE)$"))
async def call_back_func(bot, CallbackQuery):
    
    if CallbackQuery.data == "DEVS":
        await CallbackQuery.edit_message_caption(
            caption = creator_names,
            reply_markup = back_replymarkup
        )

    if CallbackQuery.data == "START":
        await CallbackQuery.edit_message_caption(
            caption = START_MESSAGE,
            reply_markup = start_replymarkup
        )

    if CallbackQuery.data == "CLOSE":
        try:
            await CallbackQuery.answer()
            await CallbackQuery.message.delete()
            umm = await CallbackQuery.message.reply_text(
            f"Cʟᴏsᴇᴅ ʙʏ : {CallbackQuery.from_user.mention}"
            )
            await asyncio.sleep(7)
            await umm.delete()
        except:
            pass  

@Client.on_callback_query(filters.regex(pattern="^ACLOSE$"))
@is_user_admin_cq
async def admincall_back_func(bot, CallbackQuery):
    try:
        await CallbackQuery.answer()
        await CallbackQuery.message.delete()
        umm = await CallbackQuery.message.reply_text(
        f"Cʟᴏsᴇᴅ ʙʏ : {CallbackQuery.from_user.mention}"
            )
        await asyncio.sleep(7)
        await umm.delete()
    except:
        pass  

async def resolve_user(bot, identifier: str):
    """
    Resolve user by ID or username.
    Returns a pyrogram User object or None.
    """
    try:
        return await bot.get_users(identifier)
    except Exception:
        return None
    
def resolve_chat_id(incoming_chat_id: int) -> int:
    """
    If incoming_chat_id is one of the alias groups, return the canonical chat id.
    Otherwise return incoming_chat_id unchanged.
    """
    if incoming_chat_id in [-1001765208805, -1002468330645, -1002931142492]:
        return -1002055598229
    return incoming_chat_id

async def send_sold_message(bot, chat_id: int, auction):
    user = await resolve_user(bot, auction.player_id)
    try:
        pfp_path = await bot.download_media(user.photo.big_file_id, file_name=f"{user.id}.jpg")
    except:
        pfp_path = None  

    # Get tournament name
    tournament = get_tournament(chat_id)
    tour_name = tournament['title'] if tournament else "N/A"

    sold_message = (
        f"💓 Pʟᴀʏᴇʀ Sᴏʟᴅ! 💓\n\n"
        f"🏆 Tournament: {tour_name}\n\n"
        f"➲ ᴘʟᴀʏᴇʀ ɴᴀᴍᴇ: {user.mention}\n"
        f"➲ ᴘʟᴀʏᴇʀ ɪᴅ: {user.id}\n\n"
        f"💰 𝙱𝚊𝚜𝚎 𝙿𝚛𝚒𝚌𝚎: {auction.base_price} ©\n"
        f"🏷️ 𝚂𝚘𝚕𝚍 𝙿𝚛𝚒𝚌𝚎: {auction.current_bid} ©\n"
        f"👑 𝚃𝚎𝚊𝚖: {auction.leading_team}\n\n"
        f"🧩 𝑺𝒕𝒂𝒕𝒖𝒔 : *Sold*\n"
        f"🌺 **<u>Made By:</u>** @Nini_arhi"
    )

    await bot.send_message(
        chat_id=chat_id, 
        text=sold_message
    )

    try:
        card = generate_card("auctionsold", user_pfp=pfp_path)
        await bot.send_photo(
            chat_id=chat_id,
            photo=card,
            caption=sold_message
        )
    except:
        pass
