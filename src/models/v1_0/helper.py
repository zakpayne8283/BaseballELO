def get_pa_result(row):
    """
    Takes a row and returns the type of result:
    # Non-interactive results (e.g. ROE) are skipped
    `['1b', '2b', '3b', 'hr', 'hbp', 'walk', 'k', 'other_out']`
    """

    skip_outcomeos = ['sh', 'iw', 'xi', 'roe']

    for col in skip_outcomeos:
        if row[col] == 1:
            return None

    if row['single'] == 1:
        return '1b'
    
    if row['double'] == 1:
        return '2b'
    
    if row['triple'] == 1:
        return '3b'
    
    if row['hr'] == 1:
        return 'hr'
    
    if row['hbp'] == 1:
        return 'hbp'
    
    if row['walk'] == 1:
        return 'walk'
    
    if row['k'] == 1:
        return 'k'
    
    return 'other_out'