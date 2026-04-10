"""003번, 010번 수동 벽 클릭 측정"""
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
import numpy as np
import csv
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

meta = {}
with open("/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        meta[row['image_id']] = row

test_images = [
    ('003', 4500, '거실 - RANSAC 18.7%'),
    ('010', 5400, '거실 - RANSAC 17.9%'),
]

PATCH = 50
results = []

for img_id, gt_mm, desc in test_images:
    m = meta[img_id]
    depth = np.load(m['npy_path'])
    H, W = depth.shape
    f_wide = float(m['f_wide_geocalib'])
    img_path = m['img_path']
    cx, cy = W/2.0, H/2.0
    gt_adj = gt_mm - 160

    print(f"\n[{img_id}] {desc}")
    print(f"  GT: {gt_adj}mm, focal: {f_wide:.0f}px")
    print(f"  양쪽 벽 부분만 클릭하세요")

    clicks = []
    result_done = [False]

    def make_onclick(clicks_list, result_flag):
        def onclick(event):
            if event.xdata is None or event.ydata is None:
                return
            if result_flag[0]:
                return
            u, v = int(event.xdata), int(event.ydata)
            clicks_list.append((u, v))

            if len(clicks_list) == 1:
                plt.plot(u, v, 'ro', markersize=15)
                ax.set_title(f"[{img_id}] 오른쪽 벽 클릭", fontsize=12)
                plt.draw()
                print(f"  왼쪽: ({u}, {v})")

            elif len(clicks_list) == 2:
                plt.plot(u, v, 'bo', markersize=15)
                plt.draw()
                print(f"  오른쪽: ({u}, {v})")

                (u1,v1), (u2,v2) = clicks_list
                def get_3d(cu, cv):
                    x1,x2 = max(0,cu-PATCH), min(W,cu+PATCH)
                    y1,y2 = max(0,cv-PATCH), min(H,cv+PATCH)
                    ug, vg = np.meshgrid(np.arange(x1,x2), np.arange(y1,y2))
                    Z = depth[y1:y2, x1:x2]
                    X = (ug-cx)*Z/f_wide
                    Y = (vg-cy)*Z/f_wide
                    pts = np.stack([X,Y,Z],-1).reshape(-1,3)
                    ok = (pts[:,2]>0.3)&(pts[:,2]<15)&np.isfinite(pts).all(1)
                    return pts[ok]
                def fit_plane(pts):
                    c = pts.mean(0)
                    _,_,Vt = np.linalg.svd(pts-c)
                    n=Vt[-1]; n/=np.linalg.norm(n)
                    return n, -np.dot(n,c)

                pl = get_3d(u1,v1)
                pr = get_3d(u2,v2)
                n1,d1 = fit_plane(pl)
                n2,d2 = fit_plane(pr)
                dot = abs(np.dot(n1,n2))
                dist = abs(d1+d2) if np.dot(n1,n2)<0 else abs(d1-d2)
                mm = int(dist*1000)
                err = abs(mm-gt_adj)
                pct = err/gt_adj*100

                print(f"  수동 측정: {mm}mm, GT: {gt_adj}mm, 오차: {err}mm ({pct:.1f}%)")
                results.append({'id':img_id, 'mm':mm, 'gt':gt_adj, 'pct':round(pct,1)})
                ax.set_title(f"[{img_id}] 수동:{mm}mm GT:{gt_adj}mm 오차:{pct:.1f}% (창 닫으면 다음)", fontsize=12)
                plt.draw()
                result_flag[0] = True
        return onclick

    img = plt.imread(img_path)
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.imshow(img)
    ax.set_title(f"[{img_id}] {desc}\n왼쪽 벽 클릭", fontsize=12)
    fig.canvas.mpl_connect('button_press_event', make_onclick(clicks, result_done))
    plt.show()

print(f"\n결과:")
for r in results:
    print(f"  [{r['id']}] 수동:{r['mm']}mm GT:{r['gt']}mm 오차:{r['pct']}%")
