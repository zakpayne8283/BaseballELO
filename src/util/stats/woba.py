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


def apply_woba_columns(df: pd.DataFrame, re_matrix: pd.Series) -> pd.DataFrame:
    """
    Adds re_pre, re_post, and re_diff columns to df.
    Requires re_state_pre and re_state_post to already be present.
    """
    for column in ['re_state_pre', 're_state_post']:
        if column not in df:
            raise ValueError(f'Cannot apply wOBA columns: missing column {column}')

    if (df['re_state_post'] > 24).any():
        raise ValueError(f'Cannot apply wOBA columns: invalid re_state_post values\n{df[df["re_state_post"] > 24]}')

    df = df.copy()
    df['re_pre']  = df['re_state_pre'].map(re_matrix)
    df['re_post'] = df['re_state_post'].map(re_matrix).fillna(0) + df['runs']
    df['re_diff'] = df['re_post'] - df['re_pre']

    return df


def compute_woba_coefficients(df: pd.DataFrame) -> dict[str, float]:
    """
    Computes wOBA coefficients as mean RE diff per PA outcome.
    Requires re_diff and pa_result columns to already be present.
    """
    for column in ['re_diff', 'pa_result']:
        if column not in df:
            raise ValueError(f'Cannot compute wOBA coefficients: missing column {column}')

    return df.groupby('pa_result')['re_diff'].mean().to_dict()