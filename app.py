import streamlit as st
import openai
import json
from docx import Document
from docx.shared import Pt, Inches
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Ellipse
import math
import re
import fitz
from PIL import Image
import base64
from datetime import datetime

st.set_page_config(page_title="AI智能出卷助手", page_icon="📝", layout="wide")

# 初始化session_state
if "paper_json" not in st.session_state:
    st.session_state.paper_json = None
if "analyzed_style" not in st.session_state:
    st.session_state.analyzed_style = None
if "syllabus_units" not in st.session_state:
    st.session_state.syllabus_units = []
if "syllabus_content" not in st.session_state:
    st.session_state.syllabus_content = ""
if "today_calls" not in st.session_state:
    st.session_state.today_calls = 0
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = datetime.now().strftime("%Y-%m-%d")

st.title("📝 AI 智能出卷助手")
st.caption("上传参考试卷和教学计划，AI学习风格后自动生成指定单元范围的试卷")


def track_api_call():
    """记录API调用次数，每天自动重置"""
    today = datetime.now().strftime("%Y-%m-%d")
    if st.session_state.last_reset_date != today:
        st.session_state.last_reset_date = today
        st.session_state.today_calls = 0
    st.session_state.today_calls += 1


def get_remaining_calls():
    """获取剩余调用次数"""
    today = datetime.now().strftime("%Y-%m-%d")
    if st.session_state.last_reset_date != today:
        st.session_state.last_reset_date = today
        st.session_state.today_calls = 0
    return 50 - st.session_state.today_calls


# 侧边栏
with st.sidebar:
    st.header("🔐 配置")
    
    if "GITHUB_TOKEN" in st.secrets:
        api_key = st.secrets["GITHUB_TOKEN"]
        openai.api_key = api_key
        openai.base_url = "https://models.inference.ai.azure.com"
        st.success("✅ GitHub Models API已配置")
        
        st.divider()
        st.header("📊 额度")
        
        remaining = get_remaining_calls()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("今日已用", f"{st.session_state.today_calls} 次")
        with col2:
            st.metric("剩余", f"{remaining} 次")
        st.progress(min(st.session_state.today_calls / 50, 1.0))
        
        if remaining < 10:
            st.warning(f"⚠️ 剩余次数不足 {remaining} 次")
    else:
        st.warning("⚠️ 请在Streamlit Secrets中设置 GITHUB_TOKEN")
        api_key = None
    
    st.divider()
    st.header("🎨 图片设置")
    auto_draw = st.checkbox("自动生成图形", value=True)
    st.info("复杂场景图片会生成【图X：描述】占位符")

# 主界面 - 三个标签页
tab1, tab2, tab3 = st.tabs(["📚 上传资料", "🎯 出卷设置", "📄 生成试卷"])

with tab1:
    st.subheader("📖 上传参考试卷")
    
    reference_papers = st.file_uploader(
        "上传之前的试卷（支持Word和PDF）",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        help="上传2-3份，AI会学习题型、分值、语言风格"
    )
    
    st.subheader("📅 上传全年教学计划")
    syllabus_file = st.file_uploader(
        "上传教学计划（Word格式）",
        type=["docx"],
        help="AI会根据教学计划判断每个单元学什么"
    )
    
    if syllabus_file and st.button("📖 解析教学计划，提取单元列表"):
        if not api_key:
            st.error("请先配置 API Key")
        else:
            with st.spinner("正在解析教学计划..."):
                syllabus_content = read_docx_content(syllabus_file)
                st.session_state.syllabus_content = syllabus_content
                
                track_api_call()
                units = extract_units_from_syllabus(syllabus_content, api_key)
                st.session_state.syllabus_units = units
                
                st.success(f"成功提取 {len(units)} 个单元")
                with st.expander("查看单元列表"):
                    for i, unit in enumerate(units, 1):
                        st.write(f"{i}. {unit}")
    
    if reference_papers:
        st.success(f"已上传 {len(reference_papers)} 份参考试卷")

