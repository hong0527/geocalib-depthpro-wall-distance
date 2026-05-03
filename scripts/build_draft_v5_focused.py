"""
draft_v5_focused.docx — 한 메시지로 좁힌 재구성판

핵심 변경 (vs v4 overlay):
  * 메인 메시지 1개로 통일:
    "광각 부동산 매물 사진에서 외부 카메라 캘리브레이션(GeoCalib)은
     단안 깊이(Depth Pro)의 metric 정확도를 결정한다.
     일반 화각에서는 큰 차이가 없다."
  * 제목 단순화 ("실패 케이스 수동 보완" 제거)
  * 요약 6줄로 압축
  * 본문에서 통계 문법 (p값/Cohen's d/CI/Bonferroni) 제거
    → 표 안에만 둠
  * 표 1: 3-way focal 비교 (A=GeoCalib, B=Depth Pro 자체, C=고정 800px)
  * 표 2: 실패 모드 정성 매트릭스 (note 컬럼 활용)
  * 그림 2: 성공/실패 6장 그리드 (정성 비교)
  * 4.5/4.6 통합 → "4.4 실패 모드 분석 및 수동 보완 가능성"
  * 원룸 부분 결론 한 줄로 흡수
  * 디스클레이머 결론 한 단락에 통합

Base: KCC2026_심사용_원본.docx (Normal 스타일=바탕 그대로 inherit)
"""
import os, shutil
from docx import Document
from docx.shared import Pt, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = '/Users/honghwasu/Desktop/research_project/output/논문양식'
SRC  = f'{BASE}/KCC2026_심사용_원본.docx'
DST  = f'{BASE}/draft_v5_focused.docx'

FIGS_DIR = '/Users/honghwasu/Desktop/research_project/output/paper_figures'
FIG2 = f'{FIGS_DIR}/fig2_qualitative_grid.png'

SIZE_TITLE     = 16
SIZE_TITLE_EN  = 13
SIZE_SECTION   = 12
SIZE_SUBSEC    = 10
SIZE_BODY      = 10
SIZE_SUMMARY   = 10
SIZE_TABLE     = 9
SIZE_REF       = 9
SIZE_CAP       = 9

# ============================================================
# Build base
# ============================================================
shutil.copy(SRC, DST)
doc = Document(DST)
body = doc.element.body

section_break_paras, other, final_sectPr = [], [], None
for child in list(body):
    if child.tag == qn('w:sectPr'):
        final_sectPr = child
    elif child.tag == qn('w:p'):
        pPr = child.find(qn('w:pPr'))
        if pPr is not None and pPr.find(qn('w:sectPr')) is not None:
            section_break_paras.append(child)
        else:
            other.append(child)
    elif child.tag == qn('w:tbl'):
        other.append(child)

for c in other:
    body.remove(c)
for sp in section_break_paras:
    for r in list(sp):
        if r.tag != qn('w:pPr'):
            sp.remove(r)
assert len(section_break_paras) == 1 and final_sectPr is not None
sec_break = section_break_paras[0]

# ============================================================
# Helpers
# ============================================================
def make_para(text, size, bold=False, italic=False,
              align=None, indent_mm=0, space_after_pt=3, line_spacing=None):
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    if align is not None:
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), {
            WD_ALIGN_PARAGRAPH.CENTER: 'center',
            WD_ALIGN_PARAGRAPH.LEFT: 'left',
            WD_ALIGN_PARAGRAPH.JUSTIFY: 'both',
            WD_ALIGN_PARAGRAPH.RIGHT: 'right',
        }[align])
        pPr.append(jc)
    if indent_mm:
        ind = OxmlElement('w:ind')
        ind.set(qn('w:firstLine'), str(int(indent_mm * 56.69)))
        pPr.append(ind)
    spacing = OxmlElement('w:spacing')
    spacing.set(qn('w:after'), str(int(space_after_pt * 20)))
    if line_spacing:
        spacing.set(qn('w:line'), str(int(line_spacing * 240)))
        spacing.set(qn('w:lineRule'), 'auto')
    pPr.append(spacing)
    p.append(pPr)
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(int(size * 2))); rPr.append(sz)
    szCs = OxmlElement('w:szCs'); szCs.set(qn('w:val'), str(int(size * 2))); rPr.append(szCs)
    if bold:
        rPr.append(OxmlElement('w:b'))
        rPr.append(OxmlElement('w:bCs'))
    if italic:
        rPr.append(OxmlElement('w:i'))
    r.append(rPr)
    t = OxmlElement('w:t')
    t.set(qn('xml:space'), 'preserve')
    t.text = text
    r.append(t)
    p.append(r)
    return p

