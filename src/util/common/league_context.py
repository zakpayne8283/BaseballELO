import pandas as pd
from dataclasses import dataclass, field

from src.util.common.structs import OutcomeMap

@dataclass
class LeagueContext:
    re_matrix: pd.DataFrame
    outcomes: OutcomeMap
    league_average: float