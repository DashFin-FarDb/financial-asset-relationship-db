import json
import logging
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yfinance as yf

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
        Builds an asset relationship graph using current market data or a
        fallback dataset when real data is unavailable.

        Attempts to load a cached graph if a cache path exists;
        if network access is disabled, returns a fallback graph.

        When fetching succeeds and a cache path is configured, the populated
        graph is persisted to cache.
        On any fetch or build failure, falls back to the sample/fallback
        dataset.

        Returns:
            AssetRelationshipGraph: Populated graph built from real financial
                data; a fallback/sample graph if loading or fetching fails
                or network is disabled.
        """
        if self.cache_path and self.cache_path.exists():
            try:
                logger.info(
                    "Loading asset graph from cache at %s",
                    self.cache_path,
                )
                return _load_from_cache(self.cache_path)
            except Exception:
                logger.exception(
                    "Failed to load cached dataset; proceeding with standard fetch",
                )

        if not self.enable_network:
            logger.info(
                "Network fetching disabled. Using fallback dataset "
                "if available."
            )
            return self._fallback()

        logger.info(
            "Creating database with real financial data "
            "from Yahoo Finance"
        )
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

        except Exception as exc:
            logger.error("Failed to create real database: %s", exc)
        logger.warning("Falling back to sample data due to real data fetch failure")
        return self._fallback()

    def _persist_cache(self, graph: AssetRelationshipGraph) -> None:
        """Persist the asset relationship graph to the cache file specified by
        cache_path.

        Serializes the graph to a temporary file and atomically replaces the cache file.
        Logs an exception if persisting the cache fails.
        """
        import os
        import tempfile

        try:
            cache_path = Path(self.cache_path).expanduser().resolve()
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

    def _fallback(self) -> AssetRelationshipGraph:
        """Return a fallback AssetRelationshipGraph using sample data.

        Called when real data fetching fails; returns a default sample graph.
        """
        if self.fallback_factory:
            return self.fallback_factory()

        from src.data.sample_data import create_sample_database

        return create_sample_database()

    @staticmethod
    def _fetch_equity_data() -> List[Equity]:
        """Fetches current market data for major equities and returns Equity objects."""
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
                info = ticker.info
                hist = ticker.history(period="1d")

                if hist.empty:
                    logger.warning("No price data for %s", symbol)
                    continue

                current_price = float(hist["Close"].iloc[-1])

                equity = Equity(
                    id=symbol,
                    symbol=symbol,
                    name=name,
                    asset_class=AssetClass.EQUITY,
    @staticmethod
    def _fetch_bond_data() -> List[Bond]:
        """
        Fetch bond and treasury ETF market data and return Bond instances used
        as fixed-income proxies.

        Retrieves price and metadata for a small set of bond and treasury ETFs
        (used as proxies for individual bonds). If yield information is missing,
        `yield_to_maturity` defaults to 0.03 and
        `coupon_rate` defaults to 0.025; maturity dates and some
        fields are approximate for ETF-based proxies.

        Returns:
            List[Bond]: Bond instances populated with id, symbol, name,
            asset_class, sector, price, yield_to_maturity, coupon_rate,
            maturity_date, credit_rating, and issuer_id.
        """
        # For bonds, we'll use Treasury ETFs and bond proxies since
        # individual bonds are harder to access
        bond_symbols = {
            "TLT": ("iShares 20+ Year Treasury Bond ETF", "Government", None, "AAA"),
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

                if hist.empty:
                    logger.warning("No price data for %s", symbol)
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
                        "yield", 0.03
                    ),  # Default 3% if not available
                    coupon_rate=info.get(
                        "yield", 0.025
                    ),  # Approximate
                    maturity_date="2035-01-01",  # Approximate for ETFs
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
            except Exception as e:
                logger.error("Failed to fetch bond data for %s: %s", symbol, e)
                continue

        return bonds

    @staticmethod
    def _fetch_commodity_data() -> List[Commodity]:
        """Fetch real commodity futures data."""
        # Define key commodity futures and their characteristics.
        commodity_symbols: Dict[str, Tuple[str, str, float, float]] = {
            # symbol: (name, sector, contract_size, volatility)
            # Example entries (adjust or extend as needed elsewhere in the file):
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

                if hist.empty:
                    logger.warning("No price data for %s", symbol)
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
                    delivery_date="2025-03-31",  # Approximate
                    volatility=volatility,
                )
                commodities.append(commodity)
                logger.info(
                    "Fetched %s: %s at $%.2f",
                    symbol,
                    name,
                    current_price,
                )

            except Exception as e:
                logger.error("Failed to fetch commodity data for %s: %s", symbol, e)
                continue

        return commodities

    @staticmethod
    def _fetch_currency_data() -> List[Currency]:
        """Fetch real currency exchange rate data"""
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

                if hist.empty:
                    logger.warning("No price data for %s", symbol)
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
                logger.info("Fetched %s: %s at %.4f", symbol, name, current_rate)

            except Exception as e:
                logger.error("Failed to fetch currency data for %s: %s", symbol, e)
                continue

        return currencies

    @staticmethod
    def _create_regulatory_events() -> List[RegulatoryEvent]:
        """
        Create a small list of regulatory events associated with fetched assets.

        Includes three sample events (an Apple earnings report, a Microsoft dividend
        announcement, and an Exxon Mobil SEC filing). Each event contains an id,
        asset_id, event_type, date, description, impact_score, and related_assets.

        Returns:
            List[RegulatoryEvent]: List of RegulatoryEvent instances representing the sample events.
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
           description=(
               "10-K Filing - Increased oil reserves and sustainability "
               "initiatives"
           ),
           impact_score=0.05,
           related_assets=["CL_FUTURE"],  # Related to oil futures
       )
       events.append(xom_filing)

       return events


