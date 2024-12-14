from PIL import Image, ImageDraw

from comm.localization.manager import BaseLocalization
from comm.picture.common import BasePictureGenerator
from comm.picture.resources import Resources
from lib.utils import async_wrap
from models.s_swap import StreamingSwap
from models.tx import ThorAction


class StreamingSwapPictureGenerator(BasePictureGenerator):
    BASE = './data'
    BG_FILE = f'{BASE}/streaming_swap_bg.png'  # todo

    LINE_COLOR = '#41484d'
    COLUMN_COLOR = '#eee'

    def __init__(self, loc: BaseLocalization, tx: ThorAction, s_swap: StreamingSwap):
        super().__init__(loc)
        self.bg = Image.open(self.BG_FILE)
        self.tx = tx
        self.s_swap = s_swap
        self.logos = {}

    FILENAME_PREFIX = 'thorchain_streaming_swap'

    async def prepare(self):
        pass
        # r = Resources()
        # logo = await r.logo_downloader.get_or_download_logo_cached(vault.asset)
        # self.logos[vault.asset] = logo

    @async_wrap
    def _get_picture_sync(self):
        # prepare data
        ...

        # prepare painting stuff
        r = Resources()
        image = self.bg.copy()
        draw = ImageDraw.Draw(image)
        return image
