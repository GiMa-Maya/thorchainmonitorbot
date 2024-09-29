import asyncio
import urllib.parse

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import exceptions, executor

from lib.config import Config
from lib.db import DB
from lib.texts import shorten_text
from lib.utils import WithLogger
from notify.channel import MessageType, CHANNEL_INACTIVE, BoardMessage

TG_TEST_USER = 192398802

TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024


class TelegramBot(WithLogger):
    EXTRA_RETRY_DELAY = 0.1

    def __init__(self, cfg: Config, db: DB, loop):
        super().__init__()

        self.db = db
        self.bot = Bot(token=cfg.telegram.bot.token, parse_mode=ParseMode.HTML)
        self.dp = Dispatcher(self.bot, loop=loop)

    @staticmethod
    def _remove_bad_tg_args(kwargs, dis_web_preview=False, dis_notification=False):
        if dis_web_preview:
            if 'disable_web_page_preview' in kwargs:
                del kwargs['disable_web_page_preview']
        if dis_notification:
            if 'disable_notification' in kwargs:
                del kwargs['disable_notification']
        return kwargs

    async def send_message(self, chat_id, msg: BoardMessage, **kwargs) -> bool:
        try:
            text = msg.text
            bot = self.bot
            if msg.message_type == MessageType.TEXT:
                trunc_text = text[:TELEGRAM_MAX_MESSAGE_LENGTH]
                if trunc_text != text:
                    s_text = shorten_text(text, 1000)
                    self.logger.error(f'Message is too long:\n"{s_text}"\n... Sending is cancelled.')
                await bot.send_message(chat_id, trunc_text, **kwargs)
            elif msg.message_type == MessageType.STICKER:
                kwargs = self._remove_bad_tg_args(kwargs, dis_web_preview=True)
                await bot.send_sticker(chat_id, sticker=text, **kwargs)
            elif msg.message_type == MessageType.PHOTO:
                kwargs = self._remove_bad_tg_args(kwargs, dis_web_preview=True)
                trunc_text = text[:TELEGRAM_MAX_CAPTION_LENGTH]
                if trunc_text != text:
                    s_text = shorten_text(text, 1000)
                    self.logger.error(f'Caption is too long:\n"{s_text}"\n... Sending is cancelled.')

                image = msg.get_bio()
                await bot.send_photo(chat_id, caption=trunc_text, photo=image, **kwargs)
        except exceptions.ChatNotFound:
            self.logger.error(f"Target [ID:{chat_id}]: invalid user ID")
        except exceptions.RetryAfter as e:
            self.logger.error(f"Target [ID:{chat_id}]: Flood limit is exceeded. Sleep {e.timeout} seconds.")
            await asyncio.sleep(e.timeout + self.EXTRA_RETRY_DELAY)
            # Recursive call
            return await self.send_message(chat_id, msg, **kwargs)
        except exceptions.Unauthorized as e:
            self.logger.error(f"Target [ID:{chat_id}]: user is Unauthorized: {e!r}. Return CHANNEL_INACTIVE")
            return CHANNEL_INACTIVE
        except exceptions.TelegramAPIError:
            self.logger.exception(f"Target [ID:{chat_id}]: failed")
            return True  # tg error is not the reason to exclude the user
        except exceptions.MessageIsTooLong:
            s_text = shorten_text(msg.text, 4000)
            self.logger.error(f'Message is too long ({len(msg.text)} b):\n"{s_text}"\n...')
            return False
        else:
            self.logger.info(f"Target [ID:{chat_id}]: success")
            return True
        return False

    def run(self, on_startup, on_shutdown):
        async def my_startup(*args):
            self.dp.storage = await self.db.get_storage()  # connect storages!
            await on_startup(*args)

        executor.start_polling(self.dp, skip_updates=True, on_startup=my_startup, on_shutdown=on_shutdown)

    async def stop(self):
        await self.db.storage.close()
        await self.db.storage.wait_closed()
        await self.bot.close()


def to_json_bool(b):
    return 'true' if b else 'false'


async def telegram_send_message_basic(bot_token, user_id, message_text: str,
                                      disable_web_page_preview=True,
                                      disable_notification=True):
    message_text = message_text.strip()

    if not message_text:
        return

    message_text = urllib.parse.quote_plus(message_text)
    url = (
        f"https://api.telegram.org/"
        f"bot{bot_token}/sendMessage?"
        f"chat_id={user_id}&"
        f"text={message_text}&"
        f"parse_mode=HTML&"
        f"disable_web_page_preview={to_json_bool(disable_web_page_preview)}&"
        f"disable_notification={to_json_bool(disable_notification)}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                err = await resp.read()
                raise Exception(f'Telegram error: "{err}"')
            return resp.status == 200
