import logging

import numpy as np
from statsmodels.tsa.stattools import adfuller  # type: ignore[import-untyped]
from statsmodels.tsa.vector_ar.vecm import coint_johansen  # type: ignore[import-untyped]

from staarb.core.types import HedgeRatio, SingleHedgeRatio

logger = logging.getLogger(__name__)


class JohansenCointegrationModel:
    _hedge_ratio: HedgeRatio | None
    _num_assets: int | None
    _half_life_window: int | None
    _vec_hedge_ratio: np.ndarray

    def __init__(
        self,
        hedge_ratio: HedgeRatio | None = None,
        num_assets: int | None = None,
        half_life_window: int | None = None,
    ):
        self._hedge_ratio = hedge_ratio
        self._num_assets = num_assets
        self._half_life_window = half_life_window

    def get_lookback_window(self):
        return self._half_life_window

    def get_hedge_ratio(self):
        if self._hedge_ratio is None:
            msg = "Hedge ratio is not fitted yet."
            raise ValueError(msg)
        return self._hedge_ratio.copy()

    def __half_life__(self, ts: np.ndarray) -> int:
        """
        Calculate the half life of the time series.

        Args:
            ts: np.ndarray 1D array

        """
        delta_ts = np.diff(ts)
        ts_lagged = ts[:-1]
        regress_results = np.polyfit(ts_lagged, delta_ts, 1)
        return round(-np.log(2) / regress_results[0])

    def analyze(self, data: np.ndarray):
        """
        Analyze the cointegration of the time series.

        Args:
            data: np.ndarray 2D array with shape (num_assets, num_samples)

        """
        johansen_test_res = coint_johansen(data.T, det_order=0, k_ar_diff=1)
        trace_stat = johansen_test_res.lr1[0]
        trace_crit_vals = johansen_test_res.cvt[0, :]
        eig_stat = johansen_test_res.lr2[0]
        eig_crit_vals = johansen_test_res.cvm[0, :]
        hedge_ratio = self.__normalize_hedge_ratio__(johansen_test_res.evec[:, 0])
        spread = np.dot(hedge_ratio, data)
        adf_res = adfuller(spread)
        adf_p_value = adf_res[1]
        return (
            trace_stat,
            trace_crit_vals,
            eig_stat,
            eig_crit_vals,
            adf_p_value,
            spread,
        )

    def __normalize_hedge_ratio__(self, hedge_ratio: np.ndarray):
        # Normalize hedge ratio so that the first component is 1
        return hedge_ratio / hedge_ratio[0]

    def fit(self, data: np.ndarray, symbols: list[str]):
        """
        Fit the hedge ratio using the Johansen test.

        Args:
            data: np.ndarray 2D array with shape (num_assets, num_samples)
            symbols: list of asset symbols w.r.t. the data rows

        """
        _hedge_ratio = coint_johansen(data.T, det_order=0, k_ar_diff=1).evec[:, 0]
        _hedge_ratio = self.__normalize_hedge_ratio__(_hedge_ratio)
        self._num_assets = data.shape[0]
        spread = np.dot(_hedge_ratio, data)
        self._hedge_ratio = [
            SingleHedgeRatio(symbol=symbol, hedge_ratio=hedge_ratio)
            for symbol, hedge_ratio in zip(symbols, _hedge_ratio, strict=True)
        ]
        self._half_life_window = self.__half_life__(spread)

    def estimate(self, data: np.ndarray) -> float:
        """
        Estimate the z-score of the spread.

        Args:
            data: np.ndarray 2D array with shape (num_assets, num_samples)

        Returns:
            float: z-score of the spread

        """
        if self._hedge_ratio is None:
            msg = "Hedge ratio is not fitted yet."
            raise ValueError(msg)
        if self._half_life_window is None:
            msg = "Half life window is not fitted yet."
            raise ValueError(msg)
        if not hasattr(self, "_vec_hedge_ratio"):
            self._vec_hedge_ratio = np.array(
                [single_hedge_ratio.hedge_ratio for single_hedge_ratio in self._hedge_ratio]
            )
        spread = np.dot(self._vec_hedge_ratio, data)[-self._half_life_window :]

        ma = np.mean(spread)
        mstd = np.std(spread)
        return (spread[-1] - ma) / mstd
