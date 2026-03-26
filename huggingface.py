from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QDialog,
    QInputDialog,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from qgis.core import QgsCoordinateTransform, QgsProject, QgsVectorLayer

import os
import re
import processing
import requests

# Inference Providers — OpenAI-compatible chat API (NOT /models/{name}; that URL returns 404).
# Token: env HF_TOKEN, or QGIS setting (first prompt), or https://huggingface.co/settings/tokens
CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
# Default router model; can be overridden by env var `HF_MODEL`.
# If you see `model_not_supported`, change `HF_MODEL` to a router-compatible chat model.
MODEL = os.environ.get(
    "HF_MODEL",
    "deepseek-ai/DeepSeek-V3:fastest",
)

SETTINGS_KEY = "buntinglabs-kue/huggingface_token"

# vgrid processing provider: vgrid_provider.VgridProvider.id() == "vgrid"
# Generators supported by this script (vgrid processing provider)
VGRID_H3_ALG_ID = "vgrid:h3_gen"
VGRID_S2_ALG_ID = "vgrid:s2_gen"
VGRID_A5_ALG_ID = "vgrid:a5_gen"
VGRID_RHEALPIX_ALG_ID = "vgrid:rhealpix_gen"

GRID_ALG_IDS = {
    "H3": VGRID_H3_ALG_ID,
    "S2": VGRID_S2_ALG_ID,
    "A5": VGRID_A5_ALG_ID,
    "rHEALPix": VGRID_RHEALPIX_ALG_ID,
}

# Grid generators require extent only above a certain resolution (see each *_gen prepareAlgorithm)
GRID_EXTENT_MIN_RES = {
    "H3": 4,
    "S2": 8,
    "A5": 8,
    "rHEALPix": 5,
}

# H3 resolutions are 0..15 (same range as plugin settings / h3gen).
# Kept for backwards compatibility with the existing h3 parser.
H3_RES_MIN = 0
H3_RES_MAX = 15


def _default_h3_resolution():
    try:
        from settings import settings

        return int(settings.h3Res)
    except Exception:
        return 7


def _parse_h3_resolution(text):
    """Pick resolution in [H3_RES_MIN, H3_RES_MAX] from user text."""
    t = text.lower()
    for pattern in (
        r"resolution\s*:?\s*(\d{1,2})",
        r"\bres(?:olution)?\s+(\d{1,2})\b",
        r"\bh3\s+(?:grid\s+)?(?:at\s+)?(\d{1,2})\b",
        r"\br\s*=\s*(\d{1,2})",
    ):
        m = re.search(pattern, t)
        if m:
            v = int(m.group(1))
            if H3_RES_MIN <= v <= H3_RES_MAX:
                return v
    for m in re.finditer(r"\b(\d{1,2})\b", t):
        v = int(m.group(1))
        if H3_RES_MIN <= v <= H3_RES_MAX:
            return v
    return _default_h3_resolution()


def _user_wants_h3_grid(text):
    # Backwards compatibility: keep the original function name but delegate to
    # the new grid detection logic.
    return bool(_detect_requested_grid_type(text) == "H3")


def _detect_requested_grid_type(text):
    t = text.lower()
    # Use word-boundaries for s2/a5/h3, but for rhealpix use a looser match.
    if "rhealpix" in t or "rheal" in t:
        return "rHEALPix"
    if re.search(r"\bs2\b", t):
        return "S2"
    if re.search(r"\ba5\b", t):
        return "A5"
    if re.search(r"\bh3\b", t):
        return "H3"
    return None


def _grid_resolution_config(grid_type):
    """
    Returns (min_res, max_res, default_res) for the selected grid_type,
    based on the plugin settings.
    """
    try:
        from settings import settings as vsettings

        cfg = vsettings.getResolution(grid_type)
        return cfg
    except Exception:
        return None


