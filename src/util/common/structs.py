from src.util.common.player_record import PlayerRecord

# Outcome label → wOBA value, e.g. {"single": 0.87, "walk": 0.69, ...}
OutcomeMap = dict[str, float]

# player_id → PlayerRecord
RatingsStore = dict[str, PlayerRecord]