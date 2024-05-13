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

user_contexts = {}  # Dictionary to store context for each user


@dp.message(F.text)
async def welcome(message: types.Message):
    await bot.send_chat_action(message.chat.id, 'typing')

    user_id = str(message.from_user.id)
    if user_id not in user_contexts:
        user_contexts[user_id] = [{"role": "system", "content": "Ты ассистент, которого зовут StudentLLMAbot, "
                                                                "ты помогаешь студентам с учёбой. Отвечай всегда "
                                                                "по-русски, только если тебя не попросят помочь с "
                                                                "английским языком"}]

    user_context = user_contexts[user_id]
    user_context.append({"role": 'user', "content": message.text})

    if len(user_context) > 10:
        user_context = user_context[-10:]

    response = groq_client.chat.completions.create(model='llama3-70b-8192',
                                                   messages=user_context, temperature=0, user=user_id)

    user_contexts[user_id] = user_context

    user_context.append({"role": 'assistant', "content": response.choices[0].message.content})

    text = response.choices[0].message.content

    await message.answer(text)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
