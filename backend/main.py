import time
import uuid
import re
import math
import logging
from fastapi import FastAPI, Header, Depends, Request, status
from pydantic import BaseModel, Field

from database import get_db, engine
from fallback_buffer import LocalFallbackCircuitBreaker
from workers import process_promotion_async

logger = logging.getLogger("lotte-promo-backend")

app = FastAPI(
    title="Promo-Lens Backend API ",
    version="24.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

fallback_circuit_breaker = LocalFallbackCircuitBreaker()

class AdvancedSimulationRequest(BaseModel):
    prompt: str = Field(..., description="마케터 자연어 지시 사항")
    discount_pct: float = Field(15.0, description="할인율 (%)")
    gift_cost_won: float = Field(30000.0, description="사은품 단가 (원)")
    target_revenue_mil: float = Field(15000.0, description="목표 매출액 (백만 원)")

# Intent Parser
def parse_natural_language_intent(prompt: str):
    p = prompt.strip()
    
    # 기본값 설정
    parsed_discount = None
    parsed_revenue = None
    category = "일반/종합"

    # 카테고리 감지
    if any(k in p for k in ["가전", "디지털", "TV", "냉장고", "세탁기"]):
        category = "대형가전/디지털"
    elif any(k in p for k in ["뷰티", "화장품", "코스메틱", "스킨케어"]):
        category = "뷰티/코스메틱"
    elif any(k in p for k in ["식품", "푸드", "신선", "가공식품", "명절"]):
        category = "가공식품/신선"

    # 할인율 추출 
    disc_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:%|퍼센트|할인)', p)
    if disc_match:
        parsed_discount = float(disc_match.group(1))

    # 매출액 추출
    rev_match_juk = re.search(r'(\d+(?:\.\d+)?)\s*억', p)
    if rev_match_juk:
        parsed_revenue = float(rev_match_juk.group(1)) * 100.0 
    else:
        rev_match_mil = re.search(r'(\d+(?:\.\d+)?)\s*(?:백만|원)', p)
        if rev_match_mil and "백만" in p:
            parsed_revenue = float(rev_match_mil.group(1))

    return {
        "category": category,
        "discount_pct": parsed_discount,
        "target_revenue_mil": parsed_revenue
    }

# Vector DB RAG Mock Engine
def retrieve_similar_past_promotions(category: str, discount: float, revenue: float):
    vector_db_registry = [
        {
            "id": "CASE-2025-01",
            "category": "대형가전/디지털",
            "case_name": "2025 프리미엄 대형가전 슈퍼위크 (삼성/LG 콜라보)",
            "avg_discount": 18.0,
            "revenue_mil": 18500.0,
            "margin_pct": 16.5,
            "insight": "대형가전은 할인율 18% 선에서 객단가가 정점에 달하며, 사은품 단가가 4만 원을 초과할 경우 역마진 발생 위험이 34% 증가함."
        },
        {
            "id": "CASE-2025-02",
            "category": "대형가전/디지털",
            "case_name": "2024 블랙프라이데이 가전 대전",
            "avg_discount": 22.0,
            "revenue_mil": 24000.0,
            "margin_pct": 11.2,
            "insight": "할인율 20% 이상 집행 시 매출은 30% 증가하나 마진율이 12% 이하로 떨어져 리스크 관리 위원회 경고 조치됨."
        },
        {
            "id": "CASE-2025-03",
            "category": "뷰티/코스메틱",
            "case_name": "2025 상반기 뷰티 페스티벌",
            "avg_discount": 25.0,
            "revenue_mil": 12000.0,
            "margin_pct": 19.0,
            "insight": "뷰티 상품군은 충성 고객 유입률이 높아 할인율 25%에서도 세트 상품 결합 시 목표 마진 방어 성공."
        },
        {
            "id": "CASE-2025-04",
            "category": "가공식품/신선",
            "case_name": "2025 추석 농축수산 특가전",
            "avg_discount": 15.0,
            "revenue_mil": 9500.0,
            "margin_pct": 21.0,
            "insight": "식품 카테고리는 무료배송 조건 결합 시 구매 전환율이 42% 향상되는 패턴 확인."
        },
        {
            "id": "CASE-2025-05",
            "category": "일반/종합",
            "case_name": "2025 연말 결산 슈퍼위크",
            "avg_discount": 15.0,
            "revenue_mil": 15000.0,
            "margin_pct": 18.5,
            "insight": "목표 매출 150억 원 구간에서 가장 안정적인 손익 구조를 보인 표준 프로모션 모델."
        }
    ]

    # 코사인 유사도 점수 계산 로직
    scored_cases = []
    for case in vector_db_registry:
        score = 0.0
        if case["category"] == category:
            score += 0.6  # 카테고리 일치 시 높은 가중치
        else:
            score += 0.2

        # 할인율 차이 역산 유사도
        disc_diff = abs(case["avg_discount"] - discount)
        score += max(0.0, 0.4 - (disc_diff * 0.02))

        scored_cases.append((score, case))

    # 유사도 점수가 가장 높은 베스트 케이스 추출
    scored_cases.sort(key=lambda x: x[0], reverse=True)
    best_score, best_case = scored_cases[0]
    
    similarity_percentage = f"{min(99.5, round(best_score * 100, 1))}%"

    return {
        "case_name": best_case["case_name"],
        "similarity_score": similarity_percentage,
        "past_revenue": best_case["revenue_mil"],
        "insight": best_case["insight"]
    }

