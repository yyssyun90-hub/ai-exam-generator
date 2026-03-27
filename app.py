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
from PyPDF2 import PdfReader

st.set_page_config(page_title="AI智能出卷助手", page_icon="📝", layout="wide")

# 初始化session_state
if "paper_json" not in st.session_state:
    st.session_state.paper_json = None
if "analyzed_style" not in st.session_state:
    st.session_state.analyzed_style = None

st.title("📝 AI 智能出卷助手")
st.caption("上传参考试卷，AI学习风格后自动生成新试卷（支持自动绘图）")

# 侧边栏 - 安全配置
with st.sidebar:
    st.header("🔐 配置")
    
    if "DEEPSEEK_API_KEY" in st.secrets:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        openai.api_key = api_key
        openai.base_url = "https://api.deepseek.com"
        st.success("✅ API已配置")
    else:
        st.warning("⚠️ 请在Streamlit Secrets中设置 DEEPSEEK_API_KEY")
        st.markdown("""
        **如何设置：**
        1. 点击应用页面的 Settings
        2. 找到 Secrets
        3. 添加：`DEEPSEEK_API_KEY = "你的key"`
        """)
        api_key = None
    
    st.divider()
    st.header("🎨 图片设置")
    auto_draw = st.checkbox("自动生成图形", value=True, help="几何图形、云朵、太阳、树、房子、鱼、花、苹果、钟表等自动绘制")
    st.info("复杂场景图片会生成【图X：描述】占位符，您稍后手动插入")

# 主界面 - 三个标签页
tab1, tab2, tab3 = st.tabs(["📚 上传资料", "🎯 出卷设置", "📄 生成试卷"])

with tab1:
    st.subheader("📖 上传参考试卷（让AI学习风格）")
    
    reference_papers = st.file_uploader(
        "上传之前的试卷（支持Word和PDF）",
        type=["docx", "pdf"],
        accept_multiple_files=True,
        help="上传2-3份之前的试卷，AI会学习题型、分值、语言风格"
    )
    
    st.subheader("📅 上传全年教学计划")
    syllabus = st.file_uploader(
        "上传教学计划（Word格式）",
        type=["docx"],
        help="AI会根据教学进度判断哪些内容可以考"
    )
    
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
    
    st.subheader("📋 额外要求")
    extra_requirements = st.text_area(
        "特殊要求",
        placeholder="例如：多出看图写话题、重点考察应用题、多出几何图形题...",
        height=100
    )
    
    if reference_papers and st.button("🔍 分析试卷风格", type="secondary"):
        with st.spinner("AI正在分析试卷风格..."):
            style_analysis = analyze_paper_style(reference_papers, api_key)
            st.session_state.analyzed_style = style_analysis
            st.success("风格分析完成！")
            with st.expander("查看分析结果"):
                st.json(style_analysis)

with tab3:
    if not st.session_state.analyzed_style:
        st.info("请先在「上传资料」标签页上传参考试卷，并点击「分析试卷风格」")
    else:
        st.subheader("🚀 生成新试卷")
        
        if st.button("📝 生成试卷", type="primary", use_container_width=True):
            with st.spinner("AI正在生成试卷（含图片标记）..."):
                paper = generate_paper(
                    style=st.session_state.analyzed_style,
                    grade=grade_level,
                    subject=subject,
                    paper_type=paper_type,
                    difficulty=difficulty,
                    extra_requirements=extra_requirements,
                    syllabus_file=syllabus,
                    api_key=api_key,
                    auto_draw=auto_draw
                )
                st.session_state.paper_json = paper
                st.success("试卷生成成功！")
    
    if st.session_state.paper_json:
        st.divider()
        st.subheader("📄 试卷预览")
        
        paper = st.session_state.paper_json
        
        st.markdown(f"### {paper.get('title', f'{grade_level}{subject}{paper_type}试卷')}")
        st.markdown(f"**总分：{paper.get('total_score', 100)}分**")
        st.markdown("---")
        
        # 显示各题型
        for section in paper.get('sections', []):
            st.markdown(f"#### {section.get('type', '')}（每题{section.get('score_per_question', 0)}分）")
            for q in section.get('questions', []):
                st.markdown(f"**{q.get('number', '')}.** {q.get('text', '')}")
                if q.get('image_marker'):
                    if q.get('image_type') == 'auto_draw':
                        st.success(f"🎨 自动绘图：{q.get('image_description', '')}")
                    else:
                        st.info(f"🖼️ {q['image_marker']}")
                if 'options' in q and q['options']:
                    for opt in q['options']:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;{opt}")
                st.markdown("")
            st.markdown("---")
        
        # 下载按钮
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
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
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
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )


