def get_pa_result(row):
    """
    Takes a row and returns the type of result:
    # Non-interactive results (e.g. ROE) are skipped
    `['1b', '2b', '3b', 'hr', 'hbp', 'walk', 'k', 'other_out']`
    """
    if row['single'] == 1:
        return '1b'
    
    if row['double'] == 1:
        return '2b'
    
    if row['triple'] == 1:
        return '3b'
    
    if row['hr'] == 1:
        return 'hr'
    
    if row['sh'] == 1:
        return None
    
    # Trying this as an out instead
    #
    # As its own thing, it's an out plus a run went in. If a RP
    # comes in and gets an out, but an unearned-run scores, that's not really on him
    #
    # if row['sf'] == 1:
    #     return 'sf'
    
    if row['hbp'] == 1:
        return 'hbp'
    
    if row['walk'] == 1:
        return 'walk'
    
    if row['k'] == 1:
        return 'k'
    
    if row['xi'] == 1:
        return None
    
    if row['roe'] == 1:
        return None
    
    # Trying this as an out instead
    #
    # As its own thing, it's an out but a runner was on base. A pitcher would have
    # had an out against the batter, but a fielder "interfered"
    #
    # if row['fc'] == 1:
    #     return 'fc'
    
    return 'other_out'