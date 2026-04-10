#!/usr/bin/env python3
"""Generate all seminar presentation figures."""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
from PIL import Image

# Korean font setup
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

BASE = Path('/Users/honghwasu/Desktop/research_project')
SEMINAR = BASE / 'seminar2'
OUT = SEMINAR / '07_figures'

# Load data
df = pd.read_csv(SEMINAR / '전체_통합_데이터.csv')
df_focal = pd.read_csv(BASE / 'results_focal_comparison.csv')
df_full = pd.read_csv(BASE / 'results_full.csv')

# Exclude failed
df_valid = df[df['classification'] != 'failed'].copy()
df_valid['error_pct'] = pd.to_numeric(df_valid['error_pct'], errors='coerce')

print(f"Total rows: {len(df)}, Valid (non-failed): {len(df_valid)}")

# ── Fig 1: Condition Comparison ──
def fig1():
    both_clear = df_valid[df_valid['wall_visible'] == 'both_clear']
    one_unclear = df_valid[df_valid['wall_visible'] == 'one_unclear']
    final_clean = df_valid[df_valid['classification'] == 'final_clean']
    obstacle_yes = df_valid[df_valid['obstacle'] == 'yes']

    groups = {
        f'전체\n(유효 {len(df_valid)}장)': df_valid,
        f'both_clear\n({len(both_clear)}장)': both_clear,
        f'one_unclear\n({len(one_unclear)}장)': one_unclear,
        f'final_clean\n({len(final_clean)}장)': final_clean,
        f'obstacle=yes\n({len(obstacle_yes)}장)': obstacle_yes,
    }

    labels = list(groups.keys())
    avg_errors = [g['error_pct'].mean() for g in groups.values()]
    under10 = [100 * (g['error_pct'] <= 10).sum() / len(g) for g in groups.values()]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(12, 6))
    bars1 = ax1.bar(x - width/2, avg_errors, width, label='평균 오차율 (%)', color='#4C72B0', edgecolor='white')
    ax1.set_ylabel('평균 오차율 (%)', fontsize=12, color='#4C72B0')
    ax1.tick_params(axis='y', labelcolor='#4C72B0')
    ax1.set_ylim(0, max(avg_errors) * 1.3)

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width/2, under10, width, label='10% 이하 비율 (%)', color='#55A868', edgecolor='white')
    ax2.set_ylabel('10% 이하 비율 (%)', fontsize=12, color='#55A868')
    ax2.tick_params(axis='y', labelcolor='#55A868')
    ax2.set_ylim(0, 105)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_title('조건별 오차율 비교', fontsize=14, fontweight='bold', pad=15)

    # Add value labels
    for bar, val in zip(bars1, avg_errors):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{val:.1f}%', ha='center', va='bottom', fontsize=9, color='#4C72B0', fontweight='bold')
    for bar, val in zip(bars2, under10):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                 f'{val:.1f}%', ha='center', va='bottom', fontsize=9, color='#55A868', fontweight='bold')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

    plt.tight_layout()
    fig.savefig(OUT / 'fig1_condition_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Fig1 saved. Groups: {[(k.split(chr(10))[0], f'avg={v:.1f}%, <=10%={u:.1f}%') for k,v,u in zip(labels, avg_errors, under10)]}")

# ── Fig 2: GeoCalib vs DepthPro ──
def fig2():
    # Merge focal comparison with classification
    df_fc = df_focal.copy()
    df_fc['classification'] = df['classification'].values[:len(df_fc)]  # same order
    df_fc = df_fc[df_fc['status'] == 'ok'].copy()
    # Also exclude failed classification
    df_fc = df_fc[df_fc['classification'] != 'failed'].copy()

    df_fc['err_A_pct'] = pd.to_numeric(df_fc['err_A_pct'], errors='coerce')
    df_fc['err_B_pct'] = pd.to_numeric(df_fc['err_B_pct'], errors='coerce')
    df_fc['f_wide_geocalib'] = pd.to_numeric(df_fc['f_wide_geocalib'], errors='coerce')

    # Drop rows with NaN errors
    df_fc = df_fc.dropna(subset=['err_A_pct', 'err_B_pct'])

    wide = df_fc[df_fc['f_wide_geocalib'] < 500]
    normal = df_fc[df_fc['f_wide_geocalib'] >= 500]

    groups = {
        f'전체\n({len(df_fc)}장)': df_fc,
        f'광각(<500px)\n({len(wide)}장)': wide,
        f'일반(>=500px)\n({len(normal)}장)': normal,
    }

    labels = list(groups.keys())
    avg_A = [g['err_A_pct'].mean() for g in groups.values()]
    avg_B = [g['err_B_pct'].mean() for g in groups.values()]

    # Win rates
    win_rates = []
    for g in groups.values():
        a_wins = (g['err_A_pct'] < g['err_B_pct']).sum()
        b_wins = (g['err_B_pct'] < g['err_A_pct']).sum()
        ties = (g['err_A_pct'] == g['err_B_pct']).sum()
        win_rates.append(f'A승: {a_wins}, B승: {b_wins}, 동률: {ties}')

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars_a = ax.bar(x - width/2, avg_A, width, label='A: GeoCalib focal', color='#4C72B0', edgecolor='white')
    bars_b = ax.bar(x + width/2, avg_B, width, label='B: DepthPro focal', color='#DD8452', edgecolor='white')

    for bar, val in zip(bars_a, avg_A):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    for bar, val in zip(bars_b, avg_B):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Add win rate annotations
    for i, wr in enumerate(win_rates):
        ax.text(x[i], max(avg_A[i], avg_B[i]) + 3, wr, ha='center', va='bottom', fontsize=8, style='italic')

    ax.set_ylabel('평균 오차율 (%)', fontsize=12)
    ax.set_title('GeoCalib vs DepthPro 초점거리 비교', fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(fontsize=11)
    ax.set_ylim(0, max(max(avg_A), max(avg_B)) * 1.4)

    plt.tight_layout()
    fig.savefig(OUT / 'fig2_geocalib_vs_depthpro.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Fig2 saved. A avgs: {[f'{v:.1f}' for v in avg_A]}, B avgs: {[f'{v:.1f}' for v in avg_B]}")
    print(f"  Win rates: {win_rates}")

# ── Fig 3: Clean Error Distribution ──
def fig3():
    clean = df_valid[df_valid['classification'] == 'final_clean'].copy()
    clean = clean.sort_values('error_pct')

    colors = ['#55A868' if e <= 10 else '#DD8452' for e in clean['error_pct']]

    fig, ax = plt.subplots(figsize=(14, 6))
    bars = ax.bar(range(len(clean)), clean['error_pct'].values, color=colors, edgecolor='white')
    ax.axhline(y=10, color='red', linestyle='--', linewidth=1.5, label='10% 기준선')

    ax.set_xticks(range(len(clean)))
    ax.set_xticklabels(clean['id'].values, rotation=45, ha='right', fontsize=8)
    ax.set_xlabel('이미지 ID', fontsize=12)
    ax.set_ylabel('오차율 (%)', fontsize=12)
    ax.set_title(f'Final Clean {len(clean)}장 오차율 분포', fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11)

    # Add value labels on bars
    for bar, val in zip(bars, clean['error_pct'].values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{val:.1f}', ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    fig.savefig(OUT / 'fig3_clean_error_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()

    under10 = (clean['error_pct'] <= 10).sum()
    print(f"Fig3 saved. Clean count: {len(clean)}, under 10%: {under10}/{len(clean)}")

# ── Fig 4: ER Distribution ──
def fig4():
    er = pd.to_numeric(df_full['ER'], errors='coerce')
    status = df_full['status'] if 'status' in df_full.columns else df_full.get('classification', pd.Series())

    # Filter: valid ER range and not failed
    mask = (er > 0.5) & (er < 1.5)
    if 'status' in df_full.columns:
        mask = mask & (df_full['status'] != 'ransac_fail')
    er_filtered = er[mask].dropna()

    median_er = er_filtered.median()
    mean_er = er_filtered.mean()

    fig, ax = plt.subplots(figsize=(10, 6))
    n, bins, patches = ax.hist(er_filtered, bins=20, color='#4C72B0', edgecolor='white', alpha=0.85)
    ax.axvline(x=1.0, color='red', linestyle='--', linewidth=2, label=f'이상적 ER = 1.0')
    ax.axvline(x=median_er, color='orange', linestyle='-', linewidth=2, label=f'중앙값 = {median_er:.4f}')

    ax.set_xlabel('ER (Error Ratio)', fontsize=12)
    ax.set_ylabel('빈도', fontsize=12)
    ax.set_title('ER 분포 (0.5 < ER < 1.5, 실패 제외)', fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11)

    # Annotation
    ax.text(0.95, 0.85, f'N = {len(er_filtered)}\n평균 = {mean_er:.4f}\n중앙값 = {median_er:.4f}',
            transform=ax.transAxes, ha='right', va='top', fontsize=11,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    fig.savefig(OUT / 'fig4_er_distribution.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Fig4 saved. N={len(er_filtered)}, median={median_er:.4f}, mean={mean_er:.4f}")

# ── Fig 5: Pipeline ──
def fig5():
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis('off')

    steps = [
        (0.8, 1.5, '1. 입력\n실내사진'),
        (2.6, 1.5, '2. GeoCalib\n초점거리 추정'),
        (4.4, 1.5, '3. Depth Pro\n단안 깊이맵'),
        (6.2, 1.5, '4. 벽면 검출\nRANSAC'),
        (8.0, 1.5, '5. 실측 거리\n환산 (mm)'),
    ]

    colors = ['#E8D5B7', '#B0C4DE', '#B0DEB0', '#DEB0B0', '#D5B0DE']

    for i, (x, y, text) in enumerate(steps):
        box = matplotlib.patches.FancyBboxPatch(
            (x - 0.7, y - 0.55), 1.4, 1.1,
            boxstyle="round,pad=0.1", facecolor=colors[i], edgecolor='#333333', linewidth=1.5)
        ax.add_patch(box)
        ax.text(x, y, text, ha='center', va='center', fontsize=11, fontweight='bold')

        if i < len(steps) - 1:
            ax.annotate('', xy=(steps[i+1][0] - 0.75, y), xytext=(x + 0.75, y),
                        arrowprops=dict(arrowstyle='->', color='#333333', lw=2))

    ax.set_title('파이프라인 흐름도', fontsize=14, fontweight='bold', pad=20)

    plt.tight_layout()
    fig.savefig(OUT / 'fig5_pipeline.png', dpi=150, bbox_inches='tight')
    plt.close()
    print("Fig5 saved.")

# ── Fig 6: Depth Map Comparison ──
def fig6():
    depth_dir = BASE / 'output' / 'depth_maps'
    photo_dir = SEMINAR / '00_전체'

    # Good: 029 (0.3%), Bad: 014 (96.9%)
    good_id, good_err = '029', '0.3%'
    bad_id, bad_err = '014', '96.9%'

    # Find photo files
    good_photo = list(photo_dir.glob(f'{good_id}_*'))[0]
    bad_photo = list(photo_dir.glob(f'{bad_id}_*'))[0]

    good_depth = np.load(depth_dir / f'{good_id}_depth.npy')
    bad_depth = np.load(depth_dir / f'{bad_id}_depth.npy')

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Good example
    img = Image.open(good_photo)
    axes[0, 0].imshow(img)
    axes[0, 0].set_title(f'원본 사진 ({good_id}, 오차 {good_err})', fontsize=12, fontweight='bold')
    axes[0, 0].axis('off')

    im1 = axes[0, 1].imshow(good_depth, cmap='viridis')
    axes[0, 1].set_title(f'깊이맵 ({good_id})', fontsize=12, fontweight='bold')
    axes[0, 1].axis('off')
    plt.colorbar(im1, ax=axes[0, 1], fraction=0.046, pad=0.04)

    # Bad example
    img2 = Image.open(bad_photo)
    axes[1, 0].imshow(img2)
    axes[1, 0].set_title(f'원본 사진 ({bad_id}, 오차 {bad_err})', fontsize=12, fontweight='bold')
    axes[1, 0].axis('off')

    im2 = axes[1, 1].imshow(bad_depth, cmap='viridis')
    axes[1, 1].set_title(f'깊이맵 ({bad_id})', fontsize=12, fontweight='bold')
    axes[1, 1].axis('off')
    plt.colorbar(im2, ax=axes[1, 1], fraction=0.046, pad=0.04)

    fig.suptitle('깊이맵 비교: 성공 vs 실패 사례', fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / 'fig6_depthmap_comparison.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Fig6 saved. Good: {good_photo.name}, Bad: {bad_photo.name}")

# Run all
fig1()
fig2()
fig3()
fig4()
fig5()
fig6()
print("\nAll figures generated successfully!")