def create_real_database() -> AssetRelationshipGraph:
    """
    Builds an AssetRelationshipGraph populated with market data, falling back to
    sample data when necessary.

    Creates or loads a graph containing assets, regulatory events and their
    relationships by attempting to:
    - load a cached graph if available,
    - fetch real market data when network access is enabled,
    - otherwise fall back to a provided or built sample dataset.

    Returns:
        AssetRelationshipGraph: The constructed graph populated with assets,
        regulatory events and relationship mappings; the content may come from
        the cache, a real-data fetch, or the sample fallback.
    """
    fetcher = RealDataFetcher()
    return fetcher.create_real_database()


def _enum_to_value(value: Any) -> Any:
    """
    Convert an Enum instance to its underlying value.
    Return the input unchanged otherwise.

    Parameters:
        value (Any): The value to normalise.
            If `value` is an `Enum` member, its `.value` is returned.

    Returns:
        Any: The underlying value of the `Enum` member if applicable,
        otherwise the original value.
    """
    return value.value if isinstance(value, Enum) else value



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
     Serialize an AssetRelationshipGraph into a JSON-serializable dictionary.

     The resulting dictionary contains serialized assets and regulatory events,
     a mapping of outgoing relationships keyed by source asset id, and a computed
     mapping of incoming relationships keyed by target asset id.

     Parameters:
         graph (AssetRelationshipGraph): The graph to serialize.

     Returns:
         Dict[str, Any]: A dictionary with the following top-level keys:
             - "assets": list of serialized asset objects
               (each includes a "__type__" field).
             - "regulatory_events": list of serialized regulatory event objects.
             - "relationships": mapping from source asset id to a list of outgoing
               relationships; each relationship is a dict
               with keys "target", "relationship_type", and "strength".
             - "incoming_relationships": mapping from target asset id to a list of incoming
               relationships; each relationship is a dict
               with keys "source", "relationship_type", and "strength".
     """
     # Compute incoming_relationships from relationships

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
    Deserialize a dictionary representation of an asset back into an Asset instance.

    Parameters:
        data(Dict[str, Any]): Dictionary containing asset data
            with a "__type__" key indicating the asset subclass.

    Returns:
        Asset: An Asset instance (or subclass like Equity, Bond, etc.)
            constructed from the provided data.
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
    Persist an AssetRelationshipGraph to a JSON file at the given filesystem path.

    The function serialises the provided graph to JSON
    (UTF - 8, pretty - printed with two - space indentation),
    creates parent directories if necessary,
    and overwrites any existing file at the path.

    Parameters:
        graph(AssetRelationshipGraph): The graph to persist.
        path(Path): Filesystem path where the JSON representation will be written.
    """
    payload = _serialize_graph(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, indent=2)
