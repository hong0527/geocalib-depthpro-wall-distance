"""
파일럿 테스트: 1장으로 GeoCalib + Depth Pro + RANSAC 파이프라인 검증
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")

import csv
import os
import unicodedata
import numpy as np
import torch
from pathlib import Path

# ============================================================
# Step 0: CSV 로드 + 이미지 경로 매칭
# ============================================================
print("=" * 60)
print("Step 0: CSV 로드 + 이미지 매칭")
print("=" * 60)

DATA_DIR = "/Users/honghwasu/Desktop/research_project/data"
CSV_PATH = "/Users/honghwasu/Desktop/research_project/depth_dataset_v1.csv"

import re

def normalize_name(s):
    s = unicodedata.normalize('NFC', s)
    base, ext = os.path.splitext(s)
    base = re.sub(r'[^a-zA-Z0-9가-힣]', '', base)
    return base, ext.lower()

# 실제 파일 인덱스 구축
actual_files = {}
for root, dirs, files in os.walk(DATA_DIR):
    for f in files:
        if f.startswith('.') or '스크린샷' in unicodedata.normalize('NFC', f):
            continue
        nb, ext = normalize_name(f)
        key = nb + ext
        actual_files[key] = os.path.join(root, f)

# CSV 읽기
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

def find_image_path(csv_filename):
    nb, ext = normalize_name(csv_filename)
    key = nb + ext
    if key in actual_files:
        return actual_files[key]
    for try_ext in ['.png', '.jpg', '.jpeg']:
        alt = nb + try_ext
        if alt in actual_files:
            return actual_files[alt]
    return None

# both_clear 첫 번째 이미지로 테스트
test_row = None
for r in rows:
    if r['wall_visible'] == 'both_clear':
        path = find_image_path(r['filename'])
        if path:
            test_row = r
            test_path = path
            break

print(f"  테스트 이미지: [{test_row['image_id']}] {test_row['filename']}")
print(f"  실제 경로: {test_path}")
print(f"  GT: {test_row['gt_mm']}mm  방: {test_row['room']}")

# ============================================================
# Step 1: GeoCalib - focal length 추정 + barrel distortion 보정
# ============================================================
print("\n" + "=" * 60)
print("Step 1: GeoCalib - focal length + 왜곡 보정")
print("=" * 60)

from geocalib import GeoCalib

device = "cpu"  # GeoCalib은 CPU에서 실행 (grid_sampler MPS 미지원)
print(f"  Device: {device}")

geocalib_model = GeoCalib(weights='distorted').to(device)
image_gc = geocalib_model.load_image(test_path).to(device)  # [1,C,H,W]
result_gc = geocalib_model.calibrate(image_gc)

camera = result_gc["camera"]
f_wide = camera.f.mean().item()  # focal length in pixels
print(f"  추정 focal length: {f_wide:.1f} px")
print(f"  Camera type: {type(camera).__name__}")

# Barrel distortion 보정 이미지 생성
# undistort_image expects [N,C,H,W] but load_image returns [C,H,W]
img_for_undist = image_gc if image_gc.dim() == 4 else image_gc.unsqueeze(0)
undistorted = camera.undistort_image(img_for_undist)  # [1,C,H,W]
from torchvision.utils import save_image
output_dir = "/Users/honghwasu/Desktop/research_project/output"
os.makedirs(output_dir, exist_ok=True)
save_image(undistorted.squeeze(0), os.path.join(output_dir, "test_corrected.png"))
print(f"  보정 이미지 저장: output/test_corrected.png")

# ============================================================
# Step 2: Depth Pro - 원본 + 보정 이미지 depth 추정
# ============================================================
print("\n" + "=" * 60)
print("Step 2: Depth Pro - depth map 생성")
print("=" * 60)

import depth_pro

dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()

# 2A: 원본 이미지 (f_wide from GeoCalib)
image_orig, _, _ = depth_pro.load_rgb(test_path)
prediction_orig = dp_model.infer(dp_transform(image_orig), f_px=torch.tensor(f_wide))
depth_orig = prediction_orig["depth"].detach().cpu().numpy()
print(f"  [원본] depth range: {depth_orig.min():.2f} ~ {depth_orig.max():.2f} m")

# 2B: 보정 이미지 (같은 f_wide)
corrected_path = os.path.join(output_dir, "test_corrected.png")
image_corr, _, _ = depth_pro.load_rgb(corrected_path)
prediction_corr = dp_model.infer(dp_transform(image_corr), f_px=torch.tensor(f_wide))
depth_corr = prediction_corr["depth"].detach().cpu().numpy()
print(f"  [보정] depth range: {depth_corr.min():.2f} ~ {depth_corr.max():.2f} m")

# ============================================================
# Step 3: RANSAC plane fitting → 벽-벽 거리 자동 측정
# ============================================================
print("\n" + "=" * 60)
print("Step 3: RANSAC 벽 탐색 + 거리 측정")
print("=" * 60)

def measure_wall_distance(depth_map, focal_px, label=""):
    H, W = depth_map.shape
    cx, cy = W / 2.0, H / 2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth_map
    X = (u - cx) * Z / focal_px
    Y = (v - cy) * Z / focal_px
    points = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
    valid = (Z.reshape(-1) > 0.5) & (Z.reshape(-1) < 8.0)
    points = points[valid]

    def fit_plane_ransac(pts, threshold=0.05, n_iter=1000):
        best_plane = None
        best_inliers = []
        n = len(pts)
        for _ in range(n_iter):
            idx = np.random.choice(n, 3, replace=False)
            p1, p2, p3 = pts[idx]
            normal = np.cross(p2 - p1, p3 - p1)
            norm_len = np.linalg.norm(normal)
            if norm_len < 1e-10:
                continue
            normal = normal / norm_len
            d = -np.dot(normal, p1)
            dists = np.abs(pts @ normal + d)
            inlier_idx = np.where(dists < threshold)[0]
            if len(inlier_idx) > len(best_inliers):
                best_inliers = inlier_idx
                best_plane = [normal[0], normal[1], normal[2], d]
        return best_plane, best_inliers

    walls = []
    remaining = points.copy()
    for i in range(6):
        if len(remaining) < 500:
            break
        plane, inliers = fit_plane_ransac(remaining, threshold=0.05, n_iter=1000)
        if plane is None:
            break
        normal = np.array(plane[:3])
        normal = normal / np.linalg.norm(normal)
        n_pts = len(inliers)
        if abs(normal[1]) > 0.7:
            ptype = "floor/ceiling"
        else:
            ptype = "WALL"
            walls.append({"normal": normal, "d": plane[3], "points": n_pts})
        mask = np.ones(len(remaining), dtype=bool)
        mask[inliers] = False
        remaining = remaining[mask]

    # 평행 벽 쌍 찾기
    best_dist = None
    for i in range(len(walls)):
        for j in range(i + 1, len(walls)):
            n1 = walls[i]["normal"]
            n2 = walls[j]["normal"]
            dot = np.dot(n1, n2)
            if abs(dot) > 0.8:
                d1 = walls[i]["d"]
                d2 = walls[j]["d"]
                dist = abs(d1 + d2) if dot < 0 else abs(d1 - d2)
                if best_dist is None or walls[i]["points"] + walls[j]["points"] > best_dist[1]:
                    best_dist = (dist, walls[i]["points"] + walls[j]["points"])

    if best_dist:
        return best_dist[0], len(walls)
    return None, len(walls)

# 원본
dist_orig, n_walls_orig = measure_wall_distance(depth_orig, f_wide, "원본")
# 보정
dist_corr, n_walls_corr = measure_wall_distance(depth_corr, f_wide, "보정")

print(f"  [원본] 벽 {n_walls_orig}개 발견, 거리: {dist_orig:.3f}m = {int(dist_orig*1000)}mm" if dist_orig else f"  [원본] 벽 거리 측정 실패 (벽 {n_walls_orig}개)")
print(f"  [보정] 벽 {n_walls_corr}개 발견, 거리: {dist_corr:.3f}m = {int(dist_corr*1000)}mm" if dist_corr else f"  [보정] 벽 거리 측정 실패 (벽 {n_walls_corr}개)")

# ============================================================
# Step 4: ER 계산 + GT 비교
# ============================================================
print("\n" + "=" * 60)
print("Step 4: 결과")
print("=" * 60)

gt_mm = int(test_row['gt_mm'])
gt_m = gt_mm / 1000.0
# GT 벽중심선 → 마감면 보정 (두께 ~160mm 가정, 양쪽 절반씩 차감)
gt_m_adjusted = gt_m - 0.16  # 벽두께 160mm 차감
print(f"  GT (벽중심선): {gt_mm}mm")
print(f"  GT (마감면 보정): {int(gt_m_adjusted*1000)}mm")

if dist_orig and dist_corr:
    ER = dist_orig / dist_corr
    error_orig = abs(dist_orig - gt_m_adjusted)
    error_corr = abs(dist_corr - gt_m_adjusted)
    print(f"  D_wide (원본):     {int(dist_orig*1000)}mm  (오차: {int(error_orig*1000)}mm)")
    print(f"  D_corrected (보정): {int(dist_corr*1000)}mm  (오차: {int(error_corr*1000)}mm)")
    print(f"  ER = D_wide / D_corrected = {ER:.4f}")
    if ER > 1.0:
        print(f"  → barrel distortion이 거리를 {(ER-1)*100:.1f}% 과장시킴")
    elif ER < 1.0:
        print(f"  → 보정 후 오히려 {(1-ER)*100:.1f}% 더 크게 추정")
    else:
        print(f"  → 보정 효과 없음")
else:
    print("  벽 거리 측정 실패 - 결과 계산 불가")

print("\n파일럿 테스트 완료!")
