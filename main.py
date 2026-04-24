from src.models.v1_0.model import Model1_0

def main():

    years = [y for y in range(1947, 2026)]

    model = Model1_0()
    model.run(years)

if __name__ == '__main__':
    main()