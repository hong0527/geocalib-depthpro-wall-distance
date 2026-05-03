"""
Figure 1 — 전체 파이프라인 흐름도 (교수님 강조 섹션)

선배의 "도서관 프레임워크" 스타일을 참고해
블록 + 화살표 + 핵심 파라미터 + 수동 보완 분기까지 한 장에 담음.

제약:
- KCC 포스터 1컬럼 폭(≈90mm)에 들어가도록 세로형으로 배치
- 방법 중심 논문이므로 각 단계의 입·출력·핵심 파라미터 명시
- 재현성: matplotlib 결과를 fig1_pipeline.png로 저장
"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

FONT = '/System/Library/Fonts/AppleSDGothicNeo.ttc'
if os.path.exists(FONT):
    font_manager.fontManager.addfont(FONT)
    plt.rcParams['font.family'] = 'Apple SD Gothic Neo'
plt.rcParams['axes.unicode_minus'] = False

OUT = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig1_pipeline.png'

# ------ Layout ------
fig, ax = plt.subplots(figsize=(8.5, 11.5))
ax.set_xlim(0, 100)
ax.set_ylim(0, 130)
ax.axis('off')

# Color palette
C_IN   = '#EAF4FC'  # 입력/출력 (옅은 파랑)
C_IN_E = '#2E6BB5'
C_M    = '#FFF4E0'  # 메인 처리 (옅은 노랑)
C_M_E  = '#D9A14C'
C_MA   = '#FCEAEA'  # 수동 보완 (옅은 빨강)
C_MA_E = '#C14B4B'
C_OUT  = '#E6F4EA'  # 최종 출력 (옅은 초록)
C_OUT_E= '#3C8C5B'

def box(ax, x, y, w, h, title, body, color_bg, color_edge, body_fs=7.5, title_fs=9):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.3,rounding_size=1.2",
                          linewidth=1.8, edgecolor=color_edge, facecolor=color_bg, zorder=2)
    ax.add_patch(rect)
    # Title
    ax.text(x + w/2, y + h - 3.2, title,
            ha='center', va='top', fontsize=title_fs, weight='bold', color=color_edge, zorder=3)
    # Body
    ax.text(x + w/2, y + h - 7.5, body,
            ha='center', va='top', fontsize=body_fs, color='#222', zorder=3)

def arrow_down(ax, x, y_top, y_bottom, label=None, label_side='right'):
    ar = FancyArrowPatch((x, y_top), (x, y_bottom),
                         arrowstyle='->,head_length=6,head_width=4',
                         color='#444', linewidth=1.8, zorder=1)
    ax.add_patch(ar)
    if label:
        lx = x + (3 if label_side == 'right' else -3)
        ha = 'left' if label_side == 'right' else 'right'
        ax.text(lx, (y_top + y_bottom)/2, label, fontsize=7, ha=ha, va='center',
                style='italic', color='#555', zorder=3)

def arrow_lr(ax, x1, y1, x2, y2, label=None, color='#C14B4B', style='dashed'):
    ar = FancyArrowPatch((x1, y1), (x2, y2),
                         arrowstyle='->,head_length=5,head_width=3.5',
                         color=color, linewidth=1.5, linestyle=style, zorder=1,
                         connectionstyle='arc3,rad=0.2')
    ax.add_patch(ar)
    if label:
        ax.text((x1+x2)/2, (y1+y2)/2 + 1.5, label, fontsize=7, ha='center',
                style='italic', color=color, zorder=3)

# Title
ax.text(50, 126, '그림 1.  전체 파이프라인 흐름도',
        ha='center', va='center', fontsize=13, weight='bold')
ax.text(50, 122.5, '(GeoCalib + Depth Pro + RANSAC + 수동 보완 분기)',
        ha='center', va='center', fontsize=9.5, style='italic', color='#555')

# ==== Main pipeline (왼쪽 중앙) ====
X_MAIN = 18   # 메인 파이프라인 x
W = 48        # 메인 박스 폭
H = 11        # 박스 높이

# Step 0: Input
box(ax, X_MAIN, 107, W, 8,
    '입력  |  Input',
    '부동산 매물 사진 I  (EXIF 제거됨)',
    C_IN, C_IN_E, body_fs=8.5, title_fs=9)

arrow_down(ax, X_MAIN+W/2, 107, 100)

# Step 1: GeoCalib
box(ax, X_MAIN, 88, W, 12,
    '① GeoCalib  [1]  (ECCV 2024)',
    'Perspective Field + LM 최적화\n출력: f̂ (px), 롤·피치, 방사왜곡 k₁,k₂',
    C_M, C_M_E, body_fs=8)

arrow_down(ax, X_MAIN+W/2, 88, 81, label='f̂')

# Step 2: Depth Pro
box(ax, X_MAIN, 69, W, 12,
    '② Depth Pro  [2]  (ICLR 2025)',
    'canonical inv.depth × (W / f̂)\n출력: metric depth D ∈ ℝ^{H×W}',
    C_M, C_M_E, body_fs=8)

arrow_down(ax, X_MAIN+W/2, 69, 62, label='D')

# Step 3: 3D 역투영
box(ax, X_MAIN, 50, W, 12,
    '③ 3D 역투영  (핀홀 모델)',
    'X=(u−cₓ)·Z/f̂,  Y=(v−c_y)·Z/f̂,  Z=D(u,v)\n유효범위 0.5 m < Z < 10 m',
    C_M, C_M_E, body_fs=7.8)

arrow_down(ax, X_MAIN+W/2, 50, 43, label='점군')

# Step 4: RANSAC
box(ax, X_MAIN, 30, W, 13,
    '④ RANSAC 평면 피팅 (최대 6회)',
    'τ = 5 cm,  iter = 1000\n수직 필터  |n_y| ≤ 0.7',
    C_M, C_M_E, body_fs=8)

arrow_down(ax, X_MAIN+W/2, 30, 23, label='벽 후보')

# Step 5: 평행 벽쌍
box(ax, X_MAIN, 11, W, 12,
    '⑤ 평행 벽쌍 선택',
    '|nᵢ · nⱼ| > 0.8  &  inlier 합 최대\n벽-벽 거리  dist = |dᵢ ± dⱼ|',
    C_M, C_M_E, body_fs=8)

arrow_down(ax, X_MAIN+W/2, 11, 4)

# Output
box(ax, X_MAIN+4, 0.5, W-8, 4,
    '', '출력: 벽-벽 거리 (mm) → GT(평면도)와 비교',
    C_OUT, C_OUT_E, body_fs=8.5, title_fs=1)

# ==== 우측: 수동 보완 경로 (실패 분기) ====
X_MAN = 76
W_MAN = 22

# 실패 분기 트리거 표시: ④ RANSAC 오른쪽에서 수동 보완 박스로 점선 화살표
# 수동 보완 박스
box(ax, X_MAN, 30, W_MAN, 18,
    '④′ 수동 보완  (실패 시)',
    '사용자가 두 벽\n클릭 (40×40 px)\n depth 중앙값으로\n거리 직접 산출\n\n(§4.7에 정량 효과)',
    C_MA, C_MA_E, body_fs=7.2, title_fs=8.2)

# 분기 화살표: ④ RANSAC → 수동 보완
arrow_lr(ax, X_MAIN+W, 36, X_MAN, 39,
         label='RANSAC 실패/\n잘못 피팅', color=C_MA_E)

# 수동 보완 → 출력 합류
arrow_lr(ax, X_MAN+W_MAN/2, 30, X_MAIN+W-2, 3.5,
         label=None, color=C_MA_E)

# ==== 범례 ====
ax.text(50, 117, '────── 자동 경로', ha='left', va='center', fontsize=7.5, color='#444')
ax.text(74, 117, '- - - - - 수동 분기', ha='left', va='center', fontsize=7.5,
        color=C_MA_E, style='italic')

# 좌측 이미지 예시 자리 표시 (optional small label)
# Skipped for clean layout

# Save
plt.savefig(OUT, dpi=200, bbox_inches='tight', facecolor='white')
print(f'Saved: {OUT}')
