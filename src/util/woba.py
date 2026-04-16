
def create_woba_dataframes(df_re, re_matrix):
    """
    Calculate the wOBA coefficients for a year given two dataframes:
    df_re: dataframe used to calculate run expectancy matrix
    re_matrix: dataframe of run expectancy matrix for that year
    """
    
    for column in ['re_state_pre', 're_state_post']:
        if not column in df_re:
            raise Exception(f'Cannot calculate wOBA coefficients: missing column {column}')
        
    if len(df_re[df_re['re_state_post'] > 24]) > 0:
        print(df_re[df_re['re_state_post'] > 24])
        raise Exception(f'Error: invalid RE states!')

    df_re['re_pre']  = df_re.apply(lambda row: re_matrix[row['re_state_pre']], axis=1)
    df_re['re_post'] = df_re.apply(lambda row: 0 + row['runs'] if row['re_state_post'] == 24 else re_matrix[row['re_state_post']] + row['runs'], axis=1)
    df_re['re_diff'] = df_re['re_post'] - df_re['re_pre']
    return df_re, df_re.groupby('pa_result')['re_diff'].mean().to_dict()

def normalize_woba_coeffs(df_re, woba_coeffs):
    w_min = min(woba_coeffs.values())
    w_max = max(woba_coeffs.values())
    outcomes = {
            k: (v - w_min) / (w_max - w_min)
            for k, v in woba_coeffs.items()
        }

    lg_avg_pa_mix = df_re['pa_result'].value_counts(normalize=True).to_dict()

    league_average = sum(
        outcomes[k] * v for k, v in lg_avg_pa_mix.items()
    )

    return outcomes, league_average