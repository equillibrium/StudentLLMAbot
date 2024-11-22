import json
import os

import redis.asyncio as aioredis
from dotenv import load_dotenv


load_dotenv()

redis = aioredis.from_url(os.getenv('REDIS_URL'))


async def get_user_context(user_id, system_message):
    data = await redis.get(user_id)
    if data:
        return json.loads(data)
    # Возвращаем начальный контекст только если это первое обращение
    # Убрали "name": user_id, так как он не нужен
    return [{"role": "system", "content": system_message}]


async def save_user_context(user_id, context):
    await redis.set(user_id, json.dumps(context))


async def get_user_files(user_id):
    data = await redis.get(f"{user_id}_files")
    if data:
        return json.loads(data)
    else:
        return []


async def save_user_files(user_id, data):
    await redis.set(f"{user_id}_files", json.dumps(data))


async def get_user_model(user_id, default_model):
    from main import MODEL_CHOICES
    model = await redis.get(f"{user_id}_model")
    if model:
        decoded_model = model.decode()
        # Проверяем, существует ли модель в списке доступных
        if decoded_model in MODEL_CHOICES:
            return decoded_model
    return default_model
