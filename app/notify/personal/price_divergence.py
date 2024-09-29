import asyncio

from lib.date_utils import parse_timespan_to_seconds
from lib.delegates import INotified
from lib.depcont import DepContainer
from lib.settings_manager import SettingsManager, SettingsContext
from lib.utils import WithLogger
from models.node_watchers import AlertWatchers
from models.price import RuneMarketInfo
from notify.channel import ChannelDescriptor, BoardMessage
from notify.personal.helpers import GeneralSettings


class PersonalPriceDivergenceNotifier(INotified, WithLogger):
    LAST_VALUE_KEY = '$PriceDivLastValue'

    def __init__(self, deps: DepContainer):
        super().__init__()
        self.deps = deps
        self.personal_cooldown = parse_timespan_to_seconds(
            deps.cfg.as_str('price.divergence.personal.cooldown', '1h')
        )

    async def on_data(self, sender, rune_market_info: RuneMarketInfo):
        users = await self.deps.alert_watcher.all_users_for_node(GeneralSettings.PRICE_DIV_ALERTS)
        their_settings = await self.deps.settings_manager.get_settings_multi(users)

        for user in users:
            settings = their_settings.get(user, {})

            if SettingsContext.is_inactive_s(settings):
                continue  # paused

            min_percent = settings.get(SettingsProcessorPriceDivergence.KEY_MIN_PERCENT)
            max_percent = settings.get(SettingsProcessorPriceDivergence.KEY_MAX_PERCENT)
            last_value = settings.get(self.LAST_VALUE_KEY)

            settings_changed, normal = False, True

            div_p = rune_market_info.divergence_percent

            if min_percent is not None and last_value != min_percent and div_p < min_percent:
                settings_changed, normal = True, True
                settings[self.LAST_VALUE_KEY] = min_percent

            if max_percent is not None and last_value != max_percent and div_p > max_percent:
                settings_changed, normal = True, False
                settings[self.LAST_VALUE_KEY] = max_percent

            if settings_changed:
                await self.deps.settings_manager.set_settings(user, settings)
                asyncio.create_task(self._send_notification(rune_market_info, user, settings, normal))

    async def _send_notification(self, rune_market_info: RuneMarketInfo, user, settings, normal):
        loc = await self.deps.loc_man.get_from_db(user, self.deps.db)
        text = loc.notification_text_price_divergence(rune_market_info, normal)
        await self.deps.broadcaster.safe_send_message_rate(
            ChannelDescriptor(SettingsManager.get_platform(settings), user),
            BoardMessage(text),
            disable_web_page_preview=True,
        )


class SettingsProcessorPriceDivergence(INotified):
    # Settings Keys
    KEY_MIN_PERCENT = 'PriceDiv.Min'
    KEY_MAX_PERCENT = 'PriceDiv.Max'

    def __init__(self, alert_watcher: AlertWatchers):
        self.alert_watcher = alert_watcher

    async def on_data(self, sender: SettingsManager, data):
        channel_id, settings = data

        min_percent = settings.get(self.KEY_MIN_PERCENT)
        max_percent = settings.get(self.KEY_MAX_PERCENT)

        is_enabled = min_percent is not None and max_percent is not None
        await self.alert_watcher.set_user_to_node(channel_id, GeneralSettings.PRICE_DIV_ALERTS, is_enabled)
