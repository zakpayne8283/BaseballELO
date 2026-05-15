import numpy as np
import pandas as pd

from src.util.common.base_model import BaseModel
from src.util.common.player_record import PlayerRecord


class Model1_1(BaseModel):
    """
    ELO model v1.1

    TODO: Write quick documentation about this model
    """

    name: str = "v1.1"
    initial_rating: float = 1500.0
    max_k: float = 30.0
    min_k: float = 4.0
    max_confidence: float = 1.0
    min_confidence: float = 0.0

    def __init__(self) -> None:
        super().__init__()

    def calc_certainty(
        self,
        row: tuple,
        df: pd.DataFrame
    ) -> tuple[float, float]:
        # Expressed as (# PA/BF in last 90 days / (3.1 * 90days)
        
        batter_conf = min(row.pa_last_90 / (90 * 3.1), self.max_confidence)

        pitcher_conf = min(row.bf_last_90 / (90 * 3.1), self.max_confidence)

        return batter_conf, pitcher_conf
    

    def add_additional_columns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        # Add a 90 days lookback window for confidence

        cutoff = pd.Timedelta(days=90)

        results = []
        indicies = []
        for batter, group in df.groupby('batter'):
            if batter == '':
                continue

            dates = group['date'].values
            lower_dates = pd.to_datetime(group['date'] - cutoff).values

            lower = np.searchsorted(dates, lower_dates, side='left')
            row_positions = np.arange(len(group))

            results.append(row_positions - lower)
            indicies.append(group.index.values)

        df['pa_last_90'] = pd.Series(np.concatenate(results), index=np.concatenate(indicies))
        
        results = []
        indicies = []
        for pitcher, group in df.groupby('pitcher'):
            if pitcher == '':
                continue

            dates = group['date'].values
            lower_dates = pd.to_datetime(group['date'] - cutoff).values

            lower = np.searchsorted(dates, lower_dates, side='left')
            row_positions = np.arange(len(group))

            results.append(row_positions - lower)
            indicies.append(group.index.values)

        df['bf_last_90'] = pd.Series(np.concatenate(results), index=np.concatenate(indicies))

        return df


    def compute_rating_update(
        self,
        batter: PlayerRecord,
        batter_confidence: float,
        pitcher: PlayerRecord,
        pitcher_confidence: float,
        actual: float,
        league_average: float
    ) -> tuple[float, float, float, float]:
        """
        Return ``(batter_delta, pitcher_delta)`` for one plate appearance.

        The exchange is zero-sum: every point gained by the batter is lost
        by the pitcher and vice versa.
        """

        # K is now derived from certainty
        batter_k = self.max_k - ((self.max_k - self.min_k) * (batter_confidence / self.max_confidence))
        pitcher_k = self.max_k - ((self.max_k - self.min_k) * (pitcher_confidence / self.max_confidence))

        elo_win_prob: float = 1.0 / (1.0 + 10.0 ** ((pitcher.rating - batter.rating) / 400.0))
        expected: float = league_average + (elo_win_prob - 0.5) * 2.0 * league_average

        batter_delta: float = batter_k * (actual - expected)
        pitcher_delta: float = pitcher_k * ((1.0 - actual) - (1.0 - expected))  # == -batter_delta

        return batter_delta, pitcher_delta, batter_k, pitcher_k

