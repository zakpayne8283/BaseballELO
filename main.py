from src.models.v1_0.model import Model1_0
from src.models.v1_1.model import Model1_1

def main():

    years = [y for y in range(1903, 2026)]

    # Model v1.0
    # model = Model1_0()
    # model.run(years)

    # Model v1.1
    model = Model1_1()
    model.run(years)



if __name__ == '__main__':
    main()