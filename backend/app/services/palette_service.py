from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, not_found
from app.schemas.palette import PaletteCreate, PaletteUpdate
from app.services.color_matcher import colorimetry_status, palette_records_lab

_PALETTE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,62}$")
_TIER_COUNTS = (24, 48, 72, 96, 120, 144, 168, 192, 221, 264, 291)
_MARD_TIER_ID = re.compile(r"^mard-(24|48|72|96|120|144|168|192|221|264)$")


class PaletteService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.custom_dir = self.settings.storage_dir / "palettes"
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        self.builtin_dir = Path(__file__).resolve().parents[1] / "palettes"

    def _builtin_path(self, palette_id: str) -> Path:
        return self.builtin_dir / f"{palette_id}.json"

    def _custom_path(self, palette_id: str) -> Path:
        if not _PALETTE_ID.fullmatch(palette_id):
            raise not_found("palette", palette_id)
        return self.custom_dir / f"{palette_id}.json"

    @staticmethod
    def _tier_size(palette_id: str) -> int | None:
        match = _MARD_TIER_ID.fullmatch(palette_id)
        return int(match.group(1)) if match else None

    @staticmethod
    def _load(path: Path, palette_id: str) -> dict[str, Any]:
        if not path.is_file():
            raise not_found("palette", palette_id)
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _expand_series(palette: dict[str, Any]) -> dict[str, Any]:
        """Expand compact manufacturer palette series into the public color list.

        Full color charts are considerably easier to review and maintain as a set
        of named series. API consumers always receive the same ``colors`` list,
        whether the source uses this compact representation or a custom list.
        """
        if "colors" in palette or not isinstance(palette.get("series"), list):
            return palette

        colors: list[dict[str, Any]] = []
        for series in palette["series"]:
            series_id = str(series.get("id", ""))
            category = str(series.get("name_zh", series_id))
            effect = str(series.get("effect", "standard"))
            for code, hex_value in dict(series.get("colors", {})).items():
                normalized_hex = str(hex_value).upper().lstrip("#")
                if not re.fullmatch(r"[0-9A-F]{6}", normalized_hex):
                    raise AppError(500, "INVALID_PALETTE", f"色卡 {palette.get('id', '')} 存在非法颜色值")
                colors.append(
                    {
                        "code": str(code),
                        "name_zh": f"{category} {code}",
                        "name_en": f"MARD {code}",
                        "hex": f"#{normalized_hex}",
                        "rgb": [int(normalized_hex[index : index + 2], 16) for index in (0, 2, 4)],
                        "category": category,
                        "series": series_id,
                        "effect": effect,
                        "available": True,
                    }
                )
        palette["colors"] = colors
        return palette

    @staticmethod
    def _validate(palette: dict[str, Any], status_code: int = 500) -> dict[str, Any]:
        colors = palette.get("colors")
        if not isinstance(colors, list) or not colors:
            raise AppError(status_code, "INVALID_PALETTE", f"色卡 {palette.get('id', '')} 不包含颜色")
        codes = [str(color.get("code", "")) for color in colors if isinstance(color, dict)]
        if len(codes) != len(colors) or not all(codes) or len(codes) != len(set(codes)):
            raise AppError(
                status_code,
                "INVALID_PALETTE",
                f"色卡 {palette.get('id', '')} 存在重复或缺失的色号",
            )
        measured_count = 0
        for color in colors:
            measured_lab = color.get("measured_lab")
            if measured_lab is None:
                continue
            measured_count += 1
            try:
                value = np.asarray(measured_lab, dtype=np.float64)
            except (TypeError, ValueError) as exc:
                raise AppError(
                    status_code,
                    "INVALID_PALETTE",
                    f"色卡 {palette.get('id', '')} 的实体 LAB 数据无效",
                ) from exc
            if (
                value.shape != (3,)
                or not np.all(np.isfinite(value))
                or not 0 <= value[0] <= 100
                or np.any(np.abs(value[1:]) > 160)
            ):
                raise AppError(
                    status_code,
                    "INVALID_PALETTE",
                    f"色卡 {palette.get('id', '')} 的实体 LAB 数据无效",
                )
        calibration = palette.get("calibration")
        if measured_count:
            if not isinstance(calibration, dict) or not str(calibration.get("source", "")).strip():
                raise AppError(status_code, "INVALID_PALETTE", "实体 LAB 色卡缺少 calibration 测量来源")
            if (
                calibration.get("color_space", "CIELAB") != "CIELAB"
                or calibration.get("illuminant", "D65") != "D65"
                or calibration.get("observer", "2_degree") != "2_degree"
            ):
                raise AppError(
                    status_code,
                    "INVALID_PALETTE",
                    "实体 LAB 色卡当前只支持 CIELAB D65/2° 数据",
                )
        elif calibration is not None:
            raise AppError(status_code, "INVALID_PALETTE", "calibration 需要至少一个带 measured_lab 的色号")
        return palette

    @staticmethod
    def _annotate_colorimetry(palette: dict[str, Any]) -> dict[str, Any]:
        colors = palette["colors"]
        measured_count = sum(color.get("measured_lab") is not None for color in colors)
        palette["colorimetry_status"] = colorimetry_status(measured_count, len(colors))
        palette["measured_color_count"] = measured_count
        palette["measurement_coverage_percent"] = round(measured_count / len(colors) * 100, 1)
        return palette

    def _prepare(self, palette: dict[str, Any]) -> dict[str, Any]:
        return self._annotate_colorimetry(self._validate(self._expand_series(palette)))

    @staticmethod
    def _derive_mard_tier(base: dict[str, Any], tier: int) -> dict[str, Any]:
        """Create a stable, perceptually distributed MARD working colour system.

        Tier palettes are real MARD manufacturer codes selected from the 291
        reference palette, never invented replacement colours. Small tiers use
        only regular colours; 264 and 291 may include the expanded/effect range.
        """
        source = (
            base["colors"] if tier > 221 else [color for color in base["colors"] if color.get("effect") != "special"]
        )
        if tier >= len(source):
            selected = list(source)
        else:
            rgb = np.asarray([color["rgb"] for color in source], dtype=np.float64)
            lab = palette_records_lab(source)
            targets = np.asarray(
                [
                    [16, 18, 24],
                    [246, 246, 242],
                    [224, 55, 58],
                    [252, 202, 67],
                    [48, 167, 104],
                    [51, 105, 214],
                    [119, 74, 184],
                ],
                dtype=np.float64,
            )
            selected_indices: list[int] = []
            for target in targets:
                index = int(np.argmin(np.linalg.norm(rgb - target, axis=1)))
                if index not in selected_indices:
                    selected_indices.append(index)
                if len(selected_indices) >= tier:
                    break
            distances = np.min(
                np.linalg.norm(lab[:, None, :] - lab[np.asarray(selected_indices)][None, :, :], axis=2), axis=1
            )
            while len(selected_indices) < tier:
                distances[selected_indices] = -1
                selected_index = int(np.argmax(distances))
                selected_indices.append(selected_index)
                distances = np.minimum(distances, np.linalg.norm(lab - lab[selected_index], axis=1))
            selected = [source[index] for index in sorted(selected_indices)]
        return PaletteService._annotate_colorimetry(
            {
                **{key: value for key, value in base.items() if key not in {"colors", "is_system"}},
                "id": f"mard-{tier}",
                "name": f"MARD 专业 {tier} 色系统",
                "version": f"derived-291-{tier}",
                "description": f"从 MARD 291 色参考色卡中按感知差异筛选的 {tier} 色工作系统；保留原始 MARD 色号。",
                "base_palette_id": "mard-291",
                "color_tier": tier,
                "colors": [dict(color) for color in selected],
                "is_system": True,
            }
        )

    def get(self, palette_id: str) -> dict[str, Any]:
        path = self._builtin_path(palette_id)
        if path.is_file():
            palette = self._prepare(self._load(path, palette_id))
            palette["is_system"] = True
            if palette_id == "mard-291":
                palette["color_tier"] = 291
            return palette
        tier = self._tier_size(palette_id)
        if tier:
            return self._derive_mard_tier(self.get("mard-291"), tier)
        palette = self._prepare(self._load(self._custom_path(palette_id), palette_id))
        palette["is_system"] = False
        return palette

    def list(self) -> list[dict[str, Any]]:
        palettes: list[dict[str, Any]] = []
        for path, is_system in [
            *[(path, True) for path in self.builtin_dir.glob("*.json")],
            *[(path, False) for path in self.custom_dir.glob("*.json")],
        ]:
            try:
                palette = self._prepare(self._load(path, path.stem))
            except (json.JSONDecodeError, AppError):
                continue
            # The historical 39-colour starter chart remains readable so old
            # projects can still open, but is no longer offered for new work.
            if palette["id"] == "mard":
                continue
            palettes.append(
                {
                    "id": palette["id"],
                    "name": palette["name"],
                    "brand": palette.get("brand", palette["name"]),
                    "version": palette.get("version", "1.0"),
                    "color_count": len(palette["colors"]),
                    "colorimetry_status": palette["colorimetry_status"],
                    "measured_color_count": palette["measured_color_count"],
                    "measurement_coverage_percent": palette["measurement_coverage_percent"],
                    "is_system": is_system,
                }
            )
        base = self.get("mard-291")
        for tier in _TIER_COUNTS:
            if tier == 291:
                continue
            derived = self._derive_mard_tier(base, tier)
            palettes.append(
                {
                    "id": derived["id"],
                    "name": derived["name"],
                    "brand": derived["brand"],
                    "version": derived["version"],
                    "color_count": tier,
                    "color_tier": tier,
                    "colorimetry_status": derived["colorimetry_status"],
                    "measured_color_count": derived["measured_color_count"],
                    "measurement_coverage_percent": derived["measurement_coverage_percent"],
                    "is_system": True,
                }
            )
        for palette in palettes:
            if palette["id"] == "mard-291":
                palette["color_tier"] = 291
        return sorted(
            palettes,
            key=lambda palette: (
                not palette["is_system"],
                palette["brand"],
                int(palette.get("color_tier") or palette["color_count"]),
                palette["name"],
            ),
        )

    def create(self, request: PaletteCreate) -> dict[str, Any]:
        if (
            self._tier_size(request.id)
            or self._builtin_path(request.id).exists()
            or self._custom_path(request.id).exists()
        ):
            raise AppError(409, "PALETTE_ALREADY_EXISTS", "色卡 ID 已存在")
        palette = {
            "id": request.id,
            "name": request.name,
            "brand": request.brand,
            "version": "1.0",
            "colors": [color.model_dump(mode="json", exclude_none=True) for color in request.colors],
        }
        if request.calibration is not None:
            palette["calibration"] = request.calibration.model_dump(mode="json", exclude_none=True)
        self._validate(palette, status_code=422)
        self._write(self._custom_path(request.id), palette)
        return self.get(request.id)

    def update(self, palette_id: str, request: PaletteUpdate) -> dict[str, Any]:
        if self._builtin_path(palette_id).exists() or self._tier_size(palette_id):
            raise AppError(403, "SYSTEM_PALETTE_READ_ONLY", "内置色卡不允许修改")
        palette = self.get(palette_id)
        updates: dict[str, Any] = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.brand is not None:
            updates["brand"] = request.brand
        if request.colors is not None:
            updates["colors"] = [color.model_dump(mode="json", exclude_none=True) for color in request.colors]
        if "calibration" in request.model_fields_set:
            if request.calibration is None:
                palette.pop("calibration", None)
            else:
                updates["calibration"] = request.calibration.model_dump(mode="json", exclude_none=True)
        palette.update(updates)
        for key in (
            "is_system",
            "colorimetry_status",
            "measured_color_count",
            "measurement_coverage_percent",
        ):
            palette.pop(key, None)
        self._validate(palette, status_code=422)
        self._write(self._custom_path(palette_id), palette)
        return self.get(palette_id)

    def delete(self, palette_id: str) -> None:
        if self._builtin_path(palette_id).exists() or self._tier_size(palette_id):
            raise AppError(403, "SYSTEM_PALETTE_READ_ONLY", "内置色卡不允许删除")
        path = self._custom_path(palette_id)
        if not path.is_file():
            raise not_found("palette", palette_id)
        path.unlink()

    @staticmethod
    def _write(path: Path, data: dict[str, Any]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)


@lru_cache
def get_palette_service() -> PaletteService:
    return PaletteService()
