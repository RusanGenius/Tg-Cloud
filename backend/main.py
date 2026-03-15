import os
import asyncio
import logging
from typing import Optional, List
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv
from supabase import create_client, Client
from postgrest.exceptions import APIError as SupabaseAPIError

from aiogram import Bot, Dispatcher, F
from aiogram.types import Update, Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, LabeledPrice, PreCheckoutQuery, ContentType
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
import aiohttp

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_USERNAME = "astermaneiro"
ADMIN2_USERNAME = "genxcid21"

# Validate configuration
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables!")
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Supabase credentials not found!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create aiohttp session with timeout
aiohttp_session: aiohttp.ClientSession = None

async def get_aiohttp_session():
    """Get or create aiohttp session."""
    global aiohttp_session
    if aiohttp_session is None or aiohttp_session.closed:
        aiohttp_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    return aiohttp_session

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- RETRY DECORATOR FOR SUPABASE ---
def retry_supabase(max_attempts=3, delay=1.0):
    """Retry decorator for Supabase operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (SupabaseAPIError, aiohttp.ClientError) as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_attempts} failed: {e}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (2 ** attempt))
            logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            raise last_exception
        return wrapper
    return decorator

# --- FSM STATES ---

class SupportReply(StatesGroup):
    waiting_for_reply = State()

# --- TEMPLATES ---

SUPPORT_TEMPLATES = {
    "bug": "Спасибо за сообщение о баге! Мы обязательно рассмотрим его и исправим в ближайшее время.",
    "complaint": "Спасибо за обратную связь! Мы рассмотрим вашу жалобу и примем необходимые меры.",
    "suggestion": "Спасибо за предложение! Мы обязательно рассмотрим его и учтём в будущей разработке."
}

# --- ADMIN HELPERS ---

def get_admin_id(username: str) -> Optional[int]:
    """Get admin ID by username."""
    try:
        # Remove @ if present
        clean_username = username.lstrip('@')
        res = supabase.table("users").select("id").eq("username", clean_username).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]['id']
        print(f"Admin '{username}' not found in database")
        return None
    except Exception as e:
        print(f"Error getting admin ID for '{username}': {e}")
        return None

def is_main_admin(user_id: int) -> bool:
    """Check if user is main admin."""
    admin_id = get_admin_id(ADMIN_USERNAME)
    return user_id == admin_id

def is_second_admin(user_id: int) -> bool:
    """Check if user is second admin."""
    admin2_id = get_admin_id(ADMIN2_USERNAME)
    return user_id == admin2_id

def is_any_admin(user_id: int) -> bool:
    """Check if user is any admin."""
    return is_main_admin(user_id) or is_second_admin(user_id)

def can_manage_support(user_id: int) -> bool:
    """Check if user can manage support (main admin always can, second admin if not blocked)."""
    if is_main_admin(user_id):
        return True
    if is_second_admin(user_id):
        # Check if second admin is blocked from support
        res = supabase.table("users").select("support_blocked").eq("id", user_id).single().execute()
        return not (res.data and res.data.get('support_blocked', False))
    return False

# --- HELPER FUNCTIONS ---

def check_is_blocked(user_id: int):
    try:
        res = supabase.table("users").select("username, is_blocked").eq("id", user_id).single().execute()
        if res.data:
            # Admin cannot be blocked
            if res.data['username'] == ADMIN_USERNAME: return
            if res.data.get('is_blocked', False):
                raise HTTPException(status_code=403, detail="USER_BLOCKED")
    except HTTPException:
        raise
    except:
        pass

def get_folder_tree_text(user_id, folder_id, indent=0):
    items = supabase.table("items").select("*").eq("user_id", user_id).eq("parent_id", folder_id).execute().data
    items.sort(key=lambda x: (x['type'] != 'folder', x['name']))
    
    text = ""
    for i, item in enumerate(items, 1):
        prefix = "    " * indent
        if item['type'] == 'folder':
            text += f"{prefix}{i}. Папка «{item['name']}»:\n"
            text += get_folder_tree_text(user_id, item['id'], indent + 1)
        else:
            text += f"{prefix}{i}. {item['name']}\n"
    return text

async def copy_folder_recursive(source_folder_id, target_user_id, target_parent_id=None):
    """Recursively copies a folder to another user."""
    folder_res = supabase.table("items").select("*").eq("id", source_folder_id).single().execute()
    if not folder_res.data: return
    
    source_folder = folder_res.data
    new_folder_data = {
        "user_id": target_user_id,
        "name": source_folder['name'],
        "type": "folder",
        "parent_id": target_parent_id
    }
    new_folder = supabase.table("items").insert(new_folder_data).execute().data[0]
    
    items = supabase.table("items").select("*").eq("parent_id", source_folder_id).execute().data
    
    for item in items:
        if item['type'] == 'folder':
            await copy_folder_recursive(item['id'], target_user_id, new_folder['id'])
        else:
            new_file = {
                "user_id": target_user_id,
                "name": item['name'],
                "type": "file",
                "file_id": item['file_id'],
                "size": item['size'],
                "parent_id": new_folder['id']
            }
            supabase.table("items").insert(new_file).execute()

async def send_folder_contents(chat_id, folder_id):
    """Recursively sends files to a chat."""
    items = supabase.table("items").select("*").eq("parent_id", folder_id).execute().data
    items.sort(key=lambda x: (x['type'] != 'folder', x['name']))

    for item in items:
        if item['type'] == 'folder':
            await bot.send_message(chat_id, f"📂 <b>{item['name']}</b>", parse_mode="HTML")
            await send_folder_contents(chat_id, item['id'])
        else:
            try:
                if item['name'].lower().endswith(('.jpg', '.jpeg', '.png')):
                    await bot.send_photo(chat_id, item['file_id'], caption=item['name'])
                elif item['name'].lower().endswith(('.mp4', '.mov')):
                    await bot.send_video(chat_id, item['file_id'], caption=item['name'])
                else:
                    await bot.send_document(chat_id, item['file_id'], caption=item['name'])
                await asyncio.sleep(0.3) # Anti-flood delay
            except:
                pass


# --- PAYMENT LOGIC (STARS) ---

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payment_info = message.successful_payment
    await message.answer(f"⭐ Спасибо за поддержку! Получено звёзд: {payment_info.total_amount}")


# --- BOT HANDLERS ---

@dp.message(CommandStart())
async def command_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    
    # Logic to fix missing usernames
    username = message.from_user.username
    if not username:
        username = message.from_user.first_name or "User"
    
    try:
        supabase.table("users").upsert({"id": user_id, "username": username}).execute()
    except Exception:
        pass

    args = command.args
    
    # 1. FILE SHARING
    if args and args.startswith("file_"):
        processing_message = await message.answer("⏳")
        requested_uuid = args.replace("file_", "")
        try:
            res = supabase.table("items").select("*").eq("id", requested_uuid).limit(1).execute()
            if res.data:
                file_data = res.data[0]
                await processing_message.edit_text(f"📂 Вам отправили файл: <b>{file_data['name']}</b>", parse_mode="HTML")
                if file_data['type'] == 'folder':
                     await message.answer("Это папка. Используйте ссылку для папки.")
                     return
                try:
                    f_id = file_data['file_id']
                    name = file_data['name'].lower()
                    if name.endswith(('.jpg', '.jpeg', '.png')):
                        await message.answer_photo(f_id)
                    elif name.endswith(('.mp4', '.mov')):
                        await message.answer_video(f_id)
                    else:
                        await message.answer_document(f_id)
                except Exception:
                    await message.answer("Ошибка при отправке файла.")
            else:
                await processing_message.edit_text("Файл не найден.")
        except Exception:
             await processing_message.edit_text("Некорректная ссылка.")
    
    # 2. FOLDER SHARING
    elif args and args.startswith("folder_"):
        processing_message = await message.answer("⏳")
        folder_uuid = args.replace("folder_", "")
        try:
            res = supabase.table("items").select("*").eq("id", folder_uuid).eq("type", "folder").limit(1).execute()
            if res.data:
                folder_data = res.data[0]
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="☁️ Сохранить в облако", callback_data=f"save_{folder_uuid}")],
                    [InlineKeyboardButton(text="📥 Выгрузить в чат", callback_data=f"send_{folder_uuid}")],
                    [InlineKeyboardButton(text="👀 Посмотреть содержимое", callback_data=f"view_{folder_uuid}")]
                ])
                await processing_message.edit_text(
                    f"📁 Вам отправили папку «<b>{folder_data['name']}</b>» с файлами.", 
                    reply_markup=kb, 
                    parse_mode="HTML"
                )
            else:
                await processing_message.edit_text("Папка не найдена или удалена.")
        except Exception:
            await processing_message.edit_text("Некорректная ссылка на папку.")
            
    else:
        await message.answer("Привет! Отправь мне файлы для сохранения или открой Mini App.", 
                             reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                 [InlineKeyboardButton(text="Открыть Tg Cloud", web_app={"url": "https://tg-cloud-frontend.vercel.app"})] 
                             ]))

@dp.callback_query(F.data.startswith("save_"))
async def cb_save_folder(callback: CallbackQuery):
    folder_id = callback.data.split("_")[1]
    user_id = callback.from_user.id
    await callback.answer("Начинаю копирование...")
    try:
        await copy_folder_recursive(folder_id, user_id, None)
        await callback.message.answer("✅ Папка успешно сохранена в ваше облако!")
    except:
        await callback.message.answer("Ошибка при копировании.")

@dp.callback_query(F.data.startswith("send_"))
async def cb_send_folder(callback: CallbackQuery):
    folder_id = callback.data.split("_")[1]
    await callback.answer("Начинаю отправку файлов...")
    await callback.message.answer("⏳ Выгрузка файлов началась...")
    try:
        await send_folder_contents(callback.from_user.id, folder_id)
        await callback.message.answer("✅ Выгрузка завершена.")
    except:
        await callback.message.answer("Ошибка при отправке.")

@dp.callback_query(F.data.startswith("view_"))
async def cb_view_folder(callback: CallbackQuery):
    folder_id = callback.data.split("_")[1]
    await callback.answer()
    
    # Get folder info for the owner's user_id
    folder_res = supabase.table("items").select("user_id, name").eq("id", folder_id).single().execute()
    if not folder_res.data:
        await callback.message.answer("Папка не найдена.")
        return
        
    tree_text = get_folder_tree_text(folder_res.data['user_id'], folder_id, indent=0)
    msg_text = f"Папка «{folder_res.data['name']}»:\n\n{tree_text}" if tree_text else f"Папка «{folder_res.data['name']}» пуста."
    
    if len(msg_text) > 4000: msg_text = msg_text[:4000] + "\n..."
    await callback.message.answer(msg_text)


# --- SUPPORT CALLBACKS ---

@dp.callback_query(F.data.startswith("rt_"))
async def cb_reply_template(callback: CallbackQuery, state: FSMContext):
    """Handle template reply button click."""
    await callback.answer()
    
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username or f"ID:{admin_id}"

    # Parse callback data: rt_{user_id}_{type}
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.message.answer("❌ Ошибка обработки запроса")
        return
    
    try:
        user_id = int(parts[1])
        support_type = parts[2] if len(parts) > 2 else "complaint"
    except ValueError:
        await callback.message.answer("❌ Ошибка обработки запроса")
        return
    
    # Get template
    template = SUPPORT_TEMPLATES.get(support_type, "Спасибо за обратную связь!")
    
    # Send template to user with admin signature
    signature = f"\n\n<i>— @{admin_username}</i>" if is_second_admin(admin_id) else ""
    message_text = f"📬 <b>Ответ от поддержки</b>:\n\n{template}{signature}"
    
    try:
        await bot.send_message(user_id, message_text, parse_mode="HTML")
        await callback.message.answer(f"✅ Шаблон отправлен пользователю ID: {user_id}")
        
        # Notify main admin if second admin responded
        if is_second_admin(admin_id):
            main_admin_id = get_admin_id(ADMIN_USERNAME)
            if main_admin_id:
                await bot.send_message(
                    main_admin_id,
                    f"📋 <b>Ответ от @{admin_username}</b>:\n\n"
                    f"Пользователю ID:{user_id} отправлен шаблон: <i>{support_type}</i>",
                    parse_mode="HTML"
                )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка отправки: {e}")
    
    await state.clear()

@dp.callback_query(F.data.startswith("rc_"))
async def cb_reply_custom(callback: CallbackQuery, state: FSMContext):
    """Handle custom reply button click - set state for waiting admin message."""
    await callback.answer()
    
    admin_id = callback.from_user.id
    admin_username = callback.from_user.username or f"ID:{admin_id}"
    
    # Parse callback data: rc_{user_id}
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.message.answer("❌ Ошибка обработки запроса")
        return
    
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await callback.message.answer("❌ Ошибка обработки запроса")
        return
    
    # Store target user and admin info in FSM state
    await state.update_data(target_user_id=target_user_id, admin_username=admin_username, admin_id=admin_id)
    await state.set_state(SupportReply.waiting_for_reply)
    
    await callback.message.answer(
        "✏️ <b>Режим ответа пользователю</b>\n\n"
        f"Отправьте сообщение, и оно будет переслано пользователю ID: {target_user_id}\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )

@dp.message(SupportReply.waiting_for_reply)
async def handle_admin_reply(message: Message, state: FSMContext):
    """Handle admin's custom reply message."""
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    admin_username = data.get("admin_username")
    admin_id = data.get("admin_id")

    if not target_user_id:
        await message.answer("❌ Ошибка: пользователь не указан")
        await state.clear()
        return

    # Copy the message to preserve all content (text, media, etc.)
    try:
        # Add signature if second admin
        caption = "📬 <b>Ответ от поддержки</b>"
        if is_second_admin(admin_id):
            caption = f"📬 <b>Ответ от поддержки</b>\n<i>— @{admin_username}</i>"
        
        await bot.copy_message(
            chat_id=target_user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode="HTML"
        )
        await message.answer(f"✅ Сообщение отправлено пользователю ID: {target_user_id}")
        
        # Notify main admin if second admin responded
        if is_second_admin(admin_id):
            main_admin_id = get_admin_id(ADMIN_USERNAME)
            if main_admin_id:
                await bot.send_message(
                    main_admin_id,
                    f"📋 <b>Ответ от @{admin_username}</b>:\n\n"
                    f"Пользователю ID:{target_user_id} отправлено сообщение:\n"
                    f"<blockquote>{message.text or '📎 Медиафайл'}</blockquote>",
                    parse_mode="HTML"
                )
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    await state.clear()

