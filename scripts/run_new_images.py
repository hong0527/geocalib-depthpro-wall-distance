"""
새 이미지 6장 파이프라인 실행
GeoCalib → Depth Pro → 3D 복원 → RANSAC → 거리 측정
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")

import numpy as np
import torch
import time
from geocalib import GeoCalib
import depth_pro

# ============================================================
# RANSAC (기존 파이프라인과 동일)
# ============================================================
def fit_plane_ransac(pts, th=0.05, n_iter=1000):
    best_p, best_i = None, []
    n = len(pts)
    for _ in range(n_iter):
        idx = np.random.choice(n, 3, replace=False)
        p1, p2, p3 = pts[idx]
        nm = np.cross(p2 - p1, p3 - p1)
        nl = np.linalg.norm(nm)
        if nl < 1e-10:
            continue
        nm /= nl
        d = -np.dot(nm, p1)
        dists = np.abs(pts @ nm + d)
        ii = np.where(dists < th)[0]
        if len(ii) > len(best_i):
            best_i, best_p = ii, [nm[0], nm[1], nm[2], d]
    return best_p, best_i

def measure_wall_distance(depth_map, fpx):
    H, W = depth_map.shape
    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx
    pts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    ok = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < 10.0)
    pts = pts[ok]
    pts = pts[np.isfinite(pts).all(1)]

    walls, rem = [], pts.copy()
    for _ in range(6):
        if len(rem) < 500:
            break
        pl, inl = fit_plane_ransac(rem)
        if pl is None:
            break
        nm = np.array(pl[:3])
        nm /= np.linalg.norm(nm)
        if abs(nm[1]) <= 0.7:
            walls.append({'n': nm, 'd': pl[3], 'pts': len(inl)})
        m = np.ones(len(rem), bool)
        m[inl] = False
        rem = rem[m]

    best = None
    for i in range(len(walls)):
        for j in range(i + 1, len(walls)):
            dot = np.dot(walls[i]['n'], walls[j]['n'])
            if abs(dot) > 0.8:
                dist = abs(walls[i]['d'] + walls[j]['d']) if dot < 0 else abs(walls[i]['d'] - walls[j]['d'])
                tp = walls[i]['pts'] + walls[j]['pts']
                if best is None or tp > best[1]:
                    best = (dist, tp)
    return best[0] if best else None, len(walls)

# ============================================================
# 새 이미지 정보
# ============================================================
images = [
    {
        'id': 'N1',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오412동거실_3500_창문쪽.jpg',
        'gt_mm': 3500,
        'room': '거실',
        'wall_visible': 'both_clear',
        'obstacle': 'none',
        'note': '412동 거실 창문쪽, 양쪽벽명확',
    },
    {
        'id': 'N2',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오412동_3500_다른관점.jpg',
        'gt_mm': 3500,
        'room': '거실',
        'wall_visible': 'both_clear',
        'obstacle': 'none',
        'note': '412동 거실 다른관점, 주방쪽',
    },
    {
        'id': 'N3',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오412동_3300_큰방.jpg',
        'gt_mm': 3300,
        'room': '큰방',
        'wall_visible': 'both_clear',
        'obstacle': 'none',
        'note': '412동 큰방, 발코니유리문',
    },
    {
        'id': 'N4',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오412동_2700_작은방2.jpg',
        'gt_mm': 2700,
        'room': '작은방',
        'wall_visible': 'both_clear',
        'obstacle': 'none',
        'note': '412동 작은방2, 양쪽벽명확',
    },
    {
        'id': 'N5',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오412동_2700_작은방1.jpg',
        'gt_mm': 2700,
        'room': '작은방',
        'wall_visible': 'both_clear',
        'obstacle': 'yes',
        'note': '412동 작은방1, 붙박이장있음',
    },
    {
        'id': 'N6',
        'path': '/Users/honghwasu/Downloads/마포래미안푸르지오309동_3000.jpg',
        'gt_mm': 3000,
        'room': '방',
        'wall_visible': 'both_clear',
        'obstacle': 'none',
        'note': '309동 방, 양쪽벽명확+줄무늬벽지',
    },
]

# ============================================================
# 모델 로드
# ============================================================
print("=" * 60)
print("모델 로딩...")
t0 = time.time()

gc_model = GeoCalib(weights='distorted').to('cpu')
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()

print(f"모델 로드 완료: {time.time()-t0:.1f}초")
print("=" * 60)

# ============================================================
# 파이프라인 실행
# ============================================================
gt_adj_offset = 160  # 마감면 보정

results = []
for img_info in images:
    img_id = img_info['id']
    img_path = img_info['path']
    gt_mm = img_info['gt_mm']
    gt_adj = gt_mm - gt_adj_offset

    print(f"\n[{img_id}] {img_info['note']}")
    print(f"  GT: {gt_mm}mm (adj: {gt_adj}mm)")
    sys.stdout.flush()

    if not os.path.exists(img_path):
        print(f"  파일 없음: {img_path}")
        continue

    # 1. GeoCalib
    img_gc = gc_model.load_image(img_path).to('cpu')
    result_gc = gc_model.calibrate(img_gc)
    f_wide = result_gc["camera"].f.mean().item()
    print(f"  GeoCalib focal: {f_wide:.1f}px")

    # 2. Depth Pro
    image, _, _ = depth_pro.load_rgb(img_path)
    prediction = dp_model.infer(dp_transform(image), f_px=torch.tensor(f_wide))
    depth_map = prediction["depth"].detach().cpu().numpy()
    print(f"  Depth map: {depth_map.shape}, range: {depth_map.min():.2f}~{depth_map.max():.2f}m")

    # 3. RANSAC 거리 측정
    np.random.seed(42)
    dist, n_walls = measure_wall_distance(depth_map, f_wide)

    if dist is not None:
        measured_mm = dist * 1000
        error_pct = abs(measured_mm - gt_adj) / gt_adj * 100
        error_cm = abs(measured_mm - gt_adj) / 10
        print(f"  측정: {measured_mm:.0f}mm | 오차: {error_pct:.1f}% ({error_cm:.1f}cm) | 벽: {n_walls}개")
        status = 'ok'
    else:
        measured_mm = None
        error_pct = None
        error_cm = None
        print(f"  RANSAC 실패 (벽 쌍 없음, 벽: {n_walls}개)")
        status = 'ransac_fail'

    results.append({
        **img_info,
        'gt_adj_mm': gt_adj,
        'focal': round(f_wide, 1),
        'measured_mm': measured_mm,
        'error_pct': error_pct,
        'error_cm': error_cm,
        'n_walls': n_walls,
        'status': status,
    })
    sys.stdout.flush()

# ============================================================
# 결과 요약
# ============================================================
print(f"\n{'='*60}")
print("결과 요약")
print(f"{'='*60}")
print(f"{'ID':>4} | {'방':>6} | {'GT':>6} | {'측정':>7} | {'오차':>6} | {'cm':>5} | obs  | note")
print("-" * 85)

ok_results = []
for r in results:
    if r['status'] == 'ok':
        print(f"{r['id']:>4} | {r['room']:>6} | {r['gt_adj_mm']:>5.0f} | {r['measured_mm']:>6.0f} | {r['error_pct']:>5.1f}% | {r['error_cm']:>4.1f} | {r['obstacle']:>4} | {r['note'][:25]}")
        ok_results.append(r)
    else:
        print(f"{r['id']:>4} | {r['room']:>6} | {r['gt_adj_mm']:>5.0f} |   FAIL |     - |     - | {r['obstacle']:>4} | {r['note'][:25]}")

if ok_results:
    errs = [r['error_pct'] for r in ok_results]
    print(f"\n성공: {len(ok_results)}/{len(results)}")
    print(f"평균 오차: {np.mean(errs):.1f}%")
    print(f"중앙값 오차: {np.median(errs):.1f}%")

# CSV 저장
import pandas as pd
df = pd.DataFrame(results)
save_path = '/Users/honghwasu/Desktop/research_project/output/new_images_results.csv'
df.to_csv(save_path, index=False, encoding='utf-8-sig')
print(f"\n결과 저장: {save_path}")
