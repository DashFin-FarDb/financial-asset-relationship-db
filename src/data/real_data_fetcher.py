"""Fetch real financial asset market data from sources such as Yahoo Finance."""

import json
import logging
import math
import threading
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, cast

from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.reconciliation_engine import RebuildCancelledError
from src.models.financial_models import (
    Asset,
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)
from src.observability.events import ObservabilityEvent
from src.observability.logger import log_event

logger = logging.getLogger(__name__)
UTC = timezone.utc


class FetchCancelledError(RebuildCancelledError):
    """Raised when data fetching is aborted via a cancellation signal."""


_YFINANCE_MODULE = None
_FETCHED_ASSET_LOG_MESSAGE = "Fetched %s: %s at $%.2f"


def _get_yfinance() -> Any:
    """
    Lazily import and cache the `yfinance` module for optional live-data features.

    Returns:
        The imported `yfinance` module.

    Raises:
        RuntimeError: If `yfinance` is not installed in the environment.
        RuntimeError: If `yfinance` or one of its dependencies fails to import.
        RuntimeError: If an unexpected error occurs during import.
    """
    global _YFINANCE_MODULE

    if _YFINANCE_MODULE is not None:
        return _YFINANCE_MODULE

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        if exc.name != "yfinance":
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="yfinance_dependency_missing",
                    message="Failed to import yfinance due to a missing dependency.",
                    metadata={"error": type(exc).__name__},
                ),
            )
            raise RuntimeError(
                "yfinance could not be imported in the current environment. "
                "Check its installation and dependency compatibility."
            ) from exc
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="yfinance_unavailable",
                message=(
                    "Failed to import yfinance. Optional live-data features are unavailable. "
                    "Install it using: pip install yfinance"
                ),
            ),
        )
        raise RuntimeError(
            "yfinance is unavailable in the current environment. Install it using: pip install yfinance"
        ) from exc
    except ImportError as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="yfinance_import_error",
                message="Failed to import yfinance due to an import/dependency problem.",
                metadata={"error": type(exc).__name__},
            ),
        )
        raise RuntimeError(
            "yfinance could not be imported in the current environment. "
            "Check its installation and dependency compatibility."
        ) from exc
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            ObservabilityEvent(
                event="yfinance_unexpected_error",
                message=f"Unexpected error while importing yfinance: {type(exc).__name__}",
                metadata={"error": type(exc).__name__},
            ),
        )
        raise RuntimeError(
            "Unexpected error while loading yfinance. Check the environment and dependency state."
        ) from exc

    _YFINANCE_MODULE = yf
    return _YFINANCE_MODULE