def _parse_resolution_for_grid(text, grid_type):
    """
    Parse resolution from user text and validate it against plugin settings.
    Falls back to the plugin's default resolution for that grid.
    """
    cfg = _grid_resolution_config(grid_type)
    default_res = 1
    if cfg:
        _, _, default_res = cfg

    t = text.lower()
    # Patterns that usually work in chat: "resolution 10", "res=10", "h3 7", etc.
    patterns = [
        r"resolution\s*:?\s*(\d{1,3})",
        r"\bres(?:olution)?\s*=?\s*(\d{1,3})",
    ]

    key_token = grid_type.lower().replace(" ", "")
    if key_token == "rhealpix":
        # allow "rhealp" / "r heal pix"
        patterns += [
            r"r\s*heal\s*p\s*(?:ix)?\s*(\d{1,3})",
            r"rhealpix\s*(?:grid\s*)?(?:at\s*)?(\d{1,3})",
        ]
    else:
        patterns += [
            rf"{re.escape(key_token)}\s*(?:grid\s*)?(?:at\s*)?(\d{{1,3}})",
        ]

    for pattern in patterns:
        m = re.search(pattern, t)
        if not m:
            continue
        v = int(m.group(1))
        if cfg:
            min_res, max_res, _ = cfg
            if min_res <= v <= max_res:
                return v
            # out of range -> fallback to default
            return default_res
        return v

    # Fallback: if no explicit "resolution", try any 0..100 number in the message.
    for m in re.finditer(r"\b(\d{1,3})\b", t):
        v = int(m.group(1))
        if cfg:
            min_res, max_res, _ = cfg
            if min_res <= v <= max_res:
                return v
        else:
            return v
    return default_res


def _user_requests_grid(text):
    t = text.lower()
    grid_action_words = ("generate", "create", "make", "draw", "run", "resolution")
    has_action = any(w in t for w in grid_action_words)
    grid_type = _detect_requested_grid_type(text)
    return has_action and grid_type is not None


def _current_map_extent_project_crs_string():
    """
    Extent string for vgrid:h3_gen EXTENT parameter.

    H3Gen reprojects using QgsProject.instance().crs() → EPSG:4326, so the extent
    must be expressed in project CRS (not WGS84), or cells end up empty.
    """
    try:
        from qgis.utils import iface

        canvas = iface.mapCanvas()
        if canvas is None:
            return None
        ext = canvas.extent()
        project_crs = QgsProject.instance().crs()
        map_crs = canvas.mapSettings().destinationCrs()
        if map_crs != project_crs:
            xform = QgsCoordinateTransform(map_crs, project_crs, QgsProject.instance())
            ext = xform.transformBoundingBox(ext)
        authid = project_crs.authid()
        return (
            f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()} "
            f"[{authid}]"
        )
    except Exception:
        return None


def _run_vgrid_grid(grid_type, resolution, feedback_append):
    """
    Run vgrid DGGS generator for the requested grid_type.
    """
    grid_type = str(grid_type)
    alg_id = GRID_ALG_IDS.get(grid_type)
    if not alg_id:
        feedback_append(f"{grid_type}: unsupported grid type.")
        return False

    resolution = int(resolution)
    extent_str = _current_map_extent_project_crs_string()

    # If the algorithm refuses to run without extent at high resolutions, explain it.
    extent_required_above = GRID_EXTENT_MIN_RES.get(grid_type, 999999)
    if resolution > extent_required_above and not extent_str:
        feedback_append(
            f"{grid_type}: resolution > {extent_required_above} needs a map canvas extent — "
            f"zoom/pan so the map has a valid extent, then try again."
        )
        return False

    # Base params (all generators take RESOLUTION + OUTPUT; most take EXTENT)
    params = {
        "RESOLUTION": resolution,
        "OUTPUT": f"memory:{grid_type}_grid_{resolution}",
    }
    if extent_str:
        params["EXTENT"] = extent_str

    # Antimeridian handling differs by generator.
    if grid_type in ("H3", "S2", "rHEALPix"):
        params["SHIFT_ANTIMERIDIAN"] = True
        params["SPLIT_ANTIMERIDIAN"] = False
    elif grid_type == "A5":
        params["SPLIT_ANTIMERIDIAN"] = False

    try:
        result = processing.run(alg_id, params)
    except Exception as e:
        feedback_append(f"{grid_type}: processing failed — {e}")
        return False

    out = result.get("OUTPUT")
    if out is None:
        feedback_append(f"{grid_type}: no OUTPUT layer returned.")
        return False

    QgsProject.instance().addMapLayer(out)
    feedback_append(f"{grid_type}: added layer “{out.name()}” at resolution {resolution}.")
    return True


def _first_valid_vector_layer():
    """native:buffer needs a vector layer; map order often starts with XYZ/WMS rasters."""
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            return layer
    return None


