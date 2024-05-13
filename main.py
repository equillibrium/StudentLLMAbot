import asyncio
import logging
import os

from aiogram import Bot, types, Dispatcher, F
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logging.basicConfig(level=logging.INFO)

groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))
bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
dp = Dispatcher()

contex = []


@dp.message(F.text)
async def welcome(message: types.Message):
    await bot.send_chat_action(message.chat.id, 'typing')

    global contex

    contex.append({"role": 'user', "content": message.text})

    if len(contex) > 10:
        messages = contex[-10:]
    response = groq_client.chat.completions.create(model='llama3-70b-8192',
                                                   messages=contex, temperature=0)

    contex.append({"role": 'assistant', "content": response.choices[0].message.content})

    text = response.choices[0].message.content

    # print(contex)

    await message.answer(text)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
