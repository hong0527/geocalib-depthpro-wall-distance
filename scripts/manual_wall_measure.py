"""
수동 벽 지정 기반 거리 측정
- 사진을 보여주고 양쪽 벽을 클릭
- depth map에서 해당 위치의 depth를 읽고 3D 거리 계산
- 클릭 주변 패치(20x20)의 depth 평균 사용 (노이즈 제거)
"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

import sys
sys.path.insert(0, "/Users/honghwasu/ml-depth-pro/src")

import csv
import unicodedata
import re
import numpy as np
import torch
import matplotlib
matplotlib.use('TkAgg')  # GUI backend
import matplotlib.pyplot as plt
import depth_pro
from geocalib import GeoCalib

# ============================================================
# 설정
# ============================================================
DATA_DIR = "/Users/honghwasu/Desktop/research_project/data"
CSV_PATH = "/Users/honghwasu/Desktop/research_project/depth_dataset_v1.csv"
RESULT_PATH = "/Users/honghwasu/Desktop/research_project/results_manual.csv"
PATCH_SIZE = 15  # 클릭 주변 패치 반경

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
# 클릭 핸들러
# ============================================================
class WallClicker:
    def __init__(self, img, depth_map, f_px, image_id, gt_mm):
        self.img = img
        self.depth = depth_map
        self.f_px = f_px
        self.H, self.W = depth_map.shape
        self.cx = self.W / 2.0
        self.cy = self.H / 2.0
        self.clicks = []
        self.image_id = image_id
        self.gt_mm = gt_mm
        self.result = None

    def onclick(self, event):
        if event.xdata is None or event.ydata is None:
            return
        u, v = int(event.xdata), int(event.ydata)
        self.clicks.append((u, v))

        # 클릭 표시
        color = 'red' if len(self.clicks) == 1 else 'blue'
        label = '왼쪽 벽' if len(self.clicks) == 1 else '오른쪽 벽'
        plt.plot(u, v, 'o', color=color, markersize=10)
        plt.annotate(label, (u, v), textcoords="offset points",
                     xytext=(10, 10), color=color, fontsize=12,
                     fontproperties={'family': 'AppleGothic'})
        plt.draw()

        if len(self.clicks) == 2:
            self.compute_distance()
            plt.close()

    def get_patch_depth(self, u, v):
        """클릭 주변 패치의 depth 평균"""
        p = PATCH_SIZE
        v_min = max(0, v - p)
        v_max = min(self.H, v + p)
        u_min = max(0, u - p)
        u_max = min(self.W, u + p)
        patch = self.depth[v_min:v_max, u_min:u_max]
        valid = patch[(patch > 0.3) & (patch < 15.0)]
        if len(valid) == 0:
            return self.depth[v, u]
        return np.median(valid)

    def compute_distance(self):
        (u1, v1), (u2, v2) = self.clicks

        Z1 = self.get_patch_depth(u1, v1)
        Z2 = self.get_patch_depth(u2, v2)

        # 3D 좌표
        X1 = (u1 - self.cx) * Z1 / self.f_px
        X2 = (u2 - self.cx) * Z2 / self.f_px
        Y1 = (v1 - self.cy) * Z1 / self.f_px
        Y2 = (v2 - self.cy) * Z2 / self.f_px

        # 3D 거리
        dist = np.sqrt((X2 - X1)**2 + (Y2 - Y1)**2 + (Z2 - Z1)**2)
        dist_mm = int(dist * 1000)

        gt_adj = self.gt_mm - 160
        error_mm = abs(dist_mm - gt_adj)
        error_pct = error_mm / gt_adj * 100

        self.result = {
            'dist_mm': dist_mm,
            'gt_adj': gt_adj,
            'error_mm': error_mm,
            'error_pct': round(error_pct, 1),
            'click1': (u1, v1),
            'click2': (u2, v2),
            'Z1': round(Z1, 3),
            'Z2': round(Z2, 3),
        }

        print(f"  측정: {dist_mm}mm  GT: {gt_adj}mm  오차: {error_mm}mm ({error_pct:.1f}%)")

# ============================================================
# 모델 로드
# ============================================================
print("모델 로딩...")
gc_model = GeoCalib(weights='distorted').to('cpu')
dp_model, dp_transform = depth_pro.create_model_and_transforms()
dp_model.eval()
print("완료!")

# ============================================================
# CSV 읽기
# ============================================================
with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# both_clear만 먼저 (가장 측정에 적합한 사진)
both_clear = [r for r in rows if r['wall_visible'] == 'both_clear']
print(f"\nboth_clear {len(both_clear)}장 측정 시작")
print("각 사진에서 왼쪽 벽 → 오른쪽 벽 순서로 클릭하세요")
print("(닫기 버튼 또는 'q'로 스킵 가능)\n")

# ============================================================
# 측정 루프
# ============================================================
results = []

for idx, row in enumerate(both_clear):
    img_id = row['image_id']
    csv_fn = row['filename']
    gt_mm = int(row['gt_mm'])
    room = row['room']

    img_path = find_image_path(csv_fn)
    if not img_path:
        print(f"[{img_id}] 파일 못 찾음, 스킵")
        continue

    print(f"[{img_id}/{len(both_clear)}] {room} gt={gt_mm}mm - 벽 2곳 클릭하세요")

    # GeoCalib focal
    img_gc = gc_model.load_image(img_path).to('cpu')
    result_gc = gc_model.calibrate(img_gc)
    f_wide = result_gc["camera"].f.mean().item()

    # Depth Pro
    image, _, _ = depth_pro.load_rgb(img_path)
    prediction = dp_model.infer(dp_transform(image), f_px=torch.tensor(f_wide))
    depth_map = prediction["depth"].detach().cpu().numpy()

    # 이미지 로드 (matplotlib용)
    img_display = plt.imread(img_path)

    # 클릭 UI
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.imshow(img_display)
    ax.set_title(f"[{img_id}] {room} | GT={gt_mm}mm | f={f_wide:.0f}px\n왼쪽 벽 클릭 → 오른쪽 벽 클릭",
                 fontproperties={'family': 'AppleGothic'}, fontsize=14)
    ax.set_xlabel("왼쪽 벽(빨강) → 오른쪽 벽(파랑) 순서로 클릭",
                  fontproperties={'family': 'AppleGothic'}, fontsize=12)

    clicker = WallClicker(img_display, depth_map, f_wide, img_id, gt_mm)
    fig.canvas.mpl_connect('button_press_event', clicker.onclick)

    plt.tight_layout()
    plt.show()

    if clicker.result:
        results.append({
            'image_id': img_id,
            'filename': csv_fn,
            'room': room,
            'gt_mm': gt_mm,
            'gt_adj_mm': clicker.result['gt_adj'],
            'f_wide': round(f_wide, 1),
            'measured_mm': clicker.result['dist_mm'],
            'error_mm': clicker.result['error_mm'],
            'error_pct': clicker.result['error_pct'],
            'click1': str(clicker.result['click1']),
            'click2': str(clicker.result['click2']),
            'Z1': clicker.result['Z1'],
            'Z2': clicker.result['Z2'],
        })
    else:
        print(f"  스킵됨")

# ============================================================
# 결과 저장
# ============================================================
if results:
    fieldnames = list(results[0].keys())
    with open(RESULT_PATH, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # 통계
    errors = [r['error_pct'] for r in results]
    print(f"\n{'='*50}")
    print(f"완료! {len(results)}장 측정")
    print(f"평균 오차: {sum(errors)/len(errors):.1f}%")
    print(f"중앙값 오차: {sorted(errors)[len(errors)//2]:.1f}%")
    print(f"결과 저장: {RESULT_PATH}")
else:
    print("측정된 사진 없음")
