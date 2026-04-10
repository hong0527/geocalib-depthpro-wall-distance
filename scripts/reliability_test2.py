"""신뢰도 테스트 v2: 결과를 파일에 직접 쓰기 + 타임아웃"""
import os, numpy as np, csv, time

RESULT_FILE = "/Users/honghwasu/Desktop/research_project/output/reliability_result.txt"
f_out = open(RESULT_FILE, 'w')

def log(msg):
    f_out.write(msg + '\n')
    f_out.flush()

accurate_ids = ['036','029','020','013','032','023','027','045','041','052','026','022','050']

meta = {}
with open("/Users/honghwasu/Desktop/research_project/output/depth_maps/depth_meta.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        meta[row['image_id']] = row

def fit_plane_ransac(pts, th=0.05, n_iter=300):
    best_p, best_i = None, []
    n = len(pts)
    for _ in range(n_iter):
        idx = np.random.choice(n, 3, replace=False)
        p1, p2, p3 = pts[idx]
        nm = np.cross(p2-p1, p3-p1)
        nl = np.linalg.norm(nm)
        if nl < 1e-10: continue
        nm /= nl
        d = -np.dot(nm, p1)
        dists = np.abs(pts @ nm + d)
        ii = np.where(dists < th)[0]
        if len(ii) > len(best_i):
            best_i, best_p = ii, [nm[0],nm[1],nm[2],d]
    return best_p, best_i

def measure_ransac(depth, fpx):
    H, W = depth.shape
    cx, cy = W/2.0, H/2.0
    u, v = np.meshgrid(np.arange(W), np.arange(H))
    Z = depth
    X = (u-cx)*Z/fpx; Y = (v-cy)*Z/fpx
    pts = np.stack([X,Y,Z],-1).reshape(-1,3)
    ok = (Z.reshape(-1)>0.5)&(Z.reshape(-1)<10)
    pts = pts[ok]
    pts = pts[np.isfinite(pts).all(1)]
    if len(pts) > 20000:
        pts = pts[np.random.choice(len(pts), 20000, replace=False)]
    walls, rem = [], pts.copy()
    for _ in range(4):
        if len(rem) < 300: break
        pl, inl = fit_plane_ransac(rem)
        if pl is None: break
        nm = np.array(pl[:3]); nm /= np.linalg.norm(nm)
        if abs(nm[1]) <= 0.7:
            walls.append({'n':nm,'d':pl[3],'pts':len(inl)})
        m = np.ones(len(rem),bool); m[inl]=False; rem=rem[m]
    best = None
    for i in range(len(walls)):
        for j in range(i+1, len(walls)):
            dot = np.dot(walls[i]['n'],walls[j]['n'])
            if abs(dot) > 0.8:
                dist = abs(walls[i]['d']+walls[j]['d']) if dot<0 else abs(walls[i]['d']-walls[j]['d'])
                tp = walls[i]['pts']+walls[j]['pts']
                if best is None or tp>best[1]: best=(dist,tp)
    return int(best[0]*1000) if best else None

def measure_fixed(depth, fpx):
    H, W = depth.shape
    cx, cy = W/2.0, H/2.0
    lx1,ly1 = int(W*0.02),int(H*0.25)
    lx2,ly2 = int(W*0.12),int(H*0.75)
    rx1,ry1 = int(W*0.88),int(H*0.25)
    rx2,ry2 = int(W*0.98),int(H*0.75)
    def to3d(x1,y1,x2,y2):
        u,v = np.meshgrid(np.arange(x1,x2),np.arange(y1,y2))
        Z=depth[y1:y2,x1:x2]
        X=(u-cx)*Z/fpx; Y=(v-cy)*Z/fpx
        pts=np.stack([X,Y,Z],-1).reshape(-1,3)
        ok=(pts[:,2]>0.3)&(pts[:,2]<15)&np.isfinite(pts).all(1)
        return pts[ok]
    def fit(pts):
        c=pts.mean(0); _,_,Vt=np.linalg.svd(pts-c)
        n=Vt[-1]; n/=np.linalg.norm(n)
        return n, -np.dot(n,c)
    pl=to3d(lx1,ly1,lx2,ly2); pr=to3d(rx1,ry1,rx2,ry2)
    if len(pl)<10 or len(pr)<10: return None
    n1,d1=fit(pl); n2,d2=fit(pr)
    dist=abs(d1+d2) if np.dot(n1,n2)<0 else abs(d1-d2)
    return int(dist*1000)

log("ID    GT    R1      R2      R3      편차    고정영역")
log("-" * 65)

for rid in accurate_ids:
    m = meta[rid]
    depth = np.load(m['npy_path'])
    fw = float(m['f_wide_geocalib'])
    gt_adj = int(m['gt_mm']) - 160

    rs = []
    for trial in range(3):
        t0 = time.time()
        r = measure_ransac(depth, fw)
        elapsed = time.time() - t0
        rs.append(r if r else 0)
        if elapsed > 30:
            log(f"  {rid} trial {trial} 타임아웃 ({elapsed:.0f}s)")
            break

    fixed = measure_fixed(depth, fw)
    fx = fixed if fixed else 0

    valid = [r for r in rs if r > 100]
    std = int(np.std(valid)) if valid else -1

    log(f"{rid}  {gt_adj:>5}  {rs[0]:>6}  {rs[1]:>6}  {rs[2]:>6}  {std:>5}  {fx:>6}")

log("\n완료!")
f_out.close()
