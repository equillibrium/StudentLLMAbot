import asyncio
import logging
import os

from aiogram import Bot, types, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logging.basicConfig(level=logging.INFO)

groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
dp = Dispatcher()

MAX_MESSAGE_LENGTH = 4096
MODEL = "llama3-8b-8192"
global response_error
global response

context = {}  # Dictionary to store context for each user

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")


@dp.message(Command("start"))
async def start(message: types.Message):
    global response_error
    global response

    user_id = str(message.from_user.id)
    context[user_id] = [{
        "role": "system",
        "content": system_message,
        "name": user_id
    }]

    user_context = context[user_id]

    user_context.append(
        {"role": 'user', "content": f"Привет, кто ты? Я {message.from_user.full_name}", "name": user_id})

    try:
        response = groq_client.chat.completions.create(model=MODEL,
                                                       messages=user_context, temperature=0.2, user=user_id)
        print(response.choices[0].message.content)
    except Exception as e:
        print(str(e))
        response_error = str(e)


@dp.message(F.text)
async def welcome(message: types.Message):
    global response_error
    global response

    await bot.send_chat_action(message.chat.id, 'typing')

    user_id = str(message.from_user.id)
    if user_id not in context:
        context[user_id] = [{
            "role": "system",
            "content": system_message,
            "name": user_id
        }]

    user_context = context[user_id]
    user_context.append({"role": 'user', "content": message.text, "name": user_id})

    if len(user_context) > 10:
        user_context = user_context[-10:]

    try:
        response = groq_client.chat.completions.create(model=MODEL,
                                                       messages=user_context, temperature=0.2, user=user_id)
        print(response.choices[0].message.content)
    except Exception as e:
        print(str(e))
        response_error = str(e)

    context[user_id] = user_context

    user_context.append({"role": 'assistant', "content": response.choices[0].message.content, "name": user_id})

    text = response.choices[0].message.content or response_error

    if len(text) <= MAX_MESSAGE_LENGTH:
        try:
            await message.answer(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await message.answer(str(e), parse_mode=ParseMode.MARKDOWN)
    else:
        chunks = [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
        for chunk in chunks:
            try:
                await message.answer(chunk, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await message.answer(str(e), parse_mode=ParseMode.MARKDOWN)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(str(e))
