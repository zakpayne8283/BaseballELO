import numpy as np
import pandas as pd
import os
import requests
import zipfile

class Retrosheet:

    plays_url_base = 'https://www.retrosheet.org/downloads/plays/[YEAR]plays.zip'

    plays_dir = os.path.join('data', 'plays')
    zips_dir = os.path.join('data', 'zips')

    def create_directories(self):
        os.makedirs(self.plays_dir, exist_ok=True)
        os.makedirs(self.zips_dir, exist_ok=True)

    def download_retrosheet_data_by_year(self, year):
        """
        For a given {year}, download the zip file
        """
        zip_file_path = os.path.join(self.zips_dir, f'{year}plays.zip')

        try:
            print(f'Downloading retrosheet plays data for {year}...')
            response = requests.get(self.plays_url_base.replace('[YEAR]', str(year)))
            response.raise_for_status()

            with open(zip_file_path, 'wb') as file:
                file.write(response.content)

            print(f'{year} downloaded.')

        except Exception as e:
            print(e)

    def extract_retrosheet_data_by_year(self, year):
        """
        For a given {year}, extract the zip file
        """
        zip_file_path = os.path.join(self.zips_dir, f'{year}plays.zip')

        print(f'Extracting {year}...')

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(self.plays_dir)

        print(f'Extracted {year} plays zip')

    def fetch_retrosheet_data_by_years(self, years):
        self.create_directories()

        for year in years:
            self.download_retrosheet_data_by_year(year)
            self.extract_retrosheet_data_by_year(year)
