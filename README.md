# GeoCalib + Depth Pro 기반 실내 벽 간 거리 추정

> **KCC 2026 발표 논문 코드 및 실험 자료**
> 부동산 매물 사진 한 장에서 EXIF 없이 실내 벽 사이 거리를 추정하는 파이프라인

---

## 1. 배경

부동산 매물 사진은 두 가지 이유로 소비자가 실측 거리를 가늠하기 어렵습니다.

1. **광각 렌즈 왜곡** — 방을 넓어 보이게 촬영하기 위해 광각 렌즈를 사용해 공간이 늘어 보임
2. **EXIF 메타데이터 삭제** — 매물 플랫폼이 업로드 시 초점거리·센서 정보를 제거

본 연구는 **사진 한 장만으로** 위 두 제약을 해결하고 메트릭(metric, 미터 단위) 거리를 추정하는 파이프라인을 제안합니다.

---

## 2. 파이프라인

```
입력 사진 ──▶ ① GeoCalib ──▶ ② Depth Pro ──▶ ③ 3D 점군 복원 ──▶ ④ RANSAC 평면 적합 ──▶ 벽 간 거리(m)
              초점거리 추정    메트릭 깊이맵      핀홀 모델            평행벽 쌍 검출
```

| 단계 | 모델/방법 | 핵심 출력 |
|---|---|---|
| ① | **GeoCalib** (`weights='distorted'`) | 초점거리 `f_px`, roll/pitch, 방사 왜곡 계수 |
| ② | **Depth Pro** | 메트릭 깊이맵 (`f_px` 주입, 역깊이 스케일을 `W/f_px` 기반 보정) |
| ③ | 핀홀 모델 역투영 | 3D 포인트 클라우드 (유효 범위 0.5 m < Z < 10 m) |
| ④ | **RANSAC 평면 적합** | 임계 5 cm, 최대 1000 회, 평면 6개까지 추출 → 평행쌍(법선 내적 ≥ 0.8) 거리 계산 |

벽 두께 보정값 **160 mm**를 도면 GT에서 차감해 비교합니다.

---

## 3. 결과 (객관 수치)

### 전체 / 조건별

| 데이터셋 | 표본 | 10% 이내 | MAPE | 비고 |
|---|---|---|---|---|
| 전체 | 74장 | **37.8 %** | — | 모든 환경 포함 |
| 양호 조건 | 24장 | **79.2 %** | **6.6 %** | 중간값 4.7 %, 장애물 없음 |

### 초점거리 추정 방법 비교 (MAPE)

| 광각 (f < 500 px, n=38) | 일반 (f ≥ 500 px, n=16) |
|---|---|
| GeoCalib **17.6 %** ⭐ | GeoCalib 15.8 % |
| Depth Pro 자체 추정 20.1 % | Depth Pro 16.2 % |
| 고정 800 px 27.8 % | 고정 800 px 15.5 % |

**광각 사진에서 GeoCalib가 베이스라인 대비 유의미한 개선**을 보였고, 일반 화각에서는 세 방법의 차이가 작습니다.

---

## 4. 디렉토리 구조

