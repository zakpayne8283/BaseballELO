import numpy as np
import pandas as pd

from src.util.common.base_model import BaseModel
from src.util.common.player_record import PlayerRecord


class Model1_1(BaseModel):
    """
    ELO model v1.1
    Built of Model 1.0 that uses a dynamic K value based on number of "recent" plate appearances.

    **See Model 1.0 Docstring for analysis of the base formula**

    The thinking behind this is that we may have a player who plays every day and we know almost exactly what to expect
    from him in terms of performance, meaning a low K value. Comparitively, a player coming back from being on the IL
    for 5 weeks may have more uncertainty around their performance; we have a baseline expectation, but we should be
    prepared for some amount of rapid change.

    Produces a dynamic K value based on the number of appearances (PA or BF) in the last 90 daysL
        K = min(appearances / (90 * 3.1), self.max_confidence)

    Note

    Sample Outputs
    --------------
    davik003	verlj001	2019-06-01	other_out	1615.628	1614.013	13.878	4.000	1719.233	1719.699
    1.
        Parameters: 
            Date: 2019-06-01
            Max K: 30.0
            Min K: 4
            Avg: 0.163
        Pitcher:
            Name: Justin Verlander
            ELO: ~1719
            K Value: 4
        Batter:
            Name: Khris Davis
            ELO: ~1615
            K Value: 13.878
        Results:
            PA Result: Out (non-K) | ~0.0001
            Batter Delta: -1.615
            Pitcher Delta: +0.466
    
    """

    name: str = "v1.1"
    col_prefix: str = 'm1_1'
    initial_rating: float = 1500.0
    max_k: float = 30.0
    min_k: float = 4.0
    max_confidence: float = 1.0
    min_confidence: float = 0.0

    def __init__(self) -> None:
        super().__init__()

    
    def __add_lookback_x_days(
        df: pd.DataFrame,
        days: int,
        group_by: str
    ) -> pd.Series:
        cutoff = pd.Timedelta(days=days)

        results = []
        indicies = []
        for group_key, group in df.groupby(group_by):
            if group_key == '':
                continue

            dates = group['date'].values
            lower_dates = pd.to_datetime(group['date'] - cutoff).values

            lower = np.searchsorted(dates, lower_dates, side='left')
            row_positions = np.arange(len(group))

            results.append(row_positions - lower)
            indicies.append(group.index.values)

        return pd.Series(np.concatenate(results), index=np.concatenate(indicies))


    def calc_certainty(
        self,
        row: tuple
    ) -> tuple[float, float]:
        # Expressed as (# PA or BF in last 90 days / (3.1 * 90days)

        pa_last_90 = getattr(row, f'{self.col_prefix}_pa_last_90')
        bf_last_90 = getattr(row, f'{self.col_prefix}_bf_last_90')
        
        batter_conf = min(pa_last_90 / (90 * 3.1), self.max_confidence)
        pitcher_conf = min(bf_last_90 / (90 * 3.1), self.max_confidence)

        return batter_conf, pitcher_conf
    

    def add_additional_columns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        # Add a 90 days lookback window for confidence

        # PAs last 90 days for batters
        df[f'{self.col_prefix}_pa_last_90'] = self.__add_lookback_x_days(df, 90, 'batter')
        
        # BF last 90 days for pitchers
        df[f'{self.col_prefix}_bf_last_90'] = self.__add_lookback_x_days(df, 90, 'pitcher')

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

