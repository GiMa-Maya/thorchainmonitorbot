import asyncio
from contextlib import AsyncExitStack
from io import BytesIO

from PIL import Image
from aiogram import Bot
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.dispatcher.storage import FSMContextProxy
from aiogram.types import Message, PhotoSize, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types.mixins import Downloadable
from aiogram.utils.helper import HelperMode

from comm.dialog.base import BaseDialog, message_handler, query_handler
from comm.dialog.my_wallets_menu import ContentTypes, CallbackQuery
from comm.dialog.picture.avatar import make_avatar
from comm.localization.manager import BaseLocalization
from lib.depcont import DepContainer
from lib.draw_utils import img_to_bio


async def download_tg_photo(photo: Downloadable) -> Image.Image:
    photo_raw = BytesIO()
    await photo.download(destination=photo_raw)
    return Image.open(photo_raw)


async def get_userpic(bot: Bot, user_id) -> Image.Image:
    pics = await bot.get_user_profile_photos(user_id, 0, 1)
    if pics.photos and pics.photos[0]:
        first_pic: PhotoSize = pics.photos[0][0]
        return await download_tg_photo(first_pic)


class AvatarStates(StatesGroup):
    mode = HelperMode.snake_case
    MAIN = State()


class AvatarDialog(BaseDialog):
    def __init__(self, loc: BaseLocalization, data: FSMContextProxy, d: DepContainer, message: Message):
        super().__init__(loc, data, d, message)
        self._work_lock = asyncio.Lock()

    def menu_inline_kbd(self):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(self.loc.BUTTON_AVA_FROM_MY_USERPIC, callback_data='from_user_pic')],
                [InlineKeyboardButton(self.loc.BUTTON_SM_BACK_MM, callback_data='back')],
            ]
        )

    @query_handler(state=AvatarStates.MAIN)
    async def on_tap_address(self, query: CallbackQuery):
        if query.data == 'back':
            await self.go_back(query.message)
            await self.safe_delete(query.message)
        elif query.data == 'from_user_pic':
            await self.handle_avatar_picture(query.message, self.loc)
            await self.safe_delete(query.message)

    @message_handler(state=AvatarStates.MAIN)
    async def on_enter(self, message: Message):
        await AvatarStates.MAIN.set()
        await message.answer(self.loc.TEXT_AVA_WELCOME, reply_markup=self.menu_inline_kbd())

    @message_handler(state=AvatarStates.MAIN, content_types=ContentTypes.PHOTO)
    async def on_picture(self, message: Message):
        await self.handle_avatar_picture(message, self.loc, explicit_picture=message.photo[0])

    @message_handler(state=AvatarStates.MAIN, content_types=ContentTypes.DOCUMENT)
    async def on_picture_doc(self, message: Message):
        await self.handle_avatar_picture(message, self.loc, explicit_picture=message.document)

    async def handle_avatar_picture(self, message: Message, loc: BaseLocalization,
                                    explicit_picture: Downloadable = None):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(self._work_lock)

            # POST A LOADING STICKER
            sticker = await self.answer_loading_sticker(message, remove_keyboard=True)

            # CLEAN UP IN THE END
            stack.push_async_callback(sticker.delete)

            user_id = self.user_id(message)

            try:
                if explicit_picture is not None:
                    user_pic = await download_tg_photo(explicit_picture)
                else:
                    user_pic = await get_userpic(message.bot, user_id)
            except Exception:
                await message.answer(loc.TEXT_AVA_ERR_INVALID, reply_markup=self.menu_inline_kbd())
                return

            if user_pic is None:
                await message.answer(loc.TEXT_AVA_ERR_NO_PIC, reply_markup=self.menu_inline_kbd())
                return

            w, h = user_pic.size
            if not w or not h:
                await message.answer(loc.TEXT_AVA_ERR_INVALID, reply_markup=self.menu_inline_kbd())
                return

            pic = await make_avatar(user_pic)

            pic = img_to_bio(pic, name=f'thor_ava_{user_id}.png')
            await message.answer_document(pic, caption=loc.TEXT_AVA_READY, reply_markup=self.menu_inline_kbd())
