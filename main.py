from src.models.v1_0.model import Model1_0
from src.models.v1_1.model import Model1_1

from src.util.orchestrator import Orchestrator

def main():

    # TODO: Also should programtically download/create this parquet file
    data_file_path = './data/plays/plays.parquet'
    years = [y for y in range(1903, 2026)]
    models = [Model1_0, Model1_1]

    orchestrator = Orchestrator(data_file_path, years, models)
    orchestrator.run()


if __name__ == '__main__':
    main()