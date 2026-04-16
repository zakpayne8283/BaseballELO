import pandas as pd

def get_base_out_state(row, pre_post):
    """
    `pre_post` is a flag to determine using the retrosheet fields `br1_pre` or `br1_post` (or similar)
    `row` is expected to be a dataframe row
    """

    bases = ''
    
    # NOTE `is None` used here because it's using pyarrow
    # TODO: Fix that
    bases += '-' if row[f'br1_{pre_post}'] == '' else '1'
    bases += '-' if row[f'br2_{pre_post}'] == '' else '2'
    bases += '-' if row[f'br3_{pre_post}'] == '' else '3'
    
    if bases == '---':
        return 0 + (8 * row[f'outs_{pre_post}'])
    elif bases == '1--':
        return 1 + (8 * row[f'outs_{pre_post}'])
    elif bases == '-2-':
        return 2 + (8 * row[f'outs_{pre_post}'])
    elif bases == '--3':
        return 3 + (8 * row[f'outs_{pre_post}'])
    elif bases == '12-':
        return 4 + (8 * row[f'outs_{pre_post}'])
    elif bases == '1-3':
        return 5 + (8 * row[f'outs_{pre_post}'])
    elif bases == '-23':
        return 6 + (8 * row[f'outs_{pre_post}'])
    elif bases == '123':
        temp = 7 + (8 * row[f'outs_{pre_post}'])
        if temp >= 24:
            val = row[f'br1_{pre_post}']
            print(type(val), repr(val))
        return temp

    return 'XXX'

def create_run_expectancy_dataframes(df_in):
    df = df_in[[
            'gid',
            'inning',
            'top_bot',
            'batter',
            'pitcher',
            'pa_result',
            'outs_pre',
            'outs_post',
            'br1_pre',
            'br2_pre',
            'br3_pre',
            'br1_post',
            'br2_post',
            'br3_post',
            'runs'
        ]]
    
    # NOTE: Consider that these should generally be sorted, but be mindful that they may not be
    df['inning_id'] = df.apply(lambda x: f'{x['gid']}_{x['inning']}_{x['top_bot']}', axis=1)
    df = df.drop(columns=['gid', 'inning', 'top_bot'])

    # Get pre and post base-out state code
    df['re_state_pre']  = df.apply(get_base_out_state, pre_post='pre', axis=1)
    df = df[df['re_state_pre'] != 24]
    df['re_state_post'] = df.apply(get_base_out_state, pre_post='post', axis=1)

    # For each play calculate how many runs are remaining in the inning
    df['runs_remaining_in_inning'] = (
        df.groupby('inning_id')['runs']
            .transform(lambda x: x[::-1].cumsum()[::-1])
    )

    # Create an average number of runs remaining in the inning
    # based on the base out state
    re_matrix = (
        df.groupby('re_state_pre')['runs_remaining_in_inning']
            .mean()
            .round(3)
    )

    df = df.drop(columns=[
        'br1_pre',
        'br2_pre',
        'br3_pre',
        'br1_post',
        'br2_post',
        'br3_post',
        'inning_id',
        'outs_pre',
        'outs_post',
        'runs_remaining_in_inning'
        ])

    return df, re_matrix