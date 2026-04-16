import pandas as pd
import pyarrow.csv as pa_csv
import pyarrow.compute as pa_comp
import os

from ...util.retrosheet import Retrosheet
from ...util.run_expectancy import create_run_expectancy_dataframes
from ...util.woba import create_woba_dataframes, normalize_woba_coeffs
import src.models.v1_0.helper as helper

def main():

    k = 20
    initial_rating = 1500

    years = [year for year in range(1947, 2026)]

    needed_columns = [
        'gametype',
        'gid',
        'inning',
        'top_bot',
        'batter',
        'pitcher',
        'outs_pre',
        'outs_post',
        'br1_pre',
        'br2_pre',
        'br3_pre',
        'br1_post',
        'br2_post',
        'br3_post',
        'runs',
        'single',
        'double',
        'triple',
        'hr',
        'sh',
        'hbp',
        'walk',
        'k',
        'xi',
        'roe',
    ]
    
    # Download Retrosheet Data
    rs = Retrosheet()
    rs.fetch_retrosheet_data_by_years()

    # Load the CSV with Arrow
    convert_options = pa_csv.ConvertOptions(include_columns=needed_columns)
    table = pa_csv.read_csv(os.path.join(rs.plays_dir, 'plays.csv'), convert_options=convert_options)

    # Rating Dicts
    batters = {}
    pitchers = {}

    # Process year-by-year
    # TODO: Also make season-only ELOs
    for year in years:
        print('-'*15)
        print(f'Processing {year}...')
        print('-'*15)

        # Filter by year and gametype
        sliced = pa_comp.utf8_slice_codeunits(table['gid'], start=3, stop=7)
        mask = pa_comp.and_(
            pa_comp.equal(sliced, str(year)),
            pa_comp.equal(table['gametype'], 'regular')
        )
        filtered_table = table.filter(mask)

        # Load the DF
        df = filtered_table.to_pandas()
        # Get the plate appearance result
        df['pa_result'] = df.apply(helper.get_pa_result, axis=1)
        df = df.loc[df['pa_result'].notna()]    # Only valid values

        # Filter only the needed fields for run expectancy
        df, re_matrix = create_run_expectancy_dataframes(df)

        # Modify data for processing and get/normalize wOBA coefficients, outcome makeups, and league average
        df, woba_coeffs = create_woba_dataframes(df, re_matrix)
        outcomes, league_average = normalize_woba_coeffs(df, woba_coeffs)

        # Add new columns
        df['batter_rating_pre'] = None
        df['batter_rating_post'] = None
        df['pitcher_rating_pre'] = None
        df['pitcher_rating_post'] = None

        # For each plate apperance in a year
        for index, row in df.iterrows():
            batter_id = row['batter']
            pitcher_id = row['pitcher']

            # Get the batter rating and instances (ABs)
            batter = {}
            if batter_id in batters:
                batter = batters[batter_id]
            else:
                batter = {
                    'rating': initial_rating,
                    'instances': 0
                }

            # Get the pitcher rating and instances (BFs)
            pitcher = {}
            if pitcher_id in pitchers:
                pitcher = pitchers[pitcher_id]
            else:
                pitcher = {
                    'rating': initial_rating,
                    'instances': 0
                }

            df.at[index, 'batter_rating_pre']  = batter['rating']
            df.at[index, 'pitcher_rating_pre'] = pitcher['rating']

            elo_change = 1 / (1 + 10 ** ((pitcher['rating'] - batter['rating']) / 400))
            expected = league_average + (elo_change - 0.5) * 2 * league_average

            actual = outcomes.get(row['pa_result'])
            
            # Volitity. Also try 40 (fewer PAs) or 16 (more PAs)
            k = 20

            # Batter Ratings
            batter['rating'] = batter['rating'] + (k * (actual - expected))
            batter['instances'] += 1
            # Save
            batters[batter_id] = batter
            df.at[index, 'batter_rating_post']  = batter['rating']

            # Pitcher Ratings
            pitcher['rating'] = pitcher['rating'] + (k * ((1 - actual) - (1 - expected)))
            pitcher['instances'] += 1
            # Save
            pitchers[pitcher_id] = pitcher
            df.at[index, 'pitcher_rating_post'] = pitcher['rating']

        # Create/Append CSV out
        df.to_csv('matchups.csv', mode='a', header=(not os.path.exists('matchups.csv')), index=False)

        print(f'Processed {year}')

    b_ratings_df = pd.DataFrame.from_dict(batters, orient='index')
    b_ratings_df.index.name = 'batter_id'
    b_ratings_df.reset_index()
    b_ratings_df.sort_values('rating', ascending=False).to_csv('batter_ratings_v1.csv')
    print(b_ratings_df.loc[b_ratings_df['instances'].ge(100)].sort_values('rating', ascending=False).head())

    p_ratings_df = pd.DataFrame.from_dict(pitchers, orient='index')
    p_ratings_df.index.name = 'pitcher_id'
    p_ratings_df.reset_index()
    p_ratings_df.sort_values('rating', ascending=False).to_csv('pitcher_ratings_v1.csv')
    print(p_ratings_df.loc[p_ratings_df['instances'].ge(100)].sort_values('rating', ascending=False).head())

if __name__ == '__main__':
    main()