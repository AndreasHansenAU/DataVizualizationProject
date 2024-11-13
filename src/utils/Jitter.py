import numpy as np
import pandas as pd
from copy import deepcopy
np.random.seed(42)

def add_jitter_coordinates(df, latitude_col, longitude_col, latitude_jitter_col, longitude_jitter_col, jitter_amount=0.0005):
    np.random.seed(42)
    df = deepcopy(df)
    # Find rows where the same longitude and latitude appear more than once for the same year
    duplicate_mask = df.duplicated(subset=[latitude_col, longitude_col], keep=False)
    
    # Add jitter to only the duplicate coordinates
    df.loc[duplicate_mask, latitude_jitter_col] = df.loc[duplicate_mask, latitude_col] + np.random.uniform(-jitter_amount, jitter_amount, df[duplicate_mask].shape[0])
    df.loc[duplicate_mask, longitude_jitter_col] = df.loc[duplicate_mask, longitude_col] + np.random.uniform(-jitter_amount, jitter_amount, df[duplicate_mask].shape[0])

    # For non-duplicates, just copy the original latitude and longitude values
    df[latitude_jitter_col].fillna(df[latitude_col], inplace=True)
    df[longitude_jitter_col].fillna(df[longitude_col], inplace=True)

    return df


def add_jitter_beeswarm(df, jitter_amount=0.2):
    nrows = df.shape[0]
    df['beeswarm_jitter'] = np.random.uniform(-jitter_amount, jitter_amount, size=nrows)
    return df