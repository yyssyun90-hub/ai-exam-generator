import streamlit as st
import openai
import json
from docx import Document
from docx.shared import Pt
from io import BytesIO

st.set_page_config(page_title="AI出卷助手", page_icon="📝", layout="wide")

# 初始化session_state
if "paper_json" not in st.session_state:
    st.session_state.paper_json = None

st.title("📝 AI 智能出卷助手")

# 侧边栏
with st.sidebar:
    st.header("🔑 配置")
    api_key = st.text_input("DeepSeek API Key", type="password", 
                            help="去 platform.deepseek.com 注册获取")
    
    if api_key:
        openai.api_key = api_key
        openai.base_url = "https://api.deepseek.com"
        st.success("✅ API已配置")
    
    st.divider()
    st.header("📄 试卷样式")
    font_name = st.selectbox("字体", ["宋体", "黑体", "楷体", "微软雅黑"])
    font_size = st.slider("字号", 10, 16, 12)

# 主界面
st.write("### 快速出卷")
st.caption("输入考试信息，AI自动生成完整试卷")

col1, col2 = st.columns(2)

with col1:
    grade = st.selectbox("年级", ["七年级", "八年级", "九年级", "高一", "高二", "高三"])
    subject = st.selectbox("科目", ["数学", "语文", "英语", "物理", "化学"])
    topic = st.text_input("考试范围", placeholder="例如：一次函数、三角形全等")

with col2:
    paper_type = st.selectbox("试卷类型", ["单元测试", "期中考试", "期中考试", "期末考试"])
    difficulty = st.select_slider("难度", ["简单", "中等偏易", "中等", "中等偏难", "难"])
    total_score = st.number_input("总分", value=100)

st.subheader("题型数量")
col_a, col_b, col_c = st.columns(3)
with col_a:
    choice_num = st.number_input("选择题", 0, 20, 5)
with col_b:
    fill_num = st.number_input("填空题", 0, 20, 5)
with col_c:
    solve_num = st.number_input("解答题", 0, 20, 3)

# 生成按钮
if st.button("🚀 生成试卷", type="primary", use_container_width=True):
    if not api_key:
        st.error("请先在左侧输入DeepSeek API Key")
    elif not topic:
        st.error("请输入考试范围")
    else:
        with st.spinner("AI正在出卷中..."):
            try:
                # 构建prompt
                prompt = f"""
你是一位经验丰富的{subject}教师，请出一份{grade}{paper_type}{subject}试卷。

【考试范围】{topic}
【难度】{difficulty}
【总分】{total_score}分
【题型】选择题{choice_num}道、填空题{fill_num}道、解答题{solve_num}道

请以JSON格式输出，结构如下：
{{
    "title": "{grade}{paper_type}{subject}试卷",
    "total_score": {total_score},
    "sections": [
        {{
            "type": "选择题",
            "score_per_question": 每道题的分值,
            "questions": [
                {{
                    "number": 1,
                    "text": "题干",
                    "options": ["A. xxx", "B. xxx", "C. xxx", "D. xxx"],
                    "answer": "A"
                }}
            ]
        }},
        {{
            "type": "填空题",
            "score_per_question": 每道题的分值,
            "questions": [
                {{"number": 1, "text": "题干", "answer": "答案"}}
            ]
        }},
        {{
            "type": "解答题",
            "score_per_question": 每道题的分值,
            "questions": [
                {{"number": 1, "text": "题干", "answer": "答案要点"}}
            ]
        }}
    ]
}}

注意：题目要符合{grade}学生水平，难度{difficulty}，紧扣{topic}这个范围。
只输出JSON，不要其他内容。
"""
                
                response = openai.ChatCompletion.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是专业出题专家，只输出JSON格式。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                paper_json = json.loads(response.choices[0].message.content)
                st.session_state.paper_json = paper_json
                
                st.success("✅ 试卷生成成功！")
                
            except Exception as e:
                st.error(f"生成失败：{str(e)}")

# 显示预览和下载
if st.session_state.paper_json:
    st.divider()
    st.subheader("📄 试卷预览")
    
    paper = st.session_state.paper_json
    
    # 显示标题
    st.markdown(f"### {paper['title']}")
    st.markdown(f"**总分：{paper['total_score']}分**")
    st.markdown("---")
    
    # 显示各题型
    for section in paper['sections']:
        st.markdown(f"#### {section['type']}（每题{section['score_per_question']}分）")
        for q in section['questions']:
            st.markdown(f"**{q['number']}.** {q['text']}")
            if 'options' in q:
                for opt in q['options']:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{opt}")
            st.markdown("")  # 空行
        st.markdown("---")
    
    # 下载按钮
    if st.button("📥 下载Word试卷", type="secondary"):
        # 生成Word文档
        doc = Document()
        
        # 设置字体
        style = doc.styles['Normal']
        style.font.name = font_name
        style.font.size = Pt(font_size)
        
        # 标题
        title = doc.add_heading(paper['title'], 0)
        title.alignment = 1
        
        # 总分
        doc.add_paragraph(f"总分：{paper['total_score']}分")
        doc.add_paragraph()
        
        # 题目
        for section in paper['sections']:
            doc.add_heading(section['type'], level=2)
            doc.add_paragraph(f"（每题{section['score_per_question']}分）")
            
            for q in section['questions']:
                p = doc.add_paragraph()
                p.add_run(f"{q['number']}. {q['text']}").bold = False
                
                if 'options' in q:
                    for opt in q['options']:
                        doc.add_paragraph(f"   {opt}")
                
                # 留空作答区
                doc.add_paragraph("作答区：")
                doc.add_paragraph()
                doc.add_paragraph()
            
            doc.add_page_break()
        
        # 保存到内存
        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        st.download_button(
            label="点击下载",
            data=buffer,
            file_name=f"{paper['title']}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
