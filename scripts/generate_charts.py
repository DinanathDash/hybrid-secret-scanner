from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def generate_confusion_matrix(output_path: Path) -> None:
    """Create a presentation-ready confusion matrix heatmap."""
    # Matrix layout:
    # rows    = Actual Truth   [Real Secret, Dummy/Safe]
    # columns = AI Prediction  [Flagged CRITICAL, Flagged SAFE]
    counts = np.array([
        [13, 5],
        [3, 19],
    ])

    # True predictions are on the diagonal; false predictions are off-diagonal.
    true_cells = np.array([
        [13, 0],
        [0, 19],
    ])
    false_cells = np.array([
        [0, 5],
        [3, 0],
    ])

    labels_x = ["Flagged CRITICAL", "Flagged SAFE"]
    labels_y = ["Real Secret", "Dummy/Safe"]

    sns.set_theme(style="white", context="talk")
    fig, ax = plt.subplots(figsize=(11, 8), dpi=180)
    fig.patch.set_facecolor("#F7F9FC")
    ax.set_facecolor("#F7F9FC")

    # Layer 1: True predictions (cool, confidence-inspiring tones).
    sns.heatmap(
        true_cells,
        mask=true_cells == 0,
        cmap=sns.color_palette("YlGnBu", as_cmap=True),
        cbar=False,
        square=True,
        linewidths=2.5,
        linecolor="#E4E8F1",
        ax=ax,
    )

    # Layer 2: False predictions (warm warning tones).
    sns.heatmap(
        false_cells,
        mask=false_cells == 0,
        cmap=sns.color_palette("YlOrRd", as_cmap=True),
        cbar=False,
        square=True,
        linewidths=2.5,
        linecolor="#E4E8F1",
        ax=ax,
    )

    # Clear numeric annotations for the presentation deck.
    for i in range(counts.shape[0]):
        for j in range(counts.shape[1]):
            ax.text(
                j + 0.5,
                i + 0.5,
                f"{counts[i, j]}",
                ha="center",
                va="center",
                fontsize=24,
                fontweight="bold",
                color="#0F172A",
            )

    ax.set_xticks(np.arange(len(labels_x)) + 0.5)
    ax.set_yticks(np.arange(len(labels_y)) + 0.5)
    ax.set_xticklabels(labels_x, rotation=0, fontsize=12)
    ax.set_yticklabels(labels_y, rotation=0, fontsize=12)

    ax.set_xlabel("AI Prediction", fontsize=14, fontweight="semibold", labelpad=16)
    ax.set_ylabel("Actual Truth", fontsize=14, fontweight="semibold", labelpad=16)
    ax.set_title("Confusion Matrix", fontsize=20, fontweight="bold", pad=20)

    # Subtle frame styling for enterprise-friendly visuals.
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.2)
        spine.set_edgecolor("#CFD8E3")

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def generate_metrics_bar(output_path: Path) -> None:
    """Create a polished horizontal bar chart for precision and recall."""
    metrics = ["Precision", "Recall"]
    values = [81.25, 72.22]

    sns.set_theme(style="whitegrid", context="talk")
    fig, ax = plt.subplots(figsize=(11, 6), dpi=180)
    fig.patch.set_facecolor("#F7F9FC")
    ax.set_facecolor("#F7F9FC")

    colors = ["#1769AA", "#2E7D32"]
    bars = ax.barh(metrics, values, color=colors, edgecolor="#0F172A", linewidth=0.4)

    ax.set_xlim(0, 100)
    ax.set_xlabel("Score (%)", fontsize=13, fontweight="semibold", labelpad=12)
    ax.set_title("Model Quality Metrics", fontsize=20, fontweight="bold", pad=18)

    ax.xaxis.grid(True, linestyle="--", linewidth=0.8, alpha=0.4)
    ax.yaxis.grid(False)

    for bar, value in zip(bars, values):
        ax.text(
            value + 1.2,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.2f}%",
            va="center",
            ha="left",
            fontsize=12,
            fontweight="bold",
            color="#0F172A",
        )

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#CFD8E3")
    ax.spines["bottom"].set_color("#CFD8E3")

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    generate_confusion_matrix(reports_dir / "confusion_matrix.png")
    generate_metrics_bar(reports_dir / "metrics_bar.png")

    print("Charts generated:")
    print(f"- {reports_dir / 'confusion_matrix.png'}")
    print(f"- {reports_dir / 'metrics_bar.png'}")


if __name__ == "__main__":
    main()
