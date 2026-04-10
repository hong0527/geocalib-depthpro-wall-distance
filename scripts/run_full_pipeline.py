"""
63장 전체 파이프라인 실행
GeoCalib(distorted) → Depth Pro(원본/보정) → RANSAC → ER + GT 비교
결과를 CSV로 저장
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
from torchvision.utils import save_image
from geocalib import GeoCalib
import depth_pro

# ============================================================
# 설정
# ============================================================
DATA_DIR = "/Users/honghwasu/Desktop/research_project/data"
CSV_PATH = "/Users/honghwasu/Desktop/research_project/depth_dataset_v1.csv"
OUTPUT_DIR = "/Users/honghwasu/Desktop/research_project/output"
RESULT_CSV = "/Users/honghwasu/Desktop/research_project/results_full.csv"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUTPUT_DIR, "corrected"), exist_ok=True)

# ============================================================
# 파일 매칭 함수
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
# RANSAC
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
# 모델 로드
# ============================================================
print("=" * 60)
print("모델 로딩...")
print("=" * 60)
t0 = time.time()

gc_model = GeoCalib(weights='distorted').to('cpu')
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()

print(f"모델 로딩 완료 ({time.time()-t0:.1f}s)")

# ============================================================
# CSV 읽기
# ============================================================
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"총 {len(rows)}장 처리 예정\n")

# ============================================================
# 전체 실행
# ============================================================
results = []
total_start = time.time()

for idx, row in enumerate(rows):
    img_id = row['image_id']
    csv_fn = row['filename']
    gt_mm = int(row['gt_mm'])
    wall_vis = row['wall_visible']
    room = row['room']
    direction = row['direction']
    note = row['note']

    img_path = find_image_path(csv_fn)
    if not img_path:
        print(f"[{img_id}] ❌ 파일 못 찾음: {csv_fn}")
        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction, 'gt_mm': gt_mm,
            'f_wide': '', 'D_wide_mm': '', 'D_corr_mm': '',
            'ER': '', 'error_wide_mm': '', 'error_corr_mm': '',
            'error_wide_pct': '', 'error_corr_pct': '', 'status': 'file_not_found',
            'note': note
        })
        continue

    print(f"[{img_id:>3}/{len(rows)}] {csv_fn[:50]}...", end=" ", flush=True)
    t1 = time.time()

    try:
        # Step 1: GeoCalib
        img_gc = gc_model.load_image(img_path).to('cpu')
        result_gc = gc_model.calibrate(img_gc)
        camera = result_gc["camera"]
        f_wide = camera.f.mean().item()

        # Step 2: Undistort
        undistorted = camera.undistort_image(img_gc)
        corr_filename = f"{img_id}_corrected.png"
        corr_path = os.path.join(OUTPUT_DIR, "corrected", corr_filename)
        save_image(undistorted.squeeze(0), corr_path)

        # Step 3: Depth Pro - 원본
        img_orig, _, _ = depth_pro.load_rgb(img_path)
        pred_orig = dp_model.infer(dp_transform(img_orig), f_px=torch.tensor(f_wide))
        depth_orig = pred_orig["depth"].detach().cpu().numpy()

        # Step 4: Depth Pro - 보정
        img_corr, _, _ = depth_pro.load_rgb(corr_path)
        pred_corr = dp_model.infer(dp_transform(img_corr), f_px=torch.tensor(f_wide))
        depth_corr = pred_corr["depth"].detach().cpu().numpy()

        # Step 5: RANSAC
        dist_wide, nw1 = measure_wall_distance(depth_orig, f_wide)
        dist_corr, nw2 = measure_wall_distance(depth_corr, f_wide)

        gt_adj = gt_mm - 160  # 마감면 보정

        if dist_wide and dist_corr:
            d_wide_mm = int(dist_wide * 1000)
            d_corr_mm = int(dist_corr * 1000)
            er = dist_wide / dist_corr
            err_w = abs(d_wide_mm - gt_adj)
            err_c = abs(d_corr_mm - gt_adj)
            err_w_pct = err_w / gt_adj * 100
            err_c_pct = err_c / gt_adj * 100
            status = 'ok'
            elapsed = time.time() - t1
            print(f"f={f_wide:.0f} D_w={d_wide_mm} D_c={d_corr_mm} ER={er:.4f} err={err_w_pct:.1f}% [{elapsed:.1f}s]", flush=True)
        else:
            d_wide_mm = int(dist_wide * 1000) if dist_wide else ''
            d_corr_mm = int(dist_corr * 1000) if dist_corr else ''
            er, err_w, err_c, err_w_pct, err_c_pct = '', '', '', '', ''
            status = 'ransac_fail'
            elapsed = time.time() - t1
            print(f"f={f_wide:.0f} RANSAC 실패 (벽: {nw1}/{nw2}) [{elapsed:.1f}s]", flush=True)

        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction, 'gt_mm': gt_mm,
            'gt_adj_mm': gt_adj, 'f_wide': round(f_wide, 1),
            'D_wide_mm': d_wide_mm, 'D_corr_mm': d_corr_mm,
            'ER': round(er, 4) if isinstance(er, float) else '',
            'error_wide_mm': err_w if isinstance(err_w, int) else '',
            'error_corr_mm': err_c if isinstance(err_c, int) else '',
            'error_wide_pct': round(err_w_pct, 1) if isinstance(err_w_pct, float) else '',
            'error_corr_pct': round(err_c_pct, 1) if isinstance(err_c_pct, float) else '',
            'status': status, 'note': note
        })

    except Exception as e:
        elapsed = time.time() - t1
        print(f"에러: {str(e)[:80]} [{elapsed:.1f}s]", flush=True)
        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction, 'gt_mm': gt_mm,
            'gt_adj_mm': gt_mm - 160, 'f_wide': '', 'D_wide_mm': '', 'D_corr_mm': '',
            'ER': '', 'error_wide_mm': '', 'error_corr_mm': '',
            'error_wide_pct': '', 'error_corr_pct': '', 'status': f'error:{str(e)[:50]}',
            'note': note
        })

# ============================================================
# 결과 CSV 저장
# ============================================================
fieldnames = ['image_id', 'filename', 'wall_visible', 'room', 'direction',
              'gt_mm', 'gt_adj_mm', 'f_wide', 'D_wide_mm', 'D_corr_mm', 'ER',
              'error_wide_mm', 'error_corr_mm', 'error_wide_pct', 'error_corr_pct',
              'status', 'note']

with open(RESULT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

# ============================================================
# 요약 통계
# ============================================================
total_time = time.time() - total_start

ok_results = [r for r in results if r['status'] == 'ok']
both_clear = [r for r in ok_results if r['wall_visible'] == 'both_clear']
one_unclear = [r for r in ok_results if r['wall_visible'] == 'one_unclear']

print(f"\n{'='*60}")
print(f"실행 완료! 총 {total_time/60:.1f}분")
print(f"{'='*60}")
print(f"성공: {len(ok_results)}/{len(rows)}장")
print(f"  both_clear: {len(both_clear)}장")
print(f"  one_unclear: {len(one_unclear)}장")
print(f"실패: {len(results) - len(ok_results)}장")

def print_stats(name, data):
    if not data:
        print(f"\n[{name}] 데이터 없음")
        return
    errs_w = [r['error_wide_pct'] for r in data if r['error_wide_pct'] != '']
    errs_c = [r['error_corr_pct'] for r in data if r['error_corr_pct'] != '']
    ers = [r['ER'] for r in data if r['ER'] != '']
    fws = [r['f_wide'] for r in data if r['f_wide'] != '']
    print(f"\n[{name}] ({len(data)}장)")
    if errs_w:
        print(f"  원본 오차: 평균 {np.mean(errs_w):.1f}%, 중앙값 {np.median(errs_w):.1f}%, 최소 {min(errs_w):.1f}%, 최대 {max(errs_w):.1f}%")
    if errs_c:
        print(f"  보정 오차: 평균 {np.mean(errs_c):.1f}%, 중앙값 {np.median(errs_c):.1f}%, 최소 {min(errs_c):.1f}%, 최대 {max(errs_c):.1f}%")
    if ers:
        print(f"  ER: 평균 {np.mean(ers):.4f}, 중앙값 {np.median(ers):.4f}, 범위 {min(ers):.4f}~{max(ers):.4f}")
    if fws:
        print(f"  f_wide: 평균 {np.mean(fws):.0f}px, 범위 {min(fws):.0f}~{max(fws):.0f}px")

print_stats("전체", ok_results)
print_stats("both_clear", both_clear)
print_stats("one_unclear", one_unclear)

print(f"\n결과 저장: {RESULT_CSV}")
print("완료!")
