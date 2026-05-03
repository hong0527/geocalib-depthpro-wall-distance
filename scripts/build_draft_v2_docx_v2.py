"""
draft_v2.docx 재생성 — KCC 양식 구조(1단 제목/요약 + 2단 본문) 엄격 준수

전략:
- 원본 템플릿의 2개 section (1col title + 2col body) 구조를 보존
- 첫 번째 section: 제목·국문요약·Keywords·Abstract (1-column)
- 두 번째 section: 본문 1~5 + 참고문헌 (2-column)
"""
import os, shutil
from copy import deepcopy
from docx import Document
from docx.shared import Pt, Mm, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = '/Users/honghwasu/Desktop/research_project/output/논문양식'
SRC  = f'{BASE}/KCC2026_심사용_원본.docx'
DST  = f'{BASE}/draft_v2.docx'

FIG2 = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig2_3d_visualization_v5.png'
FIG2_FALLBACK = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig2_3d_visualization_v3.png'
FIG3 = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig3_focal_histogram_v2.png'
FIG4 = '/Users/honghwasu/Desktop/research_project/output/paper_figures/fig4_manual_vs_auto_v2.png'

fig2_path = FIG2 if os.path.exists(FIG2) else FIG2_FALLBACK
print(f"Using FIG2: {fig2_path}")

shutil.copy(SRC, DST)
doc = Document(DST)

# ============================================================
# Clear all existing content preserving section structure
# ============================================================
body = doc.element.body

# Collect sectPr elements (final sectPr is direct body child; intermediate sectPrs are inside pPr of paragraphs)
# Strategy: find intermediate sectPr (inside pPr) and preserve those paragraphs emptied
# Find final sectPr (body child) — keep as-is

# Iterate over body children and identify the "section break paragraph"
section_break_paras = []
other_content = []
final_sectPr = None
for child in list(body):
    if child.tag == qn('w:sectPr'):
        final_sectPr = child
    elif child.tag == qn('w:p'):
        pPr = child.find(qn('w:pPr'))
        if pPr is not None and pPr.find(qn('w:sectPr')) is not None:
            section_break_paras.append(child)
        else:
            other_content.append(child)
    elif child.tag == qn('w:tbl'):
        other_content.append(child)

print(f"Found: {len(section_break_paras)} section-break paragraph(s), {len(other_content)} regular items, "
      f"final sectPr: {'yes' if final_sectPr is not None else 'no'}")

# Remove all regular content (keep section-break paragraphs + final sectPr)
for c in other_content:
    body.remove(c)
# Clean section-break paragraph content (keep the pPr+sectPr only)
for sp in section_break_paras:
    # Remove all runs, keep only pPr
    for r in list(sp):
        if r.tag != qn('w:pPr'):
            sp.remove(r)

# Now body has: [section-break para (empty, holds sectPr1)] [final sectPr (sectPr2)]
# Ensure section-break para is at index 0 and final sectPr at end
body_children = list(body)
print(f"After cleanup body has {len(body_children)} children")

# ============================================================
# HELPERS — insert BEFORE a given element
# ============================================================
def _set_font(run, size=10, bold=False, italic=False, kor='맑은 고딕', ascii_font='Times New Roman'):
    run.font.size = Pt(size)
    run.font.name = ascii_font
    run.bold = bold
    run.italic = italic
    rPr = run._element.get_or_add_rPr()
    for rF in rPr.findall(qn('w:rFonts')):
        rPr.remove(rF)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), ascii_font)
    rFonts.set(qn('w:eastAsia'), kor)
    rFonts.set(qn('w:hAnsi'), ascii_font)
    rPr.append(rFonts)

def make_para(text, size=10, bold=False, align=None, indent_mm=0, space_after=3, italic=False):
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    if align is not None:
        jc = OxmlElement('w:jc')
        jc.set(qn('w:val'), {WD_ALIGN_PARAGRAPH.CENTER:'center',
                             WD_ALIGN_PARAGRAPH.LEFT:'left',
                             WD_ALIGN_PARAGRAPH.JUSTIFY:'both',
                             WD_ALIGN_PARAGRAPH.RIGHT:'right'}[align])
        pPr.append(jc)
    if indent_mm:
        ind = OxmlElement('w:ind')
        ind.set(qn('w:firstLine'), str(int(indent_mm * 56.69)))
        pPr.append(ind)
    if space_after:
        spacing = OxmlElement('w:spacing')
        spacing.set(qn('w:after'), str(space_after * 20))
        pPr.append(spacing)
    p.append(pPr)
    r = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')
    sz = OxmlElement('w:sz'); sz.set(qn('w:val'), str(size*2)); rPr.append(sz)
    szCs = OxmlElement('w:szCs'); szCs.set(qn('w:val'), str(size*2)); rPr.append(szCs)
    if bold:
        b = OxmlElement('w:b'); rPr.append(b)
    if italic:
        it = OxmlElement('w:i'); rPr.append(it)
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:ascii'), 'Times New Roman')
    rFonts.set(qn('w:eastAsia'), '맑은 고딕')
    rFonts.set(qn('w:hAnsi'), 'Times New Roman')
    rPr.append(rFonts)
    r.append(rPr)
    t = OxmlElement('w:t')
    t.set(qn('xml:space'), 'preserve')
    t.text = text
    r.append(t)
    p.append(r)
    return p

