import asyncio
import datetime

import aiohttp

NODE_IP = '164.90.245.92'  # MCCN
from lib.date_utils import MINUTE, date_parse_rfc

# NODE_IP = '157.230.75.66'  # BEPSwap
NODE_RPC_PORT = 27147


def url_gen_block(block_height):
    return f'http://{NODE_IP}:{NODE_RPC_PORT}/block?height={block_height}'


async def get_block_info(session, height):
    url = url_gen_block(height)
    print(f'get: {url}')
    async with session.get(url) as resp:
        resp = await resp.json()
        return resp


async def get_block_date(session, block_height):
    r = await get_block_info(session, block_height)
    iso_time = r['result']['block']['header']['time']
    time = date_parse_rfc(iso_time)
    return time


# naive
BEPSWAP_LAST_BLOCKS = [(datetime.datetime(2021, 4, 27, 0, 0), 3648137), (datetime.datetime(2021, 4, 26, 0, 0), 3633737),
                       (datetime.datetime(2021, 4, 25, 0, 0), 3619337), (datetime.datetime(2021, 4, 24, 0, 0), 3604937),
                       (datetime.datetime(2021, 4, 23, 0, 0), 3590537), (datetime.datetime(2021, 4, 22, 0, 0), 3576137),
                       (datetime.datetime(2021, 4, 21, 0, 0), 3561737), (datetime.datetime(2021, 4, 20, 0, 0), 3547337),
                       (datetime.datetime(2021, 4, 19, 0, 0), 3532937), (datetime.datetime(2021, 4, 18, 0, 0), 3518537),
                       (datetime.datetime(2021, 4, 17, 0, 0), 3504137), (datetime.datetime(2021, 4, 16, 0, 0), 3489737),
                       (datetime.datetime(2021, 4, 15, 0, 0), 3475337), (datetime.datetime(2021, 4, 14, 0, 0), 3460937)]

MCCN_ITERATIVE_BLOCKS = [(datetime.datetime(2021, 4, 27, 0, 0), 258947),
                         (datetime.datetime(2021, 4, 26, 0, 0), 243367),
                         (datetime.datetime(2021, 4, 25, 0, 0), 227783),
                         (datetime.datetime(2021, 4, 24, 0, 0), 212166),
                         (datetime.datetime(2021, 4, 23, 0, 0), 196564),
                         (datetime.datetime(2021, 4, 22, 0, 0), 180936),
                         (datetime.datetime(2021, 4, 21, 0, 0), 165302),
                         (datetime.datetime(2021, 4, 20, 0, 0), 149657),
                         (datetime.datetime(2021, 4, 19, 0, 0), 134033),
                         (datetime.datetime(2021, 4, 18, 0, 0), 118386),
                         (datetime.datetime(2021, 4, 17, 0, 0), 102743),
                         (datetime.datetime(2021, 4, 16, 0, 0), 87115),
                         (datetime.datetime(2021, 4, 15, 0, 0), 71414),
                         (datetime.datetime(2021, 4, 14, 0, 0), 55697)]


async def main():
    async with aiohttp.ClientSession() as session:
        test_blocks = MCCN_ITERATIVE_BLOCKS

        results = []
        for calc_day, calc_block in test_blocks:
            real_day = await get_block_date(session, calc_block)
            results.append((calc_block, calc_day, real_day))

        for calc_block, calc_day, real_day in results:
            diff: datetime.timedelta = (calc_day - real_day).total_seconds()
            diff_minute = int(diff / MINUTE)
            print(f'#{calc_block}: {calc_day = } and {real_day = }, {diff_minute = } MINUTE')


if __name__ == '__main__':
    asyncio.run(main())
