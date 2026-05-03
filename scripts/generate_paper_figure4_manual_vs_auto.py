"""
Figure 4 - 수동 측정 vs 자동 RANSAC 측정 비교
- Left: obstacle 18장 paired 비교 막대 + 박스플롯
- Right: wrongfit 5장 극단 개선 사례 막대

사실성 100%: manual_measure_*.csv 값 그대로 사용
"""
import csv, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

# ---- Load ----
obstacle_path = '/Users/honghwasu/Desktop/research_project/output/manual_measure_obstacle.csv'
wrongfit_path = '/Users/honghwasu/Desktop/research_project/output/manual_measure_wrongfit.csv'

def load(p):
    return [dict(id=r['id'],
                 auto=float(r['auto_err']) if r['auto_err'] else None,
                 manual=float(r['manual_err']) if r['manual_err'] else None,
                 note=r['note'])
            for r in csv.DictReader(open(p, encoding='utf-8-sig'))]

obs = load(obstacle_path)
wf  = load(wrongfit_path)

# paired only
obs_pair = [r for r in obs if r['auto'] is not None and r['manual'] is not None]
wf_pair  = [r for r in wf  if r['auto'] is not None and r['manual'] is not None]
print(f"obstacle paired: {len(obs_pair)}")
print(f"wrongfit paired: {len(wf_pair)}")

# ---- Figure ----
fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
fig.suptitle('Figure 4.  자동 RANSAC vs 수동 클릭 기반 측정 비교',
             fontsize=14, weight='bold', y=0.99)

# ==================== Left: Obstacle paired bar ====================
ax = axes[0]
obs_sorted = sorted(obs_pair, key=lambda r: r['auto'] - r['manual'], reverse=True)
ids = [r['id'] for r in obs_sorted]
auto = np.array([r['auto'] for r in obs_sorted])
manu = np.array([r['manual'] for r in obs_sorted])

x = np.arange(len(ids))
w = 0.36
ax.bar(x - w/2, auto, w, label=f'자동 RANSAC (평균 {auto.mean():.1f}%)',
       color='#d62728', alpha=0.85, edgecolor='black', linewidth=0.5)
ax.bar(x + w/2, manu, w, label=f'수동 클릭 (평균 {manu.mean():.1f}%)',
       color='#2ca02c', alpha=0.85, edgecolor='black', linewidth=0.5)

for i, (a, m) in enumerate(zip(auto, manu)):
    improvement = a - m
    if improvement > 20:
        ax.annotate(f'−{improvement:.0f}%p', xy=(i, max(a,m)+2),
                    ha='center', fontsize=8, color='darkgreen', weight='bold')

ax.set_xticks(x)
ax.set_xticklabels(ids, rotation=60, fontsize=8)
ax.set_ylabel('상대 오차 (%)', fontsize=11)
ax.set_xlabel('사진 ID (장애물 있음, N=17)', fontsize=11)
ax.set_title(f'장애물 케이스 — paired 비교 (Wilcoxon p=0.057)',
             fontsize=12, pad=8)
ax.legend(loc='upper right', fontsize=10)
ax.axhline(10, ls='--', color='blue', alpha=0.5, lw=1,
           label='10% 기준선')
ax.text(0.5, 10.5, '10% 이하 목표선', fontsize=8, color='blue', alpha=0.7)
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, max(auto.max(), manu.max())*1.15)

# ==================== Right: Wrongfit extreme improvement ====================
ax = axes[1]
wf_sorted = sorted(wf_pair, key=lambda r: r['auto'] - r['manual'], reverse=True)
ids = [r['id'] for r in wf_sorted]
auto = np.array([r['auto'] for r in wf_sorted])
manu = np.array([r['manual'] for r in wf_sorted])

x = np.arange(len(ids))
w = 0.36
ax.bar(x - w/2, auto, w, label=f'자동 RANSAC (평균 {auto.mean():.1f}%)',
       color='#d62728', alpha=0.85, edgecolor='black', linewidth=0.5)
ax.bar(x + w/2, manu, w, label=f'수동 클릭 (평균 {manu.mean():.1f}%)',
       color='#2ca02c', alpha=0.85, edgecolor='black', linewidth=0.5)

for i, (a, m) in enumerate(zip(auto, manu)):
    diff = a - m
    y = max(a, m) + 3
    ax.annotate(f'{diff:+.0f}%p' if diff < 0 else f'−{diff:.0f}%p',
                xy=(i, y), ha='center', fontsize=9,
                color='darkgreen' if diff>0 else 'darkred',
                weight='bold')

ax.set_xticks(x)
ax.set_xticklabels(ids, fontsize=10)
ax.set_ylabel('상대 오차 (%)', fontsize=11)
ax.set_xlabel('사진 ID (RANSAC 잘못 피팅, N=5)', fontsize=11)
ax.set_title(f'극단적 실패 케이스 — 수동 개선',
             fontsize=12, pad=8)
ax.legend(loc='upper right', fontsize=10)
ax.axhline(10, ls='--', color='blue', alpha=0.5, lw=1)
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, max(auto.max(), manu.max())*1.20)

# Annotation — 가장 극단 개선 사례 2건
txt = ("극단 개선 사례:\n"
       "  • ID 014: 96.9% → 27.0% (−69.9%p)\n"
       "  • ID 051: 71.3% →  5.2% (−66.1%p)\n"
       "  • ID 060*: 65.1% →  1.4% (−63.7%p)   *obstacle")
ax.text(0.02, 0.78, txt, transform=ax.transAxes,
        fontsize=9, va='top', ha='left',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='#fff9b1',
                  edgecolor='#b59f00', alpha=0.9))

plt.tight_layout()
plt.subplots_adjust(top=0.92, bottom=0.12)

out = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig4_manual_vs_auto_v2.png'
plt.savefig(out, dpi=180, bbox_inches='tight', facecolor='white')
print(f"\nSaved: {out}")