def insert_before(anchor, *elements):
    """anchor 앞에 요소들을 순서대로 삽입"""
    for el in elements:
        anchor.addprevious(el)

def make_heading(text, size=12):
    return make_para(text, size=size, bold=True, space_after=3)

def make_table(headers, rows, col_widths_mm):
    tbl = OxmlElement('w:tbl')
    tblPr = OxmlElement('w:tblPr')
    tblStyle = OxmlElement('w:tblStyle'); tblStyle.set(qn('w:val'), 'TableGrid'); tblPr.append(tblStyle)
    tblW = OxmlElement('w:tblW')
    total = sum(col_widths_mm) * 56.69
    tblW.set(qn('w:w'), str(int(total))); tblW.set(qn('w:type'), 'dxa')
    tblPr.append(tblW)
    jc = OxmlElement('w:jc'); jc.set(qn('w:val'), 'center'); tblPr.append(jc)
    tblBorders = OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        b = OxmlElement(f'w:{side}')
        b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '4'); b.set(qn('w:color'), '000000')
        tblBorders.append(b)
    tblPr.append(tblBorders)
    tbl.append(tblPr)
    tblGrid = OxmlElement('w:tblGrid')
    for w_mm in col_widths_mm:
        gc = OxmlElement('w:gridCol')
        gc.set(qn('w:w'), str(int(w_mm * 56.69)))
        tblGrid.append(gc)
    tbl.append(tblGrid)

    def cell(text, bold=False):
        tc = OxmlElement('w:tc')
        tcPr = OxmlElement('w:tcPr')
        tcW = OxmlElement('w:tcW'); tcW.set(qn('w:type'), 'auto'); tcW.set(qn('w:w'), '0'); tcPr.append(tcW)
        vAlign = OxmlElement('w:vAlign'); vAlign.set(qn('w:val'), 'center'); tcPr.append(vAlign)
        tc.append(tcPr)
        p = make_para(str(text), size=8, bold=bold, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0)
        tc.append(p)
        return tc

    # header row
    tr = OxmlElement('w:tr')
    for h in headers:
        tr.append(cell(h, bold=True))
    tbl.append(tr)
    # body rows
    for row in rows:
        tr = OxmlElement('w:tr')
        for v in row:
            tr.append(cell(v))
        tbl.append(tr)
    return tbl

def make_figure_para(img_path, width_mm):
    """image embedded via add_picture (need a real Document paragraph)"""
    # python-docx requires paragraph object; fall back to using doc.paragraphs approach
    # Instead: create placeholder paragraph and later resolve via doc
    return None  # handled below

# ============================================================
# Prepare content elements (XML) in order
# ============================================================
assert len(section_break_paras) == 1, f"Expected 1 section break para, got {len(section_break_paras)}"
sec_break_para = section_break_paras[0]
# Everything BEFORE sec_break_para → section 1 (1-col): title, abstract, keywords
# Everything AFTER sec_break_para, BEFORE final sectPr → section 2 (2-col): body+refs

# ============================================================
# SECTION 1 — title, 요약, keywords, Abstract (1-column)
# ============================================================
s1_elements = []

# Title (국문)
p = make_para(
    'GeoCalib + Depth Pro 기반 부동산 매물 사진의 실내 벽-벽 거리 측정 및 실패 케이스 수동 보완 프레임워크',
    size=15, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=3)
s1_elements.append(p)

# Title (영문)
p = make_para(
    'A Framework for Indoor Wall-to-Wall Distance Measurement in Real Estate Photos '
    'using GeoCalib and Depth Pro, with Manual Refinement for RANSAC Failures',
    size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)
s1_elements.append(p)

