from src.util.base_model import BaseModel


class Model1_0(BaseModel):
    """
    ELO model v1.0 — logistic expected value anchored to league-average wOBA.

    Rating update formula
    ---------------------
    For a plate appearance where the batter produced outcome ``actual`` (a
    normalised wOBA value) against a pitcher:

        elo_win_prob  = 1 / (1 + 10 ** ((pitcher_rating - batter_rating) / 400))
        expected      = league_avg + (elo_win_prob - 0.5) * 2 * league_avg

        batter_delta  = K * (actual   - expected)
        pitcher_delta = K * ((1 - actual) - (1 - expected))
                      = -batter_delta          (zero-sum)
    """

    name: str = "v1.0"
    initial_rating: float = 1500.0
    k: float = 20.0

    def __init__(self, k: float = 20.0) -> None:
        super().__init__()
        self.k = k


    def compute_rating_update(
        self,
        batter_rating: float,
        pitcher_rating: float,
        actual: float,
        league_average: float,
    ) -> tuple[float, float]:
        """
        Return ``(batter_delta, pitcher_delta)`` for one plate appearance.

        The exchange is zero-sum: every point gained by the batter is lost
        by the pitcher and vice versa.
        """
        elo_win_prob: float = 1.0 / (1.0 + 10.0 ** ((pitcher_rating - batter_rating) / 400.0))
        expected: float = league_average + (elo_win_prob - 0.5) * 2.0 * league_average

        batter_delta: float = self.k * (actual - expected)
        pitcher_delta: float = self.k * ((1.0 - actual) - (1.0 - expected))  # == -batter_delta

        return batter_delta, pitcher_delta

