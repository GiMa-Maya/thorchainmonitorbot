import re
from typing import NamedTuple, Union, List

from lib.texts import fuzzy_search


class AggregatorRecord(NamedTuple):
    address: str
    chain: str
    name: str


AggregatorSearchResult = Union[AggregatorRecord, List[AggregatorRecord], None]

DEFAULT_AGGREGATOR_RESOLVER_PATH = './data/token_list/aggregator_list.txt'


# Use that source: https://gitlab.com/thorchain/thornode/-/blob/develop/x/thorchain/aggregators/dex_mainnet.go
class AggregatorResolver:
    def __init__(self, filename, data=None):
        self.filename = filename
        self._table = {}
        self.by_chain = {}
        self.by_name = {}

        if filename:
            with open(self.filename, 'r') as fp:
                data = fp.read()
        self._load(data)

    def _load(self, data):
        lines = [line.strip() for line in data.split('\n')]
        lines = filter(bool, lines)
        aggr_name = ''
        for line in lines:
            if line.startswith('//'):  # comment line contains names
                aggr_name = line[2:].strip()
            elif line.startswith('{'):  # datum line contains chain and address
                addresses = re.findall(r'`(.+?)`', line)
                chains = re.findall(r'common\.(.+?)Chain', line)
                if addresses and chains:
                    chain = chains[0]
                    aggr_address = addresses[0]
                    record = AggregatorRecord(aggr_address, chain, aggr_name)
                    if chain not in self.by_chain:
                        self.by_chain[chain] = {}
                    self.by_chain[chain][aggr_address] = record
                    self.by_name[aggr_name] = record
                    self._table[aggr_address.lower()] = record

    def search_aggregator_address(self, query: str, ambiguity=False) -> AggregatorSearchResult:
        return self._search(query, self._table, ambiguity)

    def search_by_name(self, query, ambiguity=False) -> AggregatorSearchResult:
        return self._search(query, self.by_name, ambiguity)

    @staticmethod
    def _search(query, dic, ambiguity_check) -> AggregatorSearchResult:
        variants = fuzzy_search(query, dic.keys(), f=str.lower)
        if not variants:
            return None

        if len(variants) > 1:
            if ambiguity_check:
                raise ValueError('Aggregator search ambiguity!')
            else:
                return [dic.get(v) for v in variants]
        else:
            return dic.get(variants[0])

    def __len__(self):
        return len(self._table)

    def __getitem__(self, item):
        return self._table.get(item)
