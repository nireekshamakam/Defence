"""Map BB tickers (from the source Excel) to Yahoo Finance symbols.

The Excel's `BB` column contains Bloomberg shortcodes (e.g., HNAL) and the
`Exch` column contains NSE tickers (e.g., HAL). Yahoo Finance expects
'<NSE_TICKER>.NS' (or '.BO' for BSE). We prefer the NSE listing for
liquidity. Override any quirks below.
"""

# Manual overrides where the Excel value doesn't cleanly map to NSE symbol.
# Key = bb_ticker (uppercase), value = Yahoo symbol.
BB_TO_YAHOO_OVERRIDES: dict[str, str] = {
    # Defence majors — most of these match exch ticker + .NS but pin them
    "HNAL": "HAL.NS",
    "BHE": "BEL.NS",
    "BDL": "BDL.NS",
    "MAZDOCKS": "MAZDOCK.NS",
    "GRSE": "GRSE.NS",
    "COCHIN": "COCHINSHIP.NS",
    "BEML": "BEML.NS",
    "MIDHANI": "MIDHANI.NS",
    "DATAPATT": "DATAPATTNS.NS",
    "PARAS": "PARAS.NS",
}

# Companies known to be unlisted / private (won't try to fetch live data).
UNLISTED: set[str] = {"SMPP", "JJG AERO", "AEQUS"}


def derive_yahoo_symbol(bb_ticker: str | None, exchange_ticker: str | None) -> str | None:
    """Best-guess Yahoo symbol. Returns None for unlisted companies."""
    bb = (bb_ticker or "").strip().upper()
    exch = (exchange_ticker or "").strip().upper()

    if bb in UNLISTED or (not bb and not exch):
        return None
    if bb in BB_TO_YAHOO_OVERRIDES:
        return BB_TO_YAHOO_OVERRIDES[bb]
    if exch:
        return f"{exch}.NS"
    if bb:
        return f"{bb}.NS"
    return None
