import asyncio
import logging
import os
import re
import shutil

from aiogram import Bot, types, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from dotenv import load_dotenv

from clients import get_client_for_model
from files import convert_to_pdf, upload_to_gemini, wait_for_files_active, get_from_gemini
from files import list_gemini_files
from states import redis, save_user_context, get_user_model, get_user_context
from states import save_user_files, get_user_files

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

SYSTEM_MESSAGE = ('''
    Ты ассистент, которого зовут StudentLLMAbot. Твоя основная задача - помогать студентам с учебой.
    Отвечай всегда на русском языке, не переходи на английский, если не просят.
    Если к тебе обратятся на английском языке или попросят помочь с английским,
    можешь использовать английский для ответа. Будь вежливым и полезным во всех своих ответах,
    помогай студентам решать их проблемы с учебой. Старайся не использовать в ответе двойные пробелы,
    большие (заглавные) буквы после двоеточия. Старайся использовать меньше списков.
''')


class TestState(StatesGroup):
    test = State()


api_server = TelegramAPIServer.from_base(
    os.getenv("API_SERVER_URL"), is_local=True)

bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'),
          session=AiohttpSession(api=api_server),
          default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=RedisStorage(redis))

MAX_MESSAGE_LENGTH = 4000
MODEL_CHOICES = os.getenv('MODEL_CHOICES').split(',')
DEFAULT_MODEL = MODEL_CHOICES[0]


async def set_user_model(user_id, model):
    await redis.set(f"{user_id}_model", model)
    # При смене модели создаем новый контекст с system message
    initial_context = [{"role": "system", "content": SYSTEM_MESSAGE}]
    await save_user_context(user_id, initial_context)


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


@dp.message(TestState.test, F.document)
async def test_state(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    dl = await bot.get_file(message.document.file_id)
    print(dl)
    print(message.document)
    local_path = f"\\\\wsl.localhost\\docker-desktop-data\\data\\docker\\volumes\\telegram-bot-api-data\\_data\\{os.getenv(
        "TELEGRAM_BOT_TOKEN")}\\documents\\" if os.name == "nt" else f"/var/lib/telegram-bot-api/{os.getenv("TELEGRAM_BOT_TOKEN")}/documents/"
    print(os.listdir(local_path))

    src_name = os.path.basename(dl.file_path)
    dest_folder = f"{local_path}{message.from_user.id}"
    try:
        os.mkdir(dest_folder)
    except FileExistsError:
        print("Don't need to create folder")
    shutil.move(local_path + src_name,
                os.path.join(dest_folder, message.document.file_name))

    print(os.listdir(local_path))


@dp.message(Command("test"))
async def test(message: types.Message, state: FSMContext):
    await state.set_state(TestState.test)
    await message.answer(await state.get_state())


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


