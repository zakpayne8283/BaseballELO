import pandas as pd


def normalize_woba_coeffs(woba_coeffs):
    """
    Normalizes the wOBA values on a 0-1 scale
    """
    w_min = min(woba_coeffs.values())
    w_max = max(woba_coeffs.values())
    normal_coeffs = {
            k: (v - w_min) / (w_max - w_min) for k, v in woba_coeffs.items()
        }

    return normal_coeffs


def compute_woba_coefficients(df: pd.DataFrame) -> dict[str, float]:
    """
    Computes wOBA coefficients as mean RE diff per PA outcome.
    Requires re_diff and pa_result columns to already be present.
    """
    for column in ['re_diff', 'pa_result']:
        if column not in df:
            raise ValueError(f'Cannot compute wOBA coefficients: missing column {column}')

    return df.groupby('pa_result')['re_diff'].mean().to_dict()