@app.post("/api/v1/promotions/simulate", status_code=status.HTTP_200_OK)
def simulate_promotion_advanced(
    req: AdvancedSimulationRequest,
    request: Request
):
    correlation_id = request.headers.get("X-Correlation-ID", f"CORR-{uuid.uuid4().hex[:12].upper()}")
    
    # Intent Parser
    intent_result = parse_natural_language_intent(req.prompt)
    
    final_discount = req.discount_pct
    final_revenue = req.target_revenue_mil
    
    # 자연어에서 명시적인 파라미터가 감지되었다면 슬라이더 값보다 우선 적용
    if intent_result["discount_pct"] is not None:
        final_discount = intent_result["discount_pct"]
    if intent_result["target_revenue_mil"] is not None:
        final_revenue = intent_result["target_revenue_mil"]

    # Vector DB RAG 검색 실행
    rag_match = retrieve_similar_past_promotions(
        category=intent_result["category"],
        discount=final_discount,
        revenue=final_revenue
    )

    # 백엔드 검증 수식 역산
    calculated_margin = round(35.0 - (final_discount * 0.9) - (req.gift_cost_won / 10000.0 * 0.4), 2)
    net_profit_mil = round(final_revenue * (calculated_margin / 100.0), 2)
    
    # Risk & Insight Auditor Agent
    risk_level = "SAFE"
    ai_briefing = f"[Intent Parser] 카테고리: {intent_result['category']} / 감지된 할인율: {final_discount}% / 목표매출: {final_revenue:,.0f}백만 원. 예상 마진율 {calculated_margin}%로 안정적입니다."
    
    if calculated_margin < 12.0:
        risk_level = "WARNING"
        ai_briefing = f"🚨 [역마진 위험 감지] 감지된 할인율({final_discount}%)과 프로모션 비용으로 인해 목표 마진선(12%)을 하회합니다. (과거 유사 사례 인사이트: {rag_match['insight']})"

    # Circuit Breaker
    fallback_circuit_breaker.push_audit_event({
        "correlation_id": correlation_id,
        "prompt": req.prompt,
        "parsed_category": intent_result["category"],
        "discount_pct": final_discount,
        "calculated_margin": calculated_margin,
        "risk_level": risk_level,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    })

    return {
        "status": "SUCCESS",
        "correlation_id": correlation_id,
        "metrics": {
            "parsed_discount": final_discount,
            "parsed_revenue": final_revenue,
            "detected_category": intent_result["category"],
            "calculated_margin_pct": calculated_margin,
            "net_profit_mil": net_profit_mil,
            "risk_level": risk_level,
            "ai_briefing": ai_briefing,
            "historical_match": rag_match
        },
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }

# FE
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    def read_index():
        return FileResponse(os.path.join(frontend_path, "index.html"))