import asyncio
import random
from pprint import pprint

from api.aionode.connector import ThorConnector
from api.aionode.types import thor_to_float
from api.w3.aggregator import AggregatorDataExtractor
from api.w3.dex_analytics import DexAnalyticsCollector
from jobs.fetch.streaming_swaps import StreamingSwapFechter
from jobs.scanner.event_db import EventDatabase
from jobs.scanner.scan_cache import BlockScannerCached
from jobs.scanner.swap_extractor import SwapExtractorBlock
from jobs.user_counter import UserCounterMiddleware
from jobs.volume_filler import VolumeFillerUpdater
from lib.money import DepthCurve
from lib.texts import sep
from lib.utils import save_pickle, load_pickle
from models.memo import THORMemo
from models.pool_info import parse_thor_pools
from models.price import LastPriceHolder
from models.s_swap import AlertSwapStart, StreamingSwap
from notify.alert_presenter import AlertPresenter
from notify.public.dex_report_notify import DexReportNotifier
from notify.public.s_swap_notify import StreamingSwapStartTxNotifier
from notify.public.tx_notify import SwapTxNotifier
from tools.lib.lp_common import LpAppFramework, save_and_show_pic

BlockScannerClass = BlockScannerCached
print(BlockScannerClass, ' <= look!')


# BlockScannerClass = BlockScanner


async def debug_fetch_ss(app: LpAppFramework):
    ssf = StreamingSwapFechter(app.deps)
    data = await ssf.run_once()
    print(data)


async def debug_block_analyse(app: LpAppFramework, block):
    scanner = BlockScannerClass(app.deps)
    # await scanner.run()
    blk = await scanner.fetch_one_block(block)
    sep()

    naex = SwapExtractorBlock(app.deps)
    actions = await naex.on_data(None, blk)
    print(actions)


async def debug_full_pipeline(app, start=None, tx_id=None, single_block=False,
                              swap_start_enabled=True):
    d = app.deps

    # Block scanner: the source of the river
    d.block_scanner = BlockScannerClass(d)
    d.block_scanner.initial_sleep = 0
    if start < 0:
        await d.block_scanner.ensure_last_block()
        d.block_scanner.last_block -= abs(start)
    elif start > 0:
        d.block_scanner.last_block = start

    d.block_scanner.one_block_per_run = single_block
    d.block_scanner.allow_jumps = True

    # Just to check stability
    user_counter = UserCounterMiddleware(d)
    d.block_scanner.add_subscriber(user_counter)

    # Extract ThorTx from BlockResult
    native_action_extractor = SwapExtractorBlock(d)
    native_action_extractor.dbg_ignore_finished_status = True

    if tx_id:
        native_action_extractor.dbg_open_file(f'../temp/txs/{tx_id}.txt')
        native_action_extractor.dbg_watch_swap_id = tx_id

        # db = native_action_extractor._db
        # await db.backup('../temp/ev_db_backup_everything.json')

    d.block_scanner.add_subscriber(native_action_extractor)

    # Enrich with aggregator data
    aggregator = AggregatorDataExtractor(d)
    native_action_extractor.add_subscriber(aggregator)

    # Volume filler (important)
    volume_filler = VolumeFillerUpdater(d)
    aggregator.add_subscriber(volume_filler)

    # Just to check stability
    d.dex_analytics = DexAnalyticsCollector(d)
    aggregator.add_subscriber(d.dex_analytics)

    # Just to check stability
    volume_filler.add_subscriber(d.volume_recorder)
    volume_filler.add_subscriber(d.tx_count_recorder)

    # # Just to check stability: DEX reports
    dex_report_notifier = DexReportNotifier(d, d.dex_analytics)
    volume_filler.add_subscriber(dex_report_notifier)
    dex_report_notifier.add_subscriber(d.alert_presenter)

    # Swap notifier (when it finishes)
    curve_pts = d.cfg.get_pure('tx.curve', default=DepthCurve.DEFAULT_TX_VS_DEPTH_CURVE)
    curve = DepthCurve(curve_pts)

    swap_notifier_tx = SwapTxNotifier(d, d.cfg.tx.swap, curve=curve)
    if tx_id:
        swap_notifier_tx.dbg_just_pass_only_tx_id = tx_id
        swap_notifier_tx.no_repeat_protection = False

        # delete
        ev_db = EventDatabase(app.deps.db)
        await ev_db.erase_tx_id(tx_id)
        # await swap_notifier_tx.deduplicator.forget(tx_id)

    swap_notifier_tx.dbg_evaluate_curve_for_pools()
    volume_filler.add_subscriber(swap_notifier_tx)
    swap_notifier_tx.add_subscriber(d.alert_presenter)

    # When SS starts we do notify as well
    if swap_start_enabled:
        stream_swap_notifier = StreamingSwapStartTxNotifier(d)
        stream_swap_notifier.check_unique = False
        d.block_scanner.add_subscriber(stream_swap_notifier)
        stream_swap_notifier.add_subscriber(d.alert_presenter)

    # Run all together
    if single_block:
        await d.block_scanner.run_once()
        await asyncio.sleep(10.0)
    else:
        while True:
            await d.block_scanner.run()
            await asyncio.sleep(5.9)