def __getattr__(name: str) -> Any:
    """
    Module-level lazy attribute access for backward-compatible ``yf`` access.

    Exposes ``yf`` as a lazily imported alias for the yfinance module so patch
    targets like ``src.data.real_data_fetcher.yf.Ticker`` continue to work
    without eager import at module load time.

    Args:
        name: Attribute name being accessed on this module.

    Returns:
        The yfinance module when ``name == "yf"``.

    Raises:
        RuntimeError: If ``name == "yf"`` and yfinance cannot be imported.
        AttributeError: For any attribute name other than ``"yf"``.
    """
    if name == "yf":
        return _get_yfinance()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class RealDataFetcher:
    """
    Fetch real financial data from Yahoo Finance with optional fallback behavior.

    Yahoo Finance fetching requires the optional ``yfinance`` package. If that
    dependency is missing, methods that attempt live fetches will raise a
    RuntimeError. Higher-level helpers such as ``create_real_database()`` catch
    failures and can fall back to cached or sample data instead.

    The fetcher also supports offline operation by disabling network access and
    using cached or sample data only.
    """

    def __init__(
        self,
        *,
        cache_path: str | None = None,
        fallback_factory: Callable[[], AssetRelationshipGraph] | None = None,
        enable_network: bool = True,
    ) -> None:
        """
        Configure the fetcher.

        Args:
            cache_path: Optional path to a JSON cache file used to load or
                persist a previously built AssetRelationshipGraph.
            fallback_factory: Optional callable producing an
                AssetRelationshipGraph to use when network fetching is disabled
                or live fetching fails. If omitted, built-in sample data is
                used.
            enable_network: When False, disables network access and causes
                ``create_real_database()`` to return fallback data instead of
                attempting live fetches.
        """
        self.cache_path = Path(cache_path) if cache_path else None
        self.fallback_factory = fallback_factory
        self.enable_network = enable_network

    def create_real_database(self) -> AssetRelationshipGraph:
        """
        Create an asset relationship graph using cached data, live Yahoo Finance data, or a fallback/sample dataset.

        If a configured cache exists it is used; otherwise, when network fetching is enabled
        a live fetch is attempted and the resulting graph is persisted to cache if configured.
        If network fetching is disabled or the live fetch fails, the configured fallback or
        the built-in sample dataset is returned.

        Returns:
            AssetRelationshipGraph: A graph populated from cache, live data, or fallback/sample data.
        """
        graph, _ = self.create_real_database_with_source()
        return graph

    def _try_load_from_cache(self) -> "AssetRelationshipGraph | None":
        """Attempt to load the asset relationship graph from cache.

        Returns:
            AssetRelationshipGraph | None: The cached graph if successful, else None.
        """
        if not self.cache_path or not self.cache_path.exists():
            return None
        try:
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="graph_cache_load_attempt",
                    message=f"Loading asset graph from cache at {self.cache_path}",
                    metadata={"cache_path": str(self.cache_path)},
                ),
            )
            return _load_from_cache(self.cache_path)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_cache_load_failed",
                    message=f"Failed to load cached dataset: {type(exc).__name__}; proceeding with standard fetch",
                    metadata={"error": type(exc).__name__},
                ),
            )
            return None

    def _try_live_fetch(
        self, cancel_event: threading.Event | None = None
    ) -> tuple["AssetRelationshipGraph", str] | None:
        """Attempt to fetch live data, build the graph, and optionally persist it.

        Args:
            cancel_event: Optional event to signal cancellation.

        Returns:
            tuple[AssetRelationshipGraph, str] | None: A tuple containing the graph and source tag, or None if failed.
        """
        try:
            assets, events, source = self._perform_live_raw_fetch(cancel_event)
            if source == "sample":
                return self._fallback(), "sample"

            from src.config.settings import get_settings

            settings = get_settings()
            graph = AssetRelationshipGraph(
                same_sector_strength=settings.same_sector_strength,
                corporate_bond_strength=settings.corporate_bond_strength,
            )
            for asset in assets:
                graph.add_asset(asset)

            for event in events:
                graph.add_regulatory_event(event)

            graph.build_relationships()

            if self.cache_path:
                self._persist_cache(graph)

            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="graph_live_fetch_completed",
                    message=(
                        f"Real database created with {len(graph.assets)} assets and "
                        f"{sum(len(rels) for rels in graph.relationships.values())} relationships"
                    ),
                    metadata={
                        "asset_count": len(graph.assets),
                        "relationship_count": sum(len(rels) for rels in graph.relationships.values()),
                    },
                ),
            )
            return graph, "real_data"

        except FetchCancelledError:
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="graph_live_fetch_failed",
                    message=f"Failed to create real database: {type(exc).__name__}",
                    metadata={"error": type(exc).__name__},
                ),
            )
            return None

    def create_real_database_with_source(
        self,
        cancel_event: threading.Event | None = None,
    ) -> tuple[AssetRelationshipGraph, str]:
        """
        Create an asset relationship graph and identify its source (cache, real_data, or sample).

        This is the provenance-safe version of create_real_database. It returns both the
        constructed graph and a source tag identifying where the data originated.

        Args:
            cancel_event: Optional event to signal cancellation.

        Returns:
            tuple[AssetRelationshipGraph, str]: A tuple containing the graph and a source
                tag: "cache", "real_data" (for live fetches), or "sample".
        """
        cached_graph = self._try_load_from_cache()
        if cached_graph is not None:
            return cached_graph, "cache"

        if not self.enable_network:
            log_event(
                logger,
                logging.INFO,
                ObservabilityEvent(
                    event="graph_network_fetching_disabled",
                    message="Network fetching disabled. Using fallback dataset if available.",
                ),
            )
            return self._fallback(), "sample"

        log_event(
            logger,
            logging.INFO,
            ObservabilityEvent(
                event="graph_live_fetch_initiated",
                message="Creating database with real financial data from Yahoo Finance",
            ),
        )

        live_result = self._try_live_fetch(cancel_event)
        if live_result is not None:
            return live_result

        log_event(
            logger,
            logging.WARNING,
            ObservabilityEvent(
                event="graph_fetch_fallback_engaged",
                message="Falling back to sample data due to real data fetch failure",
            ),
        )
        return self._fallback(), "sample"

    def fetch_raw_data(self) -> tuple[list[Asset], list[RegulatoryEvent]]:
        """
        Fetch raw asset and regulatory event data without building a graph.

        Returns:
            tuple[list[Asset], list[RegulatoryEvent]]: A tuple containing the list of
                fetched assets and the list of regulatory events.
        """
        assets, events, _ = self.fetch_raw_data_with_source()
        return assets, events

    def fetch_raw_data_with_source(
        self,
        cancel_event: threading.Event | None = None,
    ) -> tuple[list[Asset], list[RegulatoryEvent], str]:
        """
        Fetch raw asset and regulatory event data and identify its source.

        Args:
            cancel_event: Optional event to signal cancellation.

        Returns:
            tuple[list[Asset], list[RegulatoryEvent], str]: A tuple containing the
                fetched assets, the regulatory events, and a source tag ("real_data" or "sample").
        """
        if not self.enable_network:
            fb = self._fallback()
            return list(fb.assets.values()), fb.regulatory_events, "sample"

        try:
            return self._perform_live_raw_fetch(cancel_event)
        except FetchCancelledError:
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="graph_raw_fetch_failed",
                    message=f"Failed to fetch raw data: {type(exc).__name__}",
                    metadata={"error": type(exc).__name__},
                ),
            )
            raise

    def _perform_live_raw_fetch(
        self,
        cancel_event: threading.Event | None,
    ) -> tuple[list[Asset], list[RegulatoryEvent], str]:
        """Perform the actual live fetch sequence."""
        self._check_cancelled(cancel_event, "before starting")
        equities = self._fetch_equity_data(cancel_event)

        self._check_cancelled(cancel_event, "after equities")
        bonds = self._fetch_bond_data(cancel_event)

        self._check_cancelled(cancel_event, "after bonds")
        commodities = self._fetch_commodity_data(cancel_event)

        self._check_cancelled(cancel_event, "after commodities")
        currencies = self._fetch_currency_data(cancel_event)

        self._check_cancelled(cancel_event, "after currencies")
        events = self._create_regulatory_events()

        all_assets: list[Asset] = cast(list[Asset], equities + bonds + commodities + currencies)

        return all_assets, events, "real_data"

    def _check_cancelled(self, cancel_event: threading.Event | None, stage: str) -> None:
        """Raise RebuildCancelledError if the cancel_event is set."""
        if cancel_event and cancel_event.is_set():
            raise FetchCancelledError(f"Fetch cancelled {stage}")

    def _persist_cache(self, graph: AssetRelationshipGraph) -> None:
        """
        Write the asset relationship graph to the configured cache file.

        Writes the graph to a temporary file in the cache directory and atomically replaces the final cache path
        with that temporary file. If no cache path is configured this is a no-op. Any I/O or serialization errors
        are logged and suppressed; on failure the method makes a best-effort attempt to remove the temporary file.
        """
        import os
        import tempfile

        tmp_path: Path | None = None

        try:
            if self.cache_path is None:
                return

            cache_path = self.cache_path.expanduser().resolve()
            cache_dir = cache_path.parent
            cache_dir.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=cache_dir,
                delete=False,
            ) as tmp_file:
                tmp_path = Path(tmp_file.name)

            _save_to_cache(graph, tmp_path)
            os.replace(tmp_path, cache_path)

        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                ObservabilityEvent(
                    event="graph_cache_persistence_failed",
                    message=f"Failed to persist dataset cache to {self.cache_path}: {type(exc).__name__}",
                    metadata={"cache_path": str(self.cache_path), "error": type(exc).__name__},
                ),
            )
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError as os_exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        ObservabilityEvent(
                            event="graph_cache_cleanup_failed",
                            message=f"Failed to remove temporary cache file {tmp_path}: {type(os_exc).__name__}",
                            metadata={"tmp_path": str(tmp_path), "error": type(os_exc).__name__},
                        ),
                    )

    def _fallback(self) -> AssetRelationshipGraph:
        """
        Provide a fallback AssetRelationshipGraph when live fetching is unavailable.

        If a `fallback_factory` was configured, returns its result; otherwise returns the packaged sample database.

        Returns:
            AssetRelationshipGraph: The fallback graph produced by the factory or the sample database.
        """
        if self.fallback_factory:
            return self.fallback_factory()

        from src.data.sample_data import create_sample_database

        return create_sample_database()

    @staticmethod
    def _fetch_history_close(
        yf_module: Any,
        symbol: str,
    ) -> tuple[float | None, Any]:
        """
        Fetch the most recent closing price for a Yahoo Finance symbol and return it with the ticker object.

        Parameters:
            yf_module (Any): The imported yfinance module to use for fetching.
            symbol (str): Yahoo Finance ticker symbol.

        Returns:
            tuple[Optional[float], Any]: A pair (latest close price as float or `None` if unavailable, ticker object).
        """
        ticker = yf_module.Ticker(symbol)
        hist = ticker.history(period="1d")

        if hist.empty or "Close" not in hist.columns:
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_fetch_no_price_data",
                    message=f"No price data for {symbol}",
                    metadata={"symbol": symbol},
                ),
            )
            return None, ticker

        close_value = float(hist["Close"].iloc[-1])
        if not math.isfinite(close_value):
            log_event(
                logger,
                logging.WARNING,
                ObservabilityEvent(
                    event="graph_fetch_non_finite_price",
                    message=f"Non-finite price data for {symbol}",
                    metadata={"symbol": symbol, "value": close_value},
                ),
            )
            return None, ticker
        return close_value, ticker

    @staticmethod
    def _fetch_equity_data(cancel_event: threading.Event | None = None) -> list[Equity]:
        """
        Fetch latest market data for a fixed set of major equity symbols and construct Equity objects.

        Skips symbols that lack a valid latest close price; emits structured observability
        events for each symbol's success or failure.

        Returns:
            list[Equity]: Equity instances for symbols with an available valid price.
        """
        yf = _get_yfinance()

        equity_symbols: dict[str, tuple[str, str]] = {
            "AAPL": ("Apple Inc.", "Technology"),
            "MSFT": ("Microsoft Corporation", "Technology"),
            "XOM": ("Exxon Mobil Corporation", "Energy"),
            "JPM": ("JPMorgan Chase & Co.", "Financial Services"),
        }

        equities: list[Equity] = []

        for symbol, (name, sector) in equity_symbols.items():
            if cancel_event and cancel_event.is_set():
                raise FetchCancelledError("Fetch cancelled during equities")

            try:
                current_price, ticker = RealDataFetcher._fetch_history_close(yf, symbol)
                if current_price is None:
                    continue

                info = getattr(ticker, "info", {}) or {}

                equity = Equity(
                    id=symbol,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=current_price,
                    market_cap=info.get("marketCap"),
                )
                equities.append(equity)

                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_fetch_equity_success",
                        message=_FETCHED_ASSET_LOG_MESSAGE % (symbol, name, current_price),
                        metadata={"symbol": symbol, "name": name, "price": current_price, "asset_class": "equity"},
                    ),
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="graph_fetch_equity_failed",
                        message=f"Failed to fetch equity data for {symbol}: {type(exc).__name__}",
                        metadata={"symbol": symbol, "error": type(exc).__name__},
                    ),
                )

        return equities

    @staticmethod
    def _fetch_bond_data(cancel_event: threading.Event | None = None) -> list[Bond]:
        """
        Build Bond proxy objects from a fixed set of bond ETF symbols.

        For each configured ETF symbol, attempts to fetch the latest market price

        and constructs a Bond when a finite price is available;

        symbols with missing or non-finite price data are skipped.

        Emits observability events for per-symbol success and failure.

        Returns:
            list[Bond]: Bond objects constructed for ETFs that had available market data.
        """
        yf = _get_yfinance()

        bond_symbols: dict[str, tuple[str, str, str | None, str | None]] = {
            "TLT": ("iShares 20+ Year Treasury Bond ETF", "Government", None, "AAA"),
            "LQD": (
                "iShares iBoxx $ Investment Grade Corporate Bond ETF",
                "Corporate",
                None,
                None,
            ),
            "HYG": (
                "iShares iBoxx $ High Yield Corporate Bond ETF",
                "Corporate",
                None,
                None,
            ),
        }

        bonds: list[Bond] = []

        for symbol, (name, sector, issuer_id, rating) in bond_symbols.items():
            if cancel_event and cancel_event.is_set():
                raise FetchCancelledError("Fetch cancelled during bonds")

            try:
                current_price, ticker = RealDataFetcher._fetch_history_close(yf, symbol)
                if current_price is None:
                    continue

                info = getattr(ticker, "info", {}) or {}

                bond = Bond(
                    id=symbol,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.FIXED_INCOME,
                    sector=sector,
                    price=current_price,
                    yield_to_maturity=info.get("yield", 0.03),
                    coupon_rate=info.get("couponRate", info.get("yield", 0.025)),
                    maturity_date="2035-01-01",
                    credit_rating=rating,
                    issuer_id=issuer_id,
                )
                bonds.append(bond)

                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_fetch_bond_success",
                        message=_FETCHED_ASSET_LOG_MESSAGE % (symbol, name, current_price),
                        metadata={"symbol": symbol, "name": name, "price": current_price, "asset_class": "bond"},
                    ),
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="graph_fetch_bond_failed",
                        message=f"Failed to fetch bond data for {symbol}: {type(exc).__name__}",
                        metadata={"symbol": symbol, "error": type(exc).__name__},
                    ),
                )

        return bonds

    @staticmethod
    def _fetch_commodity_data(cancel_event: threading.Event | None = None) -> list[Commodity]:
        """
        Construct Commodity instances for a fixed set of futures symbols using their latest close prices.

        Symbols without a valid price are skipped; failures for individual symbols are
        logged and do not stop processing.

        Returns:
            list[Commodity]: Commodity objects created for symbols with valid prices.
        """
        yf = _get_yfinance()

        commodity_symbols: dict[str, tuple[str, str, float, float]] = {
            "GC=F": ("Gold Futures", "Metals", 100.0, 0.20),
            "CL=F": ("Crude Oil Futures", "Energy", 1000.0, 0.35),
            "SI=F": ("Silver Futures", "Metals", 5000.0, 0.25),
        }

        commodities: list[Commodity] = []

        for symbol, (name, sector, contract_size, volatility) in commodity_symbols.items():
            if cancel_event and cancel_event.is_set():
                raise FetchCancelledError("Fetch cancelled during commodities")

            try:
                current_price, _ticker = RealDataFetcher._fetch_history_close(yf, symbol)
                if current_price is None:
                    continue

                commodity = Commodity(
                    id=symbol.replace("=F", "_FUTURE"),
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.COMMODITY,
                    sector=sector,
                    price=current_price,
                    contract_size=contract_size,
                    delivery_date=(datetime.now(UTC) + timedelta(days=90)).strftime("%Y-%m-%d"),
                    volatility=volatility,
                )
                commodities.append(commodity)

                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_fetch_commodity_success",
                        message=_FETCHED_ASSET_LOG_MESSAGE % (symbol, name, current_price),
                        metadata={"symbol": symbol, "name": name, "price": current_price, "asset_class": "commodity"},
                    ),
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="graph_fetch_commodity_failed",
                        message=f"Failed to fetch commodity data for {symbol}: {type(exc).__name__}",
                        metadata={"symbol": symbol, "error": type(exc).__name__},
                    ),
                )

        return commodities

    @staticmethod
    def _fetch_currency_data(cancel_event: threading.Event | None = None) -> list[Currency]:
        """
        Construct Currency dataclass instances for a predefined set of FX pairs using the latest available rates.

        For each configured FX symbol, attempts to fetch the most recent exchange rate;

        symbols with no available rate are skipped and failures for individual symbols

        are logged but do not stop the overall fetch.

        Returns:
            list[Currency]: Currency objects for symbols with successfully retrieved rates.
        """
        yf = _get_yfinance()

        currency_symbols: dict[str, tuple[str, str, str]] = {
            "EURUSD=X": ("Euro", "EU", "EUR"),
            "GBPUSD=X": ("British Pound", "UK", "GBP"),
            "JPYUSD=X": ("Japanese Yen", "Japan", "JPY"),
        }

        currencies: list[Currency] = []

        for symbol, (name, country, currency_code) in currency_symbols.items():
            if cancel_event and cancel_event.is_set():
                raise FetchCancelledError("Fetch cancelled during currencies")

            try:
                current_rate, _ticker = RealDataFetcher._fetch_history_close(yf, symbol)
                if current_rate is None:
                    continue

                currency = Currency(
                    id=symbol.replace("=X", ""),
                    symbol=currency_code,
                    name=name,
                    asset_class=AssetClass.CURRENCY,
                    sector="Forex",
                    price=current_rate,
                    exchange_rate=current_rate,
                    country=country,
                    central_bank_rate=0.02,
                )
                currencies.append(currency)

                log_event(
                    logger,
                    logging.INFO,
                    ObservabilityEvent(
                        event="graph_fetch_currency_success",
                        message=f"Fetched {symbol}: {name} at {current_rate:.4f}",
                        metadata={"symbol": symbol, "name": name, "rate": current_rate, "asset_class": "currency"},
                    ),
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.ERROR,
                    ObservabilityEvent(
                        event="graph_fetch_currency_failed",
                        message=f"Failed to fetch currency data for {symbol}: {type(exc).__name__}",
                        metadata={"symbol": symbol, "error": type(exc).__name__},
                    ),
                )

        return currencies

    @staticmethod
    def _create_regulatory_events() -> list[RegulatoryEvent]:
        """
        Create three synthetic RegulatoryEvent instances to enrich the asset graph.

        Returns:
            list[RegulatoryEvent]: Three hard-coded regulatory events associated with specific assets.
        """
        events: list[RegulatoryEvent] = []

        events.append(
            RegulatoryEvent(
                id="AAPL_Q4_2024_REAL",
                asset_id="AAPL",
                event_type=RegulatoryActivity.EARNINGS_REPORT,
                date="2024-11-01",
                description="Q4 2024 Earnings Report - Record iPhone sales",
                impact_score=0.12,
                related_assets=["TLT", "MSFT"],
            )
        )

        events.append(
            RegulatoryEvent(
                id="MSFT_DIV_2024_REAL",
                asset_id="MSFT",
                event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
                date="2024-09-15",
                description="Quarterly dividend increase - Cloud growth continues",
                impact_score=0.08,
                related_assets=["AAPL", "LQD"],
            )
        )

        events.append(
            RegulatoryEvent(
                id="XOM_SEC_2024_REAL",
                asset_id="XOM",
                event_type=RegulatoryActivity.SEC_FILING,
                date="2024-10-01",
                description=("10-K Filing - Increased oil reserves and sustainability initiatives"),
                impact_score=0.05,
                related_assets=["CL_FUTURE"],
            )
        )

        return events