```
.
├── README.md
├── paper/                              # 논문 원본 (PDF, Pages)
│   ├── kcc_paper_final.pdf             # KCC 2026 최종 제출본
│   ├── kcc_paper_review.pdf            # 심사용
│   ├── kcc_paper_new.pages
│   ├── kcc_paper_v3.pages
│   └── experiment_paper.pages
├── figures/                            # 논문 figure
│   ├── fig1_pipeline.png               # 파이프라인 다이어그램
│   └── fig2_qualitative_grid4.png      # 정성 비교 4-grid
├── scripts/                            # 실험 코드 (40+ 스크립트)
│   ├── run_full_pipeline.py            # 전체 파이프라인 실행
│   ├── pipeline_test.py                # 단일 이미지 테스트
│   ├── run_focal_comparison.py         # 초점거리 3-방법 비교
│   ├── manual_wall_*.py                # 수동 클릭 fallback
│   ├── test_improved_ransac*.py        # RANSAC 개선 실험
│   ├── visualize_ransac_planes.py      # 평면 시각화
│   ├── generate_paper_figure*.py       # 논문 figure 생성
│   └── build_draft_v*.py               # 논문 draft (docx) 빌더
├── depth_dataset_v1.csv                # Ground truth (도면 기반, 63장)
├── results_full.csv                    # 전체 파이프라인 결과
├── results_focal_comparison.csv        # 초점거리 비교 결과
├── data/                               # 원본 이미지 (gitignore)
├── output/                             # 깊이맵, 중간 결과 (gitignore)
└── seminar/, seminar2/                 # 진행 보고 자료 (gitignore)
```

---

## 5. 실행 방법

### 의존성

| 항목 | 출처 |
|---|---|
| Depth Pro | https://github.com/apple/ml-depth-pro |
| GeoCalib | https://github.com/cvg/GeoCalib |
| Python | 3.10+ |
| 주요 패키지 | `torch`, `numpy`, `opencv-python`, `pandas`, `matplotlib` |

> 두 모델은 외부 레포에서 별도 설치 후 import 경로를 `scripts/run_full_pipeline.py` 상단에서 지정해야 합니다.

### 단일 이미지 테스트

```bash
python scripts/pipeline_test.py
```

### 전체 파이프라인 + GT 비교

```bash
python scripts/run_full_pipeline.py
# 결과: results_full.csv 갱신
```

### 초점거리 3-방법 비교 실험

```bash
python scripts/run_focal_comparison.py
# 결과: results_focal_comparison.csv (A: GeoCalib, B: Depth Pro 자체, C: 고정 800px)
```

---

## 6. 데이터 출처 및 GT 구성

| 항목 | 내용 |
|---|---|
| 환경 | 국내 아파트 5단지 (예: 올림픽파크포레온, 게포자이프레지던스 등) |
| 표본 | 도면 GT 매칭 가능 63장 + 추가 검증 11장 = 74장 |
| GT 출처 | 네이버 부동산 도면 (벽 두께 160 mm 보정) |
| GT 불확실성 | ± 40 mm (벽 두께 변동 ≈ 1–2 %) |

원본 사진과 Depth 결과는 용량 사유로 git에 포함하지 않으며, `data/`, `output/`는 `.gitignore` 처리되어 있습니다.

---

## 7. 한계 (논문 명시)

- **단일 깊이 모델 검증**: Depth Pro 외 비교 미수행
- **RANSAC 임계값 ablation 없음**: 5 cm 고정값에 대한 민감도 분석 미포함
- **GT 자체 오차**: ± 40 mm (도면 벽 두께 변동)
- **실패 패턴 4종**:
  1. 벽 모서리/벽이 가려진 경우
  2. 가구가 벽을 점유한 경우
  3. 유리 발코니 (반사·투과)
  4. 광택 표면 반사
- **일반화 한계**: 원룸·오피스텔 등 GT 미확보 평면형은 미검증
- **수동 fallback**: 사용자 클릭 정확도가 환경마다 편차

---

## 8. 인용

```bibtex
@inproceedings{hong2026wall,
  title  = {GeoCalib와 Depth Pro를 이용한 부동산 매물 사진의 실내 벽 간 거리 추정 프레임워크},
  author = {홍화수},
  booktitle = {한국정보과학회 학술발표논문집 (KCC)},
  year   = {2026}
}
```

### 사용한 외부 모델

- **GeoCalib**: Veicht, A. et al. *GeoCalib: Learning Single-image Calibration with Geometric Optimization.* ECCV 2024.
- **Depth Pro**: Bochkovskii, A. et al. *Depth Pro: Sharp Monocular Metric Depth in Less Than a Second.* Apple, 2024.
