from datetime import datetime
import pandas as pd
import pyarrow as pa
import os
from typing import Type

import src.util.constants as constants
from src.util.common.base_model import BaseModel
import src.util.helpers as helpers
from src.util.stats import re, woba

class Orchestrator:

    def __init__(
            self,
            file_path: str,
            years: list[int],
            models: list[Type[BaseModel]]
            ):
        self.file_path = file_path
        self.years = years
        self.models = models

        print('Orchestrator Created')
        print('-'*20)


    def run(self):
        print('Starting run for configuration:')
        print(f'Data File Path: {self.file_path}')
        print(f'For Years: {self.years[0]} - {self.years[-1]}')
        print(f'Using Models: {", ".join([m.name for m in self.models])}')
        print('-'*20)

        # Load the data from the parquet file
        self.__load_data_from_file()

        # Apply additional data
        self.__apply_extra_columns()

        # Create/Apply wOBA data to table
        self.__create_woba_data()

        # Run the models against the table
        self.__run_models()

        # Save the model
        # Select only the columsn we want
        output_columns = self.df.loc[:, self.df.columns.str.endswith(tuple(constants.OUTPUT_COLUMNS))].columns
        self.df[output_columns].to_csv('elo_output.csv')


    def __load_data_from_file(self):
        print(f'Loading data from {self.file_path}...')

        print(f'Selecting only rows starting with year {min(self.years)}')

        self.df = pd.read_parquet(
            self.file_path,
            columns=list(constants.NEEDED_COLUMNS),
            schema=pa.schema(constants.NEEDED_COLUMNS.items()),
            filters=[
                ('date', '>=', min(self.years)*10000),
                ('gametype', '==', 'regular')
                ]
            )
        
        # Filter out non-PAs; for some reason pyarrow doesn't like this? something with the Schema...
        self.df = self.df[self.df['pa'] == True]

        # Cast the date field to an actual date. Same thing as above, Schema is weird...
        self.df['date'] = pd.to_datetime(self.df['date'], format='%Y%m%d')
        
        print('Sucessfully read data!')
        print('-'*20)


    def __apply_extra_columns(self):
        print('Applying Additional Columns...')
        
        print('Applying `pa_result`...')
        self.df['pa_result'] = self.df.apply(helpers.get_pa_result, axis=1)
        # Drop any missing pa_results
        self.df = self.df.dropna(subset=['pa_result'])

        print('Finished applying additional columns!')
        print('-'*20)


    def __create_woba_data(self):
        """
        # TODO: 
        - If the file already exists but a provided year isn't in it, just add it instead of deleting and recalculating everything
        - Come up with a better name for this, wOBA coeffs is kind of misleading I think
        """
        woba_coeffs_list = []
        woba_coeffs_file = './normalized_coeffs.csv'

        print('Starting wOBA Calculations')

        print('Checking if coefficients are already saved...')
        if (os.path.exists(woba_coeffs_file)):
            print('Already found!')
            print('-'*20)
            self.woba_coeffs_df = pd.read_csv(woba_coeffs_file, index_col=0)
            return
        
        print('Coefficients do not exist yet, creating...')
        print('-'*10)

        # Compute & Apply Run Expectancy Numbers
        for year, year_df in self.df.groupby(self.df['date'].dt.year):
            print(f'Processing wOBA for year *{year}*')

            print('Creating RE Matrix...')
            year_re = re.compute_run_expectancy_matrix(year_df)

            print('Applying RE Matrix Fields...')

            # The base/out state before the play beings
            print('Applying Base/Out State Pre...')
            year_df['re_state_pre'] = year_df.apply(re.get_base_out_state, pre_post='pre', axis=1)

            # Filter out any invalid states (only 0-23)
            # TODO: Maybe actually handle this as an error?
            year_df = year_df[year_df['re_state_pre'] != 24]

            # The base/out state after the play ends
            print('Applying Base/Out State Post...')
            year_df['re_state_post'] = year_df.apply(re.get_base_out_state, pre_post='post', axis=1)

            print('Applying RE for pre-state...')
            # The Run Expectancy before the play starts
            year_df['re_pre'] = year_df['re_state_pre'].map(year_re)
            year_df['re_post'] = year_df['re_state_post'].map(year_re).fillna(0) + year_df['runs']
            year_df['re_diff'] = year_df['re_post'] - year_df['re_pre']

            print('Calculating wOBA Coefficients...')
            year_woba_coeffs = woba.compute_woba_coefficients(year_df)
            print('Normalizing wOBA Coefficients...')
            year_norm_coeffs = woba.normalize_woba_coeffs(year_woba_coeffs)

            print("Calculating League Average wOBA value per PA...")# Get the league's average 
            pa_result_proportions = year_df['pa_result'].value_counts(normalize=True).to_dict()
            league_average = sum(
                year_norm_coeffs[k] * v for k, v in pa_result_proportions.items()
            )

            # Add year and avg; add them to our list for conversion to DF/CSV later
            year_norm_coeffs['year'] = year
            year_norm_coeffs['average'] = league_average
            woba_coeffs_list.append(year_norm_coeffs)

            print(f'Finished processing wOBA for {year}!')
            print('-'*10)
            
        print('Savings coefficients data...')
        self.woba_coeffs_df = pd.DataFrame(woba_coeffs_list)
        self.woba_coeffs_df.to_csv(woba_coeffs_file)
        print('Finished creating coefficients data!')
        print('-'*20)


    def __run_models(self):
        print('Starting to run models...')

        print('Creating the models...')
        print('-'*10)
        models = [m() for m in self.models]

        print('Applying all extra columns for each model...')
        print('-'*10)
        for model in models:
            model.add_additional_columns(self.df)

        print('Computing the ELO in each model...')
        print('-'*10)
        for model in models:
            print(f'Beginning {model.name} run...')
            self.df = model.run(self.df, self.woba_coeffs_df)
            print('='*20)
            print('-'*10)

        print('Finished running model!')
        print('-'*20)