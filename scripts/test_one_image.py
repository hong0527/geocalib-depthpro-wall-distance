"""1장 테스트: 저장된 depth map으로 벽 거리 측정 (GUI 없음)"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import numpy as np
import csv

# depth map 로드
depth = np.load("/Users/honghwasu/Desktop/research_project/output/depth_maps/029_depth.npy")
H, W = depth.shape
print(f"이미지: {W}x{H}")
print(f"depth: {depth.min():.2f}~{depth.max():.2f}m")

# focal 로드
with open("/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        if row['image_id'] == '029':
            f_wide = float(row['f_wide_geocalib'])
            break
print(f"focal: {f_wide}px")

cx, cy = W/2.0, H/2.0

# 왼쪽 벽 영역 (이미지 왼쪽 2~12%, 높이 25~75%)
lx1, ly1 = int(W*0.02), int(H*0.25)
lx2, ly2 = int(W*0.12), int(H*0.75)

# 오른쪽 벽 영역 (이미지 오른쪽 88~98%, 높이 25~75%)
rx1, ry1 = int(W*0.88), int(H*0.25)
rx2, ry2 = int(W*0.98), int(H*0.75)

print(f"왼쪽벽: ({lx1},{ly1})~({lx2},{ly2})")
print(f"오른쪽벽: ({rx1},{ry1})~({rx2},{ry2})")

# 3D 변환
def to_3d(x1, y1, x2, y2):
    u, v = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
    Z = depth[y1:y2, x1:x2]
    X = (u - cx) * Z / f_wide
    Y = (v - cy) * Z / f_wide
    pts = np.stack([X,Y,Z], -1).reshape(-1,3)
    ok = (pts[:,2]>0.3) & (pts[:,2]<15) & np.isfinite(pts).all(1)
    return pts[ok]

pl = to_3d(lx1, ly1, lx2, ly2)
pr = to_3d(rx1, ry1, rx2, ry2)
print(f"왼쪽 {len(pl)}점, 오른쪽 {len(pr)}점")

# 평면 피팅
def fit(pts):
    c = pts.mean(0)
    _, _, Vt = np.linalg.svd(pts - c)
    n = Vt[-1]; n /= np.linalg.norm(n)
    return n, -np.dot(n, c)

n1, d1 = fit(pl)
n2, d2 = fit(pr)
dot = abs(np.dot(n1, n2))
print(f"평행성: {dot:.3f}")

# 거리
dist = abs(d1+d2) if np.dot(n1,n2)<0 else abs(d1-d2)
mm = int(dist*1000)
gt = 4340  # 4500-160
err = abs(mm - gt)
print(f"\n측정: {mm}mm")
print(f"GT: {gt}mm")
print(f"오차: {err}mm ({err/gt*100:.1f}%)")

# X좌표 차이도 확인
xdiff = abs(pl[:,0].mean() - pr[:,0].mean()) * 1000
print(f"X차이(단순): {xdiff:.0f}mm")
