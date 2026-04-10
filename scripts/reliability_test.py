"""
신뢰도 테스트: 13장을 각 3회씩 반복 측정
RANSAC이 매번 같은 결과를 주는지 확인
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import numpy as np
import csv

# 13장 ID
accurate_ids = ['036','029','020','013','032','023','027','045','041','052','026','022','050']

# meta 로드
meta = {}
with open("/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        meta[row['image_id']] = row

# RANSAC 함수 (기존과 동일)
def fit_plane_ransac(pts, th=0.05, n_iter=300):
    best_p, best_i = None, []
    n = len(pts)
    for _ in range(n_iter):
        idx = np.random.choice(n, 3, replace=False)
        p1, p2, p3 = pts[idx]
        nm = np.cross(p2 - p1, p3 - p1)
        nl = np.linalg.norm(nm)
        if nl < 1e-10: continue
        nm /= nl
        d = -np.dot(nm, p1)
        dists = np.abs(pts @ nm + d)
        ii = np.where(dists < th)[0]
        if len(ii) > len(best_i):
            best_i, best_p = ii, [nm[0], nm[1], nm[2], d]
    return best_p, best_i

def measure_wall_distance(depth_map, fpx):
    H, W = depth_map.shape
    cx, cy = W/2.0, H/2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx
    pts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    ok = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < 10.0)
    pts = pts[ok]
    pts = pts[np.isfinite(pts).all(1)]
    if len(pts) > 30000:
        idx = np.random.choice(len(pts), 30000, replace=False)
        pts = pts[idx]

    walls, rem = [], pts.copy()
    for _ in range(6):
        if len(rem) < 500: break
        pl, inl = fit_plane_ransac(rem)
        if pl is None: break
        nm = np.array(pl[:3]); nm /= np.linalg.norm(nm)
        if abs(nm[1]) <= 0.7:
            walls.append({'n': nm, 'd': pl[3], 'pts': len(inl)})
        m = np.ones(len(rem), bool); m[inl] = False; rem = rem[m]

    best = None
    for i in range(len(walls)):
        for j in range(i+1, len(walls)):
            dot = np.dot(walls[i]['n'], walls[j]['n'])
            if abs(dot) > 0.8:
                dist = abs(walls[i]['d'] + walls[j]['d']) if dot < 0 else abs(walls[i]['d'] - walls[j]['d'])
                tp = walls[i]['pts'] + walls[j]['pts']
                if best is None or tp > best[1]:
                    best = (dist, tp)
    return int(best[0] * 1000) if best else None

# 고정 영역 방식 (확정적)
def measure_fixed_region(depth_map, fpx):
    H, W = depth_map.shape
    cx, cy = W/2.0, H/2.0

    # 왼쪽 벽: 2~12%, 높이 25~75%
    lx1, ly1 = int(W*0.02), int(H*0.25)
    lx2, ly2 = int(W*0.12), int(H*0.75)
    # 오른쪽 벽: 88~98%
    rx1, ry1 = int(W*0.88), int(H*0.25)
    rx2, ry2 = int(W*0.98), int(H*0.75)

    def to_3d(x1, y1, x2, y2):
        u, v = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
        Z = depth_map[y1:y2, x1:x2]
        X = (u - cx) * Z / fpx
        Y = (v - cy) * Z / fpx
        pts = np.stack([X,Y,Z], -1).reshape(-1,3)
        ok = (pts[:,2]>0.3) & (pts[:,2]<15) & np.isfinite(pts).all(1)
        return pts[ok]

    def fit_plane(pts):
        c = pts.mean(0)
        _, _, Vt = np.linalg.svd(pts - c)
        n = Vt[-1]; n /= np.linalg.norm(n)
        return n, -np.dot(n, c)

    pl = to_3d(lx1, ly1, lx2, ly2)
    pr = to_3d(rx1, ry1, rx2, ry2)
    if len(pl) < 10 or len(pr) < 10:
        return None

    n1, d1 = fit_plane(pl)
    n2, d2 = fit_plane(pr)
    dist = abs(d1+d2) if np.dot(n1,n2)<0 else abs(d1-d2)
    return int(dist * 1000)

# 반복 측정
N_REPEAT = 3
print("=" * 80)
print(f"신뢰도 테스트: 13장 × {N_REPEAT}회 반복")
print("=" * 80)
print(f"{'ID':>4} {'GT':>6} {'RANSAC 1':>9} {'RANSAC 2':>9} {'RANSAC 3':>9} {'편차':>6} {'고정영역':>8}")
print("-" * 80)

all_results = []

for rid in accurate_ids:
    m = meta[rid]
    depth = np.load(m['npy_path'])
    fw = float(m['f_wide_geocalib'])
    gt_adj = int(m['gt_mm']) - 160

    # RANSAC 3회
    ransac_results = []
    for trial in range(N_REPEAT):
        r = measure_wall_distance(depth, fw)
        ransac_results.append(r if r else 0)

    # 고정 영역 (확정적 - 1회만)
    fixed = measure_fixed_region(depth, fw)

    # 편차
    valid_ransac = [r for r in ransac_results if r > 100]
    if valid_ransac:
        std = int(np.std(valid_ransac))
        mean_r = int(np.mean(valid_ransac))
    else:
        std = -1
        mean_r = 0

    r1, r2, r3 = ransac_results
    fx = fixed if fixed else 0

    print(f"{rid:>4} {gt_adj:>5}mm {r1:>8}mm {r2:>8}mm {r3:>8}mm {std:>5}mm {fx:>7}mm")

    all_results.append({
        'id': rid, 'gt': gt_adj,
        'r1': r1, 'r2': r2, 'r3': r3,
        'std': std, 'mean_ransac': mean_r,
        'fixed': fx,
        'room': m['room']
    })

# 통계
print(f"\n{'='*80}")
print("요약")
print("="*80)

stds = [r['std'] for r in all_results if r['std'] >= 0]
print(f"RANSAC 반복 편차: 평균 {sum(stds)/len(stds):.0f}mm, 최대 {max(stds)}mm")

# RANSAC 평균 vs 고정영역 vs GT 비교
print(f"\n{'ID':>4} {'GT':>6} {'RANSAC평균':>10} {'R오차':>7} {'고정영역':>8} {'F오차':>7}")
print("-" * 60)
for r in all_results:
    if r['mean_ransac'] > 100:
        r_err = abs(r['mean_ransac'] - r['gt']) / r['gt'] * 100
    else:
        r_err = -1
    if r['fixed'] > 100:
        f_err = abs(r['fixed'] - r['gt']) / r['gt'] * 100
    else:
        f_err = -1

    r_str = f"{r_err:.1f}%" if r_err >= 0 else "fail"
    f_str = f"{f_err:.1f}%" if f_err >= 0 else "fail"
    print(f"{r['id']:>4} {r['gt']:>5}mm {r['mean_ransac']:>9}mm {r_str:>7} {r['fixed']:>7}mm {f_str:>7}")
