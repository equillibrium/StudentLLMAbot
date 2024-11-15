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


async def get_user_model(user_id, default_model):
    model = await redis.get(f"{user_id}_model")
    return model.decode() if model else default_model
