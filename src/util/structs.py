# TODO: Move these to their own files when the /util/ folder is restructured

from src.util.player_record import PlayerRecord

# Outcome label → wOBA value, e.g. {"single": 0.87, "walk": 0.69, ...}
OutcomeMap = dict[str, float]

# player_id → PlayerRecord
RatingsStore = dict[str, PlayerRecord]