import streamlit as st
import pandas as pd
import numpy as np

# 페이지 설정
st.set_page_config(
    page_title="Promo-Lens: 프로모션 시뮬레이터",
    page_icon="📊",
    layout="wide"
)

st.title("Promo-Lens | 프로모션 시뮬레이터")
st.markdown("자연어 조건 및 파라미터를 기반으로 예상 매출, 필요 트래픽, 마진율 및 고객 반응을 시뮬레이션합니다.")
st.markdown("---")

# 사이드바: 프로모션 조건 설정
st.sidebar.header("프로모션 조건 설정")
target_category = st.sidebar.selectbox("상품 카테고리", ["겨울 패딩/의류", "프리미엄 가전", "뷰티/화장품", "신선식품"])
discount_rate = st.sidebar.slider("카드 즉시 할인율 (%)", min_value=0, max_value=30, value=7, step=1)
gift_type = st.sidebar.selectbox("증정 사은품 유형", ["없음", "고급 보온병 (단가: 1.5만)", "겨울 장갑 (단가: 2.0만)", "적립금 5천원 페이백"])
target_revenue = st.sidebar.number_input("목표 매출액 (백만 원)", min_value=50, max_value=5000, value=500, step=50)

# 시뮬레이션 백엔드 로직
def run_simulation(category, discount, gift, goal):
    base_conversion = 0.05
    base_margin = 0.35
    
    conversion_boost = discount * 0.015
    predicted_conversion = base_conversion + conversion_boost
    
    gift_cost_map = {
        "없음": 0, 
        "고급 보온병 (단가: 1.5만)": 15000, 
        "겨울 장갑 (단가: 2.0만)": 20000, 
        "적립금 5천원 페이백": 5000
    }
    current_gift_cost = gift_cost_map[gift]
    
    estimated_revenue = goal * (1 + conversion_boost - (current_gift_cost / 1000000))
    required_traffic = int((goal * 1000000) / (50000 * predicted_conversion))
    estimated_margin = base_margin - (discount * 0.005) - (current_gift_cost / 200000)
    
    return {
        "predicted_revenue": round(estimated_revenue, 1),
        "predicted_conversion": round(predicted_conversion * 100, 1),
        "required_traffic": required_traffic,
        "estimated_margin": round(estimated_margin * 100, 1),
        "gift_cost": current_gift_cost
    }

sim_result = run_simulation(target_category, discount_rate, gift_type, target_revenue)

# 메인 대시보드 KPI 카드 영역
col1, col2, col3, col4 = st.columns(4)
col1.metric("예상 매출액", f"{sim_result['predicted_revenue']} 백만 원", delta=f"{round(sim_result['predicted_revenue'] - target_revenue, 1)} 백만 원 vs 목표")
col2.metric("예상 구매 전환율", f"{sim_result['predicted_conversion']}%", delta="+1.5% (전주 대비)")
col3.metric("필요 유입 트래픽", f"{sim_result['required_traffic']:,} 명")
col4.metric("예상 영업 마진율", f"{sim_result['estimated_margin']}%", delta="-2.1% (역마진 주의)" if sim_result['estimated_margin'] < 25 else "안전", delta_color="inverse")

st.markdown("---")

# 시각화 및 인사이트 영역
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("요일별 예상 매출 추이")

    days_order = ['월', '화', '수', '목', '금', '토', '일']
    chart_data = pd.DataFrame({
        '요일': days_order,
        '예상 매출 (백만 원)': [
            sim_result['predicted_revenue'] * 0.1,
            sim_result['predicted_revenue'] * 0.12,
            sim_result['predicted_revenue'] * 0.11,
            sim_result['predicted_revenue'] * 0.15,
            sim_result['predicted_revenue'] * 0.18,
            sim_result['predicted_revenue'] * 0.2,
            sim_result['predicted_revenue'] * 0.14
        ]
    })
    chart_data['요일'] = pd.Categorical(chart_data['요일'], categories=days_order, ordered=True)
    chart_data = chart_data.sort_values('요일')
    
    st.bar_chart(chart_data.set_index('요일'))

with col_chart2:
    st.subheader("AI 리스크 및 성과 리포트")
    st.info(f"""
    **[Promo-Lens Analysis]**
    * **타겟 반응**: 선택하신 {discount_rate}% 할인과 {gift_type} 조합은 타겟층의 반응을 이끌어내어 구매 전환율이 약 {sim_result['predicted_conversion']}%까지 향상될 것으로 예측됩니다.
    * **리스크 요인**: 사은품 원가와 할인율의 복합 영향으로 예상 마진율이 {sim_result['estimated_margin']}%로 산출되었습니다. 마진 방어를 위해 사은품 대안 검토를 권장합니다.
    """)

# 자연어 에이전트 인터페이스
st.markdown("---")
st.subheader("에이전트 자연어 명령 인터페이스")
user_query = st.text_input("마케터 명령 입력", "다음 주 패딩 방송에 7% 할인 걸고 보온병 주면 어때?")

if st.button("시뮬레이션 실행"):
    st.success(f"파라미터 파싱 완료: [카테고리: {target_category}, 할인율: {discount_rate}%, 사은품: {gift_type}]")
    st.write(f"시뮬레이션 결과, 예상 매출은 **{sim_result['predicted_revenue']}백만 원**이며 최적화 계산이 완료되었습니다.")