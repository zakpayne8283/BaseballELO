import pyarrow as pa

NEEDED_COLUMNS: dict = {
    'gametype': pa.string(),
    'gid': pa.string(),
    'inning': pa.uint8(),
    'top_bot': pa.uint8(), # This is tricky, maybe come back? 0 = top | 1 = bottom
    'batter': pa.string(),
    'pitcher': pa.string(),
    'outs_pre': pa.uint8(),
    'outs_post': pa.uint8(),
    'br1_pre': pa.string(),
    'br2_pre': pa.string(),
    'br3_pre': pa.string(),
    'br1_post': pa.string(),
    'br2_post': pa.string(),
    'br3_post': pa.string(),
    'runs': pa.uint8(),
    'pa': pa.bool_(),
    'single': pa.bool_(),
    'double': pa.bool_(),
    'triple': pa.bool_(),
    'hr': pa.bool_(),
    'sh': pa.bool_(),
    'hbp': pa.bool_(),
    'walk': pa.bool_(),
    'k': pa.bool_(),
    'xi': pa.bool_(),
    'roe': pa.bool_(),
    'iw': pa.bool_(),
    'date': pa.uint32()
}

OUTPUT_COLUMNS = [
    'gid',
    'batter',
    'pitcher',
    'pa_result',
    'batter_rating_pre',
    'batter_rating_post',
    'pitcher_rating_pre',
    'pitcher_rating_post',
    'batter_k',
    'pitcher_k',
    'date'
]