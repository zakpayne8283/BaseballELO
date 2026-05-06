from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.compute as pa_comp
import pyarrow.csv as pa_csv

from src.util.retrosheet import Retrosheet
from src.util.stats import re
from src.util.stats import woba

from src.util.constants import NEEDED_COLUMNS, OUTPUT_COLUMNS
from src.util.common.player_record import PlayerRecord
from src.util.common.league_context import LeagueContext
from src.util.helpers import get_pa_result
from src.util.common.structs import CoefficientsMap, RatingsStore

from dataclasses import asdict

class BaseModel(ABC):
    """
    Base for Batter/Pitcher ELO Model

        - Loads Retrosheet data and filters by year
        - wOBA / run-expectancy calculations
        - The plate-appearance iteration loop and DataFrame bookkeeping TODO
        - CSV output TODO

    Subclasses:
        - ``name``: ``str``
        - ``initial_rating``: ``int``
        - ``compute_rating_update(...)``: ``None``

    The base class owns:

    """

    #: Readable version, e.g. "v1.0"
    name: str
    #: Initial ELO for unseen player
    initial_rating: float


    def __init__(self) -> None:
        # Require subclasses implement:
        for attr in ("name", "initial_rating"):
            if not hasattr(self, attr):
                raise NotImplementedError(
                    f"{type(self).__name__} must define class attribute '{attr}'"
                )

        self._batters: RatingsStore = {}
        self._pitchers: RatingsStore = {}
        self._league_contexts: dict[LeagueContext] = {}
        self._retrosheet = Retrosheet()

    @abstractmethod
    def compute_rating_update(
        self,
        batter_rating: float,
        pitcher_rating: float,
        actual: float,
        league_average: float,
    ) -> tuple[float, float]:
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


    def run(self, years: list[int]) -> None:
        """
        Execute the model for ``years``.

        Outputs two files per run:
            - ``matchups_<name>.csv``     — every PA with pre/post ratings
        """
        # Raw Table of PyArrow loaded CSV
        raw_table = self._load_raw_retrosheet_data()

        matchups_file_path  = f"matchups_{self.name}.csv"
        league_context_path = 'league_contexts.csv'
        # Start fresh each run so we don't append to a stale file.
        if os.path.exists(matchups_file_path):
            os.remove(matchups_file_path)

        for year in years:
            print("-" * 15)
            print(f"Processing {year}…")
            print("-" * 15)

            # Pandas DF for that specific `year`
            df_year = self._filter_year(raw_table, year)
            if df_year.empty or df_year is None:
                print(f"  No data for {year}, skipping.")
                continue

            # Run the model for that year
            # TODO: Make running year-by-year optional?
            df_rated = self._process_year(df_year, year)

            df_rated = df_rated[OUTPUT_COLUMNS]

            # Append to the matchups output
            df_rated.to_csv(
                matchups_file_path,
                mode="a",
                header=not os.path.exists(matchups_file_path),
                index=False,
            )
            print(f"  Done — {len(df_rated):,} plate appearances.")

        # Write the league contexts
        df_lg_cxt = pd.DataFrame([asdict(cxt) for cxt in self._league_contexts.values()])
        df_lg_cxt.to_csv(league_context_path, header=True)


    def _load_raw_retrosheet_data(self) -> Any:
        """Download Retrosheet data and return a PyArrow Table."""
        self._retrosheet.fetch_all_retrosheet_data()
        convert_options = pa_csv.ConvertOptions(include_columns=NEEDED_COLUMNS)
        return pa_csv.read_csv(
            os.path.join(self._retrosheet.plays_dir, "plays.csv"),
            convert_options=convert_options,
        )
    

    def _filter_year(self, table: Any, year: int) -> pd.DataFrame:
        """Return a pandas DataFrame containing only regular-season PAs for *year*."""
        # Slice year from GID
        sliced = pa_comp.utf8_slice_codeunits(table["gid"], start=3, stop=7)
        # Apply mask to slice
        mask = pa_comp.and_(
            pa_comp.equal(sliced, str(year)),
            pa_comp.equal(table["gametype"], "regular"),
        )
        return table.filter(mask).to_pandas()
    

    def _prepare_year_dataframe(
        self,
        df: pd.DataFrame,
        year: int
    ) -> tuple[pd.DataFrame, CoefficientsMap, float]:
        """
        Apply helper transforms and compute league-level values.

        Returns
        -------
        df:
            Filtered DataFrame with ``pa_result`` column added.
        outcomes:
            Mapping of PA outcome label → normalised wOBA weight.
        league_average:
            League-average wOBA (normalised) for this season.
        """
        
        # Create PA result (single, home_run, etc)
        df["pa_result"] = df.apply(get_pa_result, axis=1)
        df = df.loc[df["pa_result"].notna()].copy()

        # Compute & Apply Run Expectancy Numbers
        re_matrix = re.compute_run_expectancy_matrix(df)
        df = re.apply_run_expectancy_columns(df, re_matrix)

        # Compute, Apply, & Normalize wOBA Coefficients
        df = woba.apply_woba_columns(df, re_matrix)
        woba_coeffs = woba.compute_woba_coefficients(df)
        normal_coeffs = woba.normalize_woba_coeffs(woba_coeffs)

        if 're_diff' not in df:
            raise ValueError(f'Cannot compute Average ELO coefficient: missing column `re_diff`')

        # Get the league's average 
        pa_result_proportions = df['pa_result'].value_counts(normalize=True).to_dict()
        league_average = sum(
            normal_coeffs[k] * v for k, v in pa_result_proportions.items()
        )

        self._league_contexts[year] = LeagueContext(re_matrix, woba_coeffs, normal_coeffs, league_average)
        
        return df, normal_coeffs, league_average
    

    def _process_year(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        """
        Iterate over every PA, update ratings, and return the annotated DataFrame.
        """
        df, outcomes, league_average = self._prepare_year_dataframe(df, year)

        # Pre-allocate rating columns
        n = len(df)
        batter_rating_pre  = np.empty(n)
        batter_rating_post = np.empty(n)
        pitcher_rating_pre  = np.empty(n)
        pitcher_rating_post = np.empty(n)

        actuals = df["pa_result"].map(outcomes).to_numpy()

        for index, row in enumerate(df.itertuples(index=False)):
            batter = self._get_or_create_player(self._batters, row.batter)
            pitcher = self._get_or_create_player(self._pitchers, row.pitcher)

            batter_delta, pitcher_delta = self.compute_rating_update(
                batter_rating=batter.rating,
                pitcher_rating=pitcher.rating,
                actual=actuals[index],
                league_average=league_average,
            )

            batter_rating_pre[index]  = batter.rating
            pitcher_rating_pre[index] = pitcher.rating

            batter.rating  += batter_delta
            batter.instances += 1
            pitcher.rating += pitcher_delta
            pitcher.instances += 1

            batter_rating_post[index]  = batter.rating
            pitcher_rating_post[index] = pitcher.rating

        df = df.assign(
            batter_rating_pre=batter_rating_pre.round(3),
            batter_rating_post=batter_rating_post.round(3),
            pitcher_rating_pre=pitcher_rating_pre.round(3),
            pitcher_rating_post=pitcher_rating_post.round(3)
        )

        return df


    def _get_or_create_player(
        self, store: RatingsStore, player_id: str
    ) -> PlayerRecord:
        if player_id not in store:
            store[player_id] = PlayerRecord(rating=self.initial_rating)
        return store[player_id]