with tab2:
    st.subheader("🎯 出卷参数")
    
    col1, col2 = st.columns(2)
    with col1:
        grade_level = st.selectbox(
            "年级",
            ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]
        )
        subject = st.selectbox("科目", ["华文", "数学", "健康教育"])
    
    with col2:
        paper_type = st.selectbox("试卷类型", ["单元测验", "期中考试", "期末考试", "模拟练习"])
        difficulty = st.select_slider("难度", ["简单", "中等偏易", "中等", "中等偏难", "难"], value="中等")
    
    st.subheader("📚 出题范围（基于教学计划）")
    
    if st.session_state.syllabus_units:
        st.write("请勾选要出题的单元：")
        
        col_all1, col_all2 = st.columns(2)
        with col_all1:
            if st.button("✅ 全选"):
                for unit in st.session_state.syllabus_units:
                    st.session_state[f"unit_selected_{unit}"] = True
        with col_all2:
            if st.button("❌ 清空"):
                for unit in st.session_state.syllabus_units:
                    st.session_state[f"unit_selected_{unit}"] = False
        
        selected_units = []
        for unit in st.session_state.syllabus_units:
            key = f"unit_selected_{unit}"
            if key not in st.session_state:
                st.session_state[key] = True
            if st.checkbox(unit, key=key):
                selected_units.append(unit)
        
        st.session_state.selected_units = selected_units
        
        if selected_units:
            st.success(f"已选择 {len(selected_units)} 个单元")
        else:
            st.warning("请至少选择一个单元")
    else:
        st.info("请先在「上传资料」标签页上传教学计划并点击「解析教学计划」")
        st.session_state.selected_units = []
    
    st.subheader("📋 额外要求")
    extra_requirements = st.text_area(
        "特殊要求",
        placeholder="例如：多出应用题、重点考察计算能力、多出看图写话题...",
        height=100
    )
    
    if reference_papers and st.button("🔍 分析试卷风格", type="secondary"):
        if not api_key:
            st.error("请先配置 API Key")
        elif get_remaining_calls() <= 0:
            st.error("❌ 今日额度已用完，请明天再试")
        else:
            with st.spinner("AI正在分析试卷风格..."):
                track_api_call()
                style_analysis = analyze_paper_style(reference_papers, api_key)
                st.session_state.analyzed_style = style_analysis
                st.success("风格分析完成！")
                with st.expander("查看分析结果"):
                    st.json(style_analysis)

with tab3:
    if not st.session_state.analyzed_style:
        st.info("请先在「上传资料」标签页上传参考试卷，并点击「分析试卷风格」")
    elif not st.session_state.selected_units:
        st.info("请先在「出卷设置」标签页选择出题单元范围")
    else:
        st.subheader("🚀 生成新试卷")
        st.write(f"**出题范围：** {', '.join(st.session_state.selected_units)}")
        st.write(f"**学习风格来源：** {len(reference_papers) if reference_papers else 0} 份参考试卷")
        
        if st.button("📝 生成试卷", type="primary", use_container_width=True):
            if get_remaining_calls() <= 0:
                st.error("❌ 今日额度已用完，请明天再试")
            elif not reference_papers:
                st.error("请先上传参考试卷")
            else:
                with st.spinner("AI正在生成试卷..."):
                    track_api_call()
                    paper = generate_paper(
                        style=st.session_state.analyzed_style,
                        grade=grade_level,
                        subject=subject,
                        paper_type=paper_type,
                        difficulty=difficulty,
                        extra_requirements=extra_requirements,
                        syllabus_content=st.session_state.syllabus_content,
                        selected_units=st.session_state.selected_units,
                        api_key=api_key,
                        auto_draw=auto_draw
                    )
                    st.session_state.paper_json = paper
                    st.success("试卷生成成功！")
    
    if st.session_state.paper_json:
        st.divider()
        st.subheader("📄 试卷预览")
        
        paper = st.session_state.paper_json
        
        if "error" in paper:
            st.error(f"生成失败：{paper['error']}")
        else:
            st.markdown(f"### {paper.get('title', '试卷')}")
            st.markdown(f"**总分：{paper.get('total_score', 100)}分**")
            st.markdown("---")
            
            for section in paper.get('sections', []):
                st.markdown(f"#### {section.get('type', '')}（每题{section.get('score_per_question', 0)}分）")
                for q in section.get('questions', []):
                    st.markdown(f"**{q.get('number', '')}.** {q.get('text', '')}")
                    if q.get('image_marker'):
                        st.info(f"🖼️ {q['image_marker']}")
                    if 'options' in q and q['options']:
                        for opt in q['options']:
                            st.markdown(f"&nbsp;&nbsp;&nbsp;{opt}")
                    st.markdown("")
                st.markdown("---")
            
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                if st.button("📥 下载学生卷"):
                    doc_buffer = create_word_document(
                        st.session_state.paper_json, 
                        with_answers=False,
                        auto_draw=auto_draw
                    )
                    st.download_button(
                        label="点击下载",
                        data=doc_buffer,
                        file_name=f"{grade_level}{subject}{paper_type}_学生卷.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_student"
                    )
            with col_dl2:
                if st.button("📥 下载教师卷（含答案）"):
                    doc_buffer = create_word_document(
                        st.session_state.paper_json, 
                        with_answers=True,
                        auto_draw=auto_draw
                    )
                    st.download_button(
                        label="点击下载",
                        data=doc_buffer,
                        file_name=f"{grade_level}{subject}{paper_type}_教师卷.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="download_teacher"
                    )


