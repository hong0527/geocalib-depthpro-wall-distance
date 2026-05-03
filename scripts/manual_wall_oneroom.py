"""
원룸 수동 벽 측정 — 마지막 사진 (26.44m²)
"""
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

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
    def __init__(self, img, depth_map, f_px, title):
        self.depth = depth_map
        self.f_px = f_px
        self.H, self.W = depth_map.shape
        self.cx = self.W / 2.0
        self.cy = self.H / 2.0
        self.clicks = []
        self.patches = []
        self.texts = []
        self.result = None
        self.skipped = False
        self.fig, self.ax = plt.subplots(1, 1, figsize=(14, 10))
        self.ax.imshow(img)
        self.title = title
        self.update_title()
        self.fig.canvas.mpl_connect('button_press_event', self.on_click)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key)
        plt.tight_layout()

    def update_title(self):
        n = len(self.clicks)
        if n == 0: inst, color = "벽1 클릭 (빨강)", 'red'
        elif n == 1: inst, color = "벽2 클릭 (파랑)", 'blue'
        else: inst, color = "완료!", 'green'
        self.ax.set_title(f"{self.title}\n{inst} | s=스킵 r=초기화",
                          fontsize=11, fontproperties={'family': 'AppleGothic'}, color=color)
        self.fig.canvas.draw_idle()

    def on_key(self, event):
        if event.key == 's': self.skipped = True; plt.close()
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
        self.result = {'dist_mm': dist_mm, 'parallelism': round(abs(dot), 3)}
        txt = f"수동: {dist_mm}mm ({dist_mm/10:.1f}cm) | 평행: {abs(dot):.3f}"
        t = self.ax.text(self.W//2, self.H-20, txt, color='yellow', fontsize=14,
                         fontweight='bold', ha='center',
                         bbox=dict(boxstyle='round', facecolor='black', alpha=0.8))
        self.texts.append(t); self.fig.canvas.draw_idle()

    def show(self):
        plt.show(); return self.result

if __name__ == '__main__':
    depth = np.load('output/new_depth_maps/원룸5_depth.npy')
    img = plt.imread('/Users/honghwasu/.claude/image-cache/e72b2bc9-b5d6-4659-a0d0-c158a8724150/12.png')
    f = 505.9

    print("26.44m² 원룸 수동 벽 측정")
    print("자동 측정: 2770mm")
    print("양쪽 벽 한가운데를 클릭하세요!")

    sel = WallClickSelector(img, depth, f, "원룸 26.44m² | 자동=2770mm")
    res = sel.show()
    if res:
        print(f"\n수동: {res['dist_mm']}mm ({res['dist_mm']/10:.1f}cm) | 평행: {res['parallelism']}")
        print(f"자동: 2770mm")
        print(f"차이: {abs(res['dist_mm']-2770)}mm")
