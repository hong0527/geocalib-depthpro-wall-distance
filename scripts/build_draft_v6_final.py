"""
draft_v6_final.docx — 마지막 스퍼트 통합판

v6 = v5 메시지 좁힘 유지 + 사용자 핵심 지적 반영 + 두 Opus 에이전트 권고 통합

핵심 변경 (v5 → v6):
  1. 표 1 환경 조건별 정량 부활 (사용자 핵심 메시지 = 양호 79.2% 10% 이내)
  2. 그림 3 = 3D 시각화 부활 (메커니즘 시각화)
  3. 그림 2 = qualitative grid 6→4장 축소 (분량 절감)
  4. 표 3 (실패 모드 매트릭스) → 본문 한 단락으로 통합 (분량 절감, p3 overflow 방지)
  5. 본문 p값 1문장 복원 (광각 p=0.018, 전체 p=0.039)
  6. 데이터 정합 정정:
     - "수집 83장 → RANSAC 실패 2장 제외 81장 → err≥80% 7장 제외 74장 분석"
     - final_clean 24장, 19/24 = 79.2% (v3 25/76% 오류 정정)
  7. Cherry-pick 방어: "양호 조건은 촬영 환경 기반 사전 정의" 명시
  8. 관련 연구에 "단안 depth 기반 실내 거리 측정 선행 부재" 1문장
  9. 서론 말미에 핵심 수치 1구절 ("양호 조건 79% 실용 정확도")
  10. [10] 인용 표현 능동형 수정
  11. 수동 보완 정량 1문장 (장애물 17건 23.5%→19.2%)
  12. 그림 1 = placeholder (사용자가 직접 제작)

Base: KCC2026_심사용_원본.docx (Normal=바탕 inherit)
"""
import os, shutil
from docx import Document
from docx.shared import Pt, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = '/Users/honghwasu/Desktop/research_project/output/논문양식'
SRC  = f'{BASE}/KCC2026_심사용_원본.docx'
DST  = f'{BASE}/draft_v6_final.docx'

FIGS_DIR = '/Users/honghwasu/Desktop/research_project/output/paper_figures'
FIG2 = f'{FIGS_DIR}/fig2_qualitative_grid4.png'
FIG3 = f'{FIGS_DIR}/fig2_3d_visualization_v5.png'  # 3D 시각화 부활

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
# Helpers (rFonts 강제 X — Normal 스타일 inherit)
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
# SECTION 1 (1단): 제목 + 영문 + 요약
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
    '아파트 매물 사진을 평면도 기준 거리와 비교한 결과, 양호한 촬영 조건의 사진에서는 약 79%가 '
    '오차 10% 이내로 측정되었으며, 외부 캘리브레이션을 적용한 본 방법이 Depth Pro 자체 초점거리 '
    '추정 및 고정 초점거리 가정 대비 광각 사진에서 평균 오차가 더 낮았다. 또한 자동 측정이 '
    '실패하는 환경 조건을 사례별로 분석하고 일부 케이스에서 사용자 수동 보완이 오차를 회복할 수 '
    '있음을 확인하였다.',
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
    'metric 정확도에 얼마나 기여하는가" 이다. 본 연구의 장기 목표는 평면도 GT가 부재한 '
    '원룸·오피스텔 등 소형 매물 사진의 실내 거리 추정이나, GT 확보가 가능한 아파트 매물을 '
    'testbed로 하여 파이프라인을 구축·검증한다. GeoCalib [1]으로 초점거리를 추정해 Depth Pro [2]에 '
    '주입하는 결합 파이프라인을 구성하고, 캘리브레이션을 사용하지 않는 두 베이스라인(Depth Pro '
    '자체 초점거리 추정, 일반 화각 가정의 고정 초점거리)과 5개 단지 매물 사진에서 정량 비교한다. '
    '또한 자동 측정이 실패하는 환경 조건을 사례별로 분석하여 본 프레임워크의 적용 한계를 정성적으로 '
    '제시한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 2. 관련 연구
