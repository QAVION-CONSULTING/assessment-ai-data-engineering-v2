import numpy as np
import pandas as pd

from industrial_ml.baseline import FEATURES, add_rul, train_validation_split


def _fleet(units: int = 20, cycles: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    rows = [
        {"unit": u, "cycle": c, **{f: rng.normal() for f in FEATURES}}
        for u in range(1, units + 1)
        for c in range(1, cycles + 1)
    ]
    return pd.DataFrame(rows)


def test_rul_counts_down_to_zero_per_unit():
    df = add_rul(_fleet(units=2, cycles=5))
    assert df.groupby("unit")["rul"].min().tolist() == [0, 0]
    assert df.groupby("unit")["rul"].max().tolist() == [4, 4]


def test_no_engine_appears_in_train_and_validation():
    train, validation = train_validation_split(add_rul(_fleet()))
    assert set(train["unit"]).isdisjoint(set(validation["unit"]))
    assert len(train) + len(validation) == 20 * 50
