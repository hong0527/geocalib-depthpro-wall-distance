"""
새 이미지 6장 전부 수동 벽 측정
N1~N6 + depth map 없는 건 스킵
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import os
import sys

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
    def __init__(self, img, depth_map, f_px, image_id, note, gt_adj, auto_mm):
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
        auto_str = f"자동={self.auto_mm:.0f}mm" if self.auto_mm else "자동=FAIL"
        if n == 0:
            inst = "벽1 클릭 (빨강)"
            color = 'red'
        elif n == 1:
            inst = "벽2 클릭 (파랑)"
            color = 'blue'
        else:
            inst = "완료!"
            color = 'green'
        self.ax.set_title(
            f"[{self.image_id}] {self.note} | GT={self.gt_adj}mm | {auto_str}\n{inst} | s=스킵 r=초기화 q=종료",
            fontsize=11, fontproperties={'family': 'AppleGothic'}, color=color)
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        if event.key == 's':
            self.skipped = True; plt.close()
        elif event.key == 'q':
            self.skipped = 'quit'; plt.close()
        elif event.key == 'r':
            for p in self.patches: p.remove()
            for t in self.texts: t.remove()
            self.patches.clear(); self.texts.clear(); self.clicks.clear()
            self.result = None; self.update_title(); self.fig.canvas.draw_idle()

    def on_click(self, event):
        if event.inaxes != self.ax or len(self.clicks) >= 2 or event.button != 1: return
        cx_c, cy_c = int(event.xdata), int(event.ydata)
        self.clicks.append((cx_c, cy_c))
        x1, y1 = max(0, cx_c-PATCH_HALF), max(0, cy_c-PATCH_HALF)
        x2, y2 = min(self.W, cx_c+PATCH_HALF), min(self.H, cy_c+PATCH_HALF)
        n = len(self.clicks)
        color = 'red' if n == 1 else 'blue'
        rect = plt.Rectangle((x1,y1),x2-x1,y2-y1, lw=2, ec=color, fc=color, alpha=0.25)
        self.ax.add_patch(rect); self.patches.append(rect)
        dot = self.ax.plot(cx_c, cy_c, 'o', color=color, ms=8)[0]; self.patches.append(dot)
        txt = self.ax.text(x1+3, y1-5, f'벽{n}', color=color, fontsize=12, fontweight='bold',
                           fontproperties={'family': 'AppleGothic'})
        self.texts.append(txt); self.update_title()
        if len(self.clicks) == 2:
            self.compute(); self.fig.canvas.draw_idle(); plt.pause(3); plt.close()

    def region_to_3d(self, cx_c, cy_c):
        x1, y1 = max(0, cx_c-PATCH_HALF), max(0, cy_c-PATCH_HALF)
        x2, y2 = min(self.W, cx_c+PATCH_HALF), min(self.H, cy_c+PATCH_HALF)
        ur, vr = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
        Z = self.depth[y1:y2, x1:x2]
        X = (ur - self.cx) * Z / self.f_px
        Y = (vr - self.cy) * Z / self.f_px
        pts = np.stack([X,Y,Z], -1).reshape(-1,3)
        ok = (pts[:,2]>0.3) & (pts[:,2]<15.0) & np.isfinite(pts).all(1)
        return pts[ok]

    def compute(self):
        pts1 = self.region_to_3d(*self.clicks[0])
        pts2 = self.region_to_3d(*self.clicks[1])
        if len(pts1) < 10 or len(pts2) < 10: print("  점 부족"); return
        n1, d1 = fit_plane_least_squares(pts1)
        n2, d2 = fit_plane_least_squares(pts2)
        dot = np.dot(n1, n2)
        dist = abs(d1+d2)/np.linalg.norm(n1) if dot < 0 else abs(d1-d2)/np.linalg.norm(n1)
        dist_mm = int(dist * 1000)
        err = abs(dist_mm - self.gt_adj) / self.gt_adj * 100
        self.result = {'dist_mm': dist_mm, 'error_pct': round(err,1), 'parallelism': round(abs(dot),3)}
        auto_str = f"자동: {self.auto_mm:.0f}mm" if self.auto_mm else "자동: FAIL"
        txt = f"수동: {dist_mm}mm | GT: {self.gt_adj}mm | 오차: {err:.1f}% ({auto_str})"
        t = self.ax.text(self.W//2, self.H-20, txt, color='yellow', fontsize=13,
                         fontweight='bold', ha='center',
                         bbox=dict(boxstyle='round', facecolor='black', alpha=0.8))
        self.texts.append(t); self.fig.canvas.draw_idle()

    def show(self):
        plt.show(); return self.result, self.skipped

if __name__ == '__main__':
    # 6장 전부 — depth map 없는 건 자동 파이프라인 결과의 npy 필요
    # N1, N4, N6은 이미 저장됨. N2, N3, N5는 depth map 저장 안 됨 → 스킵
    targets = [
        ('N1', '/Users/honghwasu/Downloads/마포래미안푸르지오412동거실_3500_창문쪽.jpg',
         'output/new_depth_maps/N1_depth.npy', 504.8, 3340, 4363, '412동 거실 창문쪽'),
        ('N2', '/Users/honghwasu/Downloads/마포래미안푸르지오412동_3500_다른관점.jpg',
         'output/new_depth_maps/N2_depth.npy', 374.4, 3340, 5600, '412동 거실 주방쪽'),
        ('N3', '/Users/honghwasu/Downloads/마포래미안푸르지오412동_3300_큰방.jpg',
         'output/new_depth_maps/N3_depth.npy', 386.8, 3140, 5196, '412동 큰방 발코니유리문'),
        ('N4', '/Users/honghwasu/Downloads/마포래미안푸르지오412동_2700_작은방2.jpg',
         'output/new_depth_maps/N4_depth.npy', 351.0, 2540, 3040, '412동 작은방2'),
        ('N5', '/Users/honghwasu/Downloads/마포래미안푸르지오412동_2700_작은방1.jpg',
         'output/new_depth_maps/N5_depth.npy', 386.6, 2540, 3770, '412동 작은방1 붙박이장'),
        ('N6', '/Users/honghwasu/Downloads/마포래미안푸르지오309동_3000.jpg',
         'output/new_depth_maps/N6_depth.npy', 411.8, 2840, 4456, '309동 방'),
    ]

    print("=" * 50)
    print("새 이미지 수동 벽 측정 — 6장")
    print("=" * 50)

    results = []
    for img_id, img_path, depth_path, fpx, gt_adj, auto_mm, note in targets:
        if not os.path.exists(depth_path):
            print(f"\n[{img_id}] depth map 없음 — 스킵 ({note})")
            continue

        print(f"\n[{img_id}] {note} | GT={gt_adj}mm | 자동={auto_mm}mm")
        img = plt.imread(img_path)
        depth = np.load(depth_path)
        sel = WallClickSelector(img, depth, fpx, img_id, note, gt_adj, auto_mm)
        res, skipped = sel.show()
        if skipped == 'quit': break
        if skipped:
            print("  스킵"); continue
        if res:
            print(f"  수동: {res['dist_mm']}mm | 오차: {res['error_pct']}% | 평행: {res['parallelism']}")
            print(f"  자동 대비: {auto_mm}mm→{res['dist_mm']}mm")
            results.append({'id': img_id, 'note': note, 'gt_adj': gt_adj,
                           'auto_mm': auto_mm, 'manual_mm': res['dist_mm'],
                           'manual_err': res['error_pct']})

    if results:
        print(f"\n{'='*60}")
        print("요약")
        print(f"{'='*60}")
        for r in results:
            auto_err = abs(r['auto_mm']-r['gt_adj'])/r['gt_adj']*100
            print(f"  {r['id']}: 자동={auto_err:.1f}% → 수동={r['manual_err']}%")