async def debug_full_pipeline_search_start(app, tx_id):
    status = await app.deps.thor_connector.query_tx_details(tx_id)
    height = status['consensus_height']
    print(f"Tx link: https://runescan.io/tx/{tx_id}")
    print(f"Height = {height}")
    print(f"https://thornode.ninerealms.com/thorchain/block?height={height}")
    await debug_full_pipeline(app, tx_id=tx_id, single_block=False, start=height)


async def debug_tx_records(app: LpAppFramework, tx_id):
    ev_db = EventDatabase(app.deps.db)

    props = await ev_db.read_tx_status(tx_id)
    sep('swap')
    print(props)

    sep('tx')
    tx = props.build_action()
    print(tx)


FILE_SWAP_START_PICKLE = '../temp/swap_start_event_4.pickle'


async def get_any_ongoing_streaming_swap(app):
    thor = app.deps.thor_connector
    thor: ThorConnector
    # noinspection PyProtectedMember
    r = await thor._request('/thorchain/swaps/streaming')
    if not r:
        print('No active swaps')
        return

    swap = random.sample(r, 1)[0]
    tx_id = swap['tx_id']
    quantity, count, interval = swap['quantity'], swap['count'], swap['interval']
    target_asset = swap['target_asset']
    source_asset = swap['source_asset']
    print(f'Found active swap: {tx_id}, {quantity = }, {count = }, {source_asset} -> {target_asset}')

    details = await thor.query_tx_details(tx_id)
    tx = details['tx']['tx']
    coins = tx['coins']
    from_address = tx['from_address']
    memo_str = tx['memo']
    memo = THORMemo.parse_memo(memo_str)
    in_amount = coins[0]['amount']
    in_asset = coins[0]['asset']
    height = details['consensus_height']

    pools = parse_thor_pools(await thor.query_pools())
    price_holder = LastPriceHolder().update_pools(pools)

    ss = StreamingSwap.from_json(swap)
    event = AlertSwapStart(
        ss=ss,
        from_address=from_address,
        in_amount=in_amount,
        in_asset=in_asset,
        out_asset=target_asset,
        volume_usd=price_holder.convert_to_usd(thor_to_float(in_amount), in_asset),
        block_height=height,
        memo=memo, memo_str=memo_str,
    )

    notifier = StreamingSwapStartTxNotifier(app.deps)
    event = await notifier.load_extra_tx_information(event)
    return event


async def render_and_safe_stream_swap_start_pic(app, event):
    alert: AlertPresenter = app.deps.alert_presenter
    name_map = await alert.load_names(event.from_address)
    photo, photo_name = await alert.render_swap_start(app.deps.loc_man.default, event, name_map)
    save_and_show_pic(photo, name=f'../temp/swap_start/{event.tx_id}.png')


async def dbg_spam_any_active_swap_start(app, refresh=False, post=False):
    event = load_pickle(FILE_SWAP_START_PICKLE)
    if not event or refresh:
        event = await get_any_ongoing_streaming_swap(app)
        if not event:
            return
        save_pickle(FILE_SWAP_START_PICKLE, event)

    sep()
    print(event)
    sep()

    if not event.quote:
        await StreamingSwapStartTxNotifier(app.deps).load_quote(event)

    if post:
        # noinspection PyProtectedMember
        await app.deps.alert_presenter._handle_async(event)
        await asyncio.sleep(1)
    else:
        await render_and_safe_stream_swap_start_pic(app, event)


