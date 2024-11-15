import asyncio
import logging
import os
import re

import google.generativeai as genai
from aiogram import Bot, types, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from google.generativeai import GenerationConfig
from groq import AsyncGroq

from states import redis, save_user_context, get_user_model, get_user_context

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'),
          default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=RedisStorage(redis))

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")

# Initialize clients for Groq, OpenAI, and Gemini
groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = GenerationConfig(
    temperature=1,
    top_p=0.95,
    top_k=40,
    max_output_tokens=8192,
    response_mime_type="text/plain"
)

gemini_client = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=system_message
)

MAX_MESSAGE_LENGTH = 4096
MODEL_CHOICES = os.getenv('MODEL_CHOICES').split(',')
DEFAULT_MODEL = MODEL_CHOICES[0]


async def set_user_model(user_id, model):
    await redis.set(f"{user_id}_model", model)
    # При смене модели создаем новый контекст с system message
    initial_context = [{"role": "system", "content": system_message}]
    await save_user_context(user_id, initial_context)


async def get_client_for_model(model):
    if model == MODEL_CHOICES[0]:
        return groq_client
    elif model == MODEL_CHOICES[1]:
        return groq_client
    elif model == MODEL_CHOICES[2]:  # Gemini model
        return gemini_client
    else:
        raise ValueError(f"Unknown model: {model}")


async def replace_asterisk(text):
    # Step 1: Find code blocks and temporarily replace '*' inside them with a placeholder
    text_with_placeholder = re.sub(r'```.*?```', lambda m: m.group(0).replace('*', '<<ASTERISK>>'), text,
                                   flags=re.DOTALL)

    # Step 2: Replace only non-double '*' occurrences outside of code blocks
    text_processed = re.sub(r'(?<!\*)\*(?!\*)', '\\*', text_with_placeholder)

    # Step 3: Restore the placeholders back to '*'
    result = text_processed.replace('<<ASTERISK>>', '*')

    return result


@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    chosen_model = await get_user_model(user_id, default_model=DEFAULT_MODEL)
    text = (f"Привет, {message.from_user.first_name}! Я Student LLMAbot. Твой Telegram ID: {user_id}\n"
            f"Текущая модель: {chosen_model}\nНапиши мне запрос, и я постараюсь помочь!")
    await message.answer(text)


@dp.message(Command("reset"))
async def reset(message: types.Message):
    text = 'Контекст нашей беседы очищен!'
    try:
        await bot.send_chat_action(message.chat.id, 'typing')
        await redis.delete(message.from_user.id)
        await message.answer(text)
    except Exception as e:
        await message.answer(str(e))


@dp.message(Command("model"))
async def choose_model(message: types.Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=model, callback_data=f"set_model:{model}")] for model in
                         MODEL_CHOICES]
    )
    await message.answer("Выбери модель:", reply_markup=keyboard)


@dp.callback_query(F.data.startswith("set_model"))
async def set_model_callback(query: types.CallbackQuery):
    user_id = str(query.from_user.id)
    chosen_model = query.data.split(":")[1]
    await set_user_model(user_id, chosen_model)
    await query.answer(f"Модель '{chosen_model}' выбрана и контекст очищен.")
    await query.message.edit_text(f"Текущая модель установлена на '{chosen_model}'.")


@dp.message(F.text)
async def chat(message: types.Message):
    user_id = str(message.from_user.id)
    context = await get_user_context(user_id, system_message=system_message)
    chosen_model = await get_user_model(user_id, default_model=DEFAULT_MODEL)
    client = await get_client_for_model(chosen_model)
    response_content = ""

    await bot.send_chat_action(message.chat.id, 'typing')

    try:
        # Добавляем сообщение пользователя в контекст сразу
        context.append({"role": "user", "content": message.text})

        if chosen_model == MODEL_CHOICES[2]:  # Gemini model
            # Преобразуем контекст в формат для Gemini
            gemini_history = []
            # Пропускаем первое системное сообщение
            for msg in context[1:]:
                if msg["role"] == "assistant":
                    gemini_history.append({
                        "role": "model",
                        "parts": [{"text": msg["content"]}]
                    })
                elif msg["role"] == "user":
                    gemini_history.append({
                        "role": "user",
                        "parts": [{"text": msg["content"]}]
                    })

            # Создаем чат-сессию с историей
            chat_session = client.start_chat(history=gemini_history)
            gemini_response = await chat_session.send_message_async(message.text)
            response_content = gemini_response.text

            # Сохраняем новые сообщения в контекст
            context.append({"role": "assistant", "content": response_content})

        else:  # Groq или OpenAI
            if chosen_model == MODEL_CHOICES[0]:  # Groq model
                response = await client.chat.completions.create(
                    model=chosen_model, stream=False, stop=None, max_tokens=8000,
                    messages=context, temperature=1, top_p=0.95
                )
                response_content = response.choices[0].message.content
            elif chosen_model == MODEL_CHOICES[1]:  # OpenAI model
                response = await client.chat.completions.create(
                    model=chosen_model, stream=False, stop=None, max_tokens=8000,
                    messages=context, temperature=1, top_p=0.95
                )
                response_content = response.choices[0].message.content

            # Добавляем ответ ассистента в контекст
            context.append({"role": "assistant", "content": response_content})

        text = response_content

        if len(text) <= MAX_MESSAGE_LENGTH:
            try:
                await message.answer(await replace_asterisk(text))
            except Exception as e:
                print(str(e))
                await message.answer(text, parse_mode=None)
        else:
            chunks = [text[i:i + MAX_MESSAGE_LENGTH]
                      for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
            for chunk in chunks:
                try:
                    await message.answer(await replace_asterisk(text))
                except Exception as e:
                    print(str(e))
                    await message.answer(chunk, parse_mode=None)

        # Сохраняем контекст только после успешной отправки
        await save_user_context(user_id, context)

    except Exception as e:
        error_text = f"Произошла ошибка: {str(e)}"
        await message.answer(error_text, parse_mode=None)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(str(e))
