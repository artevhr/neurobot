import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8708783496:AAE6zAMSROFFGofMqvVNgtFWhJQd2vBBok8"           # токен от @BotFather
OPENROUTER_API_KEY = "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"  # ключ с openrouter.ai

FALLBACK_MODELS = [
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "google/gemma-3-1b-it:free",
]

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class UserState(StatesGroup):
    waiting_topic = State()
    waiting_rewrite_text = State()


# ──────────── OpenRouter с fallback-цепочкой ────────────

async def call_openrouter(prompt: str, system: str = "") -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot",
        "X-Title": "TG Neural Bot",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with aiohttp.ClientSession() as session:
        for model in FALLBACK_MODELS:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.8,
            }
            try:
                logger.info(f"Trying model: {model}")
                async with session.post(
                    OPENROUTER_URL, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data["choices"][0]["message"]["content"].strip()
                        if text:
                            logger.info(f"OK: {model}")
                            return text
                    else:
                        logger.warning(f"{model} → {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"{model} timed out")
            except Exception as e:
                logger.warning(f"{model} error: {e}")

    return "❌ Все модели недоступны. Попробуй позже."


# ──────────── Клавиатуры ────────────

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Сгенерировать текст", callback_data="generate")],
        [InlineKeyboardButton(text="🔄 Переписать текст",    callback_data="rewrite")],
        [InlineKeyboardButton(text="ℹ️ О боте",              callback_data="about")],
    ])

def style_keyboard(action: str):
    styles = [
        ("🎓 Научный",       f"style_{action}_academic"),
        ("💼 Деловой",       f"style_{action}_business"),
        ("😊 Дружелюбный",   f"style_{action}_friendly"),
        ("🎭 Креативный",    f"style_{action}_creative"),
        ("📰 Журналистский", f"style_{action}_journalistic"),
        ("📱 SMM / соцсети", f"style_{action}_smm"),
    ]
    rows = [[InlineKeyboardButton(text=n, callback_data=cb)] for n, cb in styles]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main")]
    ])

def result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Ещё раз",        callback_data="regenerate")],
        [InlineKeyboardButton(text="🏠 Главное меню",   callback_data="back_main")],
    ])


# ──────────── Стили ────────────

STYLE_PROMPTS = {
    "academic":     "Пиши в строгом научном стиле: точные формулировки, нейтральный тон.",
    "business":     "Пиши в деловом стиле: чётко, профессионально, по существу.",
    "friendly":     "Пиши дружелюбно и тепло, как будто разговариваешь с другом.",
    "creative":     "Пиши творчески и образно, используй метафоры и живой язык.",
    "journalistic": "Пиши в журналистском стиле: факты на первом месте, без воды.",
    "smm":          "Пиши для соцсетей: вовлекающе, с эмодзи, призывами к действию.",
}
STYLE_NAMES = {
    "academic": "Научный", "business": "Деловой",
    "friendly": "Дружелюбный", "creative": "Креативный",
    "journalistic": "Журналистский", "smm": "SMM / соцсети",
}


# ──────────── Хэндлеры ────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Привет! Я <b>нейросеть-бот</b>.\n"
        "Напишу или перепишу текст на любую тему.\n\nВыбери действие:",
        reply_markup=main_keyboard(), parse_mode="HTML"
    )

@dp.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=main_keyboard())

@dp.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_keyboard())

@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    models_list = "\n".join(f"• <code>{m}</code>" for m in FALLBACK_MODELS)
    await callback.message.edit_text(
        f"🤖 <b>Нейросеть-бот</b>\n\n"
        f"Использует бесплатные модели через OpenRouter.\n"
        f"Если одна не отвечает — автоматически берёт следующую.\n\n"
        f"<b>Цепочка моделей:</b>\n{models_list}",
        reply_markup=back_kb(), parse_mode="HTML"
    )

# Выбор действия → выбор стиля
@dp.callback_query(F.data == "generate")
async def generate(callback: CallbackQuery):
    await callback.message.edit_text(
        "✍️ <b>Генерация текста</b>\n\nВыбери стиль:",
        reply_markup=style_keyboard("gen"), parse_mode="HTML"
    )

@dp.callback_query(F.data == "rewrite")
async def rewrite(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔄 <b>Переписать текст</b>\n\nВыбери стиль:",
        reply_markup=style_keyboard("rew"), parse_mode="HTML"
    )

# Стиль выбран → генерация
@dp.callback_query(F.data.startswith("style_gen_"))
async def gen_style(callback: CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_gen_", "")
    await state.update_data(style=style)
    await state.set_state(UserState.waiting_topic)
    await callback.message.edit_text(
        f"✅ Стиль: <b>{STYLE_NAMES[style]}</b>\n\n"
        "📝 Напиши тему — о чём написать текст?",
        parse_mode="HTML"
    )

# Стиль выбран → переписывание
@dp.callback_query(F.data.startswith("style_rew_"))
async def rew_style(callback: CallbackQuery, state: FSMContext):
    style = callback.data.replace("style_rew_", "")
    await state.update_data(style=style)
    await state.set_state(UserState.waiting_rewrite_text)
    await callback.message.edit_text(
        f"✅ Стиль: <b>{STYLE_NAMES[style]}</b>\n\n"
        "📋 Пришли текст, который нужно переписать:",
        parse_mode="HTML"
    )

# Получили тему
@dp.message(UserState.waiting_topic)
async def on_topic(message: Message, state: FSMContext):
    data = await state.get_data()
    style = data.get("style", "friendly")
    topic = message.text.strip()
    wait = await message.answer("⏳ Генерирую...")

    system = STYLE_PROMPTS[style]
    prompt = f"Напиши развёрнутый текст на тему: «{topic}». Объём около 200–300 слов."
    result = await call_openrouter(prompt, system)

    await state.update_data(last_prompt=prompt, last_system=system)
    await state.set_state(None)
    await wait.delete()
    await message.answer(
        f"🎨 <b>{STYLE_NAMES[style]}</b> | <i>{topic}</i>\n\n{result}",
        reply_markup=result_kb(), parse_mode="HTML"
    )

# Получили текст для переписывания
@dp.message(UserState.waiting_rewrite_text)
async def on_rewrite(message: Message, state: FSMContext):
    data = await state.get_data()
    style = data.get("style", "friendly")
    original = message.text.strip()
    wait = await message.answer("⏳ Переписываю...")

    system = STYLE_PROMPTS[style]
    prompt = f"Перепиши текст, сохранив смысл, но изменив формулировки:\n\n{original}"
    result = await call_openrouter(prompt, system)

    await state.update_data(last_prompt=prompt, last_system=system)
    await state.set_state(None)
    await wait.delete()
    await message.answer(
        f"🔄 <b>{STYLE_NAMES[style]}</b>\n\n{result}",
        reply_markup=result_kb(), parse_mode="HTML"
    )

# Повторная генерация
@dp.callback_query(F.data == "regenerate")
async def on_regen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt = data.get("last_prompt")
    system = data.get("last_system", "")
    if not prompt:
        await callback.answer("Нет сохранённого запроса.", show_alert=True)
        return
    await callback.message.edit_text("⏳ Генерирую новый вариант...")
    result = await call_openrouter(prompt, system)
    await callback.message.edit_text(result, reply_markup=result_kb(), parse_mode="HTML")


# ──────────── Запуск ────────────

async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
