from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from src.util.common.player_record import PlayerRecord
from src.util.common.structs import RatingsStore

class BaseModel(ABC):
    """
    Base for Batter/Pitcher ELO Model
    """

    #: Readable version, e.g. "v1.0"
    name: str
    # Column prefix for model
    col_prefix: str
    #: Initial ELO for unseen player
    initial_rating: float
    #: Max K value for adjusting ratings
    max_k: float
    # Min K
    min_k: float
    # Max Confidence for computing K
    max_confidence: float
    # Min Confidence
    min_confidence: float


    def __init__(self) -> None:
        # Require subclasses implement:
        for attr in ('name', 'col_prefix', 'initial_rating', 'max_k', 'min_k', 'max_confidence', 'min_confidence'):
            if not hasattr(self, attr):
                raise NotImplementedError(
                    f"{type(self).__name__} must define class attribute '{attr}'"
                )

        self._batters: RatingsStore = {}
        self._pitchers: RatingsStore = {}
        self._normalized_coeffs: list[dict] = []
        self._df_norm_coeffs: pd.DataFrame = None

    @abstractmethod
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
        Compute the rating *deltas* for one plate appearance.

        Parameters
        ----------
        batter_rating:
            The batter's Elo rating before this PA.
        pitcher_rating:
            The pitcher's Elo rating before this PA.
        actual:
            The wOBA value of the PA outcome (normalised to [0, 1]).
        league_average:
            League-average wOBA for this season (normalised to [0, 1]).

        Returns
        -------
        tuple[float, float]
            ``(batter_delta, pitcher_delta)`` — signed rating changes to apply.
        """

    @abstractmethod
    def add_additional_columns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        """

    @abstractmethod
    def calc_certainty(
        self,
        row: tuple
    ) -> tuple[float, float]:
        """
        Docstring for calc_certainty
        
        :type row: tuple
        :type df: pd.DataFrame
        :return: Returns a float representing the confidence of a rating (helps produce K value)
        :rtype: float
        """


    def run(self, matchup_df, coeffs_df) -> pd.DataFrame:

        n = len(matchup_df)

        batter_rating_pre  = np.empty(n)
        batter_rating_post = np.empty(n)
        pitcher_rating_pre  = np.empty(n)
        pitcher_rating_post = np.empty(n)
        batter_k_col = np.empty(n)
        pitcher_k_col = np.empty(n)

        print('Computing actuals...')
        actuals = matchup_df.merge(
            coeffs_df.melt(id_vars='year', var_name='result', value_name='value'),
            left_on=[matchup_df['date'].dt.year, 'pa_result'],
            right_on=['year', 'result'],
            how='left'
        )['value'].to_numpy()

        print('Beginning row-by-row matchups...')
        for index, row in enumerate(matchup_df.itertuples(index=False)):

            # Get the batter and pitcher
            batter = self._get_or_create_player(self._batters, row.batter)
            pitcher = self._get_or_create_player(self._pitchers, row.pitcher)

            # Calculate the confidence in each
            batter_conf, pitcher_conf = self.calc_certainty(row, matchup_df)

            # print(coeffs_df[coeffs_df['year'] == row.date.year]['average'].values)
            # quit()

            # Run the rating update
            batter_delta, pitcher_delta, batter_k, pitcher_k = self.compute_rating_update(
                batter=batter,
                batter_confidence=batter_conf,
                pitcher=pitcher,
                pitcher_confidence=pitcher_conf,
                actual=actuals[index],
                league_average=coeffs_df[coeffs_df['year'] == row.date.year]['average'].values[0]
            )

            batter_rating_pre[index]  = batter.rating
            pitcher_rating_pre[index] = pitcher.rating

            batter_k_col[index] = batter_k
            pitcher_k_col[index] = pitcher_k

            batter.rating  += batter_delta
            batter.instances += 1
            pitcher.rating += pitcher_delta
            pitcher.instances += 1

            batter_rating_post[index]  = batter.rating
            pitcher_rating_post[index] = pitcher.rating

            if index % (n // 10) == 0:
                print(f"{index / n:.0%}")


        temp_df = pd.DataFrame()
        temp_df = temp_df.assign(
            batter_rating_pre=batter_rating_pre.round(3),
            batter_rating_post=batter_rating_post.round(3),
            batter_k=batter_k_col.round(3),
            pitcher_k=pitcher_k_col.round(3),
            pitcher_rating_pre=pitcher_rating_pre.round(3),
            pitcher_rating_post=pitcher_rating_post.round(3)
        ).add_prefix(f'{self.col_prefix}_')

        return pd.concat([matchup_df.reset_index(drop=True), temp_df.reset_index(drop=True)], axis=1)
    

    def _get_or_create_player(
        self, store: RatingsStore, player_id: str
    ) -> PlayerRecord:
        if player_id not in store:
            store[player_id] = PlayerRecord(rating=self.initial_rating)
        return store[player_id]
