"""
개선된 RANSAC 파이프라인 테스트.
기존 vs 개선 결과를 비교하여 창문 오인식 문제가 해결되는지 확인.

개선 사항:
1. 깊이 그래디언트 마스킹: 깊이 급변 영역(창문 경계) 제거
2. 공간 연속성 검증: inlier가 이미지에서 큰 연결 덩어리를 형성하는지 확인
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
from scipy import ndimage
import os

# ============================================================
# 기존 RANSAC (변경 없음)
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
# 기존 파이프라인 (원본 그대로)
# ============================================================
def measure_wall_distance_original(depth_map, fpx):
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
# 개선된 파이프라인
# ============================================================
def create_depth_gradient_mask(depth_map, gradient_th=0.3, dilate_size=5):
    """
    깊이 그래디언트 마스킹:
    깊이가 급변하는 픽셀(창문 경계 등)과 그 주변을 제거.

    gradient_th: 깊이 변화율 임계값 (인접 픽셀 대비)
    dilate_size: 경계 주변 몇 픽셀을 추가로 제거할지
    """
    # Sobel 필터로 깊이 그래디언트 계산
    grad_x = ndimage.sobel(depth_map, axis=1)
    grad_y = ndimage.sobel(depth_map, axis=0)
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    # 급변 영역 마스크
    edge_mask = grad_mag > gradient_th

    # 경계 주변도 제거 (dilation)
    if dilate_size > 0:
        struct = ndimage.generate_binary_structure(2, 1)
        edge_mask = ndimage.binary_dilation(edge_mask, struct, iterations=dilate_size)

    # True = 유효 (급변 아님), False = 제거
    return ~edge_mask


def check_spatial_connectivity(inlier_pixels, H, W, min_region_ratio=0.3):
    """
    공간 연속성 검증:
    inlier 픽셀이 이미지 상에서 큰 연결 덩어리를 형성하는지 확인.

    min_region_ratio: 최대 연결 영역이 전체 inlier의 몇 % 이상이어야 하는지
    반환: (통과 여부, 최대 연결 영역 크기)
    """
    if len(inlier_pixels) == 0:
        return False, 0

    # inlier 픽셀을 이미지 좌표에 매핑
    mask = np.zeros((H, W), dtype=bool)
    rows, cols = inlier_pixels[:, 0], inlier_pixels[:, 1]
    mask[rows, cols] = True

    # 연결 영역 라벨링
    labeled, n_features = ndimage.label(mask)
    if n_features == 0:
        return False, 0

    # 가장 큰 연결 영역
    region_sizes = ndimage.sum(mask, labeled, range(1, n_features + 1))
    max_region = max(region_sizes)

    ratio = max_region / len(inlier_pixels)
    return ratio >= min_region_ratio, max_region


def measure_wall_distance_improved(depth_map, fpx, gradient_th=0.3, dilate_size=5,
                                    min_region_ratio=0.3):
    H, W = depth_map.shape
    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx

    # --- 개선 1: 깊이 그래디언트 마스킹 ---
    grad_mask = create_depth_gradient_mask(depth_map, gradient_th, dilate_size)

    pts_all = np.stack([X, Y, Z], -1).reshape(-1, 3)
    pixel_coords = np.stack([v.reshape(-1), u.reshape(-1)], -1)

    ok = ((Z.reshape(-1) > 0.5) & (Z.reshape(-1) < 10.0) &
          np.isfinite(pts_all).all(1) &
          grad_mask.reshape(-1))  # 그래디언트 마스크 추가

    pts = pts_all[ok]
    pix = pixel_coords[ok]

    walls, rem_pts, rem_pix = [], pts.copy(), pix.copy()
    for _ in range(6):
        if len(rem_pts) < 500:
            break
        pl, inl = fit_plane_ransac(rem_pts)
        if pl is None:
            break
        nm = np.array(pl[:3])
        nm /= np.linalg.norm(nm)

        if abs(nm[1]) <= 0.7:  # 수직 평면
            inlier_pix = rem_pix[inl]

            # --- 개선 2: 공간 연속성 검증 ---
            is_connected, max_region = check_spatial_connectivity(
                inlier_pix, H, W, min_region_ratio)

            if is_connected:
                walls.append({
                    'n': nm, 'd': pl[3], 'pts': len(inl),
                    'max_region': max_region,
                    'inlier_pixels': inlier_pix
                })

        m = np.ones(len(rem_pts), bool)
        m[inl] = False
        rem_pts = rem_pts[m]
        rem_pix = rem_pix[m]

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
# 비교 테스트
# ============================================================
if __name__ == '__main__':
    np.random.seed(42)

    meta = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv')
    result = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/전체_통합_데이터.csv')

    # 테스트 대상: 창문 관련 오차가 큰 이미지 + 잘 되는 이미지
    targets = ['004', '010', '012', '014', '027', '029', '039', '053', '062']

    print(f"{'ID':>4} | {'Note':<30} | {'GT':>6} | {'기존':>7} {'오차':>6} | {'개선':>7} {'오차':>6} | {'변화':>6}")
    print("-" * 110)

    for tid in targets:
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
        note = str(row_result['note'])[:30]

        depth_map = np.load(depth_path)

        # 기존
        np.random.seed(42)
        orig_dist, orig_nw = measure_wall_distance_original(depth_map, fpx)
        orig_mm = orig_dist * 1000 if orig_dist else None
        orig_err = abs(orig_mm - gt_adj) / gt_adj * 100 if orig_mm else None

        # 개선
        np.random.seed(42)
        impr_dist, impr_nw = measure_wall_distance_improved(depth_map, fpx)
        impr_mm = impr_dist * 1000 if impr_dist else None
        impr_err = abs(impr_mm - gt_adj) / gt_adj * 100 if impr_mm else None

        orig_str = f"{orig_mm:7.0f} {orig_err:5.1f}%" if orig_mm else "  FAIL      "
        impr_str = f"{impr_mm:7.0f} {impr_err:5.1f}%" if impr_mm else "  FAIL      "

        if orig_err is not None and impr_err is not None:
            delta = impr_err - orig_err
            delta_str = f"{delta:+.1f}%"
        else:
            delta_str = "  -  "

        print(f"{tid:>4} | {note:<30} | {gt_adj:>6.0f} | {orig_str} | {impr_str} | {delta_str}")

    print()
    print("음수 = 개선됨, 양수 = 악화됨")
