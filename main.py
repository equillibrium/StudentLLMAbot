import asyncio
import json
import logging
import os

import redis.asyncio as aioredis
from aiogram import Bot, types, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from groq import AsyncGroq
from openai import AsyncOpenAI
import google.generativeai as genai

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'),
          default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
redis = aioredis.from_url(os.getenv('REDIS_URL'))
dp = Dispatcher(storage=RedisStorage(redis))

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")

# Initialize clients for Groq, OpenAI, and Gemini
groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

generation_config = {
    "temperature": 0.2,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 4096,
    "response_mime_type": "text/plain",
}
gemini_model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    system_instruction=system_message
)

MAX_MESSAGE_LENGTH = 4096
MODEL_CHOICES = os.getenv('MODEL_CHOICES').split(',')
DEFAULT_MODEL = MODEL_CHOICES[0]


async def get_user_context(user_id):
    data = await redis.get(user_id)
    if data:
        return json.loads(data)
    return [{"role": "system", "content": system_message, "name": user_id}]


async def save_user_context(user_id, context):
    await redis.set(user_id, json.dumps(context))


async def get_user_model(user_id):
    model = await redis.get(f"{user_id}_model")
    return model.decode() if model else DEFAULT_MODEL


async def set_user_model(user_id, model):
    await redis.set(f"{user_id}_model", model)
    await redis.delete(user_id)


async def get_client_for_model(model):
    if model == MODEL_CHOICES[0]:
        return groq_client
    elif model == MODEL_CHOICES[1]:
        return openai_client
    elif model == MODEL_CHOICES[2]:  # Gemini model
        return gemini_model
    else:
        raise ValueError(f"Unknown model: {model}")


@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = str(message.from_user.id)
    chosen_model = await get_user_model(user_id)
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
async def welcome(message: types.Message):
    user_id = str(message.from_user.id)
    context = await get_user_context(user_id)
    chosen_model = await get_user_model(user_id)
    client = await get_client_for_model(chosen_model)

    try:
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
            context.append({"role": "user", "content": message.text})
            context.append({"role": "assistant", "content": response_content})
            
        else:  # Groq или OpenAI
            if chosen_model == MODEL_CHOICES[0]:  # Groq model
                response = await client.chat.completions.create(
                    model=chosen_model, stream=False, stop=None, max_tokens=4096,
                    messages=context, temperature=0.2, top_p=1, user=user_id
                )
                response_content = response.choices[0].message.content
            elif chosen_model == MODEL_CHOICES[1]:  # OpenAI model
                response = await client.chat.completions.create(
                    model=chosen_model, messages=context, temperature=0.2, max_tokens=4096
                )
                response_content = response.choices[0].message.content

    except Exception as e:
        response_content = f"Error: {str(e)}"

    if chosen_model != MODEL_CHOICES[2]:
        context.append({"role": 'assistant', "content": response_content})

    await save_user_context(user_id, context)

    text = response_content or "Произошла ошибка при получении ответа."
    if len(text) <= MAX_MESSAGE_LENGTH:
        await message.answer(text)
    else:
        chunks = [text[i:i + MAX_MESSAGE_LENGTH]
                  for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for chunk in chunks:
            await message.answer(chunk)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(str(e))