@dp.message(F.text | F.document | F.photo)
async def chat_handler(message: types.Message):
    user_id = str(message.from_user.id)
    context = await get_user_context(user_id, system_message=SYSTEM_MESSAGE)
    chosen_model = await get_user_model(user_id, default_model=DEFAULT_MODEL)
    client = await get_client_for_model(chosen_model)
    uploaded_file = ""
    status = ""
    gemini_response = ""
    gemini_message = ""
    folder_type = "photos" if message.photo else "documents"
    local_path = f"\\\\wsl.localhost\\docker-desktop-data\\data\\docker\\volumes\\telegram-bot-api-data\\_data\\{os.getenv(
        "TELEGRAM_BOT_TOKEN")}\\{folder_type}\\" if os.name == "nt" else f"/var/lib/telegram-bot-api/{os.getenv("TELEGRAM_BOT_TOKEN")}/{folder_type}/"

    # Если есть документ, сначала обрабатываем его через Gemini
    if message.document or message.photo:
        await bot.send_chat_action(message.chat.id, 'upload_document')

        if message.document:
            file = {
                "path": local_path + user_id,
                "name": message.document.file_name,
                "id": message.document.file_id,
                "mimetype": message.document.mime_type,
                "size": message.document.file_size
            }
        elif message.photo:
            print(message)
            file = {
                "path": local_path + user_id,
                "name": message.photo[-1].file_id + ".jpg",
                "id": message.photo[-1].file_id,
                "mimetype": "image/jpeg",
                "size": message.photo[-1].file_size
            }

        processed_files = await get_user_files(user_id)

        gemini_saved_documents = await list_gemini_files()

        print("Processed files", processed_files)
        if processed_files:
            for pf in processed_files:
                if pf["name"] == file["name"] and pf["size"] == file['size'] and pf["mimetype"] == file["mimetype"]:
                    print("File already processed")
                    file['pdf_name'] = pf.get("pdf_name", "")
        if gemini_saved_documents:
            for gsd in gemini_saved_documents:
                if gsd.display_name == file.get('pdf_name', ''):
                    print("File already uploaded")
                    file['gemini_name'] = gsd.name

        if not file.get('gemini_name', '') and not file.get('pdf_name', ''):
            print("Downloading file from telegram...")
            try:
                dl = await bot.get_file(file["id"])
                print(dl)
                src_name = os.path.basename(dl.file_path)

                try:
                    os.mkdir(file["path"])
                except FileExistsError:
                    print("Don't need to create folder")

                shutil.move(local_path + src_name,
                            os.path.join(file["path"], file["name"]))
            except Exception as e:
                await message.answer(str(e))

        status = await message.answer("Файл получен!")
        await bot.send_chat_action(message.chat.id, 'upload_document')

        if "pdf" not in file.get("mimetype", "") and "image" not in file.get("mimetype", "") and not file.get(
                "pdf_name", "") and not file.get("gemini_name", ""):
            await bot.edit_message_text("Конвертирую файл в pdf...", message_id=status.message_id,
                                        chat_id=message.chat.id)
            await bot.send_chat_action(message.chat.id, 'upload_document')
            try:
                converted_pdf = await convert_to_pdf(file=file)
                pdf_scr = os.path.join(file["path"], converted_pdf)
                pdf_dest = os.path.join(
                    file["path"], file["name"].split(".")[0] + ".pdf")
                pdf_name = os.path.basename(pdf_dest)
                shutil.move(pdf_scr, pdf_dest)
                with open(pdf_dest, 'rb') as f:
                    pdf_file = BufferedInputFile(f.read(), filename=pdf_name)
                    await message.answer_document(pdf_file,
                                                  caption="Вот документ в PDF для повторного использования, если необходимо. Я понимаю только PDF! Ответ подготавливается...")
                await bot.edit_message_text("Файл успешно сконвертирован в pdf!", message_id=status.message_id,
                                            chat_id=message.chat.id)
            except Exception as e:
                await message.answer(str(e))
                return

            file["pdf_name"] = pdf_name

        else:
            file["pdf_name"] = file["name"]
            await save_user_files(user_id, [file])

        if not file.get('gemini_name', ''):
            await bot.edit_message_text("Загрузка файла в Gemini...", message_id=status.message_id,
                                        chat_id=message.chat.id)
            await bot.send_chat_action(message.chat.id, 'upload_document')
            try:
                uploaded_file = await upload_to_gemini(path=os.path.join(file["path"], file['pdf_name']),
                                                       mime_type='application/pdf' if ".pdf" in file["pdf_name"] else
                                                       file["mimetype"])
            except Exception as e:
                await message.answer(str(e))

            try:
                await bot.edit_message_text("Обработка файла в Gemini...", message_id=status.message_id,
                                            chat_id=status.chat.id)
                await bot.send_chat_action(message.chat.id, 'typing')
            except Exception as e:
                await message.answer(str(e))

            try:
                await wait_for_files_active([uploaded_file])
                file['gemini_name'] = uploaded_file.name
            except Exception as e:
                await message.answer(str(e))

        else:
            uploaded_file = await get_from_gemini(file['gemini_name'])

        processed_files.append(file)
        await save_user_files(user_id, processed_files)

        chosen_model = MODEL_CHOICES[2]
        await set_user_model(user_id, chosen_model)
        client = await get_client_for_model(chosen_model)
    else:
        # If msg is not document
        context.append({"role": "user", "content": message.text})

    # Продолжаем обработку с выбранной моделью
    # Gemini model
    if chosen_model == MODEL_CHOICES[2] or chosen_model == MODEL_CHOICES[3]:
        gemini_history = []
        for msg in context[1:]:
            if msg["role"] == "assistant":
                gemini_history.append({
                    "role": "model",
                    "parts": [{"text": msg["content"]}]
                })
            elif msg["role"] == "user":
                if type(msg["content"]) is list:
                    old_uploaded_file = await get_from_gemini(msg["content"][0])
                    gemini_history.append({
                        "role": "user",
                        "parts": [old_uploaded_file, msg["content"][1]]
                    })
                else:
                    gemini_history.append({
                        "role": "user",
                        "parts": [{"text": msg["content"]}]
                    })

        chat_session = client.start_chat(history=gemini_history)

        if message.document or message.photo:
            await bot.edit_message_text("Gemini подготавливает ответ, может занять долгое время....",
                                        message_id=status.message_id,
                                        chat_id=message.chat.id)
            await bot.send_chat_action(message.chat.id, 'typing')
            print("Sending file:", uploaded_file)
            gemini_message = [
                uploaded_file, message.caption or "Выполни задания в этом документе"]
            user_message = [uploaded_file.name,
                            message.caption or "Выполни задания в этом документе"]

            if file["path"]:
                try:
                    shutil.rmtree(file["path"])
                except FileNotFoundError as e:
                    print(str(e))
                    print("Nothing to delete")
        else:
            await bot.send_chat_action(message.chat.id, 'typing')
            user_message = message.text
            gemini_message = message.text

        error_msg = ""
        counter = 1
        while not gemini_response and counter <= 5:
            try:
                gemini_response = await chat_session.send_message_async(gemini_message)
            except Exception as e:
                if error_msg:
                    logging.log(level=logging.WARN, msg=str(e))
                    error_msg = await bot.edit_message_text(error_msg.text + ".",
                                                            message_id=error_msg.message_id,
                                                            chat_id=error_msg.chat.id)
                else:
                    error_msg = await message.answer(str(e))

                logging.log(level=logging.INFO, msg="Sleeping...")
                await asyncio.sleep(5)
                counter += 1
        try:
            response_content = gemini_response.text
        except Exception:
            text = "Не получен ответ от Gemini, попробуй позже...\n Или выбери другую модель Gemini (/model)"
            await bot.edit_message_text(text, message_id=status.message_id, chat_id=status.chat.id)
            await bot.delete_message(message_id=error_msg.message_id, chat_id=error_msg.chat.id) if error_msg else None
            logging.log(level=logging.ERROR, msg=text)
            return

    else:  # Groq или OpenAI
        user_message = message.text
        response = await client.chat.completions.create(
            model=chosen_model,
            stream=False,
            stop=None,
            max_tokens=8000,
            messages=context,
            temperature=0.2,
            top_p=0.95
        )
        response_content = response.choices[0].message.content

    if message.document:
        context.append({"role": "user", "content": user_message})
    context.append({"role": "assistant", "content": response_content})

    text = (await replace_asterisk(response_content))
    text = text.replace("_", "\\_")

    chunks = [text[i:i + MAX_MESSAGE_LENGTH]
              for i in range(0, len(text), MAX_MESSAGE_LENGTH)]
    not_sent = False

    try:
        await message.answer(text)
    except Exception as e:
        print(str(e), type(e))
        not_sent = True

    if not_sent:
        for chunk in chunks:
            try:
                await message.answer(chunk)
            except Exception as e:
                print(str(e), type(e))
                await message.answer(chunk, parse_mode=None)

    # Сохраняем контекст только после успешной отправки
    await save_user_context(user_id, context)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(str(e))
