import pandas as pd
from dataclasses import dataclass

from src.util.common.structs import CoefficientsMap

@dataclass
class LeagueContext:
    re_matrix: pd.DataFrame
    woba_coeffs: CoefficientsMap
    normal_coeffs: CoefficientsMap
    league_average: float