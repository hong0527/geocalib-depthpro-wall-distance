"""
Figure 2 v6_grid4 — 성공 2 + 실패 2 (4장으로 축소, 분량 절감)
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
OUT = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig2_qualitative_grid4.png'

cases = [
    ('029_거실_0.3pct.png',       'ID 029', 4340, 4353, 0.3, '창문 정면, 양쪽 벽 명확',  True),
    ('020_거실_0.9pct.png',       'ID 020', 4340, 4381, 0.9, '창문 정면, 좌측 패널 벽',  True),
    ('060_거실_65.1pct.png',      'ID 060', 4040, 1408, 65.1, '식탁·의자가 중앙 가림',    False),
    ('014_작은침실_96.9pct.png',  'ID 014', 2540,   78, 96.9, '좁은 방, 좌측 창문',       False),
]

fig, axes = plt.subplots(2, 2, figsize=(11, 8))
plt.subplots_adjust(top=0.93, bottom=0.05, left=0.07, right=0.985,
                    wspace=0.06, hspace=0.18)

for ax, (fn, lbl, gt, m, err, note, success) in zip(axes.flat, cases):
    p = os.path.join(PHOTO_DIR, fn)
    if os.path.exists(p):
        ax.imshow(mpimg.imread(p))
    else:
        ax.text(0.5, 0.5, f'(missing\n{fn})', ha='center', va='center', transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    color = '#1B5E20' if success else '#B71C1C'
    bg    = '#E8F5E9' if success else '#FFEBEE'
    title = f'{lbl}  GT {gt:,} mm  →  측정 {m:,} mm  (오차 {err:.1f}%)'
    # 제목을 axes 내부 좌상단 오버레이로 배치(이미지 밖으로 삐져나오지 않음)
    ax.text(0.015, 0.97, title, transform=ax.transAxes,
            ha='left', va='top', fontsize=10, color=color, weight='bold',
            bbox=dict(boxstyle='round,pad=0.3', facecolor=bg,
                      edgecolor=color, linewidth=1.1, alpha=0.95))
    ax.text(0.5, -0.05, note, transform=ax.transAxes,
            ha='center', va='top', fontsize=9.5, style='italic', color='#444')

# 행 라벨: 단일 단어, 마진 안쪽에 배치하여 axes/제목과 겹치지 않게
fig.text(0.022, 0.72, '성공', ha='center', va='center',
         fontsize=13, weight='bold', color='#1B5E20', rotation=90)
fig.text(0.022, 0.28, '실패', ha='center', va='center',
         fontsize=13, weight='bold', color='#B71C1C', rotation=90)

fig.suptitle('그림 2.  환경 조건별 성공/실패 사례 비교 (자동 RANSAC 측정)',
             fontsize=12.5, weight='bold', y=0.985)

plt.savefig(OUT, dpi=180, bbox_inches='tight', facecolor='white')
print(f'Saved: {OUT}')
