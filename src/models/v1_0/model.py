import pandas as pd

from src.util.common.base_model import BaseModel
from src.util.common.player_record import PlayerRecord


class Model1_0(BaseModel):
    """
    ELO model v1.0
    Logistic expected value anchored to a normalized average plate appearance run value.

    Rating Update Formula
    ---------------------
    Every plate appearance produces some amount of positive or negative run value:
        Approximate examples:
        K  -> -0.26
        1B ->  0.70
        HR ->  1.90

        wOBA then modifies these values such that lgOBP = lgwOBA, but that's unneed here.

    Traditional ELO models (like chess) typically operate on a scale of:
        Loss -> 0.0
        Win  -> 1.0

        For an average value of 0.5 per game.

    Since ELO is designed around an average value of 0.5 on a continuous scale of [0,1],
    the run values need to be normalized to that scale as well. Otherwise, pitchers average
    ELO ~2000 and hitters average ELO ~1000.
        Approximate examples:
        K  -> 0.0
        1B -> 0.45
        HR -> 1.0

        Average (weighted by PA result) of ~0.15

    So the formula becomes:
        
        elo_win_prob  = 1 / (1 + 10 ** ((pitcher_rating - batter_rating) / 400))
        expected = league_avg + (elo_win_prob - 0.5) * 2 * league_avg
        batter_delta  = K * (actual - expected)
        pitcher_delta = K * ((1 - actual) - (1 - expected))
        
    Example
    -------
    For a plate appearance where the batter produced outcome ``actual`` (a
    normalised run value for the result) against a pitcher:

        elo_win_prob  = 1 / (1 + 10 ** ((pitcher_rating - batter_rating) / 400))
            - Compute the probability that the pitcher "loses"
            - This is the `expected` in a traditional ELO model
            - Example: pitcher 1520 | batter 1500 ----> 0.47124944

        expected = league_avg + (elo_win_prob - 0.5) * 2 * league_avg
            - Put `expected` to the scale that's being used here by adjusting for league average
            - Example (cont): league_avg 0.15 ----> 0.14137483      # Pitcher "won by" ~0.0086

        batter_delta  = K * (actual - expected)
            - The amount to adjust the batter rating based on what happened
            - Example (cont): K 20 | actual 0.424 (1B) ----> 20 * (0.283 # More value produced than expected #) -> Batter ELO +5.66

        pitcher_delta = K * ((1 - actual) - (1 - expected))
            - The amount to adjust the pitcher rating based on what happened
            - Opposite rating of batter
            - Example (cont): K 20 | actual 0.424 (1B) ----> 20 * (0.576 - 0.859) -> Pitcher ELO -5.66

    Sample Outputs
    --------------
    1.
        Parameters: 
            Date: 2022-07-10
            K: 20.0
            Avg: 0.1505

        Pitcher:
            Name: Sandy Alcantara
            ELO: ~1700
        Batter:
            Name: Eduardo Escobar
            ELO: ~1501
        Results:
            PA Result: Out (non-K) | ~0.004
            Batter Delta: -1.37
            Pitcher Delta: +1.37
    
    """

    name: str = "v1.0"
    col_prefix: str = 'm1_0'
    initial_rating: float = 1500.0
    max_k: float = 20.0
    min_k: float = 20.0
    max_confidence: float = 1.0
    min_confidence: float = 1.0

    def __init__(self) -> None:
        super().__init__()


    def calc_certainty(
        self,
        row: tuple
    ) -> tuple[float, float]:
        """
        The model always has a confidence of 1.0 for all cases.
        """
        return self.max_confidence, self.max_confidence
        
        
    def add_additional_columns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        The model requires no additional columns
        """
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
        Return ``(batter_delta, pitcher_delta, batter_k, pitcher_k)`` for one plate appearance.

        See above for notes on the formula
        """

        # Calc pitcher "win" probability and normalize it to the league average
        elo_win_prob: float = 1.0 / (1.0 + 10.0 ** ((pitcher.rating - batter.rating) / 400.0))
        expected: float = league_average + (elo_win_prob - 0.5) * 2.0 * league_average

        # Adjust the batter and pitcher values
        batter_delta: float = self.max_k * (actual - expected)
        pitcher_delta: float = self.max_k * ((1.0 - actual) - (1.0 - expected))

        return batter_delta, pitcher_delta, self.max_k, self.max_k

