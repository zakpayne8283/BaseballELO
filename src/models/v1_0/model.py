from ...util.retrosheet import Retrosheet

def main():
    rs = Retrosheet()
    rs.fetch_retrosheet_data_by_years([2024, 2025])

if __name__ == '__main__':
    main()