# ========== 函数定义 ==========

def read_docx_content(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text


def read_pdf_content(file):
    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except:
        try:
            from PyPDF2 import PdfReader
            file.seek(0)
            pdf_reader = PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except:
            pass
    return text


def extract_units_from_syllabus(syllabus_content, api_key):
    prompt = f"""
请从以下教学计划中提取所有的单元/章节名称。

教学计划内容：
{syllabus_content[:3000]}

请以JSON数组格式输出，例如：
["第1单元：认识数字", "第2单元：加减法", "第3单元：图形与几何"]

只输出JSON数组，不要其他内容。
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是教学计划分析专家，只输出JSON数组。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        units = json.loads(response.choices[0].message.content)
        return units if isinstance(units, list) else []
    except Exception as e:
        return ["第1单元", "第2单元", "第3单元", "第4单元", "第5单元", "第6单元"]


def analyze_paper_style(reference_files, api_key):
    papers_content = []
    for file in reference_files:
        if file.name.endswith('.pdf'):
            content = read_pdf_content(file)
        else:
            file.seek(0)
            content = read_docx_content(file)
        papers_content.append(content[:3000])
    
    combined = "\n---\n".join(papers_content)
    
    prompt = f"""
请分析以下参考试卷的风格特点，输出JSON格式。

参考试卷内容：
{combined}

请分析并输出：
{{
    "paper_structure": {{
        "total_score": 总分值,
        "section_types": ["题型1", "题型2"]
    }},
    "question_style": {{
        "language_style": "语言风格描述",
        "difficulty_distribution": "简单:中等:难的比例"
    }},
    "scoring_pattern": {{
        "choice_score": 每题分值,
        "fill_score": 每题分值,
        "essay_score": 每题分值
    }},
    "typical_topics": ["常见知识点1", "知识点2"]
}}

只输出JSON，不要其他内容。
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是试卷分析专家，只输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}


def generate_paper(style, grade, subject, paper_type, difficulty, extra_requirements, 
                   syllabus_content, selected_units, api_key, auto_draw=True):
    if not api_key:
        return {"error": "API Key未配置"}
    
    style_str = json.dumps(style, ensure_ascii=False)
    units_str = "、".join(selected_units)
    
    unit_content = f"\n【出题范围】请只从以下单元出题：{units_str}\n"
    if syllabus_content:
        unit_content += f"\n【教学计划参考】{syllabus_content[:2000]}\n"
    
    image_instruction = """
【图片处理规则】
1. 几何图形题 → 添加【自动绘图：图形描述】
2. 复杂场景题 → 添加【图X：详细场景描述】
3. 图片标记从【图1】开始递增
"""
    
    prompt = f"""
你是一位经验丰富的小学{subject}教师，请根据以下要求生成一份完整试卷。

【年级】{grade}
【科目】{subject}
【试卷类型】{paper_type}
【难度】{difficulty}

【学习到的试卷风格】
{style_str}

{unit_content}

【额外要求】
{extra_requirements if extra_requirements else "无"}

{image_instruction if auto_draw else ""}

**重要：题目必须只覆盖以下单元：{units_str}。不要出这些单元以外的内容。**

请生成一份完整试卷，保持与参考试卷相似的风格和格式，但题目内容必须完全不同。

输出JSON格式：
{{
    "title": "试卷标题",
    "total_score": 总分,
    "sections": [
        {{
            "type": "选择题",
            "score_per_question": 每题分值,
            "questions": [
                {{
                    "number": 1,
                    "text": "题干",
                    "image_marker": "",
                    "image_type": "",
                    "image_description": "",
                    "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
                    "answer": "A",
                    "explanation": "答案解析"
                }}
            ]
        }},
        {{
            "type": "填空题",
            "score_per_question": 每题分值,
            "questions": [
                {{
                    "number": 1,
                    "text": "题干",
                    "image_marker": "",
                    "image_type": "",
                    "image_description": "",
                    "answer": "答案",
                    "explanation": "答案解析"
                }}
            ]
        }},
        {{
            "type": "简答题",
            "score_per_question": 每题分值,
            "questions": [
                {{
                    "number": 1,
                    "text": "题干",
                    "image_marker": "",
                    "image_type": "",
                    "image_description": "",
                    "answer": "参考答案",
                    "explanation": "评分要点"
                }}
            ]
        }}
    ]
}}

只输出JSON，不要其他内容。
"""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "你是小学试卷出题专家，只输出JSON。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}


