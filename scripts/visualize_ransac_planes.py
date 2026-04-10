"""
RANSAC이 실제로 어떤 평면을 잡았는지 시각화하는 스크립트.
각 평면의 inlier를 원본 이미지 위에 색칠해서 보여줌.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd
import os

# ============================================================
# RANSAC (파이프라인과 동일)
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


def analyze_image(depth_path, fpx, image_id, gt_adj_mm, note, save_dir):
    """한 이미지에 대해 RANSAC 평면 피팅 결과를 시각화"""
    depth_map = np.load(depth_path)
    H, W = depth_map.shape

    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / fpx
    Y = (v - cy) * Z / fpx

    # 전체 포인트 (픽셀 좌표 추적용)
    pts_all = np.stack([X, Y, Z], -1).reshape(-1, 3)
    pixel_coords = np.stack([v.reshape(-1), u.reshape(-1)], -1)  # (row, col)
    ok = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < 10.0) & np.isfinite(pts_all).all(1)

    pts = pts_all[ok]
    pix = pixel_coords[ok]

    # RANSAC 반복 (최대 6회)
    planes = []
    rem_pts = pts.copy()
    rem_pix = pix.copy()

    for iteration in range(6):
        if len(rem_pts) < 500:
            break
        pl, inl = fit_plane_ransac(rem_pts)
        if pl is None:
            break

        nm = np.array(pl[:3])
        nm /= np.linalg.norm(nm)
        is_wall = abs(nm[1]) <= 0.7

        # 평면의 평균 깊이(Z)
        mean_z = rem_pts[inl, 2].mean()
        mean_dist = abs(pl[3]) / np.linalg.norm(pl[:3])

        planes.append({
            'iteration': iteration,
            'normal': nm,
            'd': pl[3],
            'n_inliers': len(inl),
            'is_wall': is_wall,
            'mean_z': mean_z,
            'mean_dist': mean_dist,
            'inlier_pixels': rem_pix[inl],
            'type': '벽(수직)' if is_wall else '바닥/천장(수평)',
            'normal_y': abs(nm[1]),
        })

        m = np.ones(len(rem_pts), bool)
        m[inl] = False
        rem_pts = rem_pts[m]
        rem_pix = rem_pix[m]

    # 벽 쌍 찾기 (파이프라인과 동일 로직)
    walls = [p for p in planes if p['is_wall']]
    best_pair = None
    best_dist = None
    for i in range(len(walls)):
        for j in range(i + 1, len(walls)):
            dot = np.dot(walls[i]['normal'], walls[j]['normal'])
            if abs(dot) > 0.8:
                if dot < 0:
                    dist = abs(walls[i]['d'] + walls[j]['d'])
                else:
                    dist = abs(walls[i]['d'] - walls[j]['d'])
                tp = walls[i]['n_inliers'] + walls[j]['n_inliers']
                if best_pair is None or tp > best_pair[2]:
                    best_pair = (walls[i], walls[j], tp)
                    best_dist = dist

    # ============================================================
    # 시각화
    # ============================================================
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))

    # 1) 깊이맵
    ax = axes[0]
    im = ax.imshow(depth_map, cmap='viridis')
    ax.set_title(f'Depth Map (ID: {image_id})')
    plt.colorbar(im, ax=ax, fraction=0.046, label='depth (m)')

    # 2) RANSAC 평면 오버레이
    ax = axes[1]
    overlay = np.ones((H, W, 3)) * 0.8  # 회색 배경
    colors = [
        [1, 0, 0],    # 빨강
        [0, 0, 1],    # 파랑
        [0, 0.8, 0],  # 초록
        [1, 0.5, 0],  # 주황
        [0.5, 0, 1],  # 보라
        [0, 0.8, 0.8],# 시안
    ]

    legend_patches = []
    for idx, p in enumerate(planes):
        c = colors[idx % len(colors)]
        rows = p['inlier_pixels'][:, 0]
        cols = p['inlier_pixels'][:, 1]
        overlay[rows, cols] = c

        label = (f"P{idx}: {p['type']} | "
                 f"inliers={p['n_inliers']} | "
                 f"mean_Z={p['mean_z']:.2f}m | "
                 f"|Ny|={p['normal_y']:.2f}")
        if best_pair and (p is best_pair[0] or p is best_pair[1]):
            label += " ★선택됨"
        legend_patches.append(mpatches.Patch(color=c, label=label))

    ax.imshow(overlay)
    ax.set_title('RANSAC Planes (색 = 평면)')
    ax.legend(handles=legend_patches, loc='upper left', fontsize=7,
              framealpha=0.9, facecolor='white')

    # 3) 선택된 벽 쌍만 강조
    ax = axes[2]
    overlay2 = np.ones((H, W, 3)) * 0.9
    if best_pair:
        for k, wall in enumerate([best_pair[0], best_pair[1]]):
            c = [1, 0, 0] if k == 0 else [0, 0, 1]
            rows = wall['inlier_pixels'][:, 0]
            cols = wall['inlier_pixels'][:, 1]
            overlay2[rows, cols] = c

        measured_mm = best_dist * 1000
        error_pct = abs(measured_mm - gt_adj_mm) / gt_adj_mm * 100

        ax.set_title(
            f'선택된 벽 쌍\n'
            f'측정={measured_mm:.0f}mm | GT={gt_adj_mm:.0f}mm | 오차={error_pct:.1f}%'
        )

        p0, p1 = best_pair[0], best_pair[1]
        info = (f"빨강: Z평균={p0['mean_z']:.2f}m, inliers={p0['n_inliers']}\n"
                f"파랑: Z평균={p1['mean_z']:.2f}m, inliers={p1['n_inliers']}")
        ax.text(10, H - 30, info, fontsize=8, color='black',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    else:
        ax.set_title('벽 쌍 없음 (RANSAC 실패)')

    ax.imshow(overlay2)

    fig.suptitle(f'[{image_id}] {note}', fontsize=12, fontweight='bold')
    plt.tight_layout()

    os.makedirs(save_dir, exist_ok=True)
    out_path = os.path.join(save_dir, f'{image_id}_ransac_planes.png')
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  저장: {out_path}")

    # 텍스트 요약
    print(f"\n  === [{image_id}] 평면 분석 ===")
    print(f"  Note: {note}")
    print(f"  GT(adj): {gt_adj_mm}mm")
    for p in planes:
        marker = ""
        if best_pair and (p is best_pair[0] or p is best_pair[1]):
            marker = " ★ 선택됨"
        print(f"    P{p['iteration']}: {p['type']} | "
              f"inliers={p['n_inliers']:,} | "
              f"mean_Z={p['mean_z']:.2f}m | "
              f"|Ny|={p['normal_y']:.3f}{marker}")
    if best_dist:
        print(f"  측정 거리: {best_dist*1000:.0f}mm (오차: {abs(best_dist*1000 - gt_adj_mm)/gt_adj_mm*100:.1f}%)")
    else:
        print(f"  측정 실패: 평행 벽 쌍 없음")
    print()


# ============================================================
# 메인: 오차 큰 이미지 + 창문/발코니 관련 이미지 분석
# ============================================================
if __name__ == '__main__':
    np.random.seed(42)

    meta = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv')
    result = pd.read_csv('/Users/honghwasu/Desktop/research_project/output/전체_통합_데이터.csv')

    save_dir = '/Users/honghwasu/Desktop/research_project/output/ransac_visualization'

    # 분석 대상: 오차 큰 케이스 + 창문/발코니 언급 케이스
    # 기존 63개 중에서 선택
    targets = [
        '004',  # 29.6% 발코니유리 주의
        '010',  # 17.9% 창문 정면
        '012',  # 45.0% 발코니문 정면
        '014',  # 96.9% 좌측 창문, 좁은 방
        '027',  # 1.9%  창문 정면 (잘 된 케이스, 비교용)
        '029',  # 0.3%  창문 정면 (잘 된 케이스, 비교용)
        '039',  # 29.8% 창문 정면, 우측 아일랜드
        '053',  # 12.0% 창문 정면 중앙 (적당한 오차)
        '062',  # 5.4%  창문 정면 (잘 된 케이스)
    ]

    for tid in targets:
        tid_int = int(tid)
        row_meta = meta[meta['image_id'] == tid_int]

        if row_meta.empty:
            print(f"[{tid}] 메타 데이터 없음, 스킵")
            continue

        row_meta = row_meta.iloc[0]
        row_result = result[result['id'] == tid]
        if row_result.empty:
            print(f"[{tid}] 결과 데이터 없음, 스킵")
            continue
        row_result = row_result.iloc[0]

        depth_path = row_meta['npy_path']
        fpx = row_meta['f_wide_geocalib']
        gt_adj_mm = row_result['gt_adj_mm']
        note = row_result['note']

        print(f"\n{'='*60}")
        print(f"분석 중: [{tid}] {note}")
        print(f"{'='*60}")

        analyze_image(depth_path, fpx, tid, gt_adj_mm, note, save_dir)

    print(f"\n완료! 시각화 결과: {save_dir}/")
