"""
RANSAC이 벽을 잘못 잡은 이미지 5장 수동 측정
012, 014, 004, 051, 056(비교용)
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import os

PATCH_HALF = 30

def fit_plane_least_squares(points):
    centroid = points.mean(axis=0)
    centered = points - centroid
    _, _, Vt = np.linalg.svd(centered)
    normal = Vt[-1]
    normal = normal / np.linalg.norm(normal)
    d = -np.dot(normal, centroid)
    return normal, d


class WallClickSelector:
    def __init__(self, img, depth_map, f_px, image_id, note, gt_adj, auto_mm, auto_err):
        self.img = img
        self.depth = depth_map
        self.f_px = f_px
        self.H, self.W = depth_map.shape
        self.cx = self.W / 2.0
        self.cy = self.H / 2.0
        self.clicks = []
        self.patches = []
        self.texts = []
        self.image_id = image_id
        self.note = note
        self.gt_adj = gt_adj
        self.auto_mm = auto_mm
        self.auto_err = auto_err
        self.result = None
        self.skipped = False

        self.fig, self.ax = plt.subplots(1, 1, figsize=(14, 10))
        self.ax.imshow(img)
        self.update_title()

        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        plt.tight_layout()

    def update_title(self):
        n = len(self.clicks)
        auto_str = f"자동={self.auto_mm:.0f}mm({self.auto_err:.1f}%)" if self.auto_mm else "자동=FAIL"
        if n == 0:
            instruction = "벽1을 클릭 (빨강) — 벽 한가운데!"
            color = 'red'
        elif n == 1:
            instruction = "벽2를 클릭 (파랑) — 벽 한가운데!"
            color = 'blue'
        else:
            instruction = "완료!"
            color = 'green'

        self.ax.set_title(
            f"[{self.image_id}] {self.note} | GT={self.gt_adj}mm | {auto_str}\n"
            f"{instruction}  |  's'=스킵  'r'=초기화  'q'=종료",
            fontsize=11,
            fontproperties={'family': 'AppleGothic'},
            color=color
        )
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        if event.key == 's':
            self.skipped = True
            plt.close()
        elif event.key == 'q':
            self.skipped = 'quit'
            plt.close()
        elif event.key == 'r':
            for p in self.patches:
                p.remove()
            for t in self.texts:
                t.remove()
            self.patches.clear()
            self.texts.clear()
            self.clicks.clear()
            self.result = None
            self.update_title()
            self.fig.canvas.draw_idle()

    def on_click(self, event):
        if event.inaxes != self.ax or len(self.clicks) >= 2:
            return
        if event.button != 1:
            return

        cx_click = int(event.xdata)
        cy_click = int(event.ydata)
        self.clicks.append((cx_click, cy_click))

        x1 = max(0, cx_click - PATCH_HALF)
        y1 = max(0, cy_click - PATCH_HALF)
        x2 = min(self.W, cx_click + PATCH_HALF)
        y2 = min(self.H, cy_click + PATCH_HALF)

        n = len(self.clicks)
        color = 'red' if n == 1 else 'blue'
        label = '1' if n == 1 else '2'

        rect = plt.Rectangle((x1, y1), x2-x1, y2-y1,
                              linewidth=2, edgecolor=color, facecolor=color, alpha=0.25)
        self.ax.add_patch(rect)
        self.patches.append(rect)

        dot = self.ax.plot(cx_click, cy_click, 'o', color=color, markersize=8)[0]
        self.patches.append(dot)

        txt = self.ax.text(x1+3, y1-5, f'벽{label}', color=color,
                           fontsize=12, fontweight='bold',
                           fontproperties={'family': 'AppleGothic'})
        self.texts.append(txt)

        self.update_title()

        if len(self.clicks) == 2:
            self.compute()
            self.fig.canvas.draw_idle()
            plt.pause(3)
            plt.close()

    def region_to_3d_points(self, cx_click, cy_click):
        x1 = max(0, cx_click - PATCH_HALF)
        y1 = max(0, cy_click - PATCH_HALF)
        x2 = min(self.W, cx_click + PATCH_HALF)
        y2 = min(self.H, cy_click + PATCH_HALF)

        u_range = np.arange(x1, x2)
        v_range = np.arange(y1, y2)
        u_grid, v_grid = np.meshgrid(u_range, v_range)
        Z = self.depth[y1:y2, x1:x2]
        X = (u_grid - self.cx) * Z / self.f_px
        Y = (v_grid - self.cy) * Z / self.f_px
        points = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
        valid = (points[:, 2] > 0.3) & (points[:, 2] < 15.0) & np.isfinite(points).all(axis=1)
        return points[valid]

    def compute(self):
        pts1 = self.region_to_3d_points(*self.clicks[0])
        pts2 = self.region_to_3d_points(*self.clicks[1])

        if len(pts1) < 10 or len(pts2) < 10:
            print(f"  [{self.image_id}] 경고: 유효한 점이 너무 적음")
            return

        n1, d1 = fit_plane_least_squares(pts1)
        n2, d2 = fit_plane_least_squares(pts2)
        dot = np.dot(n1, n2)

        if dot > 0:
            dist = abs(d1 - d2) / np.linalg.norm(n1)
        else:
            dist = abs(d1 + d2) / np.linalg.norm(n1)

        dist_mm = int(dist * 1000)
        error_pct = abs(dist_mm - self.gt_adj) / self.gt_adj * 100

        self.result = {
            'dist_mm': dist_mm,
            'error_pct': round(error_pct, 1),
            'parallelism': round(abs(dot), 3),
        }

        result_txt = f"수동: {dist_mm}mm | GT: {self.gt_adj}mm | 오차: {error_pct:.1f}%"
        if self.auto_mm:
            result_txt += f" (자동: {self.auto_mm:.0f}mm, {self.auto_err:.1f}%)"

        txt = self.ax.text(self.W//2, self.H-20, result_txt,
                           color='yellow', fontsize=13, fontweight='bold', ha='center',
                           bbox=dict(boxstyle='round', facecolor='black', alpha=0.8))
        self.texts.append(txt)
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()
        return self.result, self.skipped


if __name__ == '__main__':
    meta = pd.read_csv('output/depth_maps/depth_meta.csv')
    result_csv = pd.read_csv('seminar2/전체_통합_데이터.csv')

    # RANSAC이 벽을 잘못 잡은 이미지 + 비교용
    target_ids = ['004', '012', '014', '051', '056']

    save_path = 'output/manual_measure_wrongfit.csv'
    results = []

    print("=" * 60)
    print(f"RANSAC 오피팅 이미지 수동 측정 — {len(target_ids)}장")
    print("벽 한가운데를 클릭! | r=초기화 | s=스킵 | q=종료")
    print("=" * 60)

    for i, tid in enumerate(target_ids):
        tid_int = int(tid)
        rm = meta[meta['image_id'] == tid_int]
        if rm.empty:
            print(f"[{tid}] 메타 없음")
            continue
        rm = rm.iloc[0]

        rr = result_csv[result_csv['id'] == tid]
        if rr.empty:
            continue
        rr = rr.iloc[0]

        gt_adj = rr['gt_adj_mm']
        note = str(rr['note'])
        auto_mm = rr['measured_mm'] if pd.notna(rr['measured_mm']) else None
        auto_err = rr['error_pct'] if pd.notna(rr['error_pct']) else None
        img_path = rm['img_path']
        depth_path = rm['npy_path']
        fpx = rm['f_wide_geocalib']

        print(f"\n[{i+1}/{len(target_ids)}] ID={tid} | {note}")
        print(f"  GT={gt_adj}mm | 자동={'%.0f'%auto_mm if auto_mm else 'FAIL'}mm | 자동오차={'%.1f'%auto_err if auto_err else '-'}%")

        if not os.path.exists(img_path):
            print(f"  이미지 없음: {img_path}")
            continue

        img = plt.imread(img_path)
        depth_map = np.load(depth_path)

        selector = WallClickSelector(img, depth_map, fpx, tid, note, gt_adj, auto_mm, auto_err)
        res, skipped = selector.show()

        if skipped == 'quit':
            print("종료!")
            break
        elif skipped:
            print(f"  스킵됨")
            results.append({
                'id': tid, 'note': note, 'gt_adj_mm': gt_adj,
                'auto_mm': auto_mm, 'auto_err': auto_err,
                'manual_mm': None, 'manual_err': None,
                'status': 'skipped'
            })
            continue

        if res:
            print(f"  수동: {res['dist_mm']}mm | 오차: {res['error_pct']}% | 평행성: {res['parallelism']}")
            if auto_err:
                delta = res['error_pct'] - auto_err
                print(f"  자동 대비: {delta:+.1f}%p")
            results.append({
                'id': tid, 'note': note, 'gt_adj_mm': gt_adj,
                'auto_mm': auto_mm, 'auto_err': auto_err,
                'manual_mm': res['dist_mm'], 'manual_err': res['error_pct'],
                'parallelism': res['parallelism'],
                'status': 'ok'
            })
        else:
            results.append({
                'id': tid, 'note': note, 'gt_adj_mm': gt_adj,
                'auto_mm': auto_mm, 'auto_err': auto_err,
                'manual_mm': None, 'manual_err': None,
                'status': 'failed'
            })

    # 결과 저장 + 요약
    if results:
        df_out = pd.DataFrame(results)
        df_out.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"\n결과 저장: {save_path}")

        ok = df_out[df_out['status'] == 'ok']
        if len(ok) > 0:
            print(f"\n{'='*60}")
            print(f"결과 ({len(ok)}장)")
            print(f"{'='*60}")
            print(f"{'ID':>4} | {'자동':>7} | {'수동':>7} | {'변화':>8} | note")
            print("-" * 65)
            for _, r in ok.iterrows():
                ae = f"{r['auto_err']:.1f}%" if pd.notna(r['auto_err']) else "  FAIL"
                me = f"{r['manual_err']:.1f}%"
                if pd.notna(r['auto_err']):
                    d = r['auto_err'] - r['manual_err']
                    ds = f"{d:+.1f}%p"
                else:
                    ds = "   -  "
                print(f"{r['id']:>4} | {ae:>7} | {me:>7} | {ds:>8} | {r['note'][:30]}")

            auto_v = ok[ok['auto_err'].notna()]
            if len(auto_v) > 0:
                print(f"\n자동 평균: {auto_v['auto_err'].mean():.1f}%")
                print(f"수동 평균: {ok['manual_err'].mean():.1f}%")