# 요약
s1_elements.append(make_heading('요   약', size=11))
summary_kor = (
    '부동산 매물 사진은 광각 렌즈로 촬영되어 실제보다 공간이 넓어 보이며, 플랫폼이 EXIF 정보를 삭제하여 '
    '소비자가 실내 치수를 사전에 확인하기 어렵다. 본 논문은 EXIF가 없는 단일 실내 사진에서 초점거리를 '
    'GeoCalib으로 추정하고, Depth Pro로 metric depth를 생성한 뒤, RANSAC 평면 피팅으로 평행 벽 쌍을 '
    '탐지하여 벽-벽 거리를 자동 측정하는 프레임워크를 제안한다. 5개 단지 아파트 81장의 평면도 기준 거리를 '
    'GT로 사용하여 정량 검증한 결과, 전체 유효 79장 중 35.4%(28장)가 10% 이하 오차를 달성하였으며, '
    '양호 조건 25장(전체의 30.9%)에서는 76%(19장)가 10% 이하 오차(중앙값 5.3%, MAE 28.8 cm)를 기록하였다. '
    'GeoCalib 추정 초점거리 분포의 69.8%(44/63)가 500 px 미만으로 광각 렌즈 사용을 시사하였으며, 해당 '
    '광각 영역에서 GeoCalib focal이 Depth Pro 자체 focal 추정 대비 paired 오차가 평균 3.44%p 낮았다 '
    "(paired t-test, p=0.026; Cohen's d=-0.35, 95% CI [-6.44, -0.43]%p). 또한 자동 RANSAC이 실패하거나 "
    '큰 오차를 보인 케이스에 대해 사용자가 벽 영역을 수동 지정하면 장애물 17장(paired)에서 평균 오차가 '
    '23.5%→19.2%, RANSAC 잘못 피팅 5장에서 53.2%→25.0%로 개선되어(최대 개선 69.9%p), 자동-수동 '
    '하이브리드 측정의 실용적 가능성을 시사하는 탐색적 결과를 얻었다 (장애물 Wilcoxon p=0.057).'
)
s1_elements.append(make_para(summary_kor, size=9, indent_mm=4, space_after=6))

# Keywords
p = make_para('Keywords: 부동산 매물 사진, 단안 깊이 추정, 카메라 캘리브레이션, 실내 거리 측정, '
              'GeoCalib, Depth Pro, RANSAC, 수동 보완 측정', size=9, space_after=12)
s1_elements.append(p)

# Abstract
s1_elements.append(make_heading('Abstract', size=11))
abstract_en = (
    "Real estate listing photos are typically captured with wide-angle lenses, making spaces appear larger "
    "than they are, and platforms strip EXIF metadata, preventing consumers from verifying indoor dimensions. "
    "We propose a framework that estimates focal length from a single indoor photo using GeoCalib, generates "
    "metric depth with Depth Pro, back-projects to 3D, and detects parallel wall pairs via RANSAC plane fitting "
    "to compute wall-to-wall distance. We quantitatively validate the framework on 81 apartment photos across "
    "five complexes. Of 79 valid measurements, 35.4% (28 photos) achieve relative error ≤10%; within 25 "
    "well-conditioned photos (30.9%), 76% achieve ≤10% error (median 5.3%, MAE 28.8 cm). About 69.8% of "
    "GeoCalib-estimated focal lengths fall below 500 px, indicating wide-angle capture; in this subset, the "
    "GeoCalib-based focal outperforms Depth Pro's own focal estimation by 3.44%p in paired error (p=0.026, "
    "Cohen's d=-0.35). For RANSAC-failure cases, interactive manual annotation reduces mean error from 23.5% "
    "to 19.2% on 17 paired obstacle cases (Wilcoxon p=0.057) and from 53.2% to 25.0% on 5 wrong-fit cases "
    "(up to 69.9%p improvement), suggesting a hybrid automatic-manual pathway for future work."
)
s1_elements.append(make_para(abstract_en, size=9, indent_mm=4, space_after=12))

insert_before(sec_break_para, *s1_elements)

# ============================================================
# SECTION 2 — body + references (2-column)
# After sec_break_para, before final sectPr
# ============================================================

# 마지막 sectPr 앞에 추가하기 위한 앵커: final_sectPr 자체 앞에 넣으면 된다
anchor = final_sectPr

s2_elements = []

