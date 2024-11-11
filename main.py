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
from dotenv import load_dotenv
from groq import AsyncGroq
from httpx import AsyncClient

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'),
          default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
redis = aioredis.from_url(os.getenv('REDIS_URL'))
dp = Dispatcher(storage=RedisStorage(redis))

groq_client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'),)
                        # http_client=AsyncClient(proxies=os.getenv('PROXY_STRING')))

MAX_MESSAGE_LENGTH = 4096
MODEL = "llama3-8b-8192"

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")


async def get_user_context(user_id):
    """Retrieve user context from Redis or create a new context if it doesn't exist."""
    data = await redis.get(user_id)
    if data:
        return json.loads(data)
    return [{
        "role": "system",
        "content": system_message,
        "name": user_id
    }]


async def save_user_context(user_id, context):
    """Save user context to Redis."""
    await redis.set(user_id, json.dumps(context))


@dp.message(Command("start"))
async def start(message: types.Message):
    text = f"Я Studend LLMA Bot, использующий модель {MODEL} от Groq.\r\nНапиши мне запрос и я постараюсь помочь!"
    try:
        await get_user_context(message.from_user.id)
        await message.answer(text)
    except Exception as e:
        await message.answer(str(e))


@dp.message(Command("reset"))
async def reset(message: types.Message):
    text = 'Контекст нашей беседы очищен!'
    try:
        await bot.send_chat_action(message.chat.id, 'typing')
        await redis.delete(message.from_user.id)
        await message.answer(text)
    except Exception as e:
        await message.answer(str(e))


@dp.message(F.text)
async def welcome(message: types.Message):
    user_id = str(message.from_user.id)

    # Retrieve user context from Redis
    context = await get_user_context(user_id)

    context.append({"role": 'user', "content": message.text, "name": user_id})

    if len(context) > 10:
        context = context[-10:]

    try:
        response = await groq_client.chat.completions.create(model=MODEL, stream=False, stop=None,
                                                             messages=context, temperature=0.2, user=user_id)
        response_content = response.choices[0].message.content
    except Exception as e:
        response_content = f"Error: {str(e)}"

    # Update context with assistant's response
    context.append({"role": 'assistant', "content": response_content, "name": user_id})

    # Save updated context in Redis
    await save_user_context(user_id, context)

    # Send response to the user
    text = response_content or "Произошла ошибка при получении ответа."
    if len(text) <= MAX_MESSAGE_LENGTH:
        try:
            await message.answer(text)
        except Exception as e:
            await message.answer(f"Ошибка при отправке сообщения: {str(e)}")
    else:
        chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for chunk in chunks:
            try:
                await message.answer(chunk)
            except Exception as e:
                await message.answer(f"Ошибка при отправке длинного сообщения: {str(e)}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(str(e))
