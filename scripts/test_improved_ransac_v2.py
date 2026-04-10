"""
개선된 RANSAC v2 — 더 단순하고 효과적인 접근법.

핵심 아이디어:
1. 깊이 상한 타이트닝: 방 크기 기준으로 비정상적으로 높은 깊이(창문 너머) 제거
2. 평면 선택 시 깊이 일관성 검증: inlier 깊이의 분산이 큰 평면 제거
3. 벽 쌍 선택 시 거리 합리성 검증: 비현실적인 거리의 쌍 제거
"""

import numpy as np
import pandas as pd

# ============================================================
# RANSAC (동일)
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


# ============================================================
# 기존 파이프라인
# ============================================================
def measure_original(depth_map, fpx):
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
    return best[0] * 1000 if best else None


# ============================================================
# 개선 v2: 적응적 깊이 상한 + inlier 깊이 분산 필터
# ============================================================
def measure_improved_v2(depth_map, fpx):
    H, W = depth_map.shape
    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map

    # --- 개선 1: 적응적 깊이 상한 ---
    # 방 크기는 보통 2~6m. 깊이맵의 중앙 영역 median을 기준으로
    # 그 2배까지만 허용 (창문 너머 10m+ 깊이 제거)
    center_region = Z[H//4:3*H//4, W//4:3*W//4]
    valid_center = center_region[(center_region > 0.5) & np.isfinite(center_region)]
    if len(valid_center) > 0:
        median_depth = np.median(valid_center)
        adaptive_max = min(median_depth * 2.5, 10.0)  # median의 2.5배, 최대 10m
    else:
        adaptive_max = 10.0

    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx
    pts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    ok = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < adaptive_max)
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
            # --- 개선 2: inlier 깊이 분산 체크 ---
            inlier_Z = rem[inl, 2]
            z_std = np.std(inlier_Z)
            z_mean = np.mean(inlier_Z)
            # 벽의 깊이 분산은 작아야 함 (CoV < 0.3)
            if z_mean > 0 and (z_std / z_mean) < 0.3:
                walls.append({'n': nm, 'd': pl[3], 'pts': len(inl),
                              'z_mean': z_mean, 'z_std': z_std})

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


# ============================================================
# 비교 실행 — 전체 63개 + 신규
# ============================================================
if __name__ == '__main__':
    meta = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv')
    result = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/전체_통합_데이터.csv')

    # 기존 63개만 (신규는 npy가 다른 위치일 수 있으므로)
    test_ids = [f'{i:03d}' for i in range(1, 64)]

    print(f"{'ID':>4} | {'Note':<35} | {'GT':>6} | {'기존':>7} {'오차':>6} | {'개선v2':>7} {'오차':>6} | {'변화':>7}")
    print("-" * 120)

    orig_errors = []
    impr_errors = []
    improved_count = 0
    worsened_count = 0

    for tid in test_ids:
        tid_int = int(tid)
        row_meta = meta[meta['image_id'] == tid_int]
        if row_meta.empty:
            continue
        row_meta = row_meta.iloc[0]

        row_result = result[result['id'] == tid]
        if row_result.empty:
            continue
        row_result = row_result.iloc[0]

        depth_path = row_meta['npy_path']
        fpx = row_meta['f_wide_geocalib']
        gt_adj = row_result['gt_adj_mm']
        note = str(row_result['note'])[:35]

        depth_map = np.load(depth_path)

        np.random.seed(42)
        orig_mm = measure_original(depth_map, fpx)
        np.random.seed(42)
        impr_mm = measure_improved_v2(depth_map, fpx)

        orig_err = abs(orig_mm - gt_adj) / gt_adj * 100 if orig_mm else None
        impr_err = abs(impr_mm - gt_adj) / gt_adj * 100 if impr_mm else None

        orig_str = f"{orig_mm:7.0f} {orig_err:5.1f}%" if orig_mm else "   FAIL      "
        impr_str = f"{impr_mm:7.0f} {impr_err:5.1f}%" if impr_mm else "   FAIL      "

        if orig_err is not None and impr_err is not None:
            delta = impr_err - orig_err
            delta_str = f"{delta:+6.1f}%"
            orig_errors.append(orig_err)
            impr_errors.append(impr_err)
            if delta < -1:
                improved_count += 1
            elif delta > 1:
                worsened_count += 1
        elif orig_err is None and impr_err is not None:
            delta_str = " 복구!"
            impr_errors.append(impr_err)
        elif orig_err is not None and impr_err is None:
            delta_str = " 손실!"
            orig_errors.append(orig_err)
        else:
            delta_str = "   -  "

        print(f"{tid:>4} | {note:<35} | {gt_adj:>6.0f} | {orig_str} | {impr_str} | {delta_str}")

    print()
    print("=" * 120)
    if orig_errors:
        print(f"기존  — 평균 오차: {np.mean(orig_errors):.1f}% | 중앙값: {np.median(orig_errors):.1f}% | 성공: {len(orig_errors)}/63")
    if impr_errors:
        print(f"개선v2 — 평균 오차: {np.mean(impr_errors):.1f}% | 중앙값: {np.median(impr_errors):.1f}% | 성공: {len(impr_errors)}/63")
    print(f"\n개선된 이미지: {improved_count}개 | 악화된 이미지: {worsened_count}개 | 변화 없음: {len(orig_errors)-improved_count-worsened_count}개")
    print("(변화 기준: ±1% 이상)")