def heading(text, level='section'):
    size = {'title': SIZE_TITLE, 'title_en': SIZE_TITLE_EN,
            'section': SIZE_SECTION, 'sub': SIZE_SUBSEC}[level]
    return make_para(text, size=size, bold=True, space_after_pt=1)

def table_elem(headers, rows, col_widths_mm):
    tbl = OxmlElement('w:tbl')
    tblPr = OxmlElement('w:tblPr')
    st = OxmlElement('w:tblStyle'); st.set(qn('w:val'), 'TableGrid'); tblPr.append(st)
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'), str(int(sum(col_widths_mm) * 56.69)))
    tblW.set(qn('w:type'), 'dxa'); tblPr.append(tblW)
    jc = OxmlElement('w:jc'); jc.set(qn('w:val'), 'center'); tblPr.append(jc)
    borders = OxmlElement('w:tblBorders')
    for side in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        b = OxmlElement(f'w:{side}')
        b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '4'); b.set(qn('w:color'), '000000')
        borders.append(b)
    tblPr.append(borders)
    tbl.append(tblPr)
    tblGrid = OxmlElement('w:tblGrid')
    for w_mm in col_widths_mm:
        gc = OxmlElement('w:gridCol')
        gc.set(qn('w:w'), str(int(w_mm * 56.69))); tblGrid.append(gc)
    tbl.append(tblGrid)

    def cell(txt, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER):
        tc = OxmlElement('w:tc')
        tcPr = OxmlElement('w:tcPr')
        tcW = OxmlElement('w:tcW'); tcW.set(qn('w:type'), 'auto'); tcW.set(qn('w:w'), '0'); tcPr.append(tcW)
        vA = OxmlElement('w:vAlign'); vA.set(qn('w:val'), 'center'); tcPr.append(vA)
        tc.append(tcPr)
        p = make_para(str(txt), size=SIZE_TABLE, bold=bold, align=align, space_after_pt=0)
        tc.append(p)
        return tc

    tr = OxmlElement('w:tr')
    for h in headers:
        tr.append(cell(h, bold=True))
    tbl.append(tr)
    for row in rows:
        tr = OxmlElement('w:tr')
        for v in row:
            tr.append(cell(v))
        tbl.append(tr)
    return tbl

def insert_before(anchor, *els):
    for el in els:
        anchor.addprevious(el)

# ============================================================
# SECTION 1 (1단): 제목 + 영문제목 + 요약
# ============================================================
s1 = []
s1.append(make_para(
    'GeoCalib과 Depth Pro를 활용한 부동산 매물 사진의 실내 거리 측정',
    size=SIZE_TITLE, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=3, line_spacing=1.15))
s1.append(make_para(
    'Indoor Wall-to-Wall Distance Measurement in Real Estate Photos '
    'using GeoCalib and Depth Pro',
    size=SIZE_TITLE_EN, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=12))

s1.append(heading('요   약', level='sub'))
s1.append(make_para(
    '부동산 매물 사진은 광각 렌즈로 촬영되어 실제보다 공간이 넓어 보이며, 플랫폼이 EXIF 정보를 '
    '삭제하여 소비자가 실내 치수를 사전에 가늠하기 어렵다. 본 논문은 EXIF가 없는 단일 실내 사진에서 '
    'GeoCalib으로 카메라 초점거리를 추정하고 Depth Pro로 metric depth를 생성한 뒤, RANSAC 평면 '
    '피팅으로 평행 벽 쌍을 탐지하여 벽-벽 거리를 자동 측정하는 프레임워크를 제안한다. 5개 단지 '
    '아파트 매물 사진을 평면도 기준 거리와 비교한 결과, 외부 캘리브레이션을 적용한 본 방법이 '
    'Depth Pro 자체 초점거리 추정 및 고정 초점거리 가정 대비 평균 오차가 낮았으며, 그 차이는 '
    '광각 사진에서 더 두드러졌다. 또한 자동 측정이 실패하는 환경 조건을 사례별로 분석하고 일부 '
    '케이스에서 사용자 수동 보완이 오차를 회복할 수 있음을 확인하였다.',
    size=SIZE_SUMMARY, indent_mm=4, space_after_pt=6, line_spacing=1.0))

insert_before(sec_break, *s1)

# ============================================================
# SECTION 2 (2단): 본문
# ============================================================
s2 = []

