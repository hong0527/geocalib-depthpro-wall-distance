"""
Figure 1 (v2) — 파이프라인 흐름도 재설계

v1 문제점:
  - f̂, n_y, c_x 등 유니코드 특수기호 폰트 미지원으로 깨짐
  - 수동 분기 화살표 배치 어색
  - 박스 간 간격 불균형

v2 개선:
  - ASCII로 통일: f_px (f̂ 대신), n_y (subscript 대신)
  - 블록 수평 배치 + 수동 분기 명확히
  - 폰트 크기·여백 조정으로 가독성 향상
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

OUT = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig1_pipeline_v2.png'

# Palette (KCC 적합 neutral)
C_IN    = ('#E3F2FD', '#1565C0')   # blue (입출력)
C_ALGO  = ('#FFF3E0', '#E65100')   # orange (처리 단계)
C_MAN   = ('#FCE4EC', '#C2185B')   # pink (수동 분기)
C_OUT   = ('#E8F5E9', '#2E7D32')   # green (최종 출력)

fig, ax = plt.subplots(figsize=(9, 11))
ax.set_xlim(0, 100)
ax.set_ylim(0, 125)
ax.axis('off')

def box(x, y, w, h, title, body, color_pair, title_fs=9.5, body_fs=7.8):
    bg, fg = color_pair
    rect = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.25,rounding_size=1.0",
                           linewidth=1.6, edgecolor=fg, facecolor=bg, zorder=2)
    ax.add_patch(rect)
    if title:
        ax.text(x + w/2, y + h - 2.5, title,
                ha='center', va='top', fontsize=title_fs, weight='bold', color=fg, zorder=3)
    ax.text(x + w/2, y + h - 2.5 - (3.5 if title else 0), body,
            ha='center', va='top', fontsize=body_fs, color='#222', zorder=3,
            linespacing=1.35)

def arrow_v(x, y_from, y_to, label=None, lbl_side='right', color='#555'):
    ar = FancyArrowPatch((x, y_from), (x, y_to),
                         arrowstyle='-|>,head_length=5,head_width=3.2',
                         mutation_scale=15, color=color, linewidth=1.5, zorder=1)
    ax.add_patch(ar)
    if label:
        dx = 2.5 if lbl_side == 'right' else -2.5
        ha = 'left' if lbl_side == 'right' else 'right'
        ax.text(x + dx, (y_from + y_to) / 2, label,
                fontsize=7.5, ha=ha, va='center',
                style='italic', color='#444', zorder=3,
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                          edgecolor='none', alpha=0.85))

def arrow_diag(x1, y1, x2, y2, label=None, color='#C2185B', dashed=True):
    ls = '--' if dashed else '-'
    ar = FancyArrowPatch((x1, y1), (x2, y2),
                         arrowstyle='-|>,head_length=5,head_width=3.2',
                         mutation_scale=15, color=color, linewidth=1.3,
                         linestyle=ls, zorder=1,
                         connectionstyle='arc3,rad=0.3')
    ax.add_patch(ar)
    if label:
        midx, midy = (x1+x2)/2, (y1+y2)/2
        ax.text(midx, midy + 1.8, label,
                fontsize=7.5, ha='center', va='center',
                style='italic', color=color, zorder=3,
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor=color, linewidth=0.6, alpha=0.95))

# ---- Title ----
ax.text(50, 122, '그림 1.  전체 파이프라인 흐름도',
        ha='center', va='center', fontsize=13, weight='bold')
ax.text(50, 118.5, '자동 경로 6단계 + 실패 시 수동 보완 분기',
        ha='center', va='center', fontsize=10, style='italic', color='#555')

# ---- Main pipeline (왼쪽/가운데 세로) ----
X_MAIN, W_MAIN = 10, 55

# 입력
box(X_MAIN, 108, W_MAIN, 7, '',
    '입력 (Input):  부동산 매물 사진 I  (EXIF 제거됨)',
    C_IN, body_fs=9)

arrow_v(X_MAIN + W_MAIN/2, 108, 101.5)

# ① GeoCalib
box(X_MAIN, 90, W_MAIN, 11.5,
    '① GeoCalib  (ECCV 2024)',
    'Perspective Field + LM 최적화\n출력: 초점거리 f_px, roll·pitch, 방사왜곡 k1·k2',
    C_ALGO)
arrow_v(X_MAIN + W_MAIN/2, 90, 83.5, label='f_px')

# ② Depth Pro
box(X_MAIN, 72, W_MAIN, 11.5,
    '② Depth Pro  (ICLR 2025)',
    'canonical inverse depth × (W / f_px)\n출력: metric depth D (H × W)',
    C_ALGO)
arrow_v(X_MAIN + W_MAIN/2, 72, 65.5, label='D')

# ③ 3D 역투영
box(X_MAIN, 54, W_MAIN, 11.5,
    '③ 3D 역투영  (pinhole model)',
    'X = (u − cx) · Z / f_px\nY = (v − cy) · Z / f_px,  Z = D(u,v)',
    C_ALGO)
arrow_v(X_MAIN + W_MAIN/2, 54, 47.5, label='점군')

# ④ RANSAC
box(X_MAIN, 36, W_MAIN, 11.5,
    '④ RANSAC 평면 피팅  (최대 6회)',
    'threshold τ = 5 cm,  iter = 1000\n수직 필터  |ny| ≤ 0.7',
    C_ALGO)
arrow_v(X_MAIN + W_MAIN/2, 36, 29.5, label='벽 후보')

# ⑤ 평행 벽 쌍
box(X_MAIN, 18, W_MAIN, 11.5,
    '⑤ 평행 벽쌍 선택',
    '|n_i · n_j| > 0.8  AND  inlier 합 최대 쌍\n거리 = |d_i − d_j|  또는  |d_i + d_j|',
    C_ALGO)
arrow_v(X_MAIN + W_MAIN/2, 18, 11.5)

# 출력
box(X_MAIN, 3, W_MAIN, 8, '',
    '⑥ 출력:  벽–벽 거리 (mm)  →  평면도 GT와 비교',
    C_OUT, body_fs=9)

# ---- 수동 보완 분기 (오른쪽) ----
X_MAN, W_MAN = 73, 23

box(X_MAN, 30, W_MAN, 22,
    '수동 보완  (실패 시)',
    '사용자가 두 벽의\n패치(40×40 px)를 클릭\n\ndepth 중앙값 기반\n거리 직접 산출\n\n(§4.6 정량 효과)',
    C_MAN, title_fs=9, body_fs=7.5)

# RANSAC 실패 → 수동 보완 (오른쪽으로 분기)
arrow_diag(X_MAIN + W_MAIN, 41, X_MAN, 41,
           label='RANSAC 실패·\n잘못 피팅',
           color=C_MAN[1], dashed=True)

# 수동 결과 → 출력 합류
arrow_diag(X_MAN + W_MAN/2, 30, X_MAIN + W_MAIN - 5, 7.5,
           label=None, color=C_MAN[1], dashed=True)

# ---- 범례 ----
legend_y = 114
ax.plot([67, 72], [legend_y, legend_y], color='#555', lw=1.5)
ax.text(73, legend_y, '자동 경로', fontsize=8, va='center', color='#333')
ax.plot([85, 90], [legend_y, legend_y], color=C_MAN[1], lw=1.3, ls='--')
ax.text(91, legend_y, '수동 분기', fontsize=8, va='center', color=C_MAN[1])

# Save
plt.savefig(OUT, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {OUT}')
