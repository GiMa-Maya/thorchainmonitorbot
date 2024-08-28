from dataclasses import dataclass
from typing import NamedTuple

from services.models.base import BaseModelMixin


@dataclass
class ThorCapInfo(BaseModelMixin):
    cap: int
    pooled_rune: int
    price: float = 1.0

    MAX_ALLOWED_RATIO = 1.0  # 100 %

    @classmethod
    def zero(cls):
        return cls(0, 0, 0)

    @classmethod
    def error(cls):
        return cls(-1, -1, 1e-10)

    @property
    def cap_usd(self):
        return self.price * self.cap

    @property
    def is_ok(self):
        return self.cap >= 1 and self.pooled_rune >= 1

    @property
    def can_add_liquidity(self):
        return self.cap > 0 and self.pooled_rune / self.cap < self.MAX_ALLOWED_RATIO

    @property
    def how_much_rune_you_can_lp(self):
        return max(0.0, self.cap * self.MAX_ALLOWED_RATIO - self.pooled_rune)

    @property
    def how_much_usd_you_can_lp(self):
        return self.how_much_rune_you_can_lp * self.price


class AlertLiquidityCap(NamedTuple):
    cap: ThorCapInfo
    is_full: bool = False
    is_opened_up: bool = False