# 1. 서론
s2_elements.append(make_heading('1. 서 론', size=12))
for t in [
    '부동산 매물 정보에서 전용면적은 공개되지만 개별 방의 가로·세로 치수는 제공되지 않는 경우가 많다. '
    '소비자가 공간 크기를 사전에 판단할 수 있는 거의 유일한 시각 정보는 매물 사진이나, 해당 사진은 대부분 '
    '광각 렌즈로 촬영되어 실제보다 공간이 넓어 보이는 왜곡을 발생시킨다. 주요 부동산 플랫폼은 이미지 '
    '업로드 시 EXIF 메타데이터를 삭제하므로 소비자는 촬영에 사용된 초점거리나 렌즈 종류를 확인할 수 없다. '
    '특히 원룸·오피스텔과 같은 소형 매물은 좁은 공간에서 광각 왜곡이 상대적으로 크게 체감되며, 평면도에도 '
    '개별 방의 세부 치수가 표기되지 않는 경우가 많아 문제가 더욱 심화된다.',
    '본 연구의 장기 목표는 원룸·오피스텔 등 치수 정보가 부재한 소형 매물 사진에서 실내 공간 거리를 '
    '추정하는 것이다. 그러나 소형 매물은 평면도 GT 확보가 어려워 정량 검증이 제한되므로, 본 논문에서는 '
    '평면도 치수를 확보할 수 있는 아파트 사진을 대상으로 파이프라인을 먼저 구축·검증한다.',
    '본 논문은 EXIF가 없는 단일 실내 사진에서 초점거리를 GeoCalib [1]으로 추정하고, Depth Pro [2]로 '
    'metric depth를 생성한 뒤, 3D 역투영과 RANSAC 평면 피팅을 통해 평행 벽 쌍을 자동 탐지하여 벽-벽 '
    '거리를 측정하는 프레임워크를 제안한다. 5개 단지 아파트 81장의 평면도 GT에 대해 정량 평가를 수행하고, '
    '조건별 오차 분포, 초점거리 추정 방식에 따른 성능 차이, 자동 실패 시 수동 보완 실험까지 분석한다.',
]:
    s2_elements.append(make_para(t, size=10, indent_mm=4, space_after=3))

s2_elements.append(make_para('본 논문의 주요 기여는 다음과 같다.', size=10))
for label, body_t in [
    ('(1) 프레임워크 제안', 'EXIF가 없는 부동산 매물 사진에서 GeoCalib · Depth Pro · RANSAC을 결합한 벽-벽 거리 측정 파이프라인을 제안한다.'),
    ('(2) 평면도 GT 기반 정량 검증', '아파트 5개 단지 81장에 대해 벽 중심선 치수를 GT로 삼아 정량 평가한다. 전체 유효 79장에서 35.4%가 10% 이하 오차를 달성하고, 양호 조건 25장에서는 중앙값 5.3%, 76%가 10% 이하 오차를 기록한다.'),
    ('(3) 광각 조건에서 GeoCalib focal의 통계적 우위', "Depth Pro 자체 focal 추정과의 paired 비교에서 광각(<500 px) 조건에 대해 paired t-test p=0.026, Cohen's d=-0.35로 GeoCalib 우위를 확인하고 효과 크기와 95% 신뢰구간을 함께 보고한다."),
    ('(4) 자동 실패 케이스 수동 보완 예비 실험', 'RANSAC이 실패하거나 큰 오차를 내는 케이스(장애물 paired 17장, 잘못된 피팅 5장)에 대해 사용자가 벽을 수동 지정하는 탐색적 실험을 수행하고, 최대 69.9%p의 개선 사례를 관찰한다(장애물 Wilcoxon p=0.057). 자동-수동 하이브리드 인터페이스 설계의 예비 근거로 제시한다.'),
]:
    text = f'• {label}: {body_t}'
    s2_elements.append(make_para(text, size=10, indent_mm=3, space_after=2))

