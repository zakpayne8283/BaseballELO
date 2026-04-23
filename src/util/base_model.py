from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
import pyarrow.compute as pa_comp
import pyarrow.csv as pa_csv

from src.util.retrosheet import Retrosheet
from src.util.run_expectancy import create_run_expectancy_dataframes
from src.util.woba import create_woba_dataframes, normalize_woba_coeffs

from src.util.constants import NEEDED_COLUMNS
from src.util.player_record import PlayerRecord
from src.util.helpers import get_pa_result
from src.util.structs import OutcomeMap, RatingsStore

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

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        # Require subclasses implement:
        for attr in ("name", "initial_rating"):
            if not hasattr(self, attr):
                raise NotImplementedError(
                    f"{type(self).__name__} must define class attribute '{attr}'"
                )

        self._batters: RatingsStore = {}
        self._pitchers: RatingsStore = {}
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
            - ``batter_ratings_<name>.csv``
            - ``pitcher_ratings_<name>.csv``
        """
        raw_table = self._load_raw_data()

        matchups_path = f"matchups_{self.name}.csv"
        # Start fresh each run so we don't append to a stale file.
        if os.path.exists(matchups_path):
            os.remove(matchups_path)

        for year in years:
            print("-" * 15)
            print(f"Processing {year}…")
            print("-" * 15)

            df_year = self._filter_year(raw_table, year)
            if df_year.empty:
                print(f"  No data for {year}, skipping.")
                continue

            df_rated = self._process_year(df_year)

            df_rated.to_csv(
                matchups_path,
                mode="a",
                header=not os.path.exists(matchups_path),
                index=False,
            )
            print(f"  Done — {len(df_rated):,} plate appearances.")

        self._save_ratings()


    def _load_raw_data(self) -> Any:
        """Download Retrosheet data and return a PyArrow Table."""
        self._retrosheet.fetch_retrosheet_data_by_years()
        convert_options = pa_csv.ConvertOptions(include_columns=NEEDED_COLUMNS)
        return pa_csv.read_csv(
            os.path.join(self._retrosheet.plays_dir, "plays.csv"),
            convert_options=convert_options,
        )
    

    def _filter_year(self, table: Any, year: int) -> pd.DataFrame:
        """Return a pandas DataFrame containing only regular-season PAs for *year*."""
        sliced = pa_comp.utf8_slice_codeunits(table["gid"], start=3, stop=7)
        mask = pa_comp.and_(
            pa_comp.equal(sliced, str(year)),
            pa_comp.equal(table["gametype"], "regular"),
        )
        return table.filter(mask).to_pandas()
    

    def _prepare_year_dataframe(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, OutcomeMap, float]:
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

        # TODO: Just make RE24, wOBA, and normalized wOBA into their own CSV files
        #       so each year doesn't need to compute each run
        df, re_matrix = create_run_expectancy_dataframes(df)
        df, woba_coeffs = create_woba_dataframes(df, re_matrix)
        outcomes, league_average = normalize_woba_coeffs(df, woba_coeffs)

        return df, outcomes, league_average
    

    def _process_year(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Iterate over every PA, update ratings, and return the annotated DataFrame.
        """
        df, outcomes, league_average = self._prepare_year_dataframe(df)

        # Pre-allocate rating columns
        df["batter_rating_pre"] = pd.NA
        df["batter_rating_post"] = pd.NA
        df["pitcher_rating_pre"] = pd.NA
        df["pitcher_rating_post"] = pd.NA

        for index, row in df.iterrows():
            batter = self._get_or_create_player(self._batters, row["batter"])
            pitcher = self._get_or_create_player(self._pitchers, row["pitcher"])

            actual: float = outcomes[row["pa_result"]]

            batter_delta, pitcher_delta = self.compute_rating_update(
                batter_rating=batter.rating,
                pitcher_rating=pitcher.rating,
                actual=actual,
                league_average=league_average,
            )

            df.at[index, "batter_rating_pre"] = batter.rating
            df.at[index, "pitcher_rating_pre"] = pitcher.rating

            batter.rating += batter_delta
            batter.instances += 1

            pitcher.rating += pitcher_delta
            pitcher.instances += 1

            df.at[index, "batter_rating_post"] = batter.rating
            df.at[index, "pitcher_rating_post"] = pitcher.rating

        return df


    def _get_or_create_player(
        self, store: RatingsStore, player_id: str
    ) -> PlayerRecord:
        if player_id not in store:
            store[player_id] = PlayerRecord(rating=self.initial_rating)
        return store[player_id]

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _save_ratings(self) -> None:
        """Write final batter and pitcher rating CSVs and print top-10 leaders."""
        min_instances = 100

        b_df = pd.DataFrame(
            {"rating": r.rating, "instances": r.instances}
            for r in self._batters.values()
        )
        b_df.index = pd.Index(self._batters.keys(), name="batter_id")
        b_path = f"batter_ratings_{self.name}.csv"
        b_df.sort_values("rating", ascending=False).to_csv(b_path)
        print(f"\nTop batters (≥{min_instances} PA) saved to {b_path}:")
        print(
            b_df.loc[b_df["instances"] >= min_instances]
            .sort_values("rating", ascending=False)
            .head(10)
        )

        p_df = pd.DataFrame(
            {"rating": r.rating, "instances": r.instances}
            for r in self._pitchers.values()
        )
        p_df.index = pd.Index(self._pitchers.keys(), name="pitcher_id")
        p_path = f"pitcher_ratings_{self.name}.csv"
        p_df.sort_values("rating", ascending=False).to_csv(p_path)
        print(f"\nTop pitchers (≥{min_instances} BF) saved to {p_path}:")
        print(
            p_df.loc[p_df["instances"] >= min_instances]
            .sort_values("rating", ascending=False)
            .head(10)
        )