async def dbg_collect_some_streaming_swaps(app):
    total_collected = 0
    while True:
        event = await get_any_ongoing_streaming_swap(app)
        if not event:
            print('No more swaps. Waiting...')
            await asyncio.sleep(10)
            continue

        pickle_name = f'../temp/swap_start/pickles/{event.tx_id}.pickle'
        if load_pickle(pickle_name):
            print(f'{event.tx_id}.pickle: Already collected. Skipping...')
            await asyncio.sleep(1)
            continue

        await render_and_safe_stream_swap_start_pic(app, event)

        save_pickle(pickle_name, event)
        total_collected += 1
        print(f'Collected: {total_collected} swaps')
        sep()
        await asyncio.sleep(1)


async def dbg_look_into_tx_props(app, tx_id):
    # native_action_extractor = SwapExtractorBlock(app.deps)
    # native_action_extractor.get_events_of_interest()
    ev_db = EventDatabase(app.deps.db)
    props = await ev_db.read_tx_status(tx_id)
    pprint(props)
    sep()
    print(f"{props.is_finished = }")


async def run():
    app = LpAppFramework()
    async with app(brief=True):
        await app.deps.last_block_fetcher.run_once()
        await app.deps.pool_fetcher.run_once()

        # await dbg_look_into_tx_props(app, "C35BBEEE5D3466B5C6227A41789041EC544C5DEDC4E10236A138220206406E16")

        #  Trade 2,179.26 DOGE -> Trade 421.050556 USDT
        # await debug_full_pipeline(app,
        #                           start=21388144 - 2,
        #                           tx_id="225E7E3FC81BA3EC096A9C37F3E1514753C91A3EC0F1CF1EEDC4D2125BB4EC61",
        #                           swap_start_enabled=False)

        # Native 0.0002 BTC -> 22.99379305 TWT
        # await debug_full_pipeline(app,
        #                           start=21388126 - 2,
        #                           tx_id="D668B3B676DCA5D3CFD17AB6A99CC58783758E97EEEBEE23871912CB255A7DC4",
        #                           swap_start_enabled=False)

        # 0.011 ETH -> 17.51021135 RUNE
        await debug_full_pipeline(app,
                                  start=21402727,
                                  tx_id="C35BBEEE5D3466B5C6227A41789041EC544C5DEDC4E10236A138220206406E16",
                                  swap_start_enabled=False)

        # await debug_full_pipeline(app, start=-200)


if __name__ == '__main__':
    asyncio.run(run())

# ------- old stuff to remember ----

# await debug_full_pipeline_search_start(app, "DC5E005D6AB304532038EA6946A4CBB3ECFB2C77A695F219ABFABC905E860840")


# await debug_full_pipeline(app, start=-5000)

# await debug_fetch_ss(app)
# await debug_block_analyse(app, block=17361911)
# await debug_full_pipeline(app, start=16387377, single_block=True,
#                           tx_id='BE7B085E50DE86CD9BD8959ABF3EA924AC60302330888D484219B8B7385F7B1D')
# await debug_tx_records(app, 'E8766E3D825A7BFD755ECA14454256CA25980F8B4BA1C9DCD64ABCE4904F033D')

# await debug_tx_records(app, '62065183022E32395A1538DE9AE28CCCD81247327971990D8A57FD88BE2594EC')

# ------------------- trade to trade no stream -------------------
# await debug_full_pipeline(
#     app,
#     start=16908330,
#     tx_id='BAB65D6A6A2D7AC127FDF36DF2B1219AC5F44732804848DB4FCEFC72AD5BCE77',
#     single_block=True
# )

# ------------------- trade to trade with stream -------------------
# await debug_full_pipeline(
#     app,
#     start=16908744 - 1,
#     tx_id='4824290D3C7AE55F9915D4F0FEC46C93BB87604BD403649AD5BA208940218522',
#     single_block=False
# )

# await debug_full_pipeline(
#     app, start=12802333,
#     tx_id='2065AD2148F242D59DEE34890022A2264C9B04C2297E04295BB118E29A995E05')

# await debug_full_pipeline(
#     app, start=12802040,
#     tx_id='63218D1F853AEB534B3469C4E0236F43E04BFEE99832DF124425454B8DB1528E')