# 2. 관련 연구
s2_elements.append(make_heading('2. 관련 연구', size=12))
s2_elements.append(make_heading('2.1 단일 이미지 카메라 캘리브레이션', size=10))
s2_elements.append(make_para(
    '전통적 카메라 캘리브레이션은 Zhang의 방법 [9]과 같이 체커보드 등 보정 패턴을 사용하는 다중 이미지 '
    '기법에 기반하였다. 최근 딥러닝 기반 접근이 이를 대체하고 있으며, 특히 Perspective Fields [6]는 '
    '단일 이미지에서 소실점과 수직 방향을 동시에 추정하는 표현을 제안하였다. GeoCalib [1]은 이 계보를 '
    '확장하여 기하학적 최적화와 신경망 추정을 결합함으로써 단일 이미지로부터 초점거리·롤·피치·방사 왜곡을 '
    '안정적으로 추정한다.', size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('2.2 단안 metric depth 추정', size=10))
s2_elements.append(make_para(
    '단안 깊이 추정은 ZoeDepth, Depth Anything V2 [5]를 거쳐 최근 metric 스케일의 절대 깊이까지 '
    '추정하는 방향으로 발전하였다. Metric3D v2 [3]와 UniDepth [4]는 카메라 내부 파라미터를 입력으로 '
    '활용하거나 내재적으로 추정하여 단일 이미지에서 metric depth를 예측한다. Depth Pro [2]는 카메라 '
    '내부 파라미터 없이도 3초 이내에 고해상도 metric depth를 생성할 수 있어 사후 촬영된 인-더-와일드 '
    '이미지에 적합하다.', size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('2.3 실내 공간과 부동산 사진 응용', size=10))
s2_elements.append(make_para(
    'Rent3D [7]는 부동산 광고 사진과 2D 평면도를 결합한 단안 레이아웃 추정 연구이며, Zillow Indoor '
    'Dataset [8]은 평면도와 360° 파노라마를 포함한 대규모 데이터셋을 제공한다. 국내에서는 권혁찬 등 [10]이 '
    'GeoCalib을 부동산 매물 사진에 적용하여 왜곡 여부 판별 웹 서비스(Propix)를 설계·구현한 바 있다. 다만 '
    '해당 연구는 왜곡 유무 판별에 초점이 있으며, 실제 물리 치수의 정량 측정은 다루지 않는다. 본 연구는 '
    'GeoCalib으로 초점거리·기울기를 보정한 뒤 Depth Pro 기반 단안 metric depth와 결합하여 mm 단위 '
    '거리 측정을 수행한다는 점에서 차별화된다.', size=10, indent_mm=4, space_after=3))

# 3. 제안 프레임워크
s2_elements.append(make_heading('3. 제안 프레임워크', size=12))
s2_elements.append(make_para(
    '전체 파이프라인은 6단계로 구성되며, 자동 RANSAC 실패 시 사용자 수동 보완 경로를 선택적으로 활용한다.',
    size=10, indent_mm=4, space_after=3))
for h, t in [
    ('3.1 초점거리 및 기하 보정 (GeoCalib)',
     '입력 사진 I를 GeoCalib [1]에 입력하여 초점거리 f̂ (픽셀), 롤·피치, 방사 왜곡 계수를 추정한다. '
     'Perspective Field 기반 신경망 예측과 Levenberg-Marquardt 최적화를 결합하여 단일 이미지로 '
     '캘리브레이션을 수행한다.'),
    ('3.2 Metric depth 추정 (Depth Pro)',
     '추정된 f̂를 Depth Pro [2]에 입력하여 입력 이미지와 동일 해상도의 metric depth map D ∈ ℝ^{H×W}를 얻는다. '
     'Depth Pro는 f̂를 canonical inverse depth의 최종 스케일링에만 사용한다.'),
    ('3.3 3D 역투영',
     '핀홀 모델에 따라 각 픽셀 (u,v)의 3D 좌표를 X=(u-c_x)·Z/f̂, Y=(v-c_y)·Z/f̂, Z=D(u,v) 로 복원한다. '
     '(c_x, c_y)는 이미지 중심이며, 유효 범위는 0.5 m < Z < 10 m로 제한한다.'),
    ('3.4 RANSAC 평면 피팅 및 평행 벽 쌍 탐지',
     '3D 점군에 대해 RANSAC을 반복하여 최대 6개의 평면을 순차 추출한다 (거리 임계 τ=5 cm, iteration n=1000). '
     '각 평면의 법선 n에 대해 |n_y| ≤ 0.7인 평면만 벽 후보로 보존한다. 벽 후보 쌍 (i, j) 중 |n_i · n_j| > 0.8인 '
     '평행 쌍을 찾고, inlier 개수 합이 최대인 쌍을 최종 선택한다. 본 임계값은 Depth Pro의 per-pixel noise '
     '허용을 위한 관대한 설정이며, 엄격한 임계에 대한 ablation은 향후 과제이다.'),
    ('3.5 벽-벽 거리 계산',
     '선택된 두 평면의 평면 방정식 n_i·p+d_i=0, n_j·p+d_j=0으로부터 법선 부호를 통일한 뒤 수직 거리 '
     'dist = |d_i ± d_j|를 계산한다.'),
    ('3.6 실패 케이스 수동 보완 경로',
     '자동 RANSAC이 벽을 잡지 못하거나(status=ransac_fail) 잘못 피팅하는 경우, 사용자가 원본 이미지 '
     '위에서 두 벽의 패치(40×40 px)를 클릭하면 해당 영역의 depth 중앙값을 기반으로 두 평면의 깊이 차를 '
     '직접 산출한다. 4.7절에서 본 보완 경로의 정량 효과를 보고한다.'),
]:
    s2_elements.append(make_heading(h, size=10))
    s2_elements.append(make_para(t, size=10, indent_mm=4, space_after=3))

# 4. 실험 및 결과
# Figure 2 caption (placeholder — image will be inserted before this)
s2_elements.append(make_para('그림 2. 3D 시각화: 벽-벽 거리 측정 (ID 029 거실, GT 4,340 mm, 측정 4,355 mm, 오차 0.35%).',
                              size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6))

s2_elements.append(make_heading('4. 실험 및 결과', size=12))
s2_elements.append(make_heading('4.1 데이터셋 및 GT 구성', size=10))
s2_elements.append(make_para(
    '올림픽파크포레온, 개포자이프레지던스, 래미안원베일리, 헬리오시티, 마포래미안푸르지오의 5개 단지에서 '
    '총 81장의 실내 매물 사진을 수집하였다. GT는 네이버 부동산 평면도의 벽 중심선 치수에서 벽 두께 '
    '160 mm를 차감한 값을 마감면 간 거리로 사용하였다(단지별 벽 두께 편차 ±40 mm로 GT 자체에 약 '
    '1~2%의 내재 불확실성 존재). 81장 중 RANSAC이 완전 실패한 2장(ID 018, 034)을 제외한 79장을 '
    '분석 대상으로 한다.',
    size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('4.2 광각 환경 검증', size=10))
s2_elements.append(make_para(
    'GeoCalib 추정 초점거리 분포(N=63) 결과, 평균 490 px, 중앙값 446 px이며 69.8%(44/63)가 500 px '
    '미만이었다(그림 3). 이는 수집된 부동산 매물 사진 다수가 광각 렌즈로 촬영되었을 가능성을 정량적으로 '
    '시사한다. EXIF 부재로 실제 렌즈 종류는 직접 확인할 수 없으며, 본 값은 GeoCalib 추정치임을 명시한다. '
    '해당 63장 중 4.4절 paired 비교에는 Depth Pro 자체 focal 추정이 성공한 61장(광각 43, 일반 18)을 사용한다.',
    size=10, indent_mm=4, space_after=3))
s2_elements.append(make_para('그림 3. GeoCalib 추정 초점거리 분포 (N=63). 69.8%가 500 px 미만.',
                              size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6))

s2_elements.append(make_heading('4.3 조건별 측정 오차', size=10))
s2_elements.append(make_para('표 1. 조건별 측정 오차 통계.', size=9, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2))
s2_elements.append(make_table(
    headers=['조건', 'N', 'MAE(mm)', 'RMSE(mm)', 'MAPE(%)', 'Med(%)', '≤10%'],
    rows=[
        ['전체 유효 (ALL)',   '79', '858', '1371', '24.0', '16.2', '35.4%'],
        ['final_clean (양호)', '25', '288', '390',  '7.0',  '5.3',  '76%'],
        ['both_clear',        '49', '504', '764',  '14.8', '11.3', '49%'],
        ['one_unclear',       '30', '1436','1999', '39.1', '28.5', '13%'],
        ['obstacle=yes',      '20', '818', '980',  '23.7', '22.5', '15%'],
    ],
    col_widths_mm=[22, 8, 12, 12, 11, 11, 10],
))
s2_elements.append(make_para(
    '양호 조건(final_clean)은 `wall_visible=both_clear`, `obstacle=none`, 발코니 유리문 없음을 모두 '
    '만족하는 25장(전체의 30.9%)이다. 조건 subset은 상호 배타적이지 않다. 전체 유효 79장 중 35.4%가 '
    '10% 이하 오차를 달성하였으며, 양호 조건 선별 시 76%로 상승하나 선별 비율 자체가 30.9%에 불과하므로 '
    '일반 매물 사진 전반에 적용할 경우 실용 성공률은 35%대로 추정된다.',
    size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('4.4 초점거리 추정 방식 비교', size=10))
s2_elements.append(make_para('표 2. GeoCalib focal (A) vs Depth Pro 자체 focal (B) paired 비교.',
                              size=9, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2))
s2_elements.append(make_table(
    headers=['그룹', 'N', 'A MAPE', 'B MAPE', 'Δ(%p)', '95% CI', 'p', 'd'],
    rows=[
        ['전체',         '61', '24.75%', '25.55%', '-0.80', '[-4.52,+2.92]', '0.669', '-0.055'],
        ['광각<500px',   '43', '25.08%', '28.52%', '-3.44', '[-6.44,-0.43]', '0.026', '-0.352'],
        ['일반≥500px',   '18', '23.96%', '18.47%', '+5.51', '[-5.06,+16.07]','0.287', '+0.259'],
    ],
    col_widths_mm=[14, 7, 11, 11, 9, 18, 8, 9],
))
s2_elements.append(make_para(
    "광각 subset에서 GeoCalib focal이 3.44%p 낮은 오차(paired t-test p=0.026, Cohen's d=-0.35, "
    '95% CI [-6.44, -0.43]%p)를 기록하였다. 세 그룹에 Bonferroni 보정 적용 시 α=0.0167로 원 p=0.026 > '
    '보정 α=0.0167이므로 엄격히는 유의하지 않다는 점을 투명히 명시한다. 다만 광각 그룹을 사전 설정된 '
    '주 관심 그룹으로 한 단일 검정 관점에서는 p=0.026이 유의수준을 만족한다. 일반 화각에서는 두 방식 간 '
    '유의한 차이가 없었다.', size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('4.5 Barrel Distortion 보정 효과', size=10))
s2_elements.append(make_para(
    'GeoCalib 제공 왜곡 보정을 적용한 경우와 원본 사이 거리 비율 ER = D_원본/D_보정을 분석하였다. '
    '측정값이 생성된 61장 중 Tukey IQR × 1.5 기준 이상치 8건(예: ID 012 ER=91.73, ID 014 ER=2.91 등)을 '
    '제외한 N=53장에 대해, 평균 ER=0.9956, 중앙값 0.9983, 95% CI [0.9919, 0.9992]이며 H_0:ER=1.0 '
    '일표본 t-test 결과 p=0.017이다. 평균 편차는 약 0.4%로 GT 벽 두께 불확실성(1~2%)보다 작아 '
    'Depth Pro 기반 파이프라인에서 barrel distortion 보정의 영향은 통계적으로는 검출되나 실용적 의미는 '
    '미미함을 확인하였다.', size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('4.6 실패 모드 분석', size=10))
s2_elements.append(make_para(
    '자동 RANSAC의 주요 실패 모드는 (1) 장애물(붙박이장·가구·주방 아일랜드가 벽 평면을 대체), '
    '(2) 발코니 유리문(유리 너머 depth 누락), (3) 한쪽 벽 미보임(수평 점군 불충분)의 세 가지이다.',
    size=10, indent_mm=4, space_after=3))

s2_elements.append(make_heading('4.7 실패 케이스 수동 보완 측정', size=10))
s2_elements.append(make_para(
    '자동 RANSAC의 한계를 정량적으로 검증하고 보완 가능성을 확인하기 위해, 장애물 및 잘못 피팅 케이스에 '
    '대해 사용자가 두 벽의 패치(40×40 px)를 클릭하면 해당 영역 depth 중앙값으로 거리를 산출하는 수동 '
    '보완 실험을 수행하였다.', size=10, indent_mm=4, space_after=3))
s2_elements.append(make_para('표 3. 자동 RANSAC vs 수동 클릭 기반 측정 비교.',
                              size=9, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2))
s2_elements.append(make_table(
    headers=['Subset', 'N', '자동 MAPE', '수동 MAPE', '평균 개선', 'Wilcoxon p', '개선 비율'],
    rows=[
        ['장애물 있음 (paired)', '17', '23.48%', '19.22%', '-4.26%p',  '0.057', '13/17 (76%)'],
        ['RANSAC 잘못 피팅',    '5',  '53.18%', '25.02%', '-28.16%p', '0.188', '4/5 (80%)'],
    ],
    col_widths_mm=[22, 6, 12, 12, 12, 11, 15],
))
s2_elements.append(make_para('그림 4. 자동 RANSAC vs 수동 클릭 측정 paired 비교. 최대 69.9%p 개선.',
                              size=9, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6))
s2_elements.append(make_para(
    '개별 극단 개선 사례: ID 014 (좌측 창문·좁은 방) 96.9%→27.0% (-69.9%p), ID 051 (코너·주방 가림) '
    '71.3%→5.2% (-66.1%p), ID 060 (식탁·의자 중앙 가림) 65.1%→1.4% (-63.7%p). 본 실험은 자동 '
    'RANSAC 실패가 본질적 한계가 아니라 벽 영역 분할의 불확실성에서 기인함을 시사한다. 단, 장애물 '
    'Wilcoxon 검정 p=0.057로 유의성 경계에 있으며 일부 케이스(ID 040, 004)에서는 수동이 오차를 '
    '악화시켰다(수동 클릭의 사용자 의존성 존재).',
    size=10, indent_mm=4, space_after=6))

# 5. 결론
s2_elements.append(make_heading('5. 결론 및 한계', size=12))
s2_elements.append(make_para(
    '본 논문은 EXIF가 없는 부동산 매물 사진에서 GeoCalib + Depth Pro + RANSAC을 결합한 실내 벽-벽 '
    '거리 측정 프레임워크를 제안하고, 5개 단지 아파트 81장 평면도 GT에 대해 정량 검증하였다. 전체 '
    '유효 79장에서 35.4%가 10% 이하 오차를, 양호 조건 25장에서는 76%(중앙값 5.3%)를 기록하였다. '
    "광각 조건에서 GeoCalib focal의 통계적 우위(p=0.026, Cohen's d=-0.35)와 barrel distortion 보정의 "
    '실용적 무의미성, 그리고 자동 실패 케이스에 대한 수동 보완 예비 실험에서 최대 69.9%p 개선을 '
    '관찰하여(장애물 Wilcoxon p=0.057) 향후 자동-수동 하이브리드 인터페이스 설계를 위한 탐색적 근거를 '
    '제시하였다.', size=10, indent_mm=4, space_after=3))

s2_elements.append(make_para('한계', size=10, bold=True))
for l in [
    '실용 성공률이 전체 유효 79장 기준 35.4%로, 양호 조건 선별 시의 76%가 일반 매물 사진 전반에 '
    '그대로 적용되지 않는다.',
    '단일 depth 모델(Depth Pro)만 검증되었으며 교차 모델 비교가 부재하다.',
    'RANSAC 파라미터(|n_y|≤0.7, |dot|>0.8, τ=5 cm)가 건축 기준 대비 관대하며 ablation이 수행되지 않았다.',
    'GT 벽 두께 보정(-160 mm)이 단지별 편차(±40 mm)를 일괄 흡수한다.',
    '수동 보완 실험은 단일 사용자 기준이며 사용자 간 재현성 검증이 추가로 필요하다.',
]:
    s2_elements.append(make_para('• ' + l, size=10, indent_mm=5, space_after=2))

s2_elements.append(make_para('향후 연구', size=10, bold=True))
for l in [
    '(i) 최종 응용 대상인 원룸·오피스텔 소형 매물에 대한 GT 확보 방법론 확립과 검증.',
    '(ii) Metric3D v2, UniDepth 등 대안 단안 depth 모델과의 교차 검증.',
    '(iii) 4.7절 결과를 근거로 한 자동 실패 탐지 + 사용자 개입 하이브리드 인터페이스 설계.',
    '(iv) RANSAC 파라미터 ablation 및 robust variants (MLESAC, LO-RANSAC) 비교.',
]:
    s2_elements.append(make_para('• ' + l, size=10, indent_mm=5, space_after=2))

# 참고문헌
s2_elements.append(make_heading('참고 문헌', size=11))
refs = [
    '[1] A. Veicht, P.-E. Sarlin, P. Lindenberger, M. Pollefeys, "GeoCalib: Learning Single-image Calibration with Geometric Optimization," ECCV 2024.',
    '[2] A. Bochkovskii et al., "Depth Pro: Sharp Monocular Metric Depth in Less Than a Second," ICLR 2025.',
    '[3] M. Hu et al., "Metric3D v2," TPAMI 2024.',
    '[4] L. Piccinelli et al., "UniDepth: Universal Monocular Metric Depth Estimation," CVPR 2024.',
    '[5] L. Yang et al., "Depth Anything V2," NeurIPS 2024.',
    '[6] L. Jin et al., "Perspective Fields for Single Image Camera Calibration," CVPR 2023, pp. 17307-17316.',
    '[7] C. Liu et al., "Rent3D: Floor-Plan Priors for Monocular Layout Estimation," CVPR 2015, pp. 3413-3421.',
    '[8] S. Cruz et al., "Zillow Indoor Dataset," CVPR 2021.',
    '[9] Z. Zhang, "A Flexible New Technique for Camera Calibration," IEEE PAMI, vol. 22, no. 11, pp. 1330-1334, 2000.',
    '[10] 권혁찬 외, "인공지능을 활용한 부동산 왜곡 이미지 탐지 및 보정 서비스 설계 및 구현," 한국정보기술학회 추계학술대회 논문집, pp. 898-902, 2024.',
]
for ref in refs:
    s2_elements.append(make_para(ref, size=8, indent_mm=3, space_after=1))

# Insert all section 2 elements before final sectPr
insert_before(final_sectPr, *s2_elements)

# Save + embed images
doc.save(DST)
print(f'Saved text-only draft: {DST}')

# Now re-open and embed pictures at placeholder locations
doc2 = Document(DST)
# We need to add figures. Simplest: append at specific paragraphs by iterating and matching caption text
# But since we don't have placeholders, let's just skip images in this section-aware build
# And do a SECOND pass that uses doc.paragraphs to add images AFTER specific captions.
# For simplicity: find paragraphs containing "그림 2", "그림 3", "그림 4" and insert picture BEFORE them.

figs = [('그림 2.', fig2_path), ('그림 3.', FIG3), ('그림 4.', FIG4)]
for caption_start, img_path in figs:
    if not os.path.exists(img_path):
        print(f'MISSING: {img_path}')
        continue
    # Find any paragraph mentioning the caption
    found = False
    for p in doc2.paragraphs:
        if p.text.strip().startswith(caption_start):
            # Insert image BEFORE this caption paragraph
            new_p = p.insert_paragraph_before()
            new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            new_p.add_run().add_picture(img_path, width=Mm(85))
            found = True
            break
    if not found:
        # fallback: add a new paragraph+image+caption block at end (before refs ideally)
        print(f'No placeholder found for {caption_start}; will not embed.')

# Also add figure captions where they don't exist yet
# Actually we have them embedded within the section 2 elements - wait no we don't.
# Let me add them at appropriate spots via a post-processing

# Save
doc2.save(DST)
print(f'Final saved: {DST}  size={os.path.getsize(DST):,} bytes')
