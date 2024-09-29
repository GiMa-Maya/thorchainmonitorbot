from typing import List

from lib.depcont import DepContainer
from models.node_info import NodeEvent, MapAddressToPrevAndCurrNode, NodeEventType
from .helpers import BaseChangeTracker, NodeOpSetting


class BondTracker(BaseChangeTracker):
    def __init__(self, deps: DepContainer):
        super().__init__()
        self.deps = deps

    async def get_events_unsafe(self) -> List[NodeEvent]:
        return list(self._changes_of_bond(self.prev_and_curr_node_map))

    def _changes_of_bond(self, pc_node_map: MapAddressToPrevAndCurrNode):
        for a, (prev, curr) in pc_node_map.items():
            if prev.bond != curr.bond:
                yield NodeEvent(prev.node_address, NodeEventType.BOND, (prev.bond, curr.bond),
                                node=curr, tracker=self)

    async def is_event_ok(self, event: NodeEvent, user_id, settings: dict) -> bool:
        return bool(settings.get(NodeOpSetting.BOND_ON, True))