def create_real_database() -> AssetRelationshipGraph:
    """Build an AssetRelationshipGraph from live, cached, or fallback data."""
    fetcher = RealDataFetcher()
    return fetcher.create_real_database()


def _enum_to_value(value: Any) -> Any:
    """
    Convert an Enum to its underlying value; return other objects unchanged.

    Returns:
        The underlying value if `value` is an `Enum`, otherwise `value` unchanged.
    """
    return value.value if isinstance(value, Enum) else value


def _serialize_dataclass(obj: Any) -> dict[str, Any]:
    """
    Convert a dataclass instance into a JSON-serializable dictionary that includes type metadata.

    Parameters:
        obj (Any): A dataclass instance to serialize.

    Returns:
        dict[str, Any]: Mapping of field names to values with any Enum fields replaced by their
            underlying values and an added "__type__" key containing the dataclass class name.
    """
    data = asdict(obj)
    serialized = {key: _enum_to_value(val) for key, val in data.items()}
    serialized["__type__"] = obj.__class__.__name__
    return serialized


def _serialize_graph(graph: AssetRelationshipGraph) -> dict[str, Any]:
    """
    Convert an AssetRelationshipGraph into a JSON-serializable dictionary.

    Returns:
        payload (dict): A JSON-friendly mapping with the following keys:
            - "assets": list of serialized asset objects.
            - "regulatory_events": list of serialized regulatory event objects.
            - "relationships": mapping from source asset id to a list of objects each containing
              "target", "relationship_type", and "strength".
            - "incoming_relationships": mapping from target asset id to a list of objects each
              containing "source", "relationship_type", and "strength".
    """
    incoming_relationships: dict[str, list[tuple[str, str, float]]] = {}

    for source, rels in graph.relationships.items():
        for target, rel_type, strength in rels:
            if target not in incoming_relationships:
                incoming_relationships[target] = []
            incoming_relationships[target].append((source, rel_type, strength))

    return {
        "assets": [_serialize_dataclass(asset) for asset in graph.assets.values()],
        "regulatory_events": [_serialize_dataclass(event) for event in graph.regulatory_events],
        "relationships": {
            source: [
                {
                    "target": target,
                    "relationship_type": rel_type,
                    "strength": strength,
                }
                for target, rel_type, strength in rels
            ]
            for source, rels in graph.relationships.items()
        },
        "incoming_relationships": {
            target: [
                {
                    "source": source,
                    "relationship_type": rel_type,
                    "strength": strength,
                }
                for source, rel_type, strength in rels
            ]
            for target, rels in incoming_relationships.items()
        },
    }


