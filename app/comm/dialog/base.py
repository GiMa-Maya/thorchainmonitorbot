import html
import logging
import secrets
from abc import ABC
from contextlib import suppress
from functools import wraps
from typing import Optional

from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher.storage import FSMContextProxy, FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineQuery
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToEditNotFound, MessageToDeleteNotFound

from comm.localization.eng_base import CREATOR_TG
from comm.localization.manager import BaseLocalization
from lib.depcont import DepContainer
from lib.texts import code
from notify.channel import BoardMessage

logger = logging.getLogger('DIALOGS')


async def display_error(message: Message, e: Exception):
    tag = secrets.token_hex(8)
    logger.exception(f"TAG: {tag}")

    err = html.escape(repr(e))
    await message.answer(code(f"Sorry! An error occurred: {err}. Incident ID is {tag}.") +
                         f"\nFeedback/support: {CREATOR_TG}. To reset the bot press /start command.")


def bot_query_error_guard(func):
    @wraps(func)
    async def wrapper(query: CallbackQuery, *args, **kwargs):
        try:
            return await func(query, *args, **kwargs)
        except Exception as e:
            await display_error(query.message, e)

    return wrapper


def bot_error_guard(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        try:
            return await func(message, *args, **kwargs)
        except Exception as e:
            await display_error(message, e)

    return wrapper


def message_handler(*custom_filters, commands=None, regexp=None, content_types=None, state=None):
    def outer(f):
        f.handler_stuff = {
            'custom_filters': custom_filters,
            'commands': commands.split(',') if isinstance(commands, str) else commands,
            'regexp': regexp,
            'content_types': content_types,
            'state': state,
        }
        return f

    return outer


def query_handler(*custom_filters, state=None):
    def outer(f):
        f.query_stuff = {
            'custom_filters': custom_filters,
            'state': state,
        }
        return f

    return outer


def inline_bot_handler(*custom_filters):
    def outer(f):
        f.inline_bot_stuff = {
            'custom_filters': custom_filters
        }
        return f

    return outer


class AccessRestrictedError(Exception):
    ...


class BaseDialog(ABC):
    back_dialog: 'BaseDialog' = None
    back_func = None

    @staticmethod
    def user_id(message: Message):
        return message.chat.id

    class States(StatesGroup):
        DUMMY = State()

    def __init__(self, loc: BaseLocalization, data: Optional[FSMContextProxy], d: DepContainer, message: Message):
        self.deps = d
        self.loc = loc
        self.data = data
        self.message = message

    async def pre_action(self):
        ...

    async def post_action(self):
        ...

    @classmethod
    def register(cls, d: DepContainer, back_dialog=None, back_func=None):
        cls.back_dialog = back_dialog
        cls.back_func = back_func

        members = cls.__dict__.items()
        # go through all annotated methods and register them as bot dispatcher's handlers
        for name, f in members:
            if hasattr(f, 'handler_stuff'):
                cls.register_handler(d, f, name)
            elif hasattr(f, 'query_stuff'):
                cls.register_query_handler(d, f, name)
            elif hasattr(f, 'inline_bot_stuff'):
                cls.register_inline_bot_handler(d, f, name)

    @staticmethod
    async def if_loading_please_wait(deps: DepContainer, loc: BaseLocalization, user):
        if deps.is_loading:
            await deps.telegram_bot.send_message(user, BoardMessage(loc.BOT_LOADING), disable_notification=True)
            return True

    @classmethod
    def register_query_handler(cls, d: DepContainer, f, name):
        query_stuff = f.query_stuff

        @d.telegram_bot.dp.callback_query_handler(*query_stuff['custom_filters'], state=query_stuff['state'])
        @bot_query_error_guard
        async def handler(query: CallbackQuery, state: FSMContext, that_name=name):  # name=name important!!
            logger.info({
                'from': (query.from_user.id, query.from_user.first_name, query.from_user.username),
                'data': query.data
            })
            async with state.proxy() as data:
                loc = await d.loc_man.get_from_db(query.from_user.id, d.db)
                handler_class = cls(loc, data, d, query.message)
                return await handler_class.call_in_context(that_name, query)

    @classmethod
    def register_inline_bot_handler(cls, d: DepContainer, f, name):
        inline_bot_stuff = f.inline_bot_stuff

        @d.telegram_bot.dp.inline_handler(*inline_bot_stuff['custom_filters'], state='*')
        async def handler(inline_query: InlineQuery, that_name=name):  # name=name important!!
            try:
                logger.info({
                    'from': (inline_query.from_user.id,
                             inline_query.from_user.username,
                             inline_query.from_user.first_name),
                    'query': inline_query.query
                })

                loc = d.loc_man.default

                if await cls.if_loading_please_wait(d, loc, inline_query.from_user.id):
                    return

                handler_class = cls(loc, None, d, None)
                return await handler_class.call_in_context(that_name, inline_query)
            except Exception as e:
                logger.exception(f'Inline bot query exception! {e}')

    @classmethod
    def register_handler(cls, d: DepContainer, f, name):
        handler_stuff = f.handler_stuff

        @d.telegram_bot.dp.message_handler(*handler_stuff['custom_filters'],
                                           commands=handler_stuff['commands'],
                                           state=handler_stuff['state'],
                                           regexp=handler_stuff['regexp'],
                                           content_types=handler_stuff['content_types'])
        @bot_error_guard
        async def handler(message: Message, state: FSMContext, that_name=name, cls=cls):  # name=name important!!
            logger.info({
                'from': (message.from_user.id, message.from_user.first_name, message.from_user.username),
                'text': message.text
            })
            async with state.proxy() as data:
                loc = await d.loc_man.get_from_db(cls.user_id(message), d.db)

                if await cls.if_loading_please_wait(d, loc, cls.user_id(message)):
                    return

                handler_class = cls(loc, data, d, message)
                return await handler_class.call_in_context(that_name)

    # noinspection PyCallingNonCallable
    async def go_back(self, message: Message):
        message.text = ''
        obj = self.back_dialog(self.loc, self.data, self.deps, self.message)
        func = getattr(obj, self.back_func.__name__)
        await func(message)

    @staticmethod
    async def safe_delete(message: Message):
        try:
            await message.delete()
        except (MessageCantBeDeleted, MessageToEditNotFound, MessageToDeleteNotFound):
            logger.warning('can not delete message')
            pass

    async def answer_loading_sticker(self, message: Message, silent=True, remove_keyboard=False) -> Message:
        return await message.answer(self.loc.TEXT_PLEASE_WAIT, disable_notification=silent,
                                    reply_markup=ReplyKeyboardRemove() if remove_keyboard else None)

    async def show_loading(self, message: Message):
        # todo: save message to delete it later safely even if the handler fails
        return await message.answer(self.loc.LOADING,
                                    disable_notification=True,
                                    disable_web_page_preview=True)

    def text_new_feature(self, text, key):
        return text + self.deps.new_feature.new_sing(key)

    async def update_locale(self, lang, message: Message):
        self.data['language'] = lang
        self.loc = await self.deps.loc_man.set_lang(self.user_id(message), lang, self.deps.db)

    async def call_in_context(self, method_to_call, argument=None):
        await self.pre_action()
        attr_name = method_to_call if isinstance(method_to_call, str) else method_to_call.__name__
        real_method = getattr(self, attr_name)
        result = await real_method(argument or self.message)
        await self.post_action()
        return result

    @classmethod
    def from_other_dialog(cls, d: 'BaseDialog'):
        return cls(d.loc, d.data, d.deps, d.message)

    async def require_admin(self, message: Message):
        if not self.deps.cfg.is_admin(message.from_user.id):
            raise AccessRestrictedError('You are not admin!')

    @staticmethod
    async def start_typing(message: Message):
        await message.bot.send_chat_action(message.chat.id, 'typing')


class DialogWithSettings(BaseDialog):
    def __init__(self, loc: BaseLocalization, data: Optional[FSMContextProxy], d: DepContainer, message: Message):
        super().__init__(loc, data, d, message)
        self.settings = {}
        self._settings_manager = d.settings_manager

    async def pre_action(self):
        user_id = self.user_id(self.message)
        self.settings = await self._settings_manager.get_settings(user_id)

    async def post_action(self):
        user_id = self.user_id(self.message)
        if self.settings and isinstance(self.settings, dict):
            await self._settings_manager.set_settings(user_id, self.settings)
        else:
            logger.error('Tried to save invalid settings. Rejected!')

    async def delete_message_by_id(self, chat_id, message_id):
        with suppress(Exception):
            await self.deps.telegram_bot.bot.delete_message(chat_id, message_id)
