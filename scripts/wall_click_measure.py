"""
벽 클릭 방식 거리 측정
- 왼쪽 벽 클릭 1번 → 오른쪽 벽 클릭 1번
- 클릭 주변 100x100 영역의 depth로 평면 피팅
- 두 평면 사이 수직 거리 = 벽-벽 거리
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")
import numpy as np
import csv
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

# depth map + meta 로드
depth = np.load("/Users/honghwasu/Desktop/research_project/output/depth_maps/029_depth.npy")
H, W = depth.shape

with open("/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row['image_id'] == '029':
            f_wide = float(row['f_wide_geocalib'])
            img_path = row['img_path']
            break

cx, cy = W/2.0, H/2.0
gt_mm = 4500
gt_adj = gt_mm - 160
PATCH = 50  # 클릭 주변 패치 반경

print(f"이미지: {W}x{H}, focal: {f_wide:.0f}px, GT: {gt_adj}mm")
print(f"왼쪽 벽 클릭 → 오른쪽 벽 클릭")

# 클릭 저장
clicks = []

def onclick(event):
    if event.xdata is None or event.ydata is None:
        return
    u, v = int(event.xdata), int(event.ydata)
    clicks.append((u, v))

    if len(clicks) == 1:
        plt.plot(u, v, 'ro', markersize=15)
        plt.title("오른쪽 벽을 클릭하세요", fontsize=14)
        plt.draw()
        print(f"  왼쪽 벽: ({u}, {v})")

    elif len(clicks) == 2:
        plt.plot(u, v, 'bo', markersize=15)
        plt.draw()
        print(f"  오른쪽 벽: ({u}, {v})")

        # 계산
        (u1,v1), (u2,v2) = clicks

        def get_3d_patch(cu, cv):
            x1 = max(0, cu-PATCH)
            x2 = min(W, cu+PATCH)
            y1 = max(0, cv-PATCH)
            y2 = min(H, cv+PATCH)
            u_grid, v_grid = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
            Z = depth[y1:y2, x1:x2]
            X = (u_grid - cx) * Z / f_wide
            Y = (v_grid - cy) * Z / f_wide
            pts = np.stack([X,Y,Z], -1).reshape(-1,3)
            ok = (pts[:,2]>0.3) & (pts[:,2]<15) & np.isfinite(pts).all(1)
            return pts[ok]

        def fit_plane(pts):
            c = pts.mean(0)
            _, _, Vt = np.linalg.svd(pts - c)
            n = Vt[-1]; n /= np.linalg.norm(n)
            return n, -np.dot(n, c)

        pl = get_3d_patch(u1, v1)
        pr = get_3d_patch(u2, v2)

        n1, d1 = fit_plane(pl)
        n2, d2 = fit_plane(pr)

        dot = abs(np.dot(n1, n2))
        dist = abs(d1+d2) if np.dot(n1,n2)<0 else abs(d1-d2)
        mm = int(dist * 1000)
        err = abs(mm - gt_adj)

        print(f"\n  점: 왼쪽 {len(pl)}개, 오른쪽 {len(pr)}개")
        print(f"  평행성: {dot:.3f}")
        print(f"  측정: {mm}mm")
        print(f"  GT: {gt_adj}mm")
        print(f"  오차: {err}mm ({err/gt_adj*100:.1f}%)")

        plt.title(f"측정: {mm}mm | GT: {gt_adj}mm | 오차: {err}mm ({err/gt_adj*100:.1f}%)", fontsize=14)
        plt.draw()

# 이미지 표시
img = plt.imread(img_path)
fig, ax = plt.subplots(figsize=(14, 10))
ax.imshow(img)
ax.set_title("왼쪽 벽을 클릭하세요", fontsize=14)
fig.canvas.mpl_connect('button_press_event', onclick)
plt.show()
