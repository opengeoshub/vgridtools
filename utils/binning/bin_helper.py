from collections import defaultdict
from qgis.PyQt.QtCore import QVariant

def get_default_stats_structure():
    return {
        'count': 0,
        'sum': [],
        'mean': [],
        'min': [],
        'max': [],
        'median': [],
        'std': [],
        'var': [],
        'range': [],
        'values': []
    }

def safe_float(value):
    """Convert QVariant or similar to float if possible."""
    if isinstance(value, QVariant):
        if not value.isValid() or value.isNull():
            return None
        value = value.value()  # Works for most QVariant types

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_category(cat):
    """Normalize category strings to avoid duplicates due to case/spacing."""
    if not isinstance(cat, str):
        cat = str(cat)
    return cat.strip().lower()

def append_stats_value(h3_bins, h3_id, props, stats, numeric_field=None, category_field=None):
    # Get and normalize category
    category_value = props.get(category_field, "all") if category_field else "all"
    norm_category = normalize_category(category_value)

    if h3_id not in h3_bins:
        h3_bins[h3_id] = defaultdict(get_default_stats_structure)

    stats_struct = h3_bins[h3_id][norm_category]

    if stats == 'count':
        stats_struct['count'] += 1

    elif stats in ['minority', 'majority', 'variety']:
        value = props.get(numeric_field or category_field)
        if value is not None:
            stats_struct['values'].append(value)

    elif numeric_field:
        raw_value = props.get(numeric_field)
        val = safe_float(raw_value)
        if val is not None:
            stats_struct[stats].append(val)