@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current FSM state."""
    await state.clear()
    await message.answer("✅ Режим ответа отменён")

@dp.message(Command("reset_state"))
async def cmd_reset_state(message: Message, state: FSMContext):
    """Reset FSM state (useful if bot gets stuck)."""
    await state.clear()
    logger.info(f"FSM state reset for user {message.from_user.id}")
    await message.answer("✅ Состояние сброшено. Попробуйте снова.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Check bot status and webhook info."""
    status_message = await message.answer("⏳ Проверка статуса...")
    
    try:
        bot_info = await bot.get_me()
        webhook_info = await bot.get_webhook_info()
        
        status_text = (
            f"🤖 <b>Бот:</b> @{bot_info.username}\n"
            f"✅ <b>Статус:</b> Работает\n\n"
            f"🔗 <b>Webhook:</b>\n"
            f"URL: {webhook_info.url}\n"
            f"Ошибок: {webhook_info.last_error_date or 'Нет'}\n"
            f"Ожидает: {webhook_info.pending_update_count}\n"
        )
        
        await status_message.edit_text(status_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        await status_message.edit_text(f"❌ Ошибка проверки статуса: {e}")

# --- ADMIN MANAGEMENT COMMANDS ---

@dp.message(Command("support_admins"))
async def cmd_support_admins(message: Message):
    """Show support admins status (main admin only)."""
    user_id = message.from_user.id
    
    if not is_main_admin(user_id):
        return
    
    admin2_id = get_admin_id(ADMIN2_USERNAME)
    if not admin2_id:
        await message.answer("❌ Второй админ ещё не зарегистрирован в базе")
        return
    
    # Get status
    res = supabase.table("users").select("support_blocked").eq("id", admin2_id).single().execute()
    is_blocked = res.data.get('support_blocked', False) if res.data else False
    
    status_text = "❌ Заблокирован" if is_blocked else "✅ Активен"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔒 Заблокировать" if not is_blocked else "🔓 Разблокировать",
            callback_data=f"toggle_support_{admin2_id}"
        )]
    ])
    
    await message.answer(
        f"📋 <b>Управление доступом к поддержке</b>\n\n"
        f"Второй админ: @{ADMIN2_USERNAME}\n"
        f"Статус: {status_text}\n\n"
        f"Нажми кнопку, чтобы изменить статус",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query(F.data.startswith("toggle_support_"))
async def cb_toggle_support_access(callback: CallbackQuery):
    """Toggle second admin support access."""
    admin_id = callback.from_user.id
    
    if not is_main_admin(admin_id):
        await callback.answer("❌ Доступ только для главного админа", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[2])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Get current status
    res = supabase.table("users").select("support_blocked").eq("id", target_user_id).single().execute()
    is_blocked = res.data.get('support_blocked', False) if res.data else False
    new_status = not is_blocked
    
    # Update
    supabase.table("users").update({"support_blocked": new_status}).eq("id", target_user_id).execute()
    
    status_text = "заблокирован" if new_status else "разблокирован"
    await callback.answer(f"✅ Второй админ {status_text}", show_alert=True)
    
    # Update message
    new_status_text = "❌ Заблокирован" if new_status else "✅ Активен"
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔒 Заблокировать" if not new_status else "🔓 Разблокировать",
            callback_data=f"toggle_support_{target_user_id}"
        )]
    ])
    
    await callback.message.edit_text(
        f"📋 <b>Управление доступом к поддержке</b>\n\n"
        f"Второй админ: @{ADMIN2_USERNAME}\n"
        f"Статус: {new_status_text}\n\n"
        f"Нажми кнопку, чтобы изменить статус",
        parse_mode="HTML",
        reply_markup=new_keyboard
    )