def _deserialize_asset(data: dict[str, Any]) -> Asset:
    """
    Reconstructs an Asset or a concrete Asset subclass from a serialized mapping.

    The function looks for a "__type__" key in `data` to choose the concrete dataclass (one of
    `Equity`, `Bond`, `Commodity`, `Currency`); if missing or unrecognized, `Asset` is used.
    If `data` contains an "asset_class" value, it will be converted to the `AssetClass` enum
    before instantiation.

    Parameters:
        data (dict[str, Any]): Serialized asset data produced by _serialize_dataclass.

    Returns:
        Asset: An Asset instance (or a subclass instance) populated from `data`.
    """
    data = dict(data)
    type_name = data.pop("__type__", "Asset")

    if asset_class_value := data.get("asset_class"):
        data["asset_class"] = AssetClass(asset_class_value)

    cls_map = {
        "Asset": Asset,
        "Equity": Equity,
        "Bond": Bond,
        "Commodity": Commodity,
        "Currency": Currency,
    }

    cls = cls_map.get(type_name, Asset)
    return cls(**data)


def _deserialize_event(data: dict[str, Any]) -> RegulatoryEvent:
    """
    Convert a serialized regulatory event dictionary into a RegulatoryEvent instance.

    Parameters:
        data (Dict[str, Any]): Serialized event data (as produced by _serialize_dataclass/_serialize_graph),
            where `event_type` is the stored enum value.

    Returns:
        RegulatoryEvent: A reconstructed RegulatoryEvent with `event_type` converted back
                         to the RegulatoryActivity enum.
    """
    data = dict(data)
    data["event_type"] = RegulatoryActivity(data["event_type"])
    return RegulatoryEvent(**data)