def read_pdf_content(file):
    """读取PDF文件内容"""
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text


def read_docx_content(file):
    """读取Word文件内容"""
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text


def analyze_paper_style(reference_files, api_key):
    """分析试卷风格"""
    if not api_key:
        return {"error": "API Key未配置"}
    
    papers_content = []
    for file in reference_files:
        if file.name.endswith('.pdf'):
            content = read_pdf_content(file)
        else:
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
        "section_types": ["题型1", "题型2", ...]
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
            model="deepseek-chat",
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


def generate_paper(style, grade, subject, paper_type, difficulty, extra_requirements, syllabus_file, api_key, auto_draw=True):
    """生成试卷"""
    if not api_key:
        return {"error": "API Key未配置"}
    
    syllabus_content = ""
    if syllabus_file:
        syllabus_content = read_docx_content(syllabus_file)[:2000]
    
    style_str = json.dumps(style, ensure_ascii=False)
    
    # 图片处理指令
    image_instruction = """
【图片处理规则】
1. 如果题目需要几何图形（长方形、正方形、三角形、圆形、线段图等），请在题目中添加：【自动绘图：图形描述】
   例如：一个长方形，长8厘米，宽4厘米 → 【自动绘图：长方形，长8cm，宽4cm】

2. 如果题目需要以下图形，请使用【自动绘图】：
   - 云朵 → 【自动绘图：云朵】
   - 太阳 → 【自动绘图：太阳】
   - 树 → 【自动绘图：一棵大树】
   - 房子 → 【自动绘图：房子】
   - 鱼 → 【自动绘图：鱼】
   - 花 → 【自动绘图：花】
   - 苹果 → 【自动绘图：苹果】
   - 钟表时间 → 【自动绘图：钟表显示3点整】

3. 如果题目需要复杂场景图片（人物、动物、校园场景、生活场景等），请在题目中添加：【图X：详细场景描述】
   例如：一个小男孩在公园里放风筝 → 【图1：一个小男孩在公园里放风筝，天空中飘着白云，远处有树木】

4. 图片标记从【图1】开始递增
5. 看图写话题必须在题干前加上图片标记
"""
    
    prompt = f"""
你是一位经验丰富的小学{subject}教师，请根据以下要求生成一份完整试卷。

【年级】{grade}
【科目】{subject}
【试卷类型】{paper_type}
【难度】{difficulty}

【学习到的试卷风格】
{style_str}

【教学计划（约束出题范围）】
{syllabus_content if syllabus_content else "无"}

【额外要求】
{extra_requirements if extra_requirements else "无"}

{image_instruction if auto_draw else ""}

请生成一份完整试卷，保持与参考试卷相似的风格和格式，但题目内容必须完全不同。
注意：
- {grade}的学生认知水平
- 题目要符合教学进度
- 语言要适合小学生理解
- 图片标记要清晰

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
                    "text": "题干（含图片标记）",
                    "image_marker": "如果有图片标记，填写在这里",
                    "image_type": "auto_draw 或 manual",
                    "image_description": "图片描述",
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
                    "text": "题干（用____表示填空）",
                    "image_marker": "如果有图片标记",
                    "image_type": "auto_draw 或 manual",
                    "image_description": "图片描述",
                    "answer": "答案",
                    "explanation": "答案解析"
                }}
            ]
        }},
        {{
            "type": "简答题/应用题",
            "score_per_question": 每题分值,
            "questions": [
                {{
                    "number": 1,
                    "text": "题干",
                    "image_marker": "如果有图片标记",
                    "image_type": "auto_draw 或 manual",
                    "image_description": "图片描述",
                    "answer": "参考答案要点",
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
            model="deepseek-chat",
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
    """根据描述绘制图形（支持规则图形和不规则图形）"""
    description = description.lower()
    
    fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 8)
    ax.set_aspect('equal')
    ax.axis('off')
    
    # ========== 规则图形 ==========
    
    # 长方形
    if '长方形' in description or '矩形' in description:
        numbers = re.findall(r'\d+', description)
        if len(numbers) >= 2:
            length, width = int(numbers[0]), int(numbers[1])
        else:
            length, width = 8, 4
        rect = patches.Rectangle((1, 2), length, width, linewidth=2, edgecolor='black', facecolor='lightblue', alpha=0.7)
        ax.add_patch(rect)
        ax.set_xlim(0, length + 2)
        ax.set_ylim(0, width + 3)
        ax.annotate(f'{length}cm', xy=(1 + length/2, 1.5), ha='center')
        ax.annotate(f'{width}cm', xy=(0.5, 2 + width/2), va='center', rotation=90)
    
    # 正方形
    elif '正方形' in description:
        numbers = re.findall(r'\d+', description)
        side = int(numbers[0]) if numbers else 5
        square = patches.Rectangle((2.5, 1.5), side, side, linewidth=2, edgecolor='black', facecolor='lightgreen', alpha=0.7)
        ax.add_patch(square)
        ax.set_xlim(0, side + 5)
        ax.set_ylim(0, side + 3)
        ax.annotate(f'{side}cm', xy=(2.5 + side/2, 1), ha='center')
    
    # 三角形
    elif '三角形' in description:
        triangle = patches.Polygon([[3, 1], [7, 1], [5, 5]], linewidth=2, edgecolor='black', facecolor='lightcoral', alpha=0.7)
        ax.add_patch(triangle)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
    
    # 圆形
    elif '圆' in description or '圆形' in description:
        numbers = re.findall(r'\d+', description)
        radius = int(numbers[0]) / 2 if numbers else 2
        center_x, center_y = 5, 4
        circle = patches.Circle((center_x, center_y), radius, linewidth=2, edgecolor='black', facecolor='lightyellow', alpha=0.7)
        ax.add_patch(circle)
        ax.annotate(f'半径{radius}cm', xy=(center_x, center_y - radius - 0.3), ha='center')
    
    # ========== 不规则图形（小学常用） ==========
    
    # 云朵
    elif '云' in description or 'cloud' in description:
        circle1 = patches.Circle((3, 4), 1.2, edgecolor='black', facecolor='white', linewidth=1.5)
        circle2 = patches.Circle((4.5, 4.5), 1.5, edgecolor='black', facecolor='white', linewidth=1.5)
        circle3 = patches.Circle((6, 4), 1.2, edgecolor='black', facecolor='white', linewidth=1.5)
        circle4 = patches.Circle((4, 3), 1, edgecolor='black', facecolor='white', linewidth=1.5)
        ax.add_patch(circle1)
        ax.add_patch(circle2)
        ax.add_patch(circle3)
        ax.add_patch(circle4)
    
    # 太阳
    elif '太阳' in description or 'sun' in description:
        sun = patches.Circle((5, 5), 1.5, edgecolor='orange', facecolor='yellow', linewidth=2)
        ax.add_patch(sun)
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x1 = 5 + 1.5 * math.cos(rad)
            y1 = 5 + 1.5 * math.sin(rad)
            x2 = 5 + 2.2 * math.cos(rad)
            y2 = 5 + 2.2 * math.sin(rad)
            ax.plot([x1, x2], [y1, y2], color='orange', linewidth=2)
    
    # 树
    elif '树' in description or 'tree' in description:
        trunk = patches.Rectangle((4.5, 2), 1, 2, edgecolor='brown', facecolor='saddlebrown')
        crown = patches.Polygon([[3, 4], [7, 4], [5, 7]], edgecolor='green', facecolor='forestgreen', alpha=0.8)
        ax.add_patch(trunk)
        ax.add_patch(crown)
    
    # 房子
    elif '房子' in description or 'house' in description:
        house = patches.Rectangle((3, 2), 4, 3, edgecolor='black', facecolor='lightyellow')
        roof = patches.Polygon([[2.5, 5], [7.5, 5], [5, 7]], edgecolor='brown', facecolor='lightcoral')
        door = patches.Rectangle((4.5, 2), 1, 1.5, edgecolor='black', facecolor='brown')
        window = patches.Circle((5.5, 3.5), 0.4, edgecolor='black', facecolor='lightblue')
        ax.add_patch(house)
        ax.add_patch(roof)
        ax.add_patch(door)
        ax.add_patch(window)
    
    # 鱼
    elif '鱼' in description or 'fish' in description:
        body = Ellipse((5, 4), 3, 1.5, edgecolor='black', facecolor='orange', alpha=0.8)
        tail = patches.Polygon([[3.5, 4], [2, 3.5], [2, 4.5]], edgecolor='black', facecolor='orange')
        eye = patches.Circle((4, 4.2), 0.15, facecolor='black')
        ax.add_patch(body)
        ax.add_patch(tail)
        ax.add_patch(eye)
    
    # 花
    elif '花' in description or 'flower' in description:
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x = 5 + 0.8 * math.cos(rad)
            y = 4 + 0.8 * math.sin(rad)
            petal = patches.Circle((x, y), 0.4, edgecolor='pink', facecolor='pink', alpha=0.7)
            ax.add_patch(petal)
        center = patches.Circle((5, 4), 0.3, edgecolor='brown', facecolor='yellow')
        stem = patches.Rectangle((4.8, 2), 0.4, 2, edgecolor='green', facecolor='green')
        ax.add_patch(center)
        ax.add_patch(stem)
    
    # 苹果
    elif '苹果' in description or 'apple' in description:
        apple = patches.Circle((5, 4), 1.2, edgecolor='red', facecolor='red', alpha=0.7)
        leaf = patches.Polygon([[5.2, 5.2], [5.6, 5.5], [5.4, 5]], edgecolor='green', facecolor='green')
        stem = patches.Rectangle((4.9, 5), 0.2, 0.6, edgecolor='brown', facecolor='brown')
        ax.add_patch(apple)
        ax.add_patch(leaf)
        ax.add_patch(stem)
    
    # 钟表
    elif '钟' in description or 'clock' in description or '时间' in description:
        clock = patches.Circle((5, 4), 2, edgecolor='black', facecolor='white', linewidth=2)
        ax.add_patch(clock)
        
        for hour in range(1, 13):
            angle = math.radians(90 - hour * 30)
            x1 = 5 + 1.7 * math.cos(angle)
            y1 = 4 + 1.7 * math.sin(angle)
            x2 = 5 + 1.9 * math.cos(angle)
            y2 = 4 + 1.9 * math.sin(angle)
            ax.plot([x1, x2], [y1, y2], color='black', linewidth=1.5)
            x_num = 5 + 1.5 * math.cos(angle)
            y_num = 4 + 1.5 * math.sin(angle)
            ax.annotate(str(hour), xy=(x_num, y_num), ha='center', va='center', fontsize=10)
        
        numbers = re.findall(r'\d+', description)
        if len(numbers) >= 2:
            hour = int(numbers[0]) % 12
            minute = int(numbers[1])
        elif len(numbers) >= 1:
            hour = int(numbers[0]) % 12
            minute = 0
        else:
            hour, minute = 3, 0
        
        hour_angle = math.radians(90 - (hour * 30 + minute * 0.5))
        minute_angle = math.radians(90 - minute * 6)
        
        ax.plot([5, 5 + 1.0 * math.cos(hour_angle)], [4, 4 + 1.0 * math.sin(hour_angle)], 'k-', linewidth=3)
        ax.plot([5, 5 + 1.5 * math.cos(minute_angle)], [4, 4 + 1.5 * math.sin(minute_angle)], 'k-', linewidth=2)
    
    # 默认：如果没有匹配到，显示提示文字
    else:
        ax.text(5, 4, f'【需要绘制：{description}】', ha='center', va='center', fontsize=12, color='gray')
    
    # 保存图片
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=120, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    return buffer


def create_word_document(paper_json, with_answers=False, auto_draw=True):
    """生成Word文档"""
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
            # 处理图片
            if q.get('image_marker') and auto_draw:
                image_type = q.get('image_type', 'manual')
                image_desc = q.get('image_description', '')
                
                if image_type == 'auto_draw' and image_desc:
                    # 自动生成图形
                    try:
                        img_buffer = draw_geometry(image_desc)
                        doc.add_picture(img_buffer, width=Inches(3))
                        doc.add_paragraph(f"（{image_desc}）")
                    except Exception as e:
                        doc.add_paragraph(f"【图{image_counter}：{image_desc}】（自动绘图失败）")
                        image_counter += 1
                else:
                    # 手动插入的占位符
                    doc.add_paragraph(f"【图{image_counter}：{image_desc}】")
                    image_counter += 1
            
            # 题目文本
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
