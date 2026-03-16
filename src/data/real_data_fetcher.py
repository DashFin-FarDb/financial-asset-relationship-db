"""Fetch and normalize external market data for the asset graph."""

import json
import logging
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yfinance as yf  # pylint: disable=import-error  # pyright: ignore[reportMissingImports]  # type: ignore[import-not-found]

from src.data.sample_data import create_sample_database
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
NO_PRICE_DATA_LOG = "No price data for %s"


class RealDataFetcher:
    """Fetches real financial data from Yahoo Finance and other sources."""

    def __init__(
        self,
        *,
        cache_path: Optional[str] = None,
        fallback_factory: Optional[Callable[[], AssetRelationshipGraph]] = None,
        enable_network: bool = True,
    ) -> None:
        """
        Configure the RealDataFetcher with optional cache location,
        fallback factory, and network control.

        Parameters:
            cache_path (Optional[str]): Path to a JSON cache file used to
                load or persist a previously built AssetRelationshipGraph.
                If None, no on-disk caching is performed.
            fallback_factory (Optional[Callable[[], AssetRelationshipGraph]]):
                Callable that produces an AssetRelationshipGraph to use when
                network fetching is disabled or when fetching fails.
                If None, a built-in sample database will be used as fallback.
            enable_network (bool): When False, disables network access and
                causes create_real_database to return the fallback graph
                instead of attempting live data fetches.
        """
        self.session = None
        self.cache_path = Path(cache_path) if cache_path else None
        self.fallback_factory = fallback_factory
        self.enable_network = enable_network

    def create_real_database(self) -> AssetRelationshipGraph:
        """
        Builds an AssetRelationshipGraph from a cached file, live market data, or a fallback dataset.

        Attempts to load and return a valid cached graph if present. If network access is disabled, returns the configured fallback. When network fetching is enabled, builds the graph from live market data and persists it to cache if a cache path is configured. On any IO or build failure, returns the fallback/sample graph.

        Returns:
            AssetRelationshipGraph: Populated graph from cache or live data; a fallback/sample graph if loading or fetching fails.
        """
        cached_graph = self._try_load_cached_graph()
        if cached_graph is not None:
            return cached_graph

        if not self.enable_network:
            logger.info("Network fetching disabled. Using fallback dataset if available.")
            return self._fallback()

        logger.info("Creating database with real financial data from Yahoo Finance")

        try:
            graph = self._build_graph_from_live_data()
            if self.cache_path:
                self._persist_cache(graph)

            logger.info(
                "Real database created with %s assets and %s relationships",
                len(graph.assets),
                sum(len(rels) for rels in graph.relationships.values()),
            )
            return graph

        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.error("Failed to create real database: %s", exc)
        logger.warning("Falling back to sample data due to real data fetch failure")
        return self._fallback()

    def _try_load_cached_graph(self) -> Optional[AssetRelationshipGraph]:
        """
        Load an AssetRelationshipGraph from the configured cache if present and valid.

        Attempts to read and deserialize the cached graph file at the fetcher's `cache_path`. If `cache_path` is unset, the file does not exist, or the file cannot be read/deserialized, the method returns None.

        Returns:
            AssetRelationshipGraph: The deserialized cached graph if successfully loaded, `None` otherwise.
        """
        if not self.cache_path or not self.cache_path.exists():
            return None
        try:
            logger.info(
                "Loading asset graph from cache at %s",
                self.cache_path,
            )
            return _load_from_cache(self.cache_path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.exception("Failed to load cached dataset; proceeding with standard fetch")
            return None

    def _build_graph_from_live_data(self) -> AssetRelationshipGraph:
        """
        Builds an AssetRelationshipGraph populated from live market data and regulatory events.

        Fetches equities, bonds, commodities, and currencies from configured live providers, adds the resulting assets and a set of regulatory events to a new AssetRelationshipGraph, then computes and attaches relationships between assets.

        Returns:
            AssetRelationshipGraph: A graph containing the fetched assets, regulatory events, and their computed relationships.
        """
        graph = AssetRelationshipGraph()
        equities = self._fetch_equity_data()
        bonds = self._fetch_bond_data()
        commodities = self._fetch_commodity_data()
        currencies = self._fetch_currency_data()

        for asset in equities + bonds + commodities + currencies:
            graph.add_asset(asset)

        for event in self._create_regulatory_events():
            graph.add_regulatory_event(event)

        graph.build_relationships()
        return graph

    def _persist_cache(self, graph: AssetRelationshipGraph) -> None:
        """
        Write the provided AssetRelationshipGraph to the configured cache path atomically.

        If no cache path was configured on this fetcher, this method is a no-op.
        Parent directories for the cache path are created as needed. On failure the
        method logs an exception; an existing cache file is not partially overwritten
        because the write is performed atomically.
        """
        if self.cache_path is None:
            return

        try:
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

        except (OSError, TypeError, ValueError):
            logger.exception(
                "Failed to persist dataset cache to %s",
                self.cache_path,
            )

    def _fallback(self) -> AssetRelationshipGraph:
        """
        Provide a fallback AssetRelationshipGraph from the configured factory or a sample dataset.

        Returns:
            AssetRelationshipGraph: The graph produced by `fallback_factory()` if configured; otherwise the sample database returned by `create_sample_database()`.
        """
        if self.fallback_factory:
            return self.fallback_factory()

        return create_sample_database()

    @staticmethod
    def _fetch_equity_data() -> List[Equity]:
        """
        Fetch latest price data for a small set of major equities and return them as Equity instances.

        For each predefined ticker this fetcher retrieves the most recent daily close price and constructs an Equity object with id, symbol, name, sector, asset_class, and price. Symbols with no price data are skipped (a warning is logged); individual fetch errors are logged and do not stop the overall process.

        Returns:
            List[Equity]: Equity objects for symbols successfully fetched and parsed.
        """
        equity_symbols = {
            "AAPL": ("Apple Inc.", "Technology"),
            "MSFT": ("Microsoft Corporation", "Technology"),
            "XOM": ("Exxon Mobil Corporation", "Energy"),
            "JPM": ("JPMorgan Chase & Co.", "Financial Services"),
        }

        equities = []
        for symbol, (name, sector) in equity_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")

                if hist.empty:
                    logger.warning(NO_PRICE_DATA_LOG, symbol)
                    continue

                current_price = float(hist["Close"].iloc[-1])
                equity = Equity(
                    id=symbol,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
                    sector=sector,
                    price=current_price,
                )
                equities.append(equity)
            except Exception as e:
                logger.error("Error fetching data for %s: %s", symbol, e)
        return equities

    @staticmethod
    def _fetch_bond_data() -> List[Bond]:
        """
        Fetches market data for selected bond and treasury ETFs and returns Bond instances used as fixed-income proxies.

        Fetches latest price and available metadata for a predefined set of bond and treasury ETF symbols. If price data is missing for a symbol it is skipped (a warning is logged). When yield or coupon information is missing, `yield_to_maturity` defaults to 0.03 and `coupon_rate` defaults to 0.025. Maturity dates and some fields are approximate because ETFs are used as proxies; individual symbols that fail to fetch due to errors are skipped (errors are logged).

        Returns:
            List[Bond]: Bond instances populated with id, symbol, name, asset_class, sector, price, yield_to_maturity, coupon_rate, maturity_date, credit_rating, and issuer_id.
        """
        # For bonds, we'll use Treasury ETFs and bond proxies since
        # individual bonds are harder to access
        bond_symbols = {
            "TLT": (
                "iShares 20+ Year Treasury Bond ETF",
                "Government",
                None,
                "AAA",
            ),
            "LQD": (
                "iShares iBoxx $ Investment Grade Corporate Bond ETF",
                "Corporate",
                None,
                None,
            ),
        }

        bonds = []
        for symbol, (name, sector, issuer_id, rating) in bond_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                hist = ticker.history(period="1d")

                if hist.empty or "Close" not in hist.columns:
                    logger.warning(NO_PRICE_DATA_LOG, symbol)
                    continue

                current_price = float(hist["Close"].iloc[-1])
                bond = Bond(
                    id=symbol,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.FIXED_INCOME,
                    sector=sector,
                    price=current_price,
                    yield_to_maturity=info.get(
                        "yield",
                        0.03,
                    ),  # Default 3% if not available
                    coupon_rate=info.get(
                        "couponRate", info.get("yield", 0.025)
                    ),  # Prefer explicit coupon rate when available
                    maturity_date="2035-01-01",  # Approximate for ETFs
                    issuer_id=issuer_id,
                )
                bonds.append(bond)
                logger.info(
                    "Fetched %s: %s at $%.2f",
                    symbol,
                    name,
                    current_price,
                )
            except Exception as e:
                logger.error("Failed to fetch bond data for %s: %s", symbol, e)
                continue

        return bonds

    @staticmethod
    def _fetch_commodity_data() -> List[Commodity]:
        """
        Fetches current commodity futures prices and constructs Commodity objects for a predefined set of symbols.

        Skips symbols with no available price data and continues on individual fetch failures.

        Returns:
            List[Commodity]: A list of Commodity instances populated with id, symbol, name, asset_class, sector, price, contract_size, delivery_date, and volatility.
        """
        # Define key commodity futures and their characteristics.
        commodity_symbols: Dict[str, Tuple[str, str, float, float]] = {
            # symbol: (name, sector, contract_size, volatility)
            # Example entries (adjust or extend as needed elsewhere):
            "GC=F": ("Gold Futures", "Metals", 100.0, 0.20),
            "CL=F": ("Crude Oil Futures", "Energy", 1000.0, 0.35),
        }

        commodities: List[Commodity] = []
        for symbol, (
            name,
            sector,
            contract_size,
            volatility,
        ) in commodity_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")

                if hist.empty or "Close" not in hist.columns:
                    logger.warning(NO_PRICE_DATA_LOG, symbol)
                    continue

                current_price = float(hist["Close"].iloc[-1])

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

            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.error(
                    "Failed to fetch commodity data for %s: %s",
                    symbol,
                    exc,
                )
                continue

        return commodities

    @staticmethod
    def _fetch_currency_data() -> List[Currency]:
        """
        Fetches USD exchange rates for a small set of major currencies.

        Attempts to retrieve the latest close price for EUR, GBP, and JPY quoted against USD and constructs currency objects populated with price, exchange_rate, country, and an approximate central_bank_rate. Entries with missing price data are skipped; individual fetch failures are logged and do not stop processing the remaining symbols.

        Returns:
            A list of Currency objects for the successfully fetched currencies. Each object includes the latest USD rate in `price` and `exchange_rate`, the issuing `country`, and an approximate `central_bank_rate`.
        """
        currency_symbols = {
            "EURUSD=X": ("Euro", "EU", "EUR"),
            "GBPUSD=X": ("British Pound", "UK", "GBP"),
            "JPYUSD=X": ("Japanese Yen", "Japan", "JPY"),
        }

        currencies = []
        for symbol, (name, country, currency_code) in currency_symbols.items():
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1d")

                if hist.empty or "Close" not in hist.columns:
                    logger.warning(NO_PRICE_DATA_LOG, symbol)
                    continue

                current_rate = float(hist["Close"].iloc[-1])

                currency = Currency(
                    id=symbol.replace("=X", ""),
                    symbol=currency_code,
                    name=name,
                    asset_class=AssetClass.CURRENCY,
                    sector="Forex",
                    price=current_rate,
                    exchange_rate=current_rate,
                    country=country,
                    # Approximate - would need separate API for real rates
                    central_bank_rate=0.02,
                )
                currencies.append(currency)
                logger.info(
                    "Fetched %s: %s at %.4f",
                    symbol,
                    name,
                    current_rate,
                )

            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                logger.error(
                    "Failed to fetch currency data for %s: %s",
                    symbol,
                    exc,
                )
                continue

        return currencies

    @staticmethod
    def _create_regulatory_events() -> List[RegulatoryEvent]:
        """
        Create a small set of sample regulatory events associated with fetched assets.

        Returns:
            List[RegulatoryEvent]: Three sample RegulatoryEvent instances (Apple earnings, Microsoft dividend, Exxon Mobil SEC filing) each populated with id, asset_id, event_type, date, description, impact_score, and related_assets.
        """
        # Create some realistic recent events
        events = []

        # Apple earnings event
        apple_earnings = RegulatoryEvent(
            id="AAPL_Q4_2024_REAL",
            asset_id="AAPL",
            event_type=RegulatoryActivity.EARNINGS_REPORT,
            date="2024-11-01",
            description="Q4 2024 Earnings Report - Record iPhone sales",
            impact_score=0.12,
            related_assets=["TLT", "MSFT"],  # Related tech and bonds
        )
        events.append(apple_earnings)

        # Microsoft dividend announcement
        msft_dividend = RegulatoryEvent(
            id="MSFT_DIV_2024_REAL",
            asset_id="MSFT",
            event_type=RegulatoryActivity.DIVIDEND_ANNOUNCEMENT,
            date="2024-09-15",
            description="Quarterly dividend increase - Cloud growth continues",
            impact_score=0.08,
            related_assets=["AAPL", "LQD"],
        )
        events.append(msft_dividend)

        # Energy sector regulatory event
        xom_filing = RegulatoryEvent(
            id="XOM_SEC_2024_REAL",
            asset_id="XOM",
            event_type=RegulatoryActivity.SEC_FILING,
            date="2024-10-01",
            description=("10-K Filing - Increased oil reserves and sustainability initiatives"),
            impact_score=0.05,
            related_assets=["CL_FUTURE"],  # Related to oil futures
        )
        events.append(xom_filing)

        return events


def create_real_database() -> AssetRelationshipGraph:
    """
    Create an AssetRelationshipGraph populated from cache, live market data, or a sample fallback.

    Attempts to load a previously cached graph; if none is available and network access is enabled, builds the graph from live market data; otherwise returns a fallback/sample graph.

    Returns:
        AssetRelationshipGraph: A graph containing assets, regulatory events, and relationship mappings sourced from the cache, live fetch, or fallback data.
    """
    fetcher = RealDataFetcher()
    return fetcher.create_real_database()


def _enum_to_value(_value: Any) -> Any:
    """
    Convert an Enum instance to its underlying value.
    Return the input unchanged otherwise.

    Parameters:
        _value (Any): The value to normalise.
            If `_value` is an `Enum` member, its `.value` is returned.

    Returns:
    Any: The underlying value of the `Enum` member if applicable,
    otherwise the original value.
    """
    return _value.value if isinstance(_value, Enum) else _value


def _serialize_dataclass(obj: Any) -> Dict[str, Any]:
    """
    Serialize a dataclass instance into a JSON- friendly dictionary
    with enum values converted.

    Parameters:
        obj(Any): A dataclass instance(e.g. Asset or subclass) to serialize.

    Returns:
        Dict[str, Any]: A mapping of field names to values where
        Enum members are replaced by their `.value`, and an additional
        "__type__" key containing the dataclass's class name.
    """
    data = asdict(obj)
    serialized = {key: _enum_to_value(val) for key, val in data.items()}
    serialized["__type__"] = obj.__class__.__name__
    return serialized


def _serialize_graph(graph: AssetRelationshipGraph) -> Dict[str, Any]:
    """
    Serialize an AssetRelationshipGraph into a JSON-friendly payload.

    The returned dictionary contains the graph's serialized contents under the following keys:
    - assets: list of serialized asset objects; each entry includes a "__type__" discriminator.
    - regulatory_events: list of serialized regulatory event objects.
    - relationships: mapping from source asset id to a list of outgoing relationship dictionaries with keys "target", "relationship_type", and "strength".
    - incoming_relationships: mapping from target asset id to a list of incoming relationship dictionaries with keys "source", "relationship_type", and "strength".

    Returns:
        Dict[str, Any]: A JSON-serializable dictionary representing the graph.
    """
    incoming_relationships = _build_incoming_relationships(graph.relationships)
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


def _build_incoming_relationships(
    relationships: Dict[str, List[Tuple[str, str, float]]],
) -> Dict[str, List[Tuple[str, str, float]]]:
    """
    Construct a mapping of incoming relationships keyed by target asset identifier.

    Parameters:
        relationships (Dict[str, List[Tuple[str, str, float]]]): Mapping from source asset id to a list of outgoing relationships;
            each relationship is a tuple of (target_asset_id, relationship_type, strength).

    Returns:
        Dict[str, List[Tuple[str, str, float]]]: Mapping from target asset id to a list of incoming relationships;
            each incoming relationship is a tuple of (source_asset_id, relationship_type, strength).
    """
    incoming_relationships: Dict[str, List[Tuple[str, str, float]]] = {}
    for source, rels in relationships.items():
        for target, rel_type, strength in rels:
            incoming_relationships.setdefault(target, []).append((source, rel_type, strength))
    return incoming_relationships


def _deserialize_asset(data: Dict[str, Any]) -> Asset:
    """
    Deserialize a serialized asset dictionary into an Asset (or appropriate subclass) instance.

    The input dictionary must include a "__type__" key with the asset subclass name (e.g. "Equity", "Bond"); unknown types default to `Asset`. The function copies the input dict, converts an "asset_class" field to the `AssetClass` enum when present, and constructs the corresponding dataclass.

    Parameters:
        data (Dict[str, Any]): Serialized asset data; should include a "__type__" discriminator.

    Returns:
        Asset: An instance of `Asset` or one of its subclasses reconstructed from `data`.
    """
    data = dict(data)  # Make a copy to avoid modifying the original
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
    Reconstructs a RegulatoryEvent from its serialized dictionary
    representation.
    The input dictionary is copied and its "event_type" field is converted to
    the RegulatoryActivity enum before creating the RegulatoryEvent instance.

    Parameters:
        data(Dict[str, Any]): Serialized event payload — must include an
            "event_type" value compatible with RegulatoryActivity and the
            remaining fields accepted by RegulatoryEvent.

    Returns:
        RegulatoryEvent: The deserialized RegulatoryEvent instance.
    """
    data = dict(data)
    data["event_type"] = RegulatoryActivity(data["event_type"])
    return RegulatoryEvent(**data)


def _deserialize_graph(payload: Dict[str, Any]) -> AssetRelationshipGraph:
    """
    Reconstructs an AssetRelationshipGraph from a serialized payload.

    Parameters:
        payload(Dict[str, Any]): Serialized graph payload containing the keys
            "assets", "regulatory_events", "relationships", etc.

    Returns:
        AssetRelationshipGraph: Graph reconstructed from the payload.
    """
    graph = AssetRelationshipGraph()
    for asset_data in payload.get("assets", []):
        asset = _deserialize_asset(dict(asset_data))
        graph.add_asset(asset)

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
        path(Path): Filesystem path to the cache JSON file to read.

    Returns:
        AssetRelationshipGraph: The graph reconstructed from the JSON payload.
    """
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    return _deserialize_graph(payload)


def _save_to_cache(graph: AssetRelationshipGraph, path: Path) -> None:
    """
    Write the serialized AssetRelationshipGraph to the given filesystem path as JSON.

    Creates parent directories if necessary and overwrites any existing file at the path.
    The file is UTF-8 encoded and formatted with two-space indentation.

    Parameters:
        graph (AssetRelationshipGraph): Graph to serialize and save.
        path (Path): Destination filesystem path for the JSON file.
    """
    payload = _serialize_graph(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
