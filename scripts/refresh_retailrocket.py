"""将独立项目已导出的MySQL汇总CSV同步到平台；不连接数据库、不读取.env。"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import tempfile
import pandas as pd

FILES = ['daily_metrics', 'weekday_metrics', 'july_weekend_comparison', 'july_hourly',
         'funnel_metrics', 'funnel_windows', 'retention_metrics', 'weekly_retention',
         'category_metrics', 'availability_metrics']


def refresh(source, destination):
    # Validate the whole batch before replacing any platform snapshots.
    for name in FILES:
        if not (source / f'{name}_mysql.csv').is_file():
            raise ValueError(f'缺少汇总文件：{name}_mysql.csv')
    d = pd.read_csv(source / 'daily_metrics_mysql.csv')
    if len(d) != 139 or int(d.total_events.sum()) != 2756101:
        raise ValueError('每日表规模核对失败')
    for name in ['category_metrics', 'availability_metrics']:
        f = pd.read_csv(source / f'{name}_mysql.csv')
        if int(f.total_events.sum()) != 2756101 or int(f.purchase_events.sum()) != 22457:
            raise ValueError(f'{name}总数核对失败')
    destination.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name in FILES:
        filename = f'{name}_mysql.csv'
        raw = (source / filename).read_bytes()
        hashes[filename] = hashlib.sha256(raw).hexdigest()
        with tempfile.NamedTemporaryFile(dir=destination, delete=False, suffix='.tmp') as tmp:
            tmp.write(raw)
            temporary = Path(tmp.name)
        temporary.replace(destination / filename)
    manifest = {
        'dataset': 'Retailrocket', 'source_type': 'mysql_export_snapshot', 'is_live': False,
        'source_url': 'https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset',
        'analysis_url': 'https://github.com/overlxrd123/retailrocket-business-analysis',
        'license': 'CC BY-NC-SA 4.0', 'timezone': 'UTC',
        'snapshot_imported_at': datetime.now(timezone.utc).isoformat(),
        'verified_overview': {'visitors': 1407580, 'note': '访客全期去重数来自已核对的visitor_summary；每日人数不可相加替代。'},
        'sha256': hashes,
    }
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', required=True, type=Path)
    args = parser.parse_args()
    refresh(args.results_dir, Path(__file__).resolve().parents[1] / 'data' / 'retailrocket')
    print('已同步10份MySQL汇总快照；重启平台后生效。')
