import re
from typing import List
from urllib.parse import urlparse

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from unicodedata import lookup

from services.lib.money import pretty_money, short_money
from services.lib.utils import grouper


def bold(text):
    return f"<b>{text}</b>"


def link(url, text):
    return f'<a href="{url}">{text}</a>'


def link_with_domain_text(url):
    parsed_uri = urlparse(url)
    text = parsed_uri.netloc
    return f'<a href="{url}">{text}</a>'


def code(text):
    # In new version of Telegram they changed appearance of code blocks dramatically
    # Previously: return f"<code>{text}</code>"
    return pre(text)


def ital(text):
    return f"<i>{text}</i>"


def pre(text):
    # return f"<pre>{text}</pre>"
    return bold(text)


def underline(text):
    return f"<u>{text}</u>"


def x_ses(one, two):
    if one == 0 or two == 0:
        return 'N/A'
    else:
        sign = 'x' if two > one else '-x'
        times = two / one if two > one else one / two
        return f'{sign}{pretty_money(times)}'


def progressbar(x, total, symbol_width=10):
    if total <= 0:
        s = 0
    else:
        s = int(round(symbol_width * x / total))
    s = max(0, s)
    s = min(symbol_width, s)
    return '▰' * s + '▱' * (symbol_width - s)


def regroup_joining(n, iterable, sep='\n\n', trim=True):
    if trim:
        iterable = map(str.strip, iterable)
    groups = grouper(n, iterable)
    return [
        sep.join(g) for g in groups
    ]


def kbd(buttons, resize=True, vert=False, one_time=False, row_width=3):
    if isinstance(buttons, str):
        buttons = [[buttons]]
    elif isinstance(buttons, (list, tuple, set)):
        if all(isinstance(b, str) for b in buttons):
            if vert:
                buttons = [[b] for b in buttons]
            else:
                buttons = [buttons]

    buttons = [
        [KeyboardButton(b) for b in row] for row in buttons
    ]
    return ReplyKeyboardMarkup(buttons,
                               resize_keyboard=resize,
                               one_time_keyboard=one_time,
                               row_width=row_width)


def cut_long_text(text: str, max_symbols=15, end='...'):
    end_len, text_len = len(end), len(text)
    if text_len > max_symbols - end_len:
        cut = max_symbols - end_len
        return text[:cut] + end
    else:
        return text


def bracketify(item, before='', after=''):
    if before is True:
        before = ' '
    if after is True:
        after = ' '
    return f"{before}({item}){after}" if item else ''


def bracketify_spaced(item):
    return bracketify(item, ' ', ' ')


def up_down_arrow(old_value, new_value, smiley=False, more_is_better=True, same_result='',
                  int_delta=False, money_delta=False, percent_delta=False, signed=True,
                  money_prefix='', ignore_on_no_old=True, postfix='', threshold_pct=0.0,
                  brackets=False):
    if ignore_on_no_old and not old_value:
        return same_result

    delta = new_value - old_value

    max_val = max(new_value, old_value)
    pct_change = threshold_pct + 1 if max_val == 0 else abs(delta) / max_val * 100.0
    if pct_change < threshold_pct:
        return same_result

    if int_delta is not None and delta == 0:
        return same_result

    better = delta > 0 if more_is_better else delta < 0

    smiley = ('😃' if better else '🙁') if smiley else ''
    arrow = '↑' if better else '↓'

    delta_text = ''
    if int_delta:
        sign = ('+' if delta >= 0 else '') if signed else ''
        delta_text = f"{sign}{int(delta)}"
    elif money_delta:
        delta_text = short_money(delta, prefix=money_prefix, signed=signed)
    elif percent_delta:
        delta_text = pretty_money(100.0 * delta / old_value, postfix='%', signed=signed)

    result = f"{smiley} {arrow} {delta_text}{postfix}".strip()
    if brackets:
        result = bracketify(result)
    return result


def plural(n: int, one_thing, many_things):
    return one_thing if n == 1 else many_things


def join_as_numbered_list(items, sep='\n', start=1):
    en_items = (f'{i}. {text!s}' for i, text in enumerate(items, start=start))
    return sep.join(en_items)


def split_by_camel_case(s: str, abbr_correction=True):
    items = re.findall('[A-Z][^A-Z]*', s)

    if abbr_correction:
        corrected_items = []
        curr_abbr = ''
        for item in items:
            if len(item) == 1:
                curr_abbr += item
            else:
                if curr_abbr:
                    corrected_items.append(curr_abbr)
                    curr_abbr = ''
                corrected_items.append(item)
        if curr_abbr:
            corrected_items.append(curr_abbr)
    else:
        corrected_items = items
    return ' '.join(corrected_items)


def capitalize_each_word(s):
    return ' '.join(map(str.capitalize, str(s).split()))


def sep(title='', simple=False):
    title = str(title)
    if not simple:
        title = ' '.join(title.upper())
    if title:
        title = f' {title} '
    print(f'{title:-^120}')


def fuzzy_search(query: str, realm, f=str.upper) -> List[str]:
    if not query:
        return []

    # noinspection PyArgumentList
    query = f(query) if f else query
    if query in realm:  # perfect match
        return [query]

    variants = []
    query_comp = query.split('-', 2)
    for name in realm:
        name: str
        if query in name:
            variants.append(name)
        elif len(query_comp) >= 2 and name.startswith(query_comp[0]) and name.endswith(query_comp[1]):
            # So ETH.USDT-EC7 matches ETH.USDT-0XDAC17F958D2EE523A2206206994597C13D831EC7
            variants.append(name)

    return variants


def safe_sum(*args):
    return sum((int(arg) for arg in args), 0)


def shorten_text(text, limit=200, end='...'):
    if not isinstance(text, str):
        text = str(text)
    if limit and len(text) > limit:
        return text[:limit - len(end)] + end
    else:
        return text


def find_country_emoji(country_code: str):
    if len(country_code) == 2:
        return ''.join(lookup(f'REGIONAL INDICATOR SYMBOL LETTER {symbol}') for symbol in country_code)
