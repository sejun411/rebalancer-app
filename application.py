# 정리된 코드
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import os

PASSWORD = "0813"
st.title("개인연금 ETF 리밸런싱 도구🔧")
def check_password():
    def password_entered():
        if st.session_state["password"] == PASSWORD:
            st.session_state["password_ok"] = True
        else:
            st.session_state["password_ok"] = False

    if "password_ok" not in st.session_state:
        st.text_input("비밀번호 입력", type="password", on_change=password_entered, key="password")
        return False

    if not st.session_state["password_ok"]:
        st.text_input("비밀번호 입력", type="password", on_change=password_entered, key="password")
        st.error("비밀번호가 틀렸습니다.")
        return False

    return True

if check_password():
    st.write("로그인 성공!")


    st.set_page_config(page_title="개인연금 ETF 리밸런서", layout="wide")

    DATA_DIR = "rebalancer_data"
    os.makedirs(DATA_DIR, exist_ok=True)

    st.markdown("""
    - 업로드할 CSV 포맷: **ticker,weight,qty**
    - 예: `069500,40,15`  ※ weight(비중)은 합이 100이어야 함
    - 리밸런싱은 현재가 기준으로 목표비중에 맞춰 수량을 증감 계산합니다.
    - 저장 시 원본 파일 이름 기반으로 히스토리(리밸런싱 로그)와 수익률 기록을 생성합니다. *아직 개발중
    """)

    import pandas as pd
    from io import BytesIO

    def create_friendly_sample_xlsx():
        output = BytesIO()
        writer = pd.ExcelWriter(output, engine='openpyxl')

        # ======== 1) portfolio 시트 (보유 종목 입력) ========
        portfolio_df = pd.DataFrame({
            "ticker": ["133690", "283580", "294400"],
            "weight": [40, 40, 20],
            "qty": [10, 5, 2],
        })
        portfolio_df.to_excel(writer, index=False, sheet_name="portfolio")

        # ======== 2) returns_history 시트 (자동 기록 — 수정 금지) ========
        returns_df = pd.DataFrame({
            "date": [],
            "portfolio_value": [],
            "monthly_contribution": [],
            "period_return": [],
        })
        returns_df.to_excel(writer, index=False, sheet_name="returns_history")

        # ======== 3) README 시트 (사용 설명서) ========
        readme_text = [
            ["📘 포트폴리오 템플릿 사용법"],
            [""],
            ["1) portfolio 시트는 반드시 채워야 합니다."],
            ["   - ticker: 주식 종목코드 (예: 133690, 411060)"],
            ["   - qty: 현재 보유 수량"],
            ["   - weight: 목표 비중(%) (총합 100 필요)"],
            [""],
            ["2) returns_history 시트는 앱에서 자동으로 작성됩니다."],
            ["   - 사용자가 직접 수정하지 마세요."],
            [""],
            ["3) 이 파일은 다음 작업에 사용됩니다:"],
            ["   - 실시간 가격 업데이트"],
            ["   - 리밸런싱 계산"],
            ["   - 월별 납입액 반영"],
            ["   - 기간 수익률 분석"],
            [""],
            ["✨ 필요한 시트만 간단히 입력하면 바로 분석할 수 있습니다!"],
        ]

        readme_df = pd.DataFrame(readme_text)
        readme_df.to_excel(writer, index=False, header=False, sheet_name="README")

        writer.close()
        output.seek(0)
        return output


    # ---- Streamlit Download Button ----
    st.subheader("📥 친절한 샘플 템플릿 다운로드")

    sample_file = create_friendly_sample_xlsx()

    st.download_button(
        label="샘플 파일 다운로드 (친절한 템플릿)",
        data=sample_file,
        file_name="portfolio_template_friendly.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


    st.subheader("💡 Step1. 포트폴리오 파일 업로드하기")

    uploaded = st.file_uploader("포트폴리오 파일 업로드 (CSV 또는 XLSX)", type=["csv", "xlsx"]) 

    import requests
    from bs4 import BeautifulSoup
    import numpy as np

    def fetch_price_and_name(ticker):
        try:
            tkr = ticker.zfill(6) if ticker.isdigit() else ticker
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "ko-KR,ko;q=0.9",
            }

            # 종목명 + 현재가를 한 번에 네이버 메인페이지에서 스크래핑
            url = f"https://finance.naver.com/item/main.naver?code={tkr}"
            r = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, "html.parser")

            # 종목명
            name_tag = soup.select_one("div.wrap_company h2 a")
            name = name_tag.text.strip() if name_tag else ""

            # 가격 (종가/현재가 공통)
            price_tag = soup.select_one("p.no_today span.blind")
            price = np.nan
            if price_tag:
                price = float(price_tag.text.replace(',', ''))

            return name, price

        except Exception as e:
            print("fetch error:", e)
            return "", np.nan

    def read_portfolio(df):
        df = df.copy()
        # expected columns: ticker, weight, qty
        df.columns = [c.strip() for c in df.columns]
        # normalize
        if 'ticker' not in df.columns or 'weight' not in df.columns or 'qty' not in df.columns:
            raise ValueError('CSV must contain ticker,weight,qty columns')
        df['ticker'] = df['ticker'].astype(str).str.strip()
        df['weight'] = df['weight'].astype(float)/100
        df['qty'] = df['qty'].astype(float)
        return df


    if uploaded:
        try:
            if uploaded.name.lower().endswith('.xlsx'):
                raw = pd.read_excel(uploaded)
            else:
                raw = pd.read_csv(uploaded)(uploaded)
            portfolio = read_portfolio(raw)
        except Exception as e:
            st.error(f"CSV 읽기 오류: {e}")
            st.stop()

        st.markdown("**📊업로드된 포트폴리오 (실시간 반영)**")

        # fetch prices and names
        with st.spinner("***현재가 불러오는 중...***"):
            names = []
            prices = []
            for t in portfolio['ticker']:
                name, price = fetch_price_and_name(t)
                names.append(name)
                prices.append(price)
            portfolio['name'] = names
            portfolio['price'] = prices
            portfolio['market_value'] = portfolio['price'] * portfolio['qty']

        st.markdown('**📌실시간 가격/평가액**')
        st.dataframe(
            portfolio[['ticker','name','price','qty','market_value','weight']]
            .rename(columns={
                'ticker': '종목코드',
                'name': '종목명',
                'price': '가격',
                'qty': '보유수량',
                'market_value': '평가금액',
                'weight': '목표비중'
            })
            .assign(목표비중=lambda df: df['목표비중'] * 100)
            .style.format({'가격': '{:,.0f}', '보유수량': '{:,.0f}', '평가금액': '{:,.0f}', '목표비중': '{:.2f}%'})
        )

        total_value = portfolio['market_value'].sum()
        st.markdown(f"**총 평가액:** {total_value:,.0f} 원")
        st.markdown('---')

        st.subheader("💡 Step2. 리밸런싱 계산하기")
        st.markdown("- 아래에 추가 납입액 (원)을 입력하고 '🧮리밸런싱 계산' 버튼을 클릭해 주세요.")
        st.markdown("- 추가 납입액이 없는데 총 조정 금액이 +플러스라면, 추가 납입을 하거나 매수하는 조정수량 임의 조정이 필요합니다.")
        # 월별 납입액 입력 (천 단위 콤마 표시)
        monthly_contrib_input = st.text_input("**추가 납입액 (원)**", value="0")
        # 입력값에서 콤마 제거 후 숫자로 변환
        try:
            monthly_contrib = float(monthly_contrib_input.replace(',', ''))
        except:
            monthly_contrib = 0.0
        # 변환된 값을 다시 콤마 포함 문자열로 포맷
        formatted_contrib = f"{monthly_contrib:,.0f}"
        # 화면에 포맷된 값을 표시 (읽기 전용)
        st.markdown(f"입력된 납입액: {formatted_contrib} 원")

        # Rebalance calculation
        include_contrib = st.checkbox('리밸런싱에 추가 납입액 반영하여 계산할지 체크', value=True)
        if st.button('🧮리밸런싱 계산'): 
            # 월별 납입액을 포함한 조정 총액
            adjusted_total_value = total_value + (monthly_contrib if include_contrib else 0)

            # 리밸런싱 목표 금액은 납입액이 반영된 총 금액 기준
            target_value = adjusted_total_value * portfolio['weight']
            target_qty = (target_value / portfolio['price']).fillna(0).round(0).astype(int)
            adjust_qty = (target_qty - portfolio['qty']).round(0).astype(int)
            result = portfolio.copy()

            # 원래 비중(업로드한 weight 그대로)
            result['orig_weight'] = result['weight']

            # 조정 후 평가액
            result['final_value'] = target_qty * result['price']

            # 조정 후 비중
            result['final_weight'] = result['final_value'] / result['final_value'].sum()

            # 비중 편차 (조정 후 비중 - 원래 비중)
            result['weight_diff'] = result['final_weight'] - result['orig_weight']

            result['orig_weight'] = result['weight']
            result['price'] = result['price'].round().astype(int)
            result['qty'] = result['qty'].round().astype(int)
            result['target_qty'] = target_qty
            result['adjust_qty'] = adjust_qty
            result['adjust_value'] = (result['adjust_qty'] * result['price']).astype(int)
            result['direction'] = result['adjust_qty'].apply(lambda x: '📈' if x > 0 else ('📉' if x < 0 else ''))
            result['adjust_qty_display'] = result['direction'] + ' ' + result['adjust_qty'].astype(str)
            result['adjust_qty_display'] = result.apply(lambda row: f"{row['direction']} {row['adjust_qty']:+}" , axis=1)
            # 저장을 위해 세션에 최근 계산 결과 보관
            st.session_state['last_result'] = result
            st.session_state['last_total_value'] = float(total_value)
            st.session_state['last_monthly_contrib'] = float(monthly_contrib)
            st.markdown("**📋 리밸런싱 결과**")
            st.dataframe(
                result[['ticker','name','price','qty','target_qty','adjust_qty_display','final_weight','orig_weight',
                        'adjust_value']]
                .rename(columns={
                    'ticker': '종목코드',
                    'name': '종목명',
                    'price': '가격',
                    'qty': '보유수량',
                    'target_qty': '목표수량',
                    'adjust_qty_display': '조정수량',
                    'final_weight': '조정 후 비중',
                    'orig_weight': '(목표 비중)',
                    'adjust_value': '조정금액'
                })
                .style.format({
                    '가격': '{:,.0f}',
                    '보유수량': '{:,.0f}',
                    '(목표 비중)': '({:.2%})',
                    '조정 후 비중': '{:.2%}',
                    '목표수량': '{:,.0f}',
                    '조정금액': '{:,.0f}'
                })
            )
            st.markdown('---')
            st.write('총 조정(매수:+, 매도:-) 금액:', f"{result['adjust_value'].sum():,.0f} 원")