@dp.message(Command("notify_old_admin"))
async def cmd_notify_old_admin(message: Message):
    """Send notification to old admin Ginlys (main admin only)."""
    user_id = message.from_user.id
    
    if not is_main_admin(user_id):
        return
    
    old_admin_id = get_admin_id("Ginlys")
    if not old_admin_id:
        await message.answer("❌ Старый админ Ginlys не найден в базе")
        return
    
    notification_text = (
        "Здравствуйте, Артур!\n\n"
        "Данным сообщением уведомляем вас о том, что вам предоставлены права администратора в системе Tg Cloud.\n\n"
        "С этого момента вам доступен функционал обработки входящих запросов от пользователей. В вашу компетенцию входит:\n"
        "• Рассмотрение и решение жалоб.\n"
        "• Обработка технических отчетов о багах и ошибках.\n"
        "• Рецензирование предложений по улучшению сервиса.\n\n"
        "Желаем продуктивной работы. Команда Tg Cloud всегда на связи для уточнения рабочих вопросов."
    )
    
    try:
        await bot.send_message(old_admin_id, notification_text)
        await message.answer(f"✅ Сообщение отправлено пользователю ID: {old_admin_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

@dp.message(Command("notify_new_admin"))
async def cmd_notify_new_admin(message: Message):
    """Send notification to new admin genxcid21 (main admin only)."""
    user_id = message.from_user.id
    
    if not is_main_admin(user_id):
        return
    
    new_admin_id = get_admin_id(ADMIN2_USERNAME)
    if not new_admin_id:
        await message.answer(f"❌ Новый админ {ADMIN2_USERNAME} не найден в базе")
        return
    
    notification_text = (
        "Здравствуйте!\n\n"
        "Данным сообщением уведомляем вас о том, что вам предоставлены права администратора в системе Tg Cloud.\n\n"
        "С этого момента вам доступен функционал обработки входящих запросов от пользователей. В вашу компетенцию входит:\n"
        "• Рассмотрение и решение жалоб.\n"
        "• Обработка технических отчетов о багах и ошибках.\n"
        "• Рецензирование предложений по улучшению сервиса.\n\n"
        "Желаем продуктивной работы. Команда Tg Cloud всегда на связи для уточнения рабочих вопросов."
    )
    
    try:
        await bot.send_message(new_admin_id, notification_text)
        await message.answer(f"✅ Сообщение отправлено пользователю ID: {new_admin_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Show available commands."""
    user_id = message.from_user.id
    is_main = is_main_admin(user_id)

    commands = [
        ("/start", "Запустить бота / открыть Mini App"),
        ("/status", "🔍 Проверить статус бота и webhook"),
        ("/reset_state", "🔄 Сбросить зависшее состояние (если бот не отвечает)"),
    ]

    if is_main:
        commands.extend([
            ("/support_admins", "Управление доступом второго админа к поддержке"),
            ("/notify_new_admin", "Отправить уведомление новому админу"),
            ("/notify_old_admin", "Отправить уведомление старому админу"),
            ("/help", "Показать этот список команд"),
        ])

    commands_text = "\n".join([f"<b>{cmd}</b> — {desc}" for cmd, desc in commands])

    await message.answer(
        f"📖 <b>Доступные команды</b>:\n\n{commands_text}",
        parse_mode="HTML"
    )

@dp.message(F.document | F.photo | F.video | F.audio)
async def handle_files(message: Message):
    user_id = message.from_user.id
    
    # Check for block
    try: check_is_blocked(user_id)
    except Exception: 
        await message.answer("⛔ Ваш аккаунт заблокирован администратором.")
        return

    file_id = None
    file_name = "Без названия"
    file_size = 0
    thumbnail_id = None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "doc"
        file_size = message.document.file_size
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"img_{int(message.date.timestamp())}.jpg"
        file_size = message.photo[-1].file_size
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        file_size = message.video.file_size
        if message.video.thumbnail:
            thumbnail_id = message.video.thumbnail.file_id
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or f"audio_{int(message.date.timestamp())}.mp3"
        file_size = message.audio.file_size

    if file_id:
        try:
            new_file = {
                "user_id": user_id,
                "name": file_name,
                "type": "file",
                "file_id": file_id,
                "size": file_size,
                "parent_id": None,
                "thumbnail_id": thumbnail_id
            }
            supabase.table("items").insert(new_file).execute()
            await message.answer(f"💾 Сохранено: {file_name}")
        except Exception as e:
            print(e)
            await message.answer("Ошибка сохранения.")

# --- API INITIALIZATION ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize bot and webhook on startup."""
    global aiohttp_session
    
    # Create aiohttp session
    aiohttp_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    bot.session = aiohttp_session
    
    if WEBHOOK_URL:
        try:
            # Delete old webhook first to avoid conflicts
            logger.info("🔄 Deleting old webhook...")
            await bot.delete_webhook()
            
            # Set new webhook
            webhook_full_url = f"{WEBHOOK_URL}/webhook"
            logger.info(f"🔗 Setting webhook to: {webhook_full_url}")
            result = await bot.set_webhook(webhook_full_url)
            
            if result:
                logger.info(f"✅ Webhook successfully set to {WEBHOOK_URL}/webhook")
            else:
                logger.error("❌ Failed to set webhook")
            
            yield
            
            # Cleanup on shutdown
            logger.info("🔄 Deleting webhook on shutdown...")
            await bot.delete_webhook()
            await aiohttp_session.close()
            
        except Exception as e:
            logger.error(f"❌ Webhook setup error: {e}", exc_info=True)
            # Fall back to polling mode
            logger.info("🔄 Falling back to polling mode...")
            asyncio.create_task(dp.start_polling(bot))
            yield
            await aiohttp_session.close()
    else:
        logger.warning("⚠️ WEBHOOK_URL not set. Starting in polling mode.")
        asyncio.create_task(dp.start_polling(bot))
        yield
        await aiohttp_session.close()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REQUEST MODELS ---

class AdminRequest(BaseModel):
    admin_id: int
    target_user_id: Optional[int] = None

class SupportRequest(BaseModel):
    user_id: int
    type: str
    message: str

class DeleteAllRequest(BaseModel):
    user_id: int

class FolderRequest(BaseModel):
    user_id: int
    name: str
    parent_id: Optional[str] = None

class RenameRequest(BaseModel):
    item_id: str
    new_name: str

class ItemRequest(BaseModel):
    item_id: str

class DownloadRequest(BaseModel):
    user_id: int
    file_id: str
    file_name: str
    recipient_id: Optional[int] = None

class MoveRequest(BaseModel):
    file_id: str
    folder_id: Optional[str]

class InvoiceRequest(BaseModel):
    amount: int
    title: str = "Поддержка автора"
    description: str = "Донат на развитие проекта"

# --- WEBHOOK ENDPOINT ---

@app.post("/webhook")
async def bot_webhook(update: dict):
    """
    Endpoint to receive updates from Telegram.
    Added extensive logging and error handling for debugging.
    """
    try:
        logger.info(f"📥 Received webhook update: {update.get('update_id', 'unknown')}")
        
        # Validate update
        if not update:
            logger.warning("⚠️ Empty update received")
            return {"status": "error", "message": "Empty update"}
        
        # Create Update object
        try:
            telegram_update = Update.model_validate(update, context={"bot": bot})
        except Exception as e:
            logger.error(f"❌ Failed to parse update: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid update format: {e}")
        
        # Get update type for logging
        update_type = "unknown"
        if telegram_update.message:
            update_type = f"message ({telegram_update.message.content_type})"
        elif telegram_update.callback_query:
            update_type = "callback_query"
        elif telegram_update.edited_message:
            update_type = "edited_message"
        
        logger.info(f"📩 Processing {update_type} from user {telegram_update.user_id if telegram_update.user_id else 'unknown'}")
        
        # Process update
        try:
            await dp.feed_update(bot=bot, update=telegram_update)
            logger.info(f"✅ Update {update.get('update_id', 'unknown')} processed successfully")
        except (TelegramRetryAfter, TelegramAPIError) as e:
            logger.error(f"❌ Telegram API error: {e}")
            # Don't raise - Telegram will retry
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.error(f"❌ Handler error: {e}", exc_info=True)
            # Don't raise - log and continue
            return {"status": "error", "message": f"Handler error: {e}"}
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        # Always return OK to prevent Telegram from stopping webhook
        return {"status": "ok", "warning": f"Error logged: {e}"}

# --- API ENDPOINTS: ADMIN ---

@app.post("/api/admin/users")
async def get_all_users(req: AdminRequest):
    # Check if user is admin
    admin = supabase.table("users").select("username").eq("id", req.admin_id).single().execute()
    if not admin.data or admin.data['username'] != ADMIN_USERNAME:
        raise HTTPException(403, "Access Denied")
    
    users = supabase.table("users").select("*").order("id", desc=True).execute().data
    # Admin is always on top
    users.sort(key=lambda u: u['username'] != ADMIN_USERNAME)
    return users

@app.post("/api/admin/block")
async def toggle_block_user(req: AdminRequest):
    admin = supabase.table("users").select("username").eq("id", req.admin_id).single().execute()
    if not admin.data or admin.data['username'] != ADMIN_USERNAME:
        raise HTTPException(403, "Access Denied")
    
    if req.target_user_id == req.admin_id: return {"status": "error"} # Cannot block self

    curr = supabase.table("users").select("is_blocked").eq("id", req.target_user_id).single().execute()
    new_status = not curr.data.get('is_blocked', False)
    
    supabase.table("users").update({"is_blocked": new_status}).eq("id", req.target_user_id).execute()
    return {"status": "ok", "is_blocked": new_status}

@app.post("/api/admin/delete_user")
async def delete_user_admin(req: AdminRequest):
    admin = supabase.table("users").select("username").eq("id", req.admin_id).single().execute()
    if not admin.data or admin.data['username'] != ADMIN_USERNAME:
        raise HTTPException(403, "Access Denied")

    if req.target_user_id == req.admin_id: return {"status": "error"}

    supabase.table("items").delete().eq("user_id", req.target_user_id).execute()
    supabase.table("users").delete().eq("id", req.target_user_id).execute()
    return {"status": "ok"}

@app.post("/api/admin/toggle_support_access")
async def toggle_support_access(req: AdminRequest):
    """Toggle second admin's access to support (main admin only)."""
    admin = supabase.table("users").select("username").eq("id", req.admin_id).single().execute()
    if not admin.data or admin.data['username'] != ADMIN_USERNAME:
        raise HTTPException(403, "Access Denied")
    
    # Check if target is second admin
    target = supabase.table("users").select("username").eq("id", req.target_user_id).single().execute()
    if not target.data or target.data['username'] != ADMIN2_USERNAME:
        raise HTTPException(400, detail="Target is not second admin")
    
    # Get current status
    curr = supabase.table("users").select("support_blocked").eq("id", req.target_user_id).single().execute()
    new_status = not (curr.data.get('support_blocked', False))
    
    # Update support_blocked status
    supabase.table("users").update({"support_blocked": new_status}).eq("id", req.target_user_id).execute()
    return {"status": "ok", "support_blocked": new_status}

@app.get("/api/admin/support_status")
async def get_support_status(admin_id: int):
    """Get support access status for second admin (main admin only)."""
    admin = supabase.table("users").select("username").eq("id", admin_id).single().execute()
    if not admin.data or admin.data['username'] != ADMIN_USERNAME:
        raise HTTPException(403, "Access Denied")
    
    admin2_id = get_admin_id(ADMIN2_USERNAME)
    if not admin2_id:
        return {"admin2_exists": False, "support_blocked": False}
    
    curr = supabase.table("users").select("support_blocked").eq("id", admin2_id).single().execute()
    return {
        "admin2_exists": True,
        "admin2_id": admin2_id,
        "support_blocked": curr.data.get('support_blocked', False) if curr.data else False
    }


# --- API ENDPOINTS: CLIENT ---

@app.post("/api/support")
async def handle_support_request(req: SupportRequest):
    try:
        # 1. Get Admin IDs
        admin1_id = get_admin_id(ADMIN_USERNAME)
        admin2_id = get_admin_id(ADMIN2_USERNAME)
        
        print(f"Admin IDs: {ADMIN_USERNAME}={admin1_id}, {ADMIN2_USERNAME}={admin2_id}")
        
        if not admin1_id:
            print(f"Main admin user '{ADMIN_USERNAME}' not found in database.")
            raise HTTPException(status_code=500, detail="Main admin not configured.")

        # 2. Get User Info
        user = supabase.table("users").select("username").eq("id", req.user_id).single().execute()
        username = f"@{user.data['username']}" if user.data and user.data.get('username') else f"ID: {req.user_id}"

        # 3. Format message
        type_map = {
            "bug": "сообщение о баге",
            "complaint": "жалобу",
            "suggestion": "предложение"
        }
        type_str = type_map.get(req.type, "сообщение")

        message_to_admin = (
            f"⚠️ Пользователь {username} написал {type_str}:\n\n"
            f"<blockquote>{req.message}</blockquote>"
        )

        # 4. Create inline keyboard with reply options
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Ответить шаблоном", callback_data=f"rt_{req.user_id}_{req.type}")],
            [InlineKeyboardButton(text="✏️ Написать ответ", callback_data=f"rc_{req.user_id}")]
        ])

        # 5. Send message to both admins
        sent_count = 0
        for admin_id, admin_name in [(admin1_id, ADMIN_USERNAME), (admin2_id, ADMIN2_USERNAME)]:
            if admin_id:
                try:
                    await bot.send_message(admin_id, message_to_admin, parse_mode="HTML", reply_markup=keyboard)
                    sent_count += 1
                    print(f"✅ Support message sent to {admin_name} (ID: {admin_id})")
                except Exception as e:
                    print(f"❌ Failed to send to {admin_name} (ID: {admin_id}): {e}")
            else:
                print(f"⚠️ {admin_name} not found in database (ID is None)")
        
        print(f"Support message sent to {sent_count}/2 admins from user {req.user_id}")
        return {"status": "ok"}
    except Exception as e:
        print(f"Error in /api/support: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profile")
