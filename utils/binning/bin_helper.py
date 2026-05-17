import statistics
from collections import Counter, defaultdict

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField

from vgrid.utils.io import stat_column_name


def get_default_stats_structure():
    return {
        "count": 0,
        "sum": [],
        "mean": [],
        "min": [],
        "max": [],
        "median": [],
        "std": [],
        "var": [],
        "range": [],
        "values": [],
    }


def safe_float(value):
    """Convert QVariant or similar to float if possible."""
    if isinstance(value, QVariant):
        if not value.isValid() or value.isNull():
            return None
        value = value.value()

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_category(cat):
    """Normalize category strings to avoid duplicates due to case/spacing."""
    if not isinstance(cat, str):
        cat = str(cat)
    return cat.strip().lower()


def bin_stat_column_name(stats, numeric_field=None, category_field=None, category_value=None):
    """Match vgrid DGGS binning column names via :func:`stat_column_name`."""
    cat = category_value if category_field else None
    if stats == "count":
        return stat_column_name("count", category_value=cat)
    return stat_column_name(stats, numeric_field=numeric_field, category_value=cat)


def stat_field_type(stats):
    if stats in ("count", "variety"):
        return QVariant.Int
    if stats in ("minority", "majority"):
        return QVariant.String
    return QVariant.Double


def append_bin_stat_fields(
    out_fields,
    all_categories,
    stats,
    numeric_field=None,
    category_field=None,
):
    """Append statistic columns to ``out_fields`` using vgrid naming."""
    for cat in sorted(all_categories):
        col_name = bin_stat_column_name(
            stats,
            numeric_field=numeric_field,
            category_field=category_field,
            category_value=cat,
        )
        out_fields.append(QgsField(col_name, stat_field_type(stats)))


def compute_stat_value(values, stats):
    """Compute one statistic from the accumulated per-category structure."""
    if stats == "count":
        return values["count"]
    if stats == "sum":
        return sum(values["sum"]) if values["sum"] else None
    if stats == "min":
        return min(values["min"]) if values["min"] else None
    if stats == "max":
        return max(values["max"]) if values["max"] else None
    if stats == "mean":
        return statistics.mean(values["mean"]) if values["mean"] else None
    if stats == "median":
        return statistics.median(values["median"]) if values["median"] else None
    if stats == "std":
        return statistics.stdev(values["std"]) if len(values["std"]) > 1 else 0
    if stats == "var":
        return statistics.variance(values["var"]) if len(values["var"]) > 1 else 0
    if stats == "range":
        return (
            max(values["range"]) - min(values["range"]) if values["range"] else 0
        )
    if stats == "minority":
        freq = Counter(values["values"])
        return min(freq.items(), key=lambda x: x[1])[0] if freq else None
    if stats == "majority":
        freq = Counter(values["values"])
        return max(freq.items(), key=lambda x: x[1])[0] if freq else None
    if stats == "variety":
        return len(set(values["values"]))
    raise ValueError(f"Unsupported statistic: {stats}")


def stat_props_for_category(
    values,
    stats,
    numeric_field=None,
    category_field=None,
    category_value=None,
):
    """Return ``{column_name: value}`` for one category bucket."""
    col_name = bin_stat_column_name(
        stats,
        numeric_field=numeric_field,
        category_field=category_field,
        category_value=category_value,
    )
    return {col_name: compute_stat_value(values, stats)}


def append_stats_value(
    h3_bins, h3_id, props, stats, numeric_field=None, category_field=None
):
    category_value = props.get(category_field, "all") if category_field else "all"
    norm_category = normalize_category(category_value)

    if h3_id not in h3_bins:
        h3_bins[h3_id] = defaultdict(get_default_stats_structure)

    stats_struct = h3_bins[h3_id][norm_category]

    if stats == "count":
        stats_struct["count"] += 1

    elif stats in ["minority", "majority", "variety"]:
        value = props.get(numeric_field or category_field)
        if value is not None:
            stats_struct["values"].append(value)

    elif numeric_field:
        raw_value = props.get(numeric_field)
        val = safe_float(raw_value)
        if val is not None:
            stats_struct[stats].append(val)
