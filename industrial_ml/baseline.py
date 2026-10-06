"""Remaining-useful-life baseline for C-MAPSS FD001: ``uv run python -m industrial_ml.baseline``.

This is the notebook a previous team handed over, turned into a script. The client
was shown the validation numbers it prints.
"""

from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from utils import settings

from .data import SENSORS, SETTINGS, load_split

FEATURES = [*SETTINGS, *SENSORS]


def add_rul(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rul"] = out.groupby("unit")["cycle"].transform("max") - out["cycle"]
    return out


def train_validation_split(
    df: pd.DataFrame, validation_share: float = 0.2, seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return train_test_split(df, test_size=validation_share, random_state=seed, shuffle=True)


def main() -> None:
    seed = int(settings.industrial_ml.RANDOM_SEED)
    data = add_rul(load_split("train"))
    data[FEATURES] = StandardScaler().fit_transform(data[FEATURES])

    train, validation = train_validation_split(data, seed=seed)
    model = RandomForestRegressor(n_estimators=200, n_jobs=-1, random_state=seed)
    model.fit(train[FEATURES], train["rul"])

    predicted = model.predict(validation[FEATURES])
    rmse = float(np.sqrt(mean_squared_error(validation["rul"], predicted)))
    print(f"validation rows: {len(validation)}")
    print(f"R2:   {r2_score(validation['rul'], predicted):.3f}")
    print(f"RMSE: {rmse:.1f} cycles")


if __name__ == "__main__":
    main()
