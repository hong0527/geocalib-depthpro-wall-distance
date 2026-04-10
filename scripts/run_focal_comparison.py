"""
f_px 비교 실험: 같은 63장에 대해 3가지 focal 조건으로 Depth Pro 실행
A: f_px = GeoCalib f_wide (이미 results_full.csv에 있음)
B: f_px = None (Depth Pro 자체 추정)
C: f_px = 800 (표준렌즈 가정)

RANSAC으로 벽-벽 거리 측정 후 GT 비교
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

# ============================================================
# 설정
# ============================================================
DATA_DIR = "/Users/honghwasu/Desktop/research_project/data"
CSV_PATH = "/Users/honghwasu/Desktop/research_project/depth_dataset_v1.csv"
RESULT_A_PATH = "/Users/honghwasu/Desktop/research_project/results_full.csv"
RESULT_PATH = "/Users/honghwasu/Desktop/research_project/results_focal_comparison.csv"

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
# RANSAC
# ============================================================
def fit_plane_ransac(pts, th=0.05, n_iter=500):
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

    # 다운샘플링: 최대 50000포인트로 제한 (속도 개선)
    if len(pts) > 50000:
        idx = np.random.choice(len(pts), 50000, replace=False)
        pts = pts[idx]

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
# 기존 결과(A) 로드
# ============================================================
with open(RESULT_A_PATH, 'r', encoding='utf-8-sig') as f:
    results_a = {r['image_id']: r for r in csv.DictReader(f)}

# ============================================================
# CSV 로드
# ============================================================
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# ============================================================
# 모델 로드
# ============================================================
print("=" * 60, flush=True)
print("모델 로딩...", flush=True)
t0 = time.time()
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()
print(f"Depth Pro 로딩 완료 ({time.time()-t0:.1f}s)", flush=True)
print(f"총 {len(rows)}장 × 2조건(B,C) 처리", flush=True)

# ============================================================
# 실행
# ============================================================
results = []
total_start = time.time()

for idx, row in enumerate(rows):
    img_id = row['image_id']
    csv_fn = row['filename']
    gt_mm = int(row['gt_mm'])
    gt_adj = gt_mm - 160
    wall_vis = row['wall_visible']
    room = row['room']
    direction = row['direction']
    note = row['note']

    # 기존 A 결과 가져오기
    a = results_a.get(img_id, {})
    f_wide = float(a.get('f_wide', 0)) if a.get('f_wide') else None
    d_wide_a = a.get('D_wide_mm', '')
    d_corr_a = a.get('D_corr_mm', '')
    er_a = a.get('ER', '')
    status_a = a.get('status', '')

    img_path = find_image_path(csv_fn)
    if not img_path:
        print(f"[{img_id}] ❌ 파일 못 찾음", flush=True)
        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction,
            'gt_mm': gt_mm, 'gt_adj_mm': gt_adj,
            'f_wide_geocalib': f_wide or '',
            'f_estimated_depthpro': '',
            # A results
            'D_A_fwide_mm': d_wide_a, 'err_A_pct': '',
            # B results
            'D_B_none_mm': '', 'f_B_estimated': '', 'err_B_pct': '',
            # C results
            'D_C_800_mm': '', 'err_C_pct': '',
            'status': 'file_not_found', 'note': note
        })
        continue

    # 진행률 파일에 기록
    with open('/Users/honghwasu/Desktop/research_project/output/progress.txt', 'w') as pf:
        pf.write(f"{idx+1}/{len(rows)} processing: {csv_fn}\n")

    print(f"[{img_id:>3}/{len(rows)}] {csv_fn[:45]}...", end=" ", flush=True)
    t1 = time.time()

    try:
        # 이미지 로드 (한번만)
        image, _, exif_f = depth_pro.load_rgb(img_path)
        transformed = dp_transform(image)

        # ---- 조건 B: f_px = None (Depth Pro 자체 추정) ----
        pred_b = dp_model.infer(transformed, f_px=None)
        depth_b = pred_b["depth"].detach().cpu().numpy()
        f_estimated = pred_b["focallength_px"].item()

        # B의 RANSAC: Depth Pro가 추정한 focal로 3D 복원
        dist_b, nw_b = measure_wall_distance(depth_b, f_estimated)

        # ---- 조건 C: f_px = 800 (표준렌즈 가정) ----
        pred_c = dp_model.infer(transformed, f_px=torch.tensor(800.0))
        depth_c = pred_c["depth"].detach().cpu().numpy()

        # C의 RANSAC: 800px로 3D 복원
        dist_c, nw_c = measure_wall_distance(depth_c, 800.0)

        # 결과 계산
        d_b_mm = int(dist_b * 1000) if dist_b else ''
        d_c_mm = int(dist_c * 1000) if dist_c else ''

        err_a_pct = ''
        if d_wide_a and d_wide_a != '':
            try:
                err_a_pct = round(abs(int(d_wide_a) - gt_adj) / gt_adj * 100, 1)
            except:
                pass

        err_b_pct = round(abs(d_b_mm - gt_adj) / gt_adj * 100, 1) if isinstance(d_b_mm, int) else ''
        err_c_pct = round(abs(d_c_mm - gt_adj) / gt_adj * 100, 1) if isinstance(d_c_mm, int) else ''

        status = 'ok'
        if not dist_b or not dist_c:
            status = 'partial_ransac_fail'

        elapsed = time.time() - t1

        # 로그
        a_str = f"A={d_wide_a}({err_a_pct}%)" if d_wide_a else "A=fail"
        b_str = f"B={d_b_mm}({err_b_pct}%)" if isinstance(d_b_mm, int) else "B=fail"
        c_str = f"C={d_c_mm}({err_c_pct}%)" if isinstance(d_c_mm, int) else "C=fail"
        print(f"f_gc={f_wide:.0f} f_dp={f_estimated:.0f} {a_str} {b_str} {c_str} [{elapsed:.1f}s]", flush=True)

        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction,
            'gt_mm': gt_mm, 'gt_adj_mm': gt_adj,
            'f_wide_geocalib': round(f_wide, 1) if f_wide else '',
            'f_estimated_depthpro': round(f_estimated, 1),
            'D_A_fwide_mm': d_wide_a, 'err_A_pct': err_a_pct,
            'D_B_none_mm': d_b_mm, 'f_B_estimated': round(f_estimated, 1), 'err_B_pct': err_b_pct,
            'D_C_800_mm': d_c_mm, 'err_C_pct': err_c_pct,
            'status': status, 'note': note
        })

    except Exception as e:
        elapsed = time.time() - t1
        print(f"에러: {str(e)[:60]} [{elapsed:.1f}s]", flush=True)
        results.append({
            'image_id': img_id, 'filename': csv_fn, 'wall_visible': wall_vis,
            'room': room, 'direction': direction,
            'gt_mm': gt_mm, 'gt_adj_mm': gt_adj,
            'f_wide_geocalib': f_wide or '',
            'f_estimated_depthpro': '',
            'D_A_fwide_mm': d_wide_a, 'err_A_pct': '',
            'D_B_none_mm': '', 'f_B_estimated': '', 'err_B_pct': '',
            'D_C_800_mm': '', 'err_C_pct': '',
            'status': f'error:{str(e)[:40]}', 'note': note
        })

# ============================================================
# CSV 저장
# ============================================================
fieldnames = ['image_id', 'filename', 'wall_visible', 'room', 'direction',
              'gt_mm', 'gt_adj_mm',
              'f_wide_geocalib', 'f_estimated_depthpro',
              'D_A_fwide_mm', 'err_A_pct',
              'D_B_none_mm', 'f_B_estimated', 'err_B_pct',
              'D_C_800_mm', 'err_C_pct',
              'status', 'note']

with open(RESULT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

# ============================================================
# 분석
# ============================================================
total_time = time.time() - total_start
print(f"\n{'='*70}", flush=True)
print(f"실행 완료! {total_time/60:.1f}분", flush=True)
print(f"{'='*70}", flush=True)

# 유효 데이터 필터
valid = [r for r in results if r['status'] == 'ok'
         and r['err_A_pct'] != '' and r['err_B_pct'] != '' and r['err_C_pct'] != ''
         and float(r['err_A_pct']) < 90 and float(r['err_B_pct']) < 90 and float(r['err_C_pct']) < 90]

bc = [r for r in valid if r['wall_visible'] == 'both_clear']
ou = [r for r in valid if r['wall_visible'] == 'one_unclear']

def analyze(name, data):
    if not data:
        print(f"\n[{name}] 데이터 없음", flush=True)
        return
    ea = [float(r['err_A_pct']) for r in data]
    eb = [float(r['err_B_pct']) for r in data]
    ec = [float(r['err_C_pct']) for r in data]
    fg = [float(r['f_wide_geocalib']) for r in data if r['f_wide_geocalib']]
    fd = [float(r['f_estimated_depthpro']) for r in data if r['f_estimated_depthpro']]

    print(f"\n{'='*70}", flush=True)
    print(f"[{name}] ({len(data)}장)", flush=True)
    print(f"{'='*70}", flush=True)
    print(f"  조건A (GeoCalib f_wide):    평균오차 {sum(ea)/len(ea):.1f}%  중앙값 {sorted(ea)[len(ea)//2]:.1f}%", flush=True)
    print(f"  조건B (Depth Pro 자체):      평균오차 {sum(eb)/len(eb):.1f}%  중앙값 {sorted(eb)[len(eb)//2]:.1f}%", flush=True)
    print(f"  조건C (표준렌즈 800px):     평균오차 {sum(ec)/len(ec):.1f}%  중앙값 {sorted(ec)[len(ec)//2]:.1f}%", flush=True)

    # 어떤 조건이 가장 나은가
    a_best = sum(1 for a,b,c in zip(ea,eb,ec) if a <= b and a <= c)
    b_best = sum(1 for a,b,c in zip(ea,eb,ec) if b <= a and b <= c)
    c_best = sum(1 for a,b,c in zip(ea,eb,ec) if c <= a and c <= b)
    print(f"  가장 나은 조건: A={a_best}장 B={b_best}장 C={c_best}장", flush=True)

    # focal 비교
    if fg and fd:
        print(f"  GeoCalib focal: 평균 {sum(fg)/len(fg):.0f}px  범위 {min(fg):.0f}~{max(fg):.0f}", flush=True)
        print(f"  DepthPro focal: 평균 {sum(fd)/len(fd):.0f}px  범위 {min(fd):.0f}~{max(fd):.0f}", flush=True)
        diffs = [abs(g-d) for g,d in zip(fg,fd)]
        print(f"  focal 차이: 평균 {sum(diffs)/len(diffs):.0f}px", flush=True)

    # A vs B 직접 비교 (GeoCalib vs Depth Pro 자체)
    a_better = sum(1 for a,b in zip(ea,eb) if a < b)
    b_better = sum(1 for a,b in zip(ea,eb) if b < a)
    tie = sum(1 for a,b in zip(ea,eb) if a == b)
    print(f"  A(GeoCalib) 승: {a_better}장  B(자체추정) 승: {b_better}장  동률: {tie}장", flush=True)

analyze("전체", valid)
analyze("both_clear", bc)
analyze("one_unclear", ou)

# f_wide 구간별
print(f"\n{'='*70}", flush=True)
print("f_wide 구간별 (GeoCalib 기준)", flush=True)
print("="*70, flush=True)
for lo,hi,label in [(0,400,"초광각<400"),(400,500,"광각400-500"),(500,700,"중간500-700"),(700,2000,"일반700+")]:
    s = [r for r in valid if r['f_wide_geocalib'] and lo <= float(r['f_wide_geocalib']) < hi]
    if s:
        ea = [float(r['err_A_pct']) for r in s]
        eb = [float(r['err_B_pct']) for r in s]
        ec = [float(r['err_C_pct']) for r in s]
        print(f"  {label} ({len(s)}장): A={sum(ea)/len(ea):.1f}% B={sum(eb)/len(eb):.1f}% C={sum(ec)/len(ec):.1f}%", flush=True)

# 개별 데이터: A vs B 차이가 큰 순
print(f"\n{'='*70}", flush=True)
print("A vs B 차이가 큰 사진 (GeoCalib이 도움된/안된 경우)", flush=True)
print("="*70, flush=True)
diffs_ab = [(r, float(r['err_B_pct']) - float(r['err_A_pct'])) for r in valid]
diffs_ab.sort(key=lambda x: x[1], reverse=True)
print("  GeoCalib이 크게 도움된 경우 (B오차 - A오차 큰 순):", flush=True)
for r, d in diffs_ab[:5]:
    print(f"    [{r['image_id']}] A={r['err_A_pct']}% B={r['err_B_pct']}% 차이={d:.1f}%p f_gc={r['f_wide_geocalib']} f_dp={r['f_estimated_depthpro']} {r['wall_visible']} {r['room']}", flush=True)
print("  GeoCalib이 오히려 나빴던 경우 (A오차 - B오차 큰 순):", flush=True)
for r, d in diffs_ab[-5:]:
    print(f"    [{r['image_id']}] A={r['err_A_pct']}% B={r['err_B_pct']}% 차이={d:.1f}%p f_gc={r['f_wide_geocalib']} f_dp={r['f_estimated_depthpro']} {r['wall_visible']} {r['room']}", flush=True)

print(f"\n결과 저장: {RESULT_PATH}", flush=True)
print("완료!", flush=True)
