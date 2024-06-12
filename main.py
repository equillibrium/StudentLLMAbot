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

context = {}  # Dictionary to store context for each user

system_message = ("Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой. "
                  "Отвечай всегда на русском языке, не переходи на английский, если не просят. "
                  "Если к тебе обратятся на английском языке или попросят помочь с английским, "
                  "можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах, "
                  "помогай студентам решать их проблемы с учебой.")

@dp.message(Command("start"))
async def start(message: types.Message):
    context = []
    user_context = []
    text = (f"Привет, {message.from_user.first_name}\r\nЯ StudentLLMAbot, использую модель llama3-70b-8192."
            f"Помогу тебе с задачами по учебе!")
    await message.answer(text)

@dp.message(F.text)
async def welcome(message: types.Message):
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

    response = groq_client.chat.completions.create(model='llama3-70b-8192',
                                                   messages=user_context, temperature=0, user=user_id)

    context[user_id] = user_context

    user_context.append({"role": 'assistant', "content": response.choices[0].message.content, "name": user_id})

    text = response.choices[0].message.content

    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
