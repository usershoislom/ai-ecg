"""
export_thresholds.py

Конвертирует test_results.csv (из раздела 8 ноутбука ecg_finetune_v2.ipynb)
в weights/thresholds.json, который читает model_service.py при старте бэкенда.

Использование:
    python export_thresholds.py path/to/test_results.csv weights/thresholds.json
"""

import json
import sys

import pandas as pd


def main(csv_path: str, out_path: str):
    df = pd.read_csv(csv_path)
    thresholds = dict(zip(df["Label"], df["Threshold"]))
    with open(out_path, "w") as f:
        json.dump(thresholds, f, indent=2, ensure_ascii=False)
    print(f"Сохранено {len(thresholds)} порогов в {out_path}: {thresholds}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Использование: python export_thresholds.py <test_results.csv> <thresholds.json>"
        )
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
