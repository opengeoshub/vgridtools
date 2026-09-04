#!/usr/bin/env python3
"""Qualify QGIS enums for the plugins.qgis.org Qt6 checker."""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Longest / most specific first so we never double-qualify.
REPLACEMENTS = [
    ("QgsWkbTypes.PolygonGeometry", "QgsWkbTypes.GeometryType.PolygonGeometry"),
    ("QgsWkbTypes.LineGeometry", "QgsWkbTypes.GeometryType.LineGeometry"),
    ("QgsWkbTypes.PointGeometry", "QgsWkbTypes.GeometryType.PointGeometry"),
    ("QgsWkbTypes.MultiLineString", "QgsWkbTypes.Type.MultiLineString"),
    ("QgsWkbTypes.MultiPolygon", "QgsWkbTypes.Type.MultiPolygon"),
    ("QgsWkbTypes.MultiPoint", "QgsWkbTypes.Type.MultiPoint"),
    ("QgsWkbTypes.LineString", "QgsWkbTypes.Type.LineString"),
    ("QgsWkbTypes.Polygon", "QgsWkbTypes.Type.Polygon"),
    ("QgsWkbTypes.Point", "QgsWkbTypes.Type.Point"),
    ("Qgis.Warning", "Qgis.MessageLevel.Warning"),
    ("Qgis.Info", "Qgis.MessageLevel.Info"),
    ("Qgis.Critical", "Qgis.MessageLevel.Critical"),
    ("Qgis.Success", "Qgis.MessageLevel.Success"),
    ("QgsVertexMarker.ICON_BOX", "QgsVertexMarker.IconType.ICON_BOX"),
    ("QgsVertexMarker.ICON_CROSS", "QgsVertexMarker.IconType.ICON_CROSS"),
    ("QgsProcessingParameterNumber.Integer", "QgsProcessingParameterNumber.Type.Integer"),
    ("QgsProcessingParameterNumber.Double", "QgsProcessingParameterNumber.Type.Double"),
    ("QgsFeatureSink.FastInsert", "QgsFeatureSink.Flag.FastInsert"),
    ("QgsProcessing.TypeVectorPolygon", "QgsProcessing.SourceType.TypeVectorPolygon"),
    ("QgsProcessing.TypeVectorPoint", "QgsProcessing.SourceType.TypeVectorPoint"),
    ("QgsProcessing.TypeVectorLine", "QgsProcessing.SourceType.TypeVectorLine"),
    ("QgsProcessing.TypeVector", "QgsProcessing.SourceType.TypeVector"),
    ("QgsProcessingParameterField.String", "QgsProcessingParameterField.DataType.String"),
    ("QgsProcessingParameterField.Numeric", "QgsProcessingParameterField.DataType.Numeric"),
]

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "dggrid", "scripts"}


def should_skip(path: pathlib.Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def main() -> None:
    changed_files = 0
    total_subs = 0
    for path in ROOT.rglob("*.py"):
        if should_skip(path):
            continue
        text = path.read_text(encoding="utf-8")
        new = text
        file_subs = 0
        for old, replacement in REPLACEMENTS:
            count = new.count(old)
            if not count:
                continue
            # Avoid replacing already-qualified names that contain the old token
            # as a suffix after an extra enum type (handled by ordering).
            new = new.replace(old, replacement)
            file_subs += count
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed_files += 1
            total_subs += file_subs
            print(f"{path.relative_to(ROOT)}: {file_subs}")
    print(f"Updated {changed_files} files, {total_subs} substitutions")


if __name__ == "__main__":
    main()
