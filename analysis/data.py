"""数据加载 — 统一入口，带缓存。

所有模块只从这里取数据，避免同一个 CSV 被重复读进内存。
"""
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def load_food():
    """北京餐饮：44,512 家店铺，含经纬度/商圈/评分/评论数/米其林。"""
    return pd.read_excel(ROOT / "bj_food_analysis.xlsx")


@lru_cache(maxsize=1)
def load_game():
    """Metacritic 游戏评论：2,531 条，Review / Rating / Platform。"""
    return pd.read_csv(ROOT / "Metacriticgames8.csv")


@lru_cache(maxsize=1)
def load_rental():
    """北京租房：35,082 条房源，含经纬度/地铁/配套/装修/楼层。

    数据已复制到 data/ 下，保证仓库 clone 后可直接运行，不依赖同级项目目录。
    """
    local = ROOT / "data" / "beijing_rental.csv"
    path = local if local.exists() else ROOT.parent / "beijing-rental" / "北京市租房数据集.csv"
    return pd.read_csv(path, encoding="utf-8")


@lru_cache(maxsize=1)
def load_jobs():
    """数据岗招聘：3,523 条岗位（岗位名/城市/薪资/经验/学历/公司）。"""
    local = ROOT / "data" / "job_data.csv"
    path = local if local.exists() else ROOT.parent / "job_analysis" / "job_data.csv"
    return pd.read_csv(path)


def jsonable(obj):
    """把 numpy / pandas 类型转成标准 Python 类型，便于 FastAPI 序列化。"""
    import numpy as np

    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if obj is pd.NaT or (isinstance(obj, float) and obj != obj):
        return None
    return obj