def get_hf_token(parent=None):
    t = os.environ.get("HF_TOKEN", "").strip()
    if t:
        return t
    t = QSettings().value(SETTINGS_KEY, "", type=str) or ""
    t = str(t).strip()
    if t:
        return t
    if parent is None:
        return ""
    text, ok = QInputDialog.getText(
        parent,
        "Hugging Face",
        "Paste your Hugging Face access token (saved in QGIS settings).\n"
        "Create one at huggingface.co/settings/tokens — enable Inference Providers.",
        QLineEdit.EchoMode.Password,
    )
    if ok and text.strip():
        QSettings().setValue(SETTINGS_KEY, text.strip())
        return text.strip()
    return ""


def query_hf_api(prompt, parent=None):
    token = get_hf_token(parent)
    if not token:
        return (
            "Error: no token — set environment variable HF_TOKEN, or enter it when prompted "
            "(run this dialog from the console so a window can appear)."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
    }
    response = requests.post(CHAT_URL, headers=headers, json=payload, timeout=120)
    if response.status_code == 200:
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return str(data)
    return f"Error: {response.status_code} {response.text[:500]}"


class QGISFreeAPIChat(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QGIS AI Chatbot (Free API)")
        self.resize(500, 500)

        # Remember last requested grid type so follow-ups like
        # "resolution 4 instead" apply to the same grid.
        self.last_grid_type = None

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)

        self.input_line = QLineEdit()
        self.input_line.returnPressed.connect(self.handle_input)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.handle_input)

        layout = QVBoxLayout()
        layout.addWidget(self.chat_display)
        layout.addWidget(self.input_line)
        layout.addWidget(self.send_button)
        self.setLayout(layout)
        # Ask once if no env var and no saved token (saved under QGIS settings).
        get_hf_token(self)

    def handle_input(self):
        user_text = self.input_line.text().strip()
        if not user_text:
            return
        self.chat_display.append(f"You: {user_text}")
        self.input_line.clear()

        # If the user explicitly asks for a grid (or a resolution change for the
        # last grid), generate it directly and skip the HF chat response.
        grid_type = _detect_requested_grid_type(user_text)
        if _user_requests_grid(user_text) and grid_type:
            res = _parse_resolution_for_grid(user_text, grid_type)
            self.chat_display.append(
                f"AI: Generating {grid_type} grid at resolution {res}..."
            )
            ok = _run_vgrid_grid(grid_type, res, self.chat_display.append)
            if ok:
                self.last_grid_type = grid_type
            return

        # Follow-up: "resolution 4 instead" (no grid type) -> reuse last_grid_type.
        if self.last_grid_type is not None and grid_type is None:
            if _parse_resolution_for_grid(user_text, self.last_grid_type) is not None:
                # Heuristic: only treat it as a resolution update if the text contains
                # "resolution" or "res" with a number.
                t = user_text.lower()
                if re.search(r"\b(res(?:olution)?\s*=?\s*\d{1,3}|\d{1,3}\b)\b", t):
                    res = _parse_resolution_for_grid(user_text, self.last_grid_type)
                    self.chat_display.append(
                        f"AI: Updating {self.last_grid_type} grid to resolution {res}..."
                    )
                    ok = _run_vgrid_grid(
                        self.last_grid_type, res, self.chat_display.append
                    )
                    if ok:
                        # Resolution-only update keeps the same grid type.
                        pass
                    return

        # Otherwise, use the HF chat response for non-grid requests (e.g. buffer).
        ai_response = query_hf_api(user_text, parent=self)
        self.chat_display.append(f"AI: {ai_response}")

        if "buffer" in ai_response.lower():
            layer = _first_valid_vector_layer()
            if layer is None:
                self.chat_display.append(
                    "AI: Buffer skipped — add a vector layer to the project (basemaps are rasters, not valid INPUT)."
                )
            else:
                result = processing.run(
                    "native:buffer",
                    {
                        "INPUT": layer,
                        "DISTANCE": 50,
                        "SEGMENTS": 5,
                        "END_CAP_STYLE": 0,
                        "JOIN_STYLE": 0,
                        "MITER_LIMIT": 2,
                        "DISSOLVE": False,
                        "OUTPUT": "memory:",
                    },
                )
                QgsProject.instance().addMapLayer(result["OUTPUT"])
                self.chat_display.append(
                    f"AI: Buffer created on vector layer “{layer.name()}”."
                )


dialog = QGISFreeAPIChat()
dialog.show()