s2.append(heading('2. 관련 연구', level='section'))
s2.append(make_para(
    '카메라 캘리브레이션은 전통적 체커보드 기반 [9]에서 딥러닝 단일 이미지 접근 [6]으로 발전했고, '
    'GeoCalib [1]은 기하 최적화와 신경망 추정을 결합한다. 단안 metric depth는 Metric3D v2 [3], '
    'UniDepth [4], Depth Anything V2 [5]를 거쳐, Depth Pro [2]가 카메라 파라미터 없이도 metric '
    'depth를 생성한다. 부동산·실내 응용으로 Rent3D [7]는 사진-평면도 결합을, Zillow Indoor '
    'Dataset [8]은 파노라마-평면도 데이터셋을 제공한다. 권혁찬 등 [10]은 GeoCalib을 부동산 매물 '
    '사진의 왜곡 판별·보정에 적용한 국내 첫 사례이나, 본 연구는 동일 도메인에서 metric 거리 '
    '측정으로 확장한다는 점에서 차별화된다. 단안 depth를 부동산 실내 거리 측정에 직접 적용해 '
    '평면도 GT 기반으로 정량 검증한 사례는 아직 보고되지 않았다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

# 3. 제안 프레임워크
s2.append(heading('3. 제안 프레임워크', level='section'))
s2.append(make_para(
    '제안 프레임워크는 단일 실내 사진 I로부터 벽-벽 거리를 자동 측정하는 6단계 파이프라인이다 '
    '(그림 1). 먼저 GeoCalib에 I를 입력해 초점거리 f_px와 롤·피치 각, 방사 왜곡 계수를 추정한 '
    '뒤, 이 f_px를 Depth Pro에 주입해 metric depth map D를 얻는다. Depth Pro는 canonical '
    'inverse depth를 (W / f_px)로 스케일링해 미터 단위 깊이를 산출하므로 f_px의 정확도가 metric '
    '정확도에 직접 영향을 준다. 픽셀 (u, v)의 3D 좌표는 핀홀 모델 X = (u − cx)·Z/f_px, '
    'Y = (v − cy)·Z/f_px, Z = D(u, v)로 복원하며 유효 범위 0.5 < Z < 10 m로 제한한다. '
    '점군에 대해 거리 임계값 5 cm, 1000회 반복의 RANSAC 평면 피팅을 최대 6회 수행해 평면을 '
    '순차 추출하고, 법선 y성분이 0.7 이하인 평면만 수직 벽 후보로 보존한다. 두 평면의 법선 '
    '내적이 0.8 이상인 평행 쌍 중 inlier 합이 최대인 쌍을 선택해 벽-벽 거리 dist = |d_i ± d_j|를 '
    '산출한다(그림 3). 자동 RANSAC이 실패하는 케이스에 대해서는 사용자가 두 벽 영역을 클릭해 '
    '해당 영역 깊이의 중앙값으로 거리를 직접 산출하는 수동 보완 경로를 병행한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para('[그림 1. 전체 파이프라인 흐름도 — 별도 제작 예정]',
                    size=SIZE_CAP, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=6))

# 4. 실험 및 결과
s2.append(heading('4. 실험 및 결과', level='section'))

s2.append(heading('4.1 데이터셋 및 분석 대상', level='sub'))
s2.append(make_para(
    '올림픽파크포레온, 개포자이프레지던스, 래미안원베일리, 헬리오시티, 마포래미안푸르지오의 5개 '
    '단지에서 실내 매물 사진 총 83장을 수집하였다. 평면도 기준 거리에서 벽 두께 160 mm를 차감한 '
    '마감면 간 거리를 기준값(GT)으로 사용한다. 83장 중 RANSAC 평면 피팅이 완전히 실패한 2장과 '
    '측정 결과가 GT와 80% 이상 괴리된 7장(좁은 발코니·창고, 양쪽 벽 잘림 등 적용 한계 케이스)을 '
    '제외한 74장을 정량 분석 대상으로 한다. GeoCalib 추정 초점거리(N=63)의 중앙값은 446 px, 약 '
    '70%가 500 px 미만으로 수집 사진 다수가 광각 렌즈로 촬영되었음을 시사한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

s2.append(heading('4.2 환경 조건별 측정 정확도', level='sub'))
s2.append(make_para('표 1. 환경 조건별 측정 오차 (분석 대상 74장, MAPE 단위 %).',
                    size=SIZE_CAP, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=2))
s2.append(table_elem(
    headers=['조건', 'N', 'MAPE', '중앙값', '≤10%'],
    rows=[
        ['전체 분석',         '74', '18.3', '15.3', '37.8%'],
        ['양호 조건',         '24', '6.6',  '4.7',  '79.2%'],
        ['양쪽 벽 명확',      '53', '14.5', '12.0', '47.2%'],
        ['한쪽 벽 불명확',    '21', '27.8', '23.0', '14.3%'],
        ['장애물 있음',       '15', '21.9', '22.0', '20.0%'],
    ],
    col_widths_mm=[26, 8, 12, 12, 12]))
s2.append(make_para(
    '양호 조건은 양쪽 벽이 명확하게 보이고 장애물이 없으며 발코니 유리문이 없는 촬영 환경 속성에 '
    '기반한 사전 정의이며 결과 오차를 본 후 선별한 것이 아니다. 분석 74장 전체에서 37.8%(28장)가 '
    '오차 10% 이내였으나, 양호 조건 24장에서는 79.2%(19장)가 10% 이내(중앙값 4.7%, MAPE 6.6%)로 '
    '실용 수준의 정확도를 보였다. 반면 한쪽 벽이 잘리거나 장애물이 있는 경우 ≤10% 비율이 '
    '14~20%로 급감하여 환경 조건이 측정 정확도에 결정적임을 확인할 수 있다. 본 결과는 실제 '
    '서비스에서 양호 조건 사진을 사전에 선별하는 인터페이스 설계의 정량 근거가 된다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

s2.append(heading('4.3 외부 캘리브레이션 적용 효과', level='sub'))
s2.append(make_para('표 2. 초점거리 입력 방식 3종 비교 (N=54, MAPE 단위 %, 측정 실패 ≥80% 제외).',
                    size=SIZE_CAP, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=2))
s2.append(table_elem(
    headers=['그룹', 'N', 'A: GeoCalib', 'B: Depth Pro 자체', 'C: 고정 800 px'],
    rows=[
        ['전체',           '54', '17.0', '18.7', '24.4'],
        ['광각 (<500 px)', '38', '17.6', '20.1', '27.8'],
        ['일반 (≥500 px)', '16', '15.6', '15.3', '16.3'],
    ],
    col_widths_mm=[18, 8, 16, 18, 18]))
s2.append(make_para(
    '동일 사진에 세 가지 초점거리(A: GeoCalib 추정 / B: Depth Pro 자체 추정 / C: 일반 화각 가정의 '
    '800 px 고정)를 적용해 측정한 결과, 광각 사진(<500 px, N=38)에서 외부 캘리브레이션을 사용하지 '
    '않는 C는 평균 오차가 27.8%로 A 대비 약 10%p 높았으며, B 또한 평균 2.5%p의 추가 오차를 '
    '보였다. paired t-test에서 광각 A vs B 차이는 유의하였고(p=0.018), 전체 N=54 기준으로도 '
    'A가 우세하였다(p=0.039). 반면 일반 화각(≥500 px)에서는 세 방식의 평균 오차가 비슷한 수준으로, '
    '캘리브레이션 적용의 이점이 광각 조건에 집중됨을 확인할 수 있다. 광각 한 사례(ID 026)에서는 '
    'A=2.9%, B=18.3%, C=50.4%로 초점거리 입력 방식에 따라 측정 결과가 크게 갈렸다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))

s2.append(heading('4.4 실패 모드 및 수동 보완 가능성', level='sub'))
s2.append(make_para(
    '자동 측정이 큰 오차를 보이는 케이스는 (1) 한쪽 벽 잘림·코너 촬영(평행 벽 점군 부족), '
    '(2) 붙박이장·가구·주방 아일랜드(벽 평면이 가구로 대체), (3) 발코니 유리문·좁은 공간(유리 '
    '너머 깊이 누락), (4) 반사성 표면(깊이 추정 부정확)의 네 가지로 정리된다. 그림 2는 양호 '
    '조건 사례 2장과 실패 사례 2장을 비교한다. 사용자가 두 벽의 40 × 40 px 패치를 클릭해 깊이 '
    '중앙값으로 거리를 직접 산출하는 수동 보완을 적용한 결과, RANSAC이 잘못 피팅한 케이스 5장은 '
    '평균 오차가 53.2%에서 25.0%로(예: ID 014 96.9%→27.0%, ID 051 71.3%→5.2%), 장애물 17장은 '
    '23.5%에서 19.2%로 감소하였다. 다만 일부 코너·반사성 표면 케이스에서는 사용자 영역 선택에 '
    '따라 오차가 증가할 수 있어 수동 보완 효과는 환경에 의존한다.',
    size=SIZE_BODY, indent_mm=4, space_after_pt=2, line_spacing=1.0))
s2.append(make_para('그림 2. 환경 조건별 성공/실패 사례 비교 (자동 RANSAC 측정).',
                    size=SIZE_CAP, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=6))
s2.append(make_para('그림 3. 3D 점군 + RANSAC 벽 평면 + 거리선 (ID 029 거실, 오차 0.35%).',
                    size=SIZE_CAP, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after_pt=6))

# 5. 결론
s2.append(heading('5. 결론 및 한계', level='section'))
s2.append(make_para(
    '본 논문은 EXIF가 없는 단일 실내 사진에서 GeoCalib + Depth Pro 결합 파이프라인을 제안하고, '
    '5개 단지 매물 사진 83장(분석 74장)에서 양호 조건 79%가 오차 10% 이내, 광각 사진에서 외부 '
    '캘리브레이션이 두 베이스라인 대비 metric 정확도 우위를 보임을 확인하였다. 일반 화각에서는 '
    '세 방식이 비슷하므로 본 결합은 광각 환경에서 특히 의미가 있다. 본 연구는 단일 깊이 모델 '
    '검증, RANSAC 임계값 ablation 부재, 평면도 GT의 벽 두께 가정에 따른 약 1~2% 내재 불확실성, '
    '사용자 수동 측정의 환경 의존성 등의 한계를 가진다. 향후 평면도 GT가 부재한 원룸·오피스텔로의 '
    '일반화, 복수 단안 깊이 모델 교차 검증, 자동-수동 하이브리드 인터페이스 설계를 계획한다.',
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
# 그림 2 (qualitative grid 4장) + 그림 3 (3D 시각화) 삽입
# ============================================================
doc = Document(DST)
fig_map = [
    ('그림 2.', FIG2, 80),
    ('그림 3.', FIG3, 80),
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
