from logic.onetime_logic import analyze_entries
from realtimeparser import start_mc_realtime


def iterate_realtime(path: str, dangers: dict, stop_event=None):
    yield from analyze_entries(start_mc_realtime(path, stop_event), dangers)
