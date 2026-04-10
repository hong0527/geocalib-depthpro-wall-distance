"""
63장 전체 depth map을 .npy로 저장
나중에 수동 벽 지정할 때 Depth Pro 대기 없이 바로 사용 가능
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")

import csv
import time
import unicodedata
import re
import numpy as np
import torch
import depth_pro
from geocalib import GeoCalib

# ============================================================
# 설정
# ============================================================
DATA_DIR = "/Users/honghwasu/Desktop/research_project/data"
CSV_PATH = "/Users/honghwasu/Desktop/research_project/depth_dataset_v1.csv"
DEPTH_DIR = "/Users/honghwasu/Desktop/research_project/output/depth_maps"
os.makedirs(DEPTH_DIR, exist_ok=True)

# ============================================================
# 파일 매칭
# ============================================================
def normalize_name(s):
    s = unicodedata.normalize('NFC', s)
    base, ext = os.path.splitext(s)
    base = re.sub(r'[^a-zA-Z0-9가-힣]', '', base)
    return base, ext.lower()

actual_files = {}
for root, dirs, files in os.walk(DATA_DIR):
    for f in files:
        if f.startswith('.') or '스크린샷' in unicodedata.normalize('NFC', f):
            continue
        nb, ext = normalize_name(f)
        key = nb + ext
        actual_files[key] = os.path.join(root, f)

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

# ============================================================
# 모델 로드
# ============================================================
print("=" * 60, flush=True)
print("모델 로딩...", flush=True)
t0 = time.time()

gc_model = GeoCalib(weights='distorted').to('cpu')
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()

print(f"모델 로딩 완료 ({time.time()-t0:.1f}s)", flush=True)

# ============================================================
# CSV 로드
# ============================================================
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"총 {len(rows)}장 처리 예정\n", flush=True)

# ============================================================
# depth map 생성 + 저장
# ============================================================
total_start = time.time()
meta_list = []  # focal 등 메타 정보 저장

for idx, row in enumerate(rows):
    img_id = row['image_id']
    csv_fn = row['filename']
    gt_mm = int(row['gt_mm'])
    wall_vis = row['wall_visible']
    room = row['room']

    img_path = find_image_path(csv_fn)
    if not img_path:
        print(f"[{img_id:>3}/{len(rows)}] ❌ 파일 못 찾음: {csv_fn}", flush=True)
        continue

    # 진행률 파일
    with open('/Users/honghwasu/Desktop/research_project/output/progress.txt', 'w') as pf:
        pf.write(f"{idx+1}/{len(rows)} processing: {csv_fn}\n")

    t1 = time.time()

    try:
        # GeoCalib → focal length
        img_gc = gc_model.load_image(img_path).to('cpu')
        result_gc = gc_model.calibrate(img_gc)
        f_wide = result_gc["camera"].f.mean().item()

        # Depth Pro → depth map (GeoCalib focal 사용)
        image, _, _ = depth_pro.load_rgb(img_path)
        prediction = dp_model.infer(dp_transform(image), f_px=torch.tensor(f_wide))
        depth_map = prediction["depth"].detach().cpu().numpy()
        f_dp_estimated = prediction["focallength_px"].item()

        # depth map 저장
        npy_path = os.path.join(DEPTH_DIR, f"{img_id}_depth.npy")
        np.save(npy_path, depth_map)

        # 메타 정보 저장
        meta_list.append({
            'image_id': img_id,
            'filename': csv_fn,
            'img_path': img_path,
            'wall_visible': wall_vis,
            'room': room,
            'direction': row['direction'],
            'gt_mm': gt_mm,
            'gt_adj_mm': gt_mm - 160,
            'f_wide_geocalib': round(f_wide, 1),
            'f_estimated_depthpro': round(f_dp_estimated, 1),
            'depth_shape': f"{depth_map.shape[0]}x{depth_map.shape[1]}",
            'depth_min': round(float(depth_map.min()), 3),
            'depth_max': round(float(depth_map.max()), 3),
            'npy_path': npy_path,
            'note': row['note']
        })

        elapsed = time.time() - t1
        print(f"[{img_id:>3}/{len(rows)}] f_gc={f_wide:.0f} f_dp={f_dp_estimated:.0f} depth={depth_map.min():.1f}~{depth_map.max():.1f}m [{elapsed:.1f}s]", flush=True)

    except Exception as e:
        elapsed = time.time() - t1
        print(f"[{img_id:>3}/{len(rows)}] ❌ 에러: {str(e)[:60]} [{elapsed:.1f}s]", flush=True)

# ============================================================
# 메타 정보 CSV 저장
# ============================================================
meta_path = os.path.join(DEPTH_DIR, "depth_meta.csv")
if meta_list:
    fieldnames = list(meta_list[0].keys())
    with open(meta_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(meta_list)

total_time = time.time() - total_start
print(f"\n{'='*60}", flush=True)
print(f"완료! {len(meta_list)}장 저장, {total_time/60:.1f}분", flush=True)
print(f"depth maps: {DEPTH_DIR}/", flush=True)
print(f"메타 정보: {meta_path}", flush=True)
print(f"{'='*60}", flush=True)
