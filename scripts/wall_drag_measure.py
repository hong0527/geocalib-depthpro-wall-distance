"""
벽 영역 드래그 방식 거리 측정 (제안서 방법)
1. Depth Pro로 depth map 생성
2. 사진에서 왼쪽 벽 영역 드래그 → 오른쪽 벽 영역 드래그
3. 각 영역의 3D 점 → 평면 피팅
4. 두 평면 사이 수직 거리 = 벽-벽 거리

테스트: both_clear 첫 번째 이미지 1장으로 먼저 검증
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")

import numpy as np
import torch
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.widgets import RectangleSelector
import depth_pro
from geocalib import GeoCalib

# ============================================================
# 평면 피팅 (최소제곱법 - RANSAC 아닌 확정적 방법)
# ============================================================
def fit_plane_least_squares(points):
    """점들에 최소제곱 평면 피팅. ax + by + cz + d = 0 반환"""
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, Vt = np.linalg.svd(centered)
    normal = Vt[-1]  # 가장 작은 singular value에 대응하는 벡터
    normal = normal / np.linalg.norm(normal)
    d = -np.dot(normal, centroid)
    return normal, d

def plane_distance(n1, d1, n2, d2):
    """두 평면 사이 수직 거리"""
    dot = np.dot(n1, n2)
    if dot > 0:
        return abs(d1 - d2) / np.linalg.norm(n1)
    else:
        return abs(d1 + d2) / np.linalg.norm(n1)

# ============================================================
# 드래그 UI 클래스
# ============================================================
class WallSelector:
    def __init__(self, img, depth_map, f_px, title_info):
        self.img = img
        self.depth = depth_map
        self.f_px = f_px
        self.H, self.W = depth_map.shape
        self.cx = self.W / 2.0
        self.cy = self.H / 2.0
        self.regions = []  # [(x1,y1,x2,y2), ...]
        self.current_wall = 0  # 0=왼쪽, 1=오른쪽
        self.title_info = title_info
        self.result = None

        self.fig, self.ax = plt.subplots(1, 1, figsize=(14, 10))
        self.ax.imshow(img)
        self.update_title()

        self.selector = RectangleSelector(
            self.ax, self.on_select,
            useblit=True,
            button=[1],
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=False
        )

        plt.tight_layout()

    def update_title(self):
        if self.current_wall == 0:
            instruction = "왼쪽 벽을 드래그하세요 (사각형)"
            color = "red"
        elif self.current_wall == 1:
            instruction = "오른쪽 벽을 드래그하세요 (사각형)"
            color = "blue"
        else:
            instruction = "완료!"
            color = "green"

        self.ax.set_title(
            f"{self.title_info}\n{instruction}",
            fontsize=13,
            fontproperties={'family': 'AppleGothic'},
            color=color
        )
        self.fig.canvas.draw_idle()

    def on_select(self, eclick, erelease):
        x1, y1 = int(eclick.xdata), int(eclick.ydata)
        x2, y2 = int(erelease.xdata), int(erelease.ydata)

        # 정렬
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)

        self.regions.append((x1, y1, x2, y2))

        # 사각형 표시
        color = 'red' if self.current_wall == 0 else 'blue'
        label = 'L' if self.current_wall == 0 else 'R'
        rect = plt.Rectangle((x1, y1), x2-x1, y2-y1,
                              linewidth=2, edgecolor=color, facecolor=color, alpha=0.3)
        self.ax.add_patch(rect)
        self.ax.text(x1+5, y1+20, label, color='white', fontsize=16, fontweight='bold')

        self.current_wall += 1
        self.update_title()

        if self.current_wall >= 2:
            self.compute()
            plt.pause(1.5)
            plt.close()

    def region_to_3d_points(self, x1, y1, x2, y2):
        """드래그 영역 내의 depth를 3D 점으로 변환"""
        u_range = np.arange(x1, x2)
        v_range = np.arange(y1, y2)
        u_grid, v_grid = np.meshgrid(u_range, v_range)

        Z = self.depth[y1:y2, x1:x2]
        X = (u_grid - self.cx) * Z / self.f_px
        Y = (v_grid - self.cy) * Z / self.f_px

        points = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)

        # 유효한 점만 (depth가 합리적인 범위)
        valid = (points[:, 2] > 0.3) & (points[:, 2] < 15.0)
        valid &= np.isfinite(points).all(axis=1)
        return points[valid]

    def compute(self):
        (x1a, y1a, x2a, y2a) = self.regions[0]  # 왼쪽 벽
        (x1b, y1b, x2b, y2b) = self.regions[1]  # 오른쪽 벽

        pts_left = self.region_to_3d_points(x1a, y1a, x2a, y2a)
        pts_right = self.region_to_3d_points(x1b, y1b, x2b, y2b)

        if len(pts_left) < 10 or len(pts_right) < 10:
            print("  경고: 벽 영역에 유효한 depth 점이 너무 적습니다")
            return

        # 평면 피팅 (최소제곱법)
        n1, d1 = fit_plane_least_squares(pts_left)
        n2, d2 = fit_plane_least_squares(pts_right)

        # 평행성 확인
        dot = abs(np.dot(n1, n2))
        print(f"  왼쪽 벽: {len(pts_left)}점, normal=[{n1[0]:.3f}, {n1[1]:.3f}, {n1[2]:.3f}]")
        print(f"  오른쪽 벽: {len(pts_right)}점, normal=[{n2[0]:.3f}, {n2[1]:.3f}, {n2[2]:.3f}]")
        print(f"  평행성 (|dot|): {dot:.3f} (0.8 이상이면 평행)")

        # 거리 계산
        dist = plane_distance(n1, d1, n2, d2)
        dist_mm = int(dist * 1000)

        self.result = {
            'dist_mm': dist_mm,
            'n_pts_left': len(pts_left),
            'n_pts_right': len(pts_right),
            'parallelism': round(dot, 3),
            'normal_left': n1.tolist(),
            'normal_right': n2.tolist(),
        }

        # 결과 표시
        self.ax.text(self.W//2, self.H-30,
                     f"측정: {dist_mm}mm | 평행성: {dot:.3f}",
                     color='yellow', fontsize=16, fontweight='bold',
                     ha='center',
                     bbox=dict(boxstyle='round', facecolor='black', alpha=0.7))
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()
        return self.result


# ============================================================
# 테스트: 1장
# ============================================================
print("모델 로딩...")
gc_model = GeoCalib(weights='distorted').to('cpu')
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()
print("완료!\n")

# 테스트 이미지: 개포자이 거실 (이전에 오차 0.3%였던 사진)
test_path = "/Users/honghwasu/Desktop/research_project/data/게포자이프레지던스/개포자이프레지던스 408동저층 110.79㎡:84.75㎡_거실1방향.png"
gt_mm = 4500
gt_adj = gt_mm - 160

print(f"테스트 이미지: 개포자이 408동 거실")
print(f"GT: {gt_mm}mm (마감면 보정: {gt_adj}mm)\n")

# GeoCalib focal
img_gc = gc_model.load_image(test_path).to('cpu')
result_gc = gc_model.calibrate(img_gc)
f_wide = result_gc["camera"].f.mean().item()
print(f"GeoCalib focal: {f_wide:.1f}px")

# Depth Pro
image, _, _ = depth_pro.load_rgb(test_path)
prediction = dp_model.infer(dp_transform(image), f_px=torch.tensor(f_wide))
depth_map = prediction["depth"].detach().cpu().numpy()
print(f"Depth map: {depth_map.shape}, range: {depth_map.min():.2f}~{depth_map.max():.2f}m\n")

# 이미지 로드
img_display = plt.imread(test_path)

# UI 실행
print("=" * 50)
print("사진이 뜨면:")
print("  1. 왼쪽 벽을 드래그 (사각형)")
print("  2. 오른쪽 벽을 드래그 (사각형)")
print("=" * 50)

selector = WallSelector(
    img_display, depth_map, f_wide,
    f"개포자이 408동 거실 | GT={gt_mm}mm | f={f_wide:.0f}px"
)
result = selector.show()

if result:
    error_mm = abs(result['dist_mm'] - gt_adj)
    error_pct = error_mm / gt_adj * 100
    print(f"\n{'='*50}")
    print(f"결과:")
    print(f"  측정 거리: {result['dist_mm']}mm")
    print(f"  GT (마감면): {gt_adj}mm")
    print(f"  오차: {error_mm}mm ({error_pct:.1f}%)")
    print(f"  평행성: {result['parallelism']}")
    print(f"  왼쪽 벽 점: {result['n_pts_left']}개")
    print(f"  오른쪽 벽 점: {result['n_pts_right']}개")
    print(f"{'='*50}")
else:
    print("측정 실패 또는 스킵됨")
