"""
Figure 2 v6 — 성공/실패 사례 그리드 (정성 비교)

목적: 통계 수치 대신 "어떤 환경에서 잘 되고 어떤 환경에서 안 되는지"
      를 사진 6장으로 정성적으로 보여줌.
구성: 2행 × 3열
  상: 성공 사례 (final_clean) — ID 020, 027, 029
  하: 실패 사례 — ID 014(좁은 방), ID 051(코너+장애물), ID 060(식탁)
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib import font_manager

FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

PHOTO_DIR = '/Users/honghwasu/Desktop/research_project/seminar2/00_전체'
OUT = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig2_qualitative_grid.png'

# (filename_pattern_in_dir, label, gt_mm, measured_mm, err_pct, note, success)
cases = [
    # 성공 (양호 조건)
    ('020_거실_0.9pct.png',       'ID 020', 4340, 4381, 0.9, '창문 정면, 양쪽 벽 명확',  True),
    ('027_거실_1.9pct.png',       'ID 027', 4340, 4259, 1.9, '창문 정면, 흰 벽',         True),
    ('029_거실_0.3pct.png',       'ID 029', 4340, 4353, 0.3, '창문 정면, 좌측 패널 벽',  True),
    # 실패 (전형적인 실패 모드)
    ('014_작은침실_96.9pct.png',  'ID 014', 2540,   78, 96.9, '좁은 방, 좌측 창문',       False),
    ('051_거실_71.3pct.png',      'ID 051', 2940,  844, 71.3, '코너 촬영, 우측 빌트인장', False),
    ('060_거실_65.1pct.png',      'ID 060', 4040, 1408, 65.1, '식탁·의자가 중앙 차지',    False),
]

fig, axes = plt.subplots(2, 3, figsize=(13, 8))
plt.subplots_adjust(top=0.92, bottom=0.04, left=0.02, right=0.98,
                    wspace=0.06, hspace=0.20)

for ax, (fn, lbl, gt, m, err, note, success) in zip(axes.flat, cases):
    p = os.path.join(PHOTO_DIR, fn)
    if os.path.exists(p):
        img = mpimg.imread(p)
        ax.imshow(img)
    else:
        ax.text(0.5, 0.5, f'(missing\n{fn})', ha='center', va='center', transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    color = '#1B5E20' if success else '#B71C1C'
    bg    = '#E8F5E9' if success else '#FFEBEE'
    title = f'{lbl}  GT {gt:,} mm  →  측정 {m:,} mm  (오차 {err:.1f}%)'
    ax.set_title(title, fontsize=10.5, color=color,
                 weight='bold', pad=4,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor=bg,
                           edgecolor=color, linewidth=1.2, alpha=0.95))
    ax.text(0.5, -0.06, note, transform=ax.transAxes,
            ha='center', va='top', fontsize=9.5, style='italic', color='#444')

# 행 레이블
fig.text(0.005, 0.72, '성공\n사례', ha='left', va='center',
         fontsize=11, weight='bold', color='#1B5E20', rotation=90)
fig.text(0.005, 0.26, '실패\n사례', ha='left', va='center',
         fontsize=11, weight='bold', color='#B71C1C', rotation=90)

fig.suptitle('그림 2.  환경 조건별 성공/실패 사례 비교 (자동 RANSAC 측정)',
             fontsize=13, weight='bold', y=0.985)

plt.savefig(OUT, dpi=180, bbox_inches='tight', facecolor='white')
print(f'Saved: {OUT}')
