import json
import logging
from dataclasses import asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.logic.asset_graph import AssetRelationshipGraph
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

logger = logging.getLogger(__name__)
_YFINANCE_MODULE = None
_FETCHED_ASSET_LOG_MESSAGE = "Fetched %s: %s at $%.2f"


def _get_yfinance() -> Any:
    """
    Lazily import yfinance so optional dependency absence does not break startup.

    Returns:
        The imported yfinance module.

    Raises:
        RuntimeError: If yfinance is not installed.
        RuntimeError: If yfinance or one of its dependencies fails during import.
        RuntimeError: If an unexpected import-time error occurs.
    """
    global _YFINANCE_MODULE

    if _YFINANCE_MODULE is not None:
        return _YFINANCE_MODULE

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:
        logger.error(
            "Failed to import yfinance. Optional live-data features are "
            "unavailable. Install it using: pip install yfinance"
        )
        raise RuntimeError(
            "yfinance is unavailable in the current environment. Install it using: pip install yfinance"
        ) from exc
    except ImportError as exc:
        logger.exception("Failed to import yfinance due to an import/dependency problem.")
        raise RuntimeError(
            "yfinance could not be imported in the current environment. "
            "Check its installation and dependency compatibility."
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error while importing yfinance.")
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
        cache_path: Optional[str] = None,
        fallback_factory: Optional[Callable[[], AssetRelationshipGraph]] = None,
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
        Build an asset relationship graph from live data or fallback data.

        Returns:
            AssetRelationshipGraph: A populated graph built from cached, live,
            or fallback/sample data depending on availability and configuration.
        """
        if self.cache_path and self.cache_path.exists():
            try:
                logger.info("Loading asset graph from cache at %s", self.cache_path)
                return _load_from_cache(self.cache_path)
            except Exception:
                logger.exception("Failed to load cached dataset; proceeding with standard fetch")

        if not self.enable_network:
            logger.info("Network fetching disabled. Using fallback dataset if available.")
            return self._fallback()

        logger.info("Creating database with real financial data from Yahoo Finance")
        graph = AssetRelationshipGraph()

        try:
            equities = self._fetch_equity_data()
            bonds = self._fetch_bond_data()
            commodities = self._fetch_commodity_data()
            currencies = self._fetch_currency_data()

            for asset in equities + bonds + commodities + currencies:
                graph.add_asset(asset)

            for event in self._create_regulatory_events():
                graph.add_regulatory_event(event)

            graph.build_relationships()

            if self.cache_path:
                self._persist_cache(graph)

            logger.info(
                "Real database created with %s assets and %s relationships",
                len(graph.assets),
                sum(len(rels) for rels in graph.relationships.values()),
            )
            return graph

        except Exception:
            logger.exception("Failed to create real database")
            logger.warning("Falling back to sample data due to real data fetch failure")
            return self._fallback()

    def _persist_cache(self, graph: AssetRelationshipGraph) -> None:
        """
        Persist the asset relationship graph to the configured cache file.

        The graph is written to a temporary file and then atomically moved into
        place. Cache persistence failures are logged and do not raise.
        """
        import os
        import tempfile

        tmp_path: Optional[Path] = None

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

        except Exception:
            logger.exception(
                "Failed to persist dataset cache to %s",
                self.cache_path,
            )
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    logger.warning(
                        "Failed to remove temporary cache file %s",
                        tmp_path,
                    )

    def _fallback(self) -> AssetRelationshipGraph:
        """
        Return fallback data when live fetching is unavailable.
        """
        if self.fallback_factory:
            return self.fallback_factory()

        from src.data.sample_data import create_sample_database

        return create_sample_database()

    @staticmethod
    def _fetch_history_close(
        yf_module: Any,
        symbol: str,
    ) -> Tuple[Optional[float], Any]:
        """
        Fetch the latest close price and ticker object for a symbol.

        Args:
            yf_module: Imported yfinance module.
            symbol: Yahoo Finance symbol.

        Returns:
            A tuple of:
            - latest close price as float, or None when unavailable
            - ticker object
        """
        ticker = yf_module.Ticker(symbol)
        hist = ticker.history(period="1d")

        if hist.empty or "Close" not in hist.columns:
            logger.warning("No price data for %s", symbol)
            return None, ticker

        return float(hist["Close"].iloc[-1]), ticker

    @staticmethod
    def _fetch_equity_data() -> List[Equity]:
        """
        Fetch current market data for major equities.
        """
        yf = _get_yfinance()

        equity_symbols: Dict[str, Tuple[str, str]] = {
            "AAPL": ("Apple Inc.", "Technology"),
            "MSFT": ("Microsoft Corporation", "Technology"),
            "XOM": ("Exxon Mobil Corporation", "Energy"),
            "JPM": ("JPMorgan Chase & Co.", "Financial Services"),
        }

        equities: List[Equity] = []

        for symbol, (name, sector) in equity_symbols.items():
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

                logger.info(
                    "Fetched %s: %s at $%.2f",
                    symbol,
                    name,
                    current_price,
                )
            except Exception:
                logger.exception("Failed to fetch equity data for %s", symbol)

        return equities

    @staticmethod
    def _fetch_bond_data() -> List[Bond]:
        """
        Fetch bond and treasury ETF market data and return Bond proxy instances.

        Since individual bond data is less directly accessible, this uses a
        small set of treasury and corporate bond ETFs as fixed-income proxies.
        """
        yf = _get_yfinance()

        bond_symbols: Dict[str, Tuple[str, str, Optional[str], Optional[str]]] = {
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

        bonds: List[Bond] = []

        for symbol, (name, sector, issuer_id, rating) in bond_symbols.items():
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

                logger.info(
                    "Fetched %s: %s at $%.2f",
                    symbol,
                    name,
                    current_price,
                )
            except Exception:
                logger.exception("Failed to fetch bond data for %s", symbol)

        return bonds

    @staticmethod
    def _fetch_commodity_data() -> List[Commodity]:
        """
        Fetch commodity futures data.
        """
        yf = _get_yfinance()

        commodity_symbols: Dict[str, Tuple[str, str, float, float]] = {
            "GC=F": ("Gold Futures", "Metals", 100.0, 0.20),
            "CL=F": ("Crude Oil Futures", "Energy", 1000.0, 0.35),
            "SI=F": ("Silver Futures", "Metals", 5000.0, 0.25),
        }

        commodities: List[Commodity] = []

        for symbol, (name, sector, contract_size, volatility) in commodity_symbols.items():
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
                    delivery_date=(datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d"),
                    volatility=volatility,
                )
                commodities.append(commodity)

                logger.info(
                    "Fetched %s: %s at $%.2f",
                    symbol,
                    name,
                    current_price,
                )
            except Exception:
                logger.exception("Failed to fetch commodity data for %s", symbol)

        return commodities

    @staticmethod
    def _fetch_currency_data() -> List[Currency]:
        """
        Fetch foreign exchange rate data.
        """
        yf = _get_yfinance()

        currency_symbols: Dict[str, Tuple[str, str, str]] = {
            "EURUSD=X": ("Euro", "EU", "EUR"),
            "GBPUSD=X": ("British Pound", "UK", "GBP"),
            "JPYUSD=X": ("Japanese Yen", "Japan", "JPY"),
        }

        currencies: List[Currency] = []

        for symbol, (name, country, currency_code) in currency_symbols.items():
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

                logger.info("Fetched %s: %s at %.4f", symbol, name, current_rate)
            except Exception:
                logger.exception("Failed to fetch currency data for %s", symbol)

        return currencies

    @staticmethod
    def _create_regulatory_events() -> List[RegulatoryEvent]:
        """
        Create a small set of sample regulatory events associated with assets.

        These are synthetic enrichment events used alongside fetched price data.
        """
        events: List[RegulatoryEvent] = []

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
    """
    Build an AssetRelationshipGraph from live, cached, or fallback data.
    """
    fetcher = RealDataFetcher()
    return fetcher.create_real_database()


def _enum_to_value(value: Any) -> Any:
    """
    Convert an Enum instance to its underlying value.
    """
    return value.value if isinstance(value, Enum) else value


def _serialize_dataclass(obj: Any) -> Dict[str, Any]:
    """
    Serialize a dataclass instance into a JSON-friendly dictionary.
    """
    data = asdict(obj)
    serialized = {key: _enum_to_value(val) for key, val in data.items()}
    serialized["__type__"] = obj.__class__.__name__
    return serialized


def _serialize_graph(graph: AssetRelationshipGraph) -> Dict[str, Any]:
    """
    Serialize an AssetRelationshipGraph into a JSON-serializable dictionary.
    """
    incoming_relationships: Dict[str, List[Tuple[str, str, float]]] = {}

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


def _deserialize_asset(data: Dict[str, Any]) -> Asset:
    """
    Deserialize a dictionary representation of an asset.
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


def _deserialize_event(data: Dict[str, Any]) -> RegulatoryEvent:
    """
    Deserialize a dictionary representation of a regulatory event.
    """
    data = dict(data)
    data["event_type"] = RegulatoryActivity(data["event_type"])
    return RegulatoryEvent(**data)


def _deserialize_graph(payload: Dict[str, Any]) -> AssetRelationshipGraph:
    """
    Reconstruct an AssetRelationshipGraph from a serialized payload.
    """
    graph = AssetRelationshipGraph()

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
    """
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    return _deserialize_graph(payload)


def _save_to_cache(graph: AssetRelationshipGraph, path: Path) -> None:
    """
    Persist an AssetRelationshipGraph to a JSON file.
    """
    payload = _serialize_graph(graph)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