def draw_geometry(description):
    description = description.lower()
    
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.set_aspect('equal')
    ax.axis('off')
    
    if '长方形' in description or '矩形' in description:
        numbers = re.findall(r'\d+', description)
        length, width = (int(numbers[0]), int(numbers[1])) if len(numbers) >= 2 else (8, 4)
        rect = patches.Rectangle((1, 2), length, width, linewidth=2, edgecolor='black', facecolor='lightblue', alpha=0.7)
        ax.add_patch(rect)
        ax.set_xlim(0, length + 2)
        ax.set_ylim(0, width + 3)
        ax.annotate(f'{length}cm', xy=(1 + length/2, 1.5), ha='center')
        ax.annotate(f'{width}cm', xy=(0.5, 2 + width/2), va='center', rotation=90)
    
    elif '正方形' in description:
        numbers = re.findall(r'\d+', description)
        side = int(numbers[0]) if numbers else 5
        square = patches.Rectangle((2.5, 1.5), side, side, linewidth=2, edgecolor='black', facecolor='lightgreen', alpha=0.7)
        ax.add_patch(square)
        ax.annotate(f'{side}cm', xy=(2.5 + side/2, 1), ha='center')
    
    elif '三角形' in description:
        triangle = patches.Polygon([[3, 1], [7, 1], [5, 5]], linewidth=2, edgecolor='black', facecolor='lightcoral', alpha=0.7)
        ax.add_patch(triangle)
    
    elif '圆' in description or '圆形' in description:
        numbers = re.findall(r'\d+', description)
        radius = int(numbers[0]) / 2 if numbers else 2
        circle = patches.Circle((5, 4), radius, linewidth=2, edgecolor='black', facecolor='lightyellow', alpha=0.7)
        ax.add_patch(circle)
        ax.annotate(f'半径{radius}cm', xy=(5, 4 - radius - 0.3), ha='center')
    
    elif '云' in description:
        for pos in [(3,4,1.2), (4.5,4.5,1.5), (6,4,1.2), (4,3,1)]:
            circle = patches.Circle((pos[0], pos[1]), pos[2], edgecolor='black', facecolor='white', linewidth=1.5)
            ax.add_patch(circle)
    
    elif '太阳' in description:
        sun = patches.Circle((5, 5), 1.5, edgecolor='orange', facecolor='yellow', linewidth=2)
        ax.add_patch(sun)
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            ax.plot([5 + 1.5*math.cos(rad), 5 + 2.2*math.cos(rad)], 
                   [5 + 1.5*math.sin(rad), 5 + 2.2*math.sin(rad)], color='orange', linewidth=2)
    
    elif '树' in description:
        trunk = patches.Rectangle((4.5, 2), 1, 2, edgecolor='brown', facecolor='saddlebrown')
        crown = patches.Polygon([[3, 4], [7, 4], [5, 7]], edgecolor='green', facecolor='forestgreen', alpha=0.8)
        ax.add_patch(trunk)
        ax.add_patch(crown)
    
    elif '房子' in description:
        house = patches.Rectangle((3, 2), 4, 3, edgecolor='black', facecolor='lightyellow')
        roof = patches.Polygon([[2.5, 5], [7.5, 5], [5, 7]], edgecolor='brown', facecolor='lightcoral')
        door = patches.Rectangle((4.5, 2), 1, 1.5, edgecolor='black', facecolor='brown')
        window = patches.Circle((5.5, 3.5), 0.4, edgecolor='black', facecolor='lightblue')
        ax.add_patch(house)
        ax.add_patch(roof)
        ax.add_patch(door)
        ax.add_patch(window)
    
    elif '鱼' in description:
        body = Ellipse((5, 4), 3, 1.5, edgecolor='black', facecolor='orange', alpha=0.8)
        tail = patches.Polygon([[3.5, 4], [2, 3.5], [2, 4.5]], edgecolor='black', facecolor='orange')
        eye = patches.Circle((4, 4.2), 0.15, facecolor='black')
        ax.add_patch(body)
        ax.add_patch(tail)
        ax.add_patch(eye)
    
    elif '花' in description:
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            petal = patches.Circle((5 + 0.8*math.cos(rad), 4 + 0.8*math.sin(rad)), 0.4, 
                                   edgecolor='pink', facecolor='pink', alpha=0.7)
            ax.add_patch(petal)
        center = patches.Circle((5, 4), 0.3, edgecolor='brown', facecolor='yellow')
        stem = patches.Rectangle((4.8, 2), 0.4, 2, edgecolor='green', facecolor='green')
        ax.add_patch(center)
        ax.add_patch(stem)
    
    elif '苹果' in description:
        apple = patches.Circle((5, 4), 1.2, edgecolor='red', facecolor='red', alpha=0.7)
        leaf = patches.Polygon([[5.2, 5.2], [5.6, 5.5], [5.4, 5]], edgecolor='green', facecolor='green')
        stem = patches.Rectangle((4.9, 5), 0.2, 0.6, edgecolor='brown', facecolor='brown')
        ax.add_patch(apple)
        ax.add_patch(leaf)
        ax.add_patch(stem)
    
    elif '钟' in description or '时间' in description:
        clock = patches.Circle((5, 4), 2, edgecolor='black', facecolor='white', linewidth=2)
        ax.add_patch(clock)
        for hour in range(1, 13):
            angle = math.radians(90 - hour * 30)
            ax.plot([5 + 1.7*math.cos(angle), 5 + 1.9*math.cos(angle)],
                   [4 + 1.7*math.sin(angle), 4 + 1.9*math.sin(angle)], color='black', linewidth=1.5)
            ax.annotate(str(hour), xy=(5 + 1.5*math.cos(angle), 4 + 1.5*math.sin(angle)), 
                       ha='center', va='center', fontsize=10)
        numbers = re.findall(r'\d+', description)
        hour = int(numbers[0]) % 12 if numbers else 3
        minute = int(numbers[1]) if len(numbers) >= 2 else 0
        hour_angle = math.radians(90 - (hour * 30 + minute * 0.5))
        minute_angle = math.radians(90 - minute * 6)
        ax.plot([5, 5 + 1.0*math.cos(hour_angle)], [4, 4 + 1.0*math.sin(hour_angle)], 'k-', linewidth=3)
        ax.plot([5, 5 + 1.5*math.cos(minute_angle)], [4, 4 + 1.5*math.sin(minute_angle)], 'k-', linewidth=2)
    
    else:
        ax.text(5, 4, f'【需要绘制：{description}】', ha='center', va='center', fontsize=12, color='gray')
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    return buffer


