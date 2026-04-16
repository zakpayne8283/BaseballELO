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

    def zip_already_exists(self, year=''):
        return os.path.exists(os.path.join(self.zips_dir, f'{year}plays.zip'))

    def csv_already_exists(self, year=''):
        return os.path.exists(os.path.join(self.plays_dir, f'{year}plays.csv'))

    def download_retrosheet_data(self, year=''):
        """
        For a given {year}, download the zip file. If year is blank, downloads the plays.zip
        """
        zip_file_path = os.path.join(self.zips_dir, f'{year}plays.zip')

        try:
            print(f'Downloading retrosheet plays data for {'' if year is '' else year}...')
            response = requests.get(self.plays_url_base.replace('[YEAR]', str(year)))
            response.raise_for_status()

            with open(zip_file_path, 'wb') as file:
                file.write(response.content)

            print(f'{year} downloaded.')

        except Exception as e:
            print(e)

    def extract_retrosheet_data(self, year=''):
        """
        For a given {year}, extract the zip file. If year is blank, extracts the plays.zip 
        """
        zip_file_path = os.path.join(self.zips_dir, f'{year}plays.zip')

        print(f'Extracting {year}...')

        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(self.plays_dir)

        print(f'Extracted {year} plays zip')

    def fetch_retrosheet_data_by_years(self, years=None):
        self.create_directories()

        if years is None:
            if (self.zip_already_exists()):
                print(f'ZIP for plays already found!')
            else:
                self.download_retrosheet_data()

            if (self.csv_already_exists()):
                print(f'CSV for plays already found!')
            else:
                self.extract_retrosheet_data()

            return

        for year in years:

            if (self.zip_already_exists(year)):
                print(f'ZIP for {year} already found!')
            else:
                self.download_retrosheet_data(year=year)

            if (self.csv_already_exists(year)):
                print(f'CSV for {year} already found!')
            else:
                self.extract_retrosheet_data(year=year)

    def fetch_retrosheet_all_parsed_events(self):
        self.create_directories()

        if self.zip_already_exists():
            print('Parsed ZIP file already found!')
        else:
            self.download_retrosheet_data()


        if self.csv_already_exists():
            print('Parsed CSV file already found!')
        else:
            self.extract_retrosheet_data()