# 1. 서론
s2.append(heading('1. 서 론', level='section'))
s2.append(make_para(
    '부동산 매물 정보에서 전용면적은 공개되지만 개별 방의 가로·세로 치수는 제공되지 않는 경우가 '
    '많다. 소비자가 공간 크기를 사전에 판단할 수 있는 거의 유일한 시각 정보는 매물 사진이나, '
    '해당 사진은 대부분 광각 렌즈로 촬영되어 실제보다 공간이 넓어 보이는 왜곡을 발생시키며, 주요 '
    '플랫폼은 업로드 시 EXIF 메타데이터를 삭제하므로 촬영 초점거리도 확인할 수 없다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para(
    '본 논문의 핵심 질문은 "EXIF가 없는 광각 매물 사진에서 외부 카메라 캘리브레이션이 단안 깊이의 '
    'metric 정확도에 얼마나 기여하는가" 이다. 이를 검증하기 위해 GeoCalib [1]으로 초점거리를 '
    '추정해 Depth Pro [2]에 주입하는 결합 파이프라인을 구성하고, 캘리브레이션을 사용하지 않는 두 '
    '베이스라인(Depth Pro 자체 초점거리 추정, 일반 화각 가정의 고정 초점거리)과 5개 단지 81장의 '
    '평면도 기준 거리에 대해 비교한다. 또한 자동 RANSAC이 실패하는 환경 조건을 사례별로 분석하여 '
    '본 프레임워크의 적용 한계를 정성적으로 제시한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 2. 관련 연구
s2.append(heading('2. 관련 연구', level='section'))
s2.append(make_para(
    '카메라 캘리브레이션은 전통적 체커보드 기반 [9]에서 딥러닝 단일 이미지 접근 [6]으로 발전했고, '
    'GeoCalib [1]은 기하 최적화와 신경망 추정을 결합한다. 단안 metric depth는 Metric3D v2 [3], '
    'UniDepth [4], Depth Anything V2 [5]를 거쳐, Depth Pro [2]가 카메라 파라미터 없이도 metric '
    'depth를 생성한다. 부동산·실내 응용으로 Rent3D [7]는 사진-평면도 결합을, Zillow Indoor '
    'Dataset [8]은 파노라마-평면도 데이터셋을 제공한다. 국내에서 권혁찬 등 [10]은 GeoCalib을 '
    '매물 사진의 왜곡 판별에 활용하였으나 정량 치수 측정은 다루지 않는다. 본 연구는 GeoCalib + '
    'Depth Pro 결합 시 metric 정확도가 캘리브레이션 미적용 베이스라인 대비 어떻게 달라지는지를 '
    '5개 단지 매물 사진에서 검증한다는 점에서 차별화된다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 3. 제안 프레임워크
s2.append(heading('3. 제안 프레임워크', level='section'))
s2.append(make_para(
    '제안 프레임워크는 단일 실내 사진 I로부터 벽-벽 거리를 자동 측정하는 6단계 파이프라인이다 '
    '(그림 1). 먼저 GeoCalib에 I를 입력해 초점거리 f_px와 롤·피치 각, 방사 왜곡 계수를 추정한 '
    '뒤, 이 f_px를 Depth Pro에 주입해 metric depth map D를 얻는다. Depth Pro는 canonical '
    'inverse depth를 (W / f_px)로 스케일링해 미터 단위 깊이를 산출하므로 f_px의 정확도가 '
    'metric 정확도에 직접 영향을 준다. 픽셀 (u, v)의 3D 좌표는 핀홀 모델 X = (u − cx)·Z/f_px, '
    'Y = (v − cy)·Z/f_px, Z = D(u, v)로 복원하며 유효 범위 0.5 < Z < 10 m로 제한한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para(
    '점군에 대해 거리 임계값 5 cm, 1000회 반복의 RANSAC 평면 피팅을 최대 6회 수행해 평면을 '
    '순차 추출하고, 법선 y성분이 0.7 이하인 평면만 수직 벽 후보로 보존한다. 두 평면의 법선 내적이 '
    '0.8 이상인 평행 쌍 중 inlier 합이 최대인 쌍을 선택해 벽-벽 거리 dist = |d_i ± d_j|를 '
    '산출한다. 자동 RANSAC이 실패하거나 큰 오차를 보이는 케이스에 대해서는, 사용자가 두 벽 '
    '영역을 클릭해 해당 영역 깊이의 중앙값으로 거리를 직접 산출하는 수동 보완 경로를 병행한다 '
    '(4.4절 참조).',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para('[그림 1. 전체 파이프라인 흐름도 — 별도 제작 예정]',
                    size=SIZE_CAP, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=6))

# 4. 실험 및 결과
s2.append(heading('4. 실험 및 결과', level='section'))

s2.append(heading('4.1 데이터셋', level='sub'))
s2.append(make_para(
    '올림픽파크포레온, 개포자이프레지던스, 래미안원베일리, 헬리오시티, 마포래미안푸르지오의 5개 '
    '단지에서 실내 매물 사진 81장을 수집하였다. 평면도 기준 거리에서 벽 두께 160 mm를 차감한 '
    '마감면 간 거리를 기준값(GT)으로 사용한다. GeoCalib 추정 초점거리(N=63)의 중앙값은 446 px, '
    '약 70%가 500 px 미만으로 나타나 수집 사진 다수가 광각 렌즈로 촬영되었음을 시사한다. 비교 '
    '실험은 Depth Pro 자체 초점거리 추정이 성공한 61장에서 수행하였다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

s2.append(heading('4.2 캘리브레이션 적용 효과 (메인 결과)', level='sub'))
s2.append(make_para('표 1. 초점거리 입력 방식 3종 비교 (MAPE %, 측정 실패 ≥80% 케이스 제외 N=54).',
                    size=SIZE_CAP, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=2))
s2.append(table_elem(
    headers=['그룹', 'N', 'A: GeoCalib', 'B: 자체 추정', 'C: 고정 800 px'],
    rows=[
        ['전체',          '54', '17.0',  '18.7',  '24.4'],
        ['광각 (<500 px)', '38', '17.6',  '20.1',  '27.8'],
        ['일반 (≥500 px)', '16', '15.6',  '15.3',  '16.3'],
    ],
    col_widths_mm=[20, 8, 16, 16, 18]))
s2.append(make_para(
    '동일 사진에 세 가지 초점거리(A: GeoCalib 추정 / B: Depth Pro 자체 추정 / C: 일반 화각 가정의 '
    '800 px 고정)를 적용해 측정한 결과, 광각 사진에서 외부 캘리브레이션을 사용하지 않는 C는 평균 '
    '오차가 27.8%로 A 대비 약 10%p 높았으며, B 또한 광각에서 평균 2.5%p의 추가 오차를 보였다. '
    '반면 일반 화각(≥500 px)에서는 세 방식의 평균 오차가 비슷한 수준으로, 캘리브레이션 적용의 '
    '이점이 광각 조건에 집중됨을 확인할 수 있다. 광각 한 사례에서는 A=2.9%, B=18.3%, C=50.4%로 '
    '초점거리 입력 방식에 따라 측정 결과가 크게 달라졌다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

s2.append(heading('4.3 환경 조건별 정성 분석', level='sub'))
s2.append(make_para(
    '동일 파이프라인이 사진 환경에 따라 매우 다른 정확도를 보였다. 그림 2는 자동 측정이 양호한 '
    '사례 3장과 큰 오차를 보인 사례 3장을 비교한다. 양호 사례는 양쪽 벽이 명확하게 보이고 정면 '
    '구도이며 장애물이 적다는 공통점이 있다. 반면 실패 사례는 좁은 공간(ID 014), 코너 촬영 시 '
    '한쪽 벽 잘림과 빌트인 장애물(ID 051), 식탁·의자 등 가구가 화면 중앙을 점유하는 경우(ID '
    '060)에 집중된다. 81장 전체에서 RANSAC이 완전 실패한 2장과 측정 결과가 GT 대비 80% 이상 '
    '괴리된 6장을 합한 8장이 실패로 분류되었다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para('그림 2. 환경 조건별 성공/실패 사례 비교 (자동 RANSAC 측정).',
                    size=SIZE_CAP, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=6))

s2.append(heading('4.4 실패 모드 정리 및 수동 보완 가능성', level='sub'))
s2.append(make_para('표 2. 자동 측정 실패 모드 분류 및 수동 보완 적용 가능성.',
                    size=SIZE_CAP, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=2))
s2.append(table_elem(
    headers=['실패 모드', '대표 사례', '주요 원인', '수동 보완'],
    rows=[
        ['한쪽 벽 잘림 / 코너 촬영', 'ID 030, 043, 051', '평행 벽 점군 부족',     '효과적'],
        ['붙박이장 · 가구 · 아일랜드', 'ID 017, 023, 060', '벽 평면이 가구로 대체', '부분 효과'],
        ['발코니 유리문 / 좁은 공간', 'ID 014, 028, 031', '유리 너머 깊이 누락',   '효과적'],
        ['반사성 표면 (대리석 등)',  'ID 040 등',         '깊이 추정 부정확',     '제한적'],
    ],
    col_widths_mm=[27, 21, 23, 14]))
s2.append(make_para(
    '대표적인 실패 모드는 위 4종으로 정리된다. 사용자가 두 벽의 40 × 40 px 패치를 클릭하면 해당 '
    '영역 깊이의 중앙값으로 거리를 직접 산출하는 수동 보완을 적용한 결과, RANSAC이 창문·코너와 '
    '혼동한 잘못된 평면 피팅 사례에서는 평균 오차가 53%대에서 25%대로 감소하였고(예: ID 014 '
    '96.9%→27.0%, ID 051 71.3%→5.2%), 한쪽 벽 잘림 사례 일부에서도 회복이 확인되었다. 다만 '
    '코너 촬영에서 사용자가 부적절한 영역을 선택하면 오차가 오히려 증가하는 사용자 의존성이 '
    '존재하며, 반사성 표면이나 유리문 케이스에서는 수동 보완 효과가 제한적이었다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 5. 결론 및 한계
s2.append(heading('5. 결론 및 한계', level='section'))
s2.append(make_para(
    '본 논문은 EXIF가 없는 단일 실내 사진에서 GeoCalib + Depth Pro 결합 파이프라인을 제안하고, '
    '캘리브레이션을 사용하지 않는 두 베이스라인 대비 광각 사진에서 metric 정확도 우위를 5개 단지 '
    '81장에서 확인하였다. 일반 화각에서는 세 방식이 비슷하므로 본 결합은 광각 환경에서 특히 '
    '의미가 있다. 본 연구는 단일 깊이 모델 검증, RANSAC 임계값 ablation 부재, 평면도 GT의 벽 '
    '두께 가정에 따른 약 1~2% 내재 불확실성, 사용자 수동 측정의 의존성 등의 한계를 가진다. 향후 '
    '평면도 GT 확보가 어려운 원룸·오피스텔로의 일반화, 복수 단안 깊이 모델 교차 검증, 자동-수동 '
    '하이브리드 인터페이스 설계를 계획한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 참고문헌
s2.append(heading('참고 문헌', level='sub'))
for ref in [
    '[1] A. Veicht et al., "GeoCalib," ECCV 2024.',
    '[2] A. Bochkovskii et al., "Depth Pro," ICLR 2025.',
    '[3] M. Hu et al., "Metric3D v2," TPAMI 2024.',
    '[4] L. Piccinelli et al., "UniDepth," CVPR 2024.',
    '[5] L. Yang et al., "Depth Anything V2," NeurIPS 2024.',
    '[6] L. Jin et al., "Perspective Fields for Single Image Camera Calibration," CVPR 2023.',
    '[7] C. Liu et al., "Rent3D," CVPR 2015.',
    '[8] S. Cruz et al., "Zillow Indoor Dataset," CVPR 2021.',
    '[9] Z. Zhang, "Flexible Camera Calibration," IEEE PAMI 22(11), 2000.',
    '[10] 권혁찬 외, "AI 부동산 왜곡 탐지·보정," 한국정보기술학회, 2024.',
]:
    s2.append(make_para(ref, size=SIZE_REF, indent_mm=3, space_after_pt=0, line_spacing=0.9))

insert_before(final_sectPr, *s2)
doc.save(DST)
print(f'[step1] text saved: {DST}')

# ============================================================
# 그림 2 삽입 (Figure 1은 사용자가 직접 제작)
# ============================================================
doc = Document(DST)
fig_map = [
    ('그림 2.', FIG2, 88),
]
for cap_prefix, path, width_mm in fig_map:
    if not os.path.exists(path):
        print(f'  MISSING {path}')
        continue
    inserted = False
    for p in doc.paragraphs:
        if p.text.strip().startswith(cap_prefix):
            new_p = p.insert_paragraph_before()
            new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            new_p.add_run().add_picture(path, width=Mm(width_mm))
            inserted = True
            print(f'  inserted {cap_prefix} ← {os.path.basename(path)}')
            break
    if not inserted:
        print(f'  placeholder not found for {cap_prefix}')

doc.save(DST)
print(f'\n[DONE] {DST}  size={os.path.getsize(DST):,} bytes')