def create_word_document(paper_json, with_answers=False, auto_draw=True):
    doc = Document()
    
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style.font.size = Pt(12)
    
    title = doc.add_heading(paper_json.get('title', '试卷'), level=0)
    title.alignment = 1
    
    info = doc.add_paragraph()
    info.add_run(f"总分：{paper_json.get('total_score', 100)}分")
    info.alignment = 1
    doc.add_paragraph()
    
    info_row = doc.add_paragraph()
    info_row.add_run("班级：_________________  姓名：_________________  学号：_________________")
    doc.add_paragraph()
    
    image_counter = 1
    
    for section in paper_json.get('sections', []):
        doc.add_heading(section.get('type', ''), level=2)
        doc.add_paragraph(f"（每题{section.get('score_per_question', 0)}分）")
        
        for q in section.get('questions', []):
            if q.get('image_marker') and auto_draw and q.get('image_type') == 'auto_draw':
                try:
                    img_buffer = draw_geometry(q.get('image_description', ''))
                    doc.add_picture(img_buffer, width=Inches(3))
                except:
                    doc.add_paragraph(f"【图{image_counter}：{q.get('image_description', '')}】")
                    image_counter += 1
            elif q.get('image_marker'):
                doc.add_paragraph(f"【图{image_counter}：{q.get('image_description', '')}】")
                image_counter += 1
            
            p = doc.add_paragraph()
            p.add_run(f"{q.get('number', '')}. {q.get('text', '')}")
            
            if 'options' in q and q['options']:
                for opt in q['options']:
                    doc.add_paragraph(f"   {opt}")
            
            if with_answers and 'answer' in q:
                ans = doc.add_paragraph()
                ans.add_run(f"【答案】{q['answer']}").italic = True
                ans.paragraph_format.left_indent = Pt(20)
            
            if not with_answers:
                doc.add_paragraph()
                doc.add_paragraph()
        
        doc.add_paragraph()
    
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
