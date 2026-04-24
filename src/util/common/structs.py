from src.util.common.player_record import PlayerRecord

# Coefficient Map for wOBA values -> wOBA value, e.g. {"single": 0.87, "walk": 0.69, ...}
CoefficientsMap = dict[str, float]

# player_id → PlayerRecord
RatingsStore = dict[str, PlayerRecord]