def _deserialize_graph(payload: dict[str, Any]) -> AssetRelationshipGraph:
    """
    Reconstructs an AssetRelationshipGraph from a serialized payload.

    Deserializes and adds assets from payload["assets"], deserializes and adds regulatory
    events from payload["regulatory_events"], and recreates directed relationships from
    payload["relationships"] (each relationship's `strength` is converted to `float`).
    The `"incoming_relationships"` key, if present, is ignored.

    Returns:
        AssetRelationshipGraph: Graph populated with assets, regulatory events, and relationships.
    """
    from src.config.settings import get_settings

    settings = get_settings()
    graph = AssetRelationshipGraph(
        same_sector_strength=settings.same_sector_strength,
        corporate_bond_strength=settings.corporate_bond_strength,
    )

    for asset_data in payload.get("assets", []):
        graph.add_asset(_deserialize_asset(dict(asset_data)))

    for event_data in payload.get("regulatory_events", []):
        graph.add_regulatory_event(_deserialize_event(event_data))

    relationships_payload = payload.get("relationships", {})
    for source, rels in relationships_payload.items():
        for item in rels:
            graph.add_relationship(
                source,
                item["target"],
                item["relationship_type"],
                float(item["strength"]),
                bidirectional=False,
            )

    return graph


def _load_from_cache(path: Path) -> AssetRelationshipGraph:
    """
    Load an AssetRelationshipGraph from a JSON cache file.

    Parameters:
        path (Path): Filesystem path to the JSON cache file to read.

    Returns:
        AssetRelationshipGraph: The reconstructed graph deserialized from the file's JSON payload.
    """
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    return _deserialize_graph(payload)


def _save_to_cache(graph: AssetRelationshipGraph, path: Path) -> None:
    """Serialize an AssetRelationshipGraph to JSON and write to filesystem.

    Creates parent directories if needed. The JSON is written using UTF-8
    encoding with two-space indentation.

    Parameters:
        graph (AssetRelationshipGraph): Graph to serialize and persist.
        path (Path): Filesystem path for the output JSON file; parent directories will be created if missing.
    """
    payload = _serialize_graph(graph)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
