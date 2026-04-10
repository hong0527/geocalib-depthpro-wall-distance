"""
개선 v2 빠른 테스트 — n_iter=300, flush 출력
"""
import sys
import numpy as np
import pandas as pd

def fit_plane_ransac(pts, th=0.05, n_iter=300):
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

def make_points(depth_map, fpx, max_depth=10.0):
    H, W = depth_map.shape
    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx
    pts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    ok = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < max_depth) & np.isfinite(pts).all(1)
    return pts[ok]

def find_walls_and_distance(pts):
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
    return best[0] * 1000 if best else None

def measure_original(depth_map, fpx):
    pts = make_points(depth_map, fpx, max_depth=10.0)
    return find_walls_and_distance(pts)

def measure_v2(depth_map, fpx):
    H, W = depth_map.shape
    # 적응적 깊이 상한
    center = depth_map[H//4:3*H//4, W//4:3*W//4]
    vc = center[(center > 0.5) & np.isfinite(center)]
    if len(vc) > 0:
        adaptive_max = min(np.median(vc) * 2.5, 10.0)
    else:
        adaptive_max = 10.0

    pts = make_points(depth_map, fpx, max_depth=adaptive_max)

    # RANSAC + 깊이 분산 필터
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
            inlier_Z = rem[inl, 2]
            z_std = np.std(inlier_Z)
            z_mean = np.mean(inlier_Z)
            if z_mean > 0 and (z_std / z_mean) < 0.3:
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
    return best[0] * 1000 if best else None

if __name__ == '__main__':
    meta = pd.read_csv('output/depth_maps/depth_meta.csv')
    result = pd.read_csv('output/전체_통합_데이터.csv')

    test_ids = [f'{i:03d}' for i in range(1, 64)]

    print(f"{'ID':>4} | {'Note':<30} | {'GT':>6} | {'기존':>7} {'err':>6} | {'v2':>7} {'err':>6} | {'delta':>7}")
    print("-" * 105)
    sys.stdout.flush()

    orig_errs, v2_errs = [], []
    both_orig, both_v2 = [], []
    improved, worsened = 0, 0

    for tid in test_ids:
        tid_int = int(tid)
        rm = meta[meta['image_id'] == tid_int]
        if rm.empty: continue
        rm = rm.iloc[0]
        rr = result[result['id'] == tid]
        if rr.empty: continue
        rr = rr.iloc[0]

        dm = np.load(rm['npy_path'])
        fpx = rm['f_wide_geocalib']
        gt = rr['gt_adj_mm']
        note = str(rr['note'])[:30]
        vis = rr['wall_visible']

        np.random.seed(42)
        o = measure_original(dm, fpx)
        np.random.seed(42)
        v = measure_v2(dm, fpx)

        oe = abs(o - gt) / gt * 100 if o else None
        ve = abs(v - gt) / gt * 100 if v else None

        os_ = f"{o:7.0f} {oe:5.1f}%" if o else "   FAIL      "
        vs_ = f"{v:7.0f} {ve:5.1f}%" if v else "   FAIL      "

        if oe is not None and ve is not None:
            d = ve - oe
            ds = f"{d:+6.1f}%"
            orig_errs.append(oe); v2_errs.append(ve)
            if d < -1: improved += 1
            elif d > 1: worsened += 1
        else:
            ds = "   -  "

        print(f"{tid:>4} | {note:<30} | {gt:>6.0f} | {os_} | {vs_} | {ds}")
        sys.stdout.flush()

    print()
    print("=" * 105)
    if orig_errs:
        print(f"기존  — 평균: {np.mean(orig_errs):.1f}% | 중앙값: {np.median(orig_errs):.1f}% | N={len(orig_errs)}")
    if v2_errs:
        print(f"개선v2 — 평균: {np.mean(v2_errs):.1f}% | 중앙값: {np.median(v2_errs):.1f}% | N={len(v2_errs)}")
    print(f"개선: {improved} | 악화: {worsened} | 변화없음: {len(orig_errs)-improved-worsened}")
    sys.stdout.flush()
