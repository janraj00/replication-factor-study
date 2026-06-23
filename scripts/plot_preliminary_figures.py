#!/usr/bin/env python3
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_cockroach(data_dir: Path, out_dir: Path) -> None:
    df = pd.read_csv(data_dir / "cockroach_rf_sweep_bg_20260617_summary_grouped.csv")
    df = df.sort_values(["ratio", "rf"])

    plt.figure(figsize=(7.2, 4.2))
    for ratio, group in df.groupby("ratio"):
        group = group.sort_values("rf")
        plt.errorbar(
            group["rf"],
            group["qps_actual_mean"],
            yerr=group["qps_actual_std"].fillna(0),
            marker="o",
            capsize=4,
            linewidth=1.8,
            label=f"ratio {ratio}",
        )
    plt.xlabel("Replication factor")
    plt.ylabel("Actual throughput [QPS]")
    plt.title("CockroachDB preliminary throughput")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "preliminary_cockroach_qps.png", dpi=180)
    plt.close()


def plot_hdfs(data_dir: Path, out_dir: Path) -> None:
    df = pd.read_csv(data_dir / "hdfs_rf_sweep_seed_20260623_summary_grouped.csv")
    df = df.sort_values(["rf", "readers"])

    plt.figure(figsize=(7.2, 4.2))
    for rf, group in df.groupby("rf"):
        group = group.sort_values("readers")
        plt.errorbar(
            group["readers"],
            group["read_throughput_mb_s_mean"],
            yerr=group["read_throughput_mb_s_std"].fillna(0),
            marker="o",
            capsize=4,
            linewidth=1.8,
            label=f"RF={rf}",
        )
    plt.xlabel("Parallel readers")
    plt.ylabel("Read throughput [MB/s]")
    plt.title("HDFS preliminary read throughput")
    plt.xticks(sorted(df["readers"].unique()))
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=2)
    plt.tight_layout()
    plt.savefig(out_dir / "preliminary_hdfs_read_throughput.png", dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="paper/data/preliminary")
    parser.add_argument("--out-dir", default="paper/figures")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_cockroach(data_dir, out_dir)
    plot_hdfs(data_dir, out_dir)
    print(f"Wrote figures to {out_dir}")


if __name__ == "__main__":
    main()
