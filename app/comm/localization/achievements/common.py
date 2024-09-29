import abc
import random

from jobs.achievement.ach_list import AchievementDescription, Achievement, META_KEY_SPEC, AchievementName, \
    ACHIEVEMENT_DESC_MAP
from lib.date_utils import seconds_human
from lib.money import short_money, pretty_money


class AchievementsLocalizationBase(abc.ABC):
    CELEBRATION_EMOJIES = "🎉🎊🥳🙌🥂🪅🎆"
    DEVIATION_TO_SHOW_VALUE_PCT = 10
    MORE_THAN = 'More than'
    TRANSLATION_MAP = {}  # fill in

    @classmethod
    def check_if_all_achievements_have_description(cls):
        all_achievements = set(AchievementName.all_keys())
        all_achievements_with_desc = set(a for a in ACHIEVEMENT_DESC_MAP)
        assert all_achievements == all_achievements_with_desc, \
            f'Not all achievements have description. Missing: {all_achievements - all_achievements_with_desc}'

    def get_achievement_description(self, achievement_key: str) -> AchievementDescription:
        # return self.desc_map.get(achievement, 'Unknown achievement. Please contact support')
        desc = ACHIEVEMENT_DESC_MAP.get(achievement_key)
        if not desc:
            raise ValueError(f'Unknown achievement {achievement_key!r}')

        desc: AchievementDescription

        new_desc = self.TRANSLATION_MAP.get(achievement_key)

        return desc._replace(description=new_desc)

    @classmethod
    def _do_substitutions(cls, achievement: Achievement, text: str) -> str:
        return text.replace(META_KEY_SPEC, achievement.specialization)

    @staticmethod
    def space_before_non_empty(s):
        return f' {s}' if s else ''

    def format_value(self, value, ach: 'Achievement', desc: AchievementDescription, short=True):
        f = short_money if short else pretty_money
        return f(
            value,
            prefix=self._do_substitutions(ach, desc.prefix),
            postfix=self.space_before_non_empty(self._do_substitutions(ach, desc.postfix)),
            integer=True,
            signed=desc.signed
        )

    def prepare_achievement_data(self, a: Achievement, newlines=False):
        desc = self.get_achievement_description(a.key)
        emoji = random.choice(self.CELEBRATION_EMOJIES)
        ago = seconds_human(a.timestamp - a.previous_ts) if a.previous_ts and a.has_previous else ''

        # Milestone string is used as the main number on the picture
        if a.descending:
            # show the real value for descending sequences
            milestone_str = self.format_value(a.value, a, desc)
        else:
            milestone_str = self.format_value(a.milestone, a, desc)

        prev_milestone_str = self.format_value(a.prev_milestone, a, desc)

        # Description
        desc_text = desc.description
        desc_text = self._do_substitutions(a, desc_text)
        if not newlines:
            desc_text = desc_text.replace('\n', ' ')

        # Value string (goes in parentheses after the milestone_str)
        value_str = ''
        if a.value and not a.descending:
            if abs(a.value - a.milestone) < 0.01 * self.DEVIATION_TO_SHOW_VALUE_PCT * a.milestone:
                # clear it if it's too close to the milestone
                value_str = ''
            else:
                # short = False => full value!
                value_str = self.format_value(a.value, a, desc, short=False)
            value_str = self._do_substitutions(a, value_str)

        return desc, ago, desc_text, emoji, milestone_str, prev_milestone_str, value_str

    def __init__(self):
        self.check_if_all_achievements_have_description()

    @abc.abstractmethod
    def notification_achievement_unlocked(self, a: Achievement):
        ...