async def get_profile_stats(user_id: int):
    check_is_blocked(user_id)
    try:
        res = supabase.table("items").select("type, name, size").eq("user_id", user_id).execute()
        items = res.data
        total_files = 0; total_size_bytes = 0
        count_photos = 0; count_videos = 0; count_docs = 0; count_folders = 0
        
        for i in items:
            total_size_bytes += (i['size'] or 0)
            if i['type'] == 'folder': count_folders += 1
            else:
                total_files += 1
                name = i['name'].lower()
                if name.endswith(('.jpg', '.jpeg', '.png')): count_photos += 1
                elif name.endswith(('.mp4', '.mov')): count_videos += 1
                else: count_docs += 1
        
        total_size_mb = round(total_size_bytes / (1024 * 1024), 2)
        return {
            "total_files": total_files,
            "total_size_mb": total_size_mb,
            "counts": {"photos": count_photos, "videos": count_videos, "docs": count_docs, "folders": count_folders}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Stats error")

@app.get("/api/files")
async def get_files(user_id: int, folder_id: str = None, mode: str = 'strict'):
    check_is_blocked(user_id)
    query = supabase.table("items").select("*").eq("user_id", user_id)
    if mode == 'global': query = query.neq("type", "folder")
    elif mode == 'folders': query = query.eq("type", "folder")
    elif folder_id and folder_id != "null" and folder_id != "root": query = query.eq("parent_id", folder_id)
    else: query = query.is_("parent_id", "null")
    query = query.order("type", desc=True).order("created_at", desc=True)
    return query.execute().data

@app.post("/api/delete_all")
async def delete_all_data(req: DeleteAllRequest):
    check_is_blocked(req.user_id)
    try:
        supabase.table("items").delete().eq("user_id", req.user_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create_folder")
async def create_folder(req: FolderRequest):
    check_is_blocked(req.user_id)
    try:
        parent = req.parent_id
        if parent == "null" or parent == "": parent = None
        new_folder = {"user_id": req.user_id, "name": req.name, "type": "folder", "parent_id": parent}
        supabase.table("items").insert(new_folder).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rename")
async def rename_item(req: RenameRequest):
    try:
        supabase.table("items").update({"name": req.new_name}).eq("id", req.item_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete")
async def delete_item(req: ItemRequest):
    """Normal deletion: if it's a folder, files are moved to the root."""
    try:
        item = supabase.table("items").select("type").eq("id", req.item_id).execute()
        if item.data and item.data[0]['type'] == 'folder':
            supabase.table("items").update({"parent_id": None}).eq("parent_id", req.item_id).execute()
        supabase.table("items").delete().eq("id", req.item_id).execute()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/delete_folder_recursive")
async def delete_folder_recursive_api(req: ItemRequest):
    """Recursively deletes a folder with all its contents."""
    try:
        async def recursive_del(folder_id):
             children = supabase.table("items").select("id, type").eq("parent_id", folder_id).execute().data
             for child in children:
                 if child['type'] == 'folder':
                     await recursive_del(child['id'])
                 else:
                     supabase.table("items").delete().eq("id", child['id']).execute()
             supabase.table("items").delete().eq("id", folder_id).execute()

        await recursive_del(req.item_id)
        return {"status": "deleted_recursive"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download")
async def download_file(req: DownloadRequest):
    target_id = req.recipient_id if req.recipient_id else req.user_id
    
    if target_id != req.user_id:
        try:
            admin_check = supabase.table("users").select("username").eq("id", target_id).single().execute()
            if not admin_check.data or admin_check.data['username'] != ADMIN_USERNAME:
                raise HTTPException(status_code=403, detail="Access Denied: Only admin can redirect downloads")
        except:
            raise HTTPException(status_code=403, detail="Access Denied")

    if target_id == req.user_id:
        check_is_blocked(req.user_id)

    try:
        is_photo = req.file_name.lower().endswith(('.jpg', '.jpeg', '.png'))
        is_video = req.file_name.lower().endswith(('.mp4', '.mov'))
        
        if is_photo: await bot.send_photo(target_id, req.file_id, caption="📸")
        elif is_video: await bot.send_video(target_id, req.file_id, caption="🎥")
        else: await bot.send_document(target_id, req.file_id, caption="📄")
        
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/preview/{file_id}")
async def get_preview(file_id: str):
    try:
        file_info = await bot.get_file(file_id)
        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200: raise HTTPException(status_code=404)
                content = await resp.read()
                return Response(content=content, media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=404)

@app.post("/api/move_file")
async def move_file(req: MoveRequest):
    try:
        supabase.table("items").update({"parent_id": req.folder_id}).eq("id", req.file_id).execute()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from datetime import datetime

@app.post("/api/generate_invoice")
async def generate_invoice(req: InvoiceRequest):
    try:
        link = await bot.create_invoice_link(
            title=req.title,
            description=req.description,
            payload="donate",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Stars", amount=req.amount)]
        )
        return {"link": link}
    except Exception as e:
        logger.error(f"Error generating invoice: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Use this with cron-job.org or uptimerobot.com to prevent Render sleep.
    """
    try:
        # Check bot connection
        bot_info = await bot.get_me()
        bot_status = "ok"
    except Exception as e:
        logger.error(f"Bot health check failed: {e}")
        bot_status = f"error: {e}"
    
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "webhook_url": WEBHOOK_URL,
        "bot_username": bot_info.username if bot_info else None,
        "bot_status": bot_status
    }

@app.get("/")
async def root():
    return {"message": "Tg Cloud v3.0 (Backend)"}
