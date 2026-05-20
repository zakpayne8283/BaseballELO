from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from src.util.common.player_record import PlayerRecord
from src.util.common.structs import RatingsStore

class BaseModel(ABC):
    """
    Abstract base class (ABC) for Batter/Pitcher ELO Model.

    Models implement this base class to ensure they have base functionality that the orchestrator expects.

    Attributes
    ----------
    name : str
        The friendly name of the model
        Example: `v1.0`
    col_prefix : str
        The column prefix the model will use when adding columns to the output data.
        Example: `m1_0`
    initial_rating : float
        The ELO rating that new players will start at. Typically 1500.
    max_k : float
        The maximum K value to adjust ratings by. High K values rapidly change ratings.
    min_k : float
        The minimum K value to adjust ratings by. Low K values slowly change ratings.
    max_confidence : float
        The maximum confidence level available for a rating, typically 1.0. 
    min_confidence : float
        The minimum confidence level available for a rating, typically 0.0.
    ----------
    _batters : RatingsStore
        A dictionary for all batters encountered so far. `RatingsStore` holds current rating and number of instances.
        Not implemented by child classes.
    _pitchers : RatingsStore
        A dictionary for all pitchers encountered so far. `RatingsStore` holds current rating and number of instances.
        Not implemented by child classes.
    """

    name: str = None
    col_prefix: str = None
    initial_rating: float = None
    max_k: float = None
    min_k: float = None
    max_confidence: float = None
    min_confidence: float = None

    _batters: RatingsStore = {}
    _pitchers: RatingsStore = {}


    def __init__(self) -> None:
        # Require subclasses implement:
        for attr in ('name', 'col_prefix', 'initial_rating', 'max_k', 'min_k', 'max_confidence', 'min_confidence'):
            if not hasattr(self, attr):
                raise NotImplementedError(
                    f'Model `{type(self).__name__}` must define class attribute `{attr}`'
                )
        
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
        Compute the batter and pitcher rating deltas and K values for one matchup.

        Parameters
        ----------
        batter : PlayerRecord
            PlayerRecord containing the batter's current ELO and number of instances.
        batter_confidence : float
            Batter confidence rating, typically based on number of recent PAs and typically mutates K values.
        pitcher : PlayerRecord
            PlayerRecord containing the pitcher's current ELO and number of instances.
        pitcher_confidence : float
            Pitcher confidence rating, typically based on number of recent BF and typically mutates K values.
        actual:
            The typical run value of the PA outcome (normalised to [0, 1]).
        league_average:
            League-wide average PA run value for this season (normalised to [0, 1]).

        Returns
        -------
        tuple[float, float, float, float]
            A tuple containing `(batter_delta, pitcher_delta, batter_k, pitcher_k)` following the PA result.

        """

    @abstractmethod
    def add_additional_columns(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Adds any additional columns that the model needs to compute the deltas in each matchup. E.g. PAs in last 90 days.

        Parameters
        ----------
        df : pd.DataFrame
            The dataframe containing the base data from which the additional columns are calculated/created.

        Returns
        -------
        pd.DataFrame
            The base dataframe modified to contain the newly added columns.
        """

    @abstractmethod
    def calc_certainty(
        self,
        row: tuple
    ) -> tuple[float, float]:
        """
        Calculates the certainty that can be applied to the ELO update calculation.
        
        Low certainty might change ELO more rapidly, high certainty might change ELO more slowly.

        Example: A model might compute certainty based on number of plate
                 apperances or batters faced over the last 90 days.

        Parameters
        ----------
        row : tuple
            A row which represents a single plate apperance.

        Returns
        -------
        tuple[float, float]
            A tuple containing `(batter_confidence, pitcher_confidence)`, typically on a continuous scale of [0, 1].
        """

    def run(
        self,
        matchup_df : pd.DataFrame,
        coeffs_df : pd.DataFrame
    ) -> pd.DataFrame:
        """
        Starts the run of a model.
        
        1. Creates empty np.array objects to contain the outputs from `compute_rating_update`
        2. Determines the run values of each PA for the years provided.
        3. Iterates over all rows in the `matchup_df`:
            3.1. Find or create the batter and pitcher.
            3.2. Calculate the certainty in the batter and pitcher.
            3.3. Calculate the deltas and K values for the batter and pitcher.
            3.4. Update the ratings in the ratings store and store the ratings for later.
        4. Append all results to `matchup_df` and return results.

        Parameters
        ----------
        matchup_df : pd.DataFrame
            A dataframe containing all plate apperances for the years provided. 
            Contains the batter, pitcher, and result of the PA.
        coeffs_df : pd.DataFrame
            A dataframe containing all normalized run values for all possible results.

        Returns
        -------
        pd.DataFrame
            A mutated version of matchup_df containing the computed ratings and K values from the model.
        """

        # Number of total PAs
        n = len(matchup_df)

        # Create the output arrays
        batter_rating_pre  = np.empty(n)
        batter_rating_post = np.empty(n)
        pitcher_rating_pre  = np.empty(n)
        pitcher_rating_post = np.empty(n)
        batter_k_col = np.empty(n)
        pitcher_k_col = np.empty(n)

        # Determine the run value for each plate apperance
        print('Finding run values for all PAs...')
        actuals = matchup_df.merge(
            coeffs_df.melt(id_vars='year', var_name='result', value_name='value'),
            left_on=[matchup_df['date'].dt.year, 'pa_result'],
            right_on=['year', 'result'],
            how='left'
        )['value'].to_numpy()

        # Compute the ELOs
        print('Beginning row-by-row matchups...')
        for index, row in enumerate(matchup_df.itertuples(index=False)):

            # Get the batter and pitcher
            batter = self._get_or_create_player(self._batters, row.batter)
            pitcher = self._get_or_create_player(self._pitchers, row.pitcher)

            # Calculate the confidence in each
            batter_conf, pitcher_conf = self.calc_certainty(row, matchup_df)

            # Run the rating update
            batter_delta, pitcher_delta, batter_k, pitcher_k = self.compute_rating_update(
                batter=batter,
                batter_confidence=batter_conf,
                pitcher=pitcher,
                pitcher_confidence=pitcher_conf,
                actual=actuals[index],
                league_average=coeffs_df[coeffs_df['year'] == row.date.year]['average'].values[0]
            )

            # Store the ratings before the AB
            batter_rating_pre[index]  = batter.rating
            pitcher_rating_pre[index] = pitcher.rating

            # Store the K values for the batter and pitcher
            batter_k_col[index] = batter_k
            pitcher_k_col[index] = pitcher_k

            # Determine the new ratings
            batter.rating  += batter_delta
            batter.instances += 1
            pitcher.rating += pitcher_delta
            pitcher.instances += 1

            # Store the new ratings
            batter_rating_post[index]  = batter.rating
            pitcher_rating_post[index] = pitcher.rating

            # Show progress every 5% completed 
            if index % (n // 5) == 0:
                print(f"{index / n:.0%}")

        # Compile all the calculated columns into a single dataframe        
        temp_df = pd.DataFrame()
        temp_df = temp_df.assign(
            batter_rating_pre=batter_rating_pre.round(3),
            batter_rating_post=batter_rating_post.round(3),
            batter_k=batter_k_col.round(3),
            pitcher_k=pitcher_k_col.round(3),
            pitcher_rating_pre=pitcher_rating_pre.round(3),
            pitcher_rating_post=pitcher_rating_post.round(3)
        ).add_prefix(f'{self.col_prefix}_')

        # Add the compiled dataframe to the base dataframe
        return pd.concat([matchup_df.reset_index(drop=True), temp_df.reset_index(drop=True)], axis=1)
    
    def _get_or_create_player(
        self, store: RatingsStore, player_id: str
    ) -> PlayerRecord:
        """
        Finds or creates a player based on their Retrosheet ID (stored as `batter` or `pitcher` by Retroshet)

        Parameters
        ----------
        store : RatingsStore
            The dictionary where all batters or pitchers are stored
        player_id : str
            The Retrosheet ID of the player to look up

        Returns
        -------
        PlayerRecord
            Returns a `PlayerRecord` containing the player's current rating and number of instances.
        """
        if player_id not in store:
            store[player_id] = PlayerRecord(rating=self.initial_rating)
        return store[player_id]
