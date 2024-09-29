import asyncio

import aiohttp

from jobs.poll_tcp import TCPPollster

IP_ADDRESS_LIST = ["100.21.135.206", "13.124.24.134", "13.237.27.250", "13.37.119.225", "13.48.171.132", "13.49.101.79",
                   "1.1.1.1"]
PORT_LIST = [6040, 27147, 6041]


async def my_test_multi_connect(pollster: TCPPollster):
    r = await pollster.test_connectivity_multiple([], [])
    print(r)

    r = await pollster.test_connectivity_multiple(IP_ADDRESS_LIST, [])
    print(r)

    r = await pollster.test_connectivity_multiple([], PORT_LIST)
    print(r)

    r = await pollster.test_connectivity_multiple(IP_ADDRESS_LIST, PORT_LIST, group_size=3)
    print(r)
    stats = pollster.count_stats(r)
    print(stats, len(r))


async def my_test_single_connect(pollster):
    r = await pollster.test_connectivity('34.249.205.131', 6040)
    print(r)
    r = await pollster.test_connectivity('34.249.205.132', 6040)
    print(r)


async def find_nodes(pollster: TCPPollster):
    async with aiohttp.ClientSession() as session:
        async with session.get('https://thornode.ninerealms.com/thorchain/nodes') as resp:
            data = await resp.json()
            ip_addresses = list(filter(bool, (node['ip_address'] for node in data)))
        print('total ip: ', len(ip_addresses))
        r = await pollster.test_connectivity_multiple(ip_addresses, ['1317', '8080'], group_size=20)
        r = {ip: data for ip, data in r.items() if any(data.values())}
        print(r)


async def main():
    pollster = TCPPollster()

    # await my_test_single_connect(pollster)
    # await my_test_multi_connect(pollster)
    await find_nodes(pollster)


if __name__ == '__main__':
    asyncio.run(main())
