"""质量站路径：代码在本目录；数据优先沿用仓库 output/e2e-quality。"""

from pathlib import Path

STATION = Path(__file__).resolve().parent


def quality_root() -> Path:
    parent = STATION.parent
    if STATION.name == "e2e-quality-station" and (parent / "output" / "e2e-quality").is_dir():
        return parent
    return STATION


ROOT = quality_root()
SITE_DIR = ROOT / "output" / "e2e-quality"
