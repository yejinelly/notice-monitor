"""Public subscription form for Notice Monitor Agent."""
import streamlit as st

from src.database import save_subscription
from src.fetchers import fetch_notices
from src.filters import filter_notices
from src.pilot import end_message, is_active

st.set_page_config(page_title="Notice Monitor Agent", page_icon="🔔")
st.title("🔔 Notice Monitor Agent")
st.caption("학과·대학·외부기관 공지에서 관심 있는 새 공지만 이메일로 알려드립니다.")

if not is_active():
    st.info(end_message() + " 이 저장소를 복제해 개인용 Agent로 계속 운영할 수 있습니다.")
    st.stop()


def words(value: str) -> list[str]:
    return [word.strip() for word in value.split(",") if word.strip()]


with st.form("subscription"):
    st.subheader("새 공지 알림 등록")
    email = st.text_input("알림을 받을 이메일", placeholder="you@example.com")
    site_name = st.text_input("추적할 채널 이름", placeholder="예: 학과 공지사항, 대학 장학금 게시판, 기관 사업공고")
    site_url = st.text_input("공지 페이지 또는 RSS 주소", placeholder="https://...")
    keywords_text = st.text_input("관심 키워드", placeholder="예: 장학, 대학원")
    schedule_label = st.selectbox("알림 시간", ["매일 오전 10시", "매일 오후 2시", "매일 오전 10시와 오후 2시"])
    submitted = st.form_submit_button("알림 등록", type="primary")
    previewed = st.form_submit_button("등록 전 공지 미리보기")

selectors = {"item": "tr", "title": "a", "date": "time, .date"}
site_url = site_url.strip()

if submitted:
    if not email or "@" not in email:
        st.error("알림을 받을 유효한 이메일 주소를 입력하세요.")
    elif not site_name or not site_url.startswith(("https://", "http://")):
        st.error("채널 이름과 올바른 공지 주소를 입력하세요.")
    else:
        subscription = {
            "email": email.strip(), "site_name": site_name.strip(), "site_url": site_url.strip(),
            "site_type": "auto",
            "keywords": {"any": words(keywords_text), "all": []},
            "selectors": selectors,
            "frequency": {
                "매일 오전 10시": "schedule_10",
                "매일 오후 2시": "schedule_14",
                "매일 오전 10시와 오후 2시": "schedule_10_14",
            }[schedule_label],
        }
        try:
            save_subscription(subscription)
            st.success("알림을 등록했습니다. 첫 정기 실행 때 등록 확인 메일을 받고, 그다음부터 새 공지를 이메일로 받아봅니다.")
        except Exception:
            st.error("현재 등록을 저장할 수 없습니다. 잠시 후 다시 시도해 주세요.")

st.divider()
st.subheader("등록 전 공지 미리보기")
st.caption("위 입력값으로 공지를 수집합니다. 키워드를 쉼표로 여러 개 입력하면 하나라도 포함된 공지를 보여줍니다. 미리보기는 구독 기록을 저장하지 않습니다.")
if previewed:
    if not site_url.startswith(("https://", "http://")):
        st.warning("먼저 공지 주소를 입력하세요.")
    else:
        site = {
            "url": site_url, "type": "auto",
            "selectors": selectors,
        }
        try:
            with st.spinner("공지사항을 불러오고 있습니다..."):
                fetched = fetch_notices(site)
                notices = filter_notices(fetched, {"any": words(keywords_text), "all": []})
            st.write(f"전체 공지 {len(fetched)}건 중 조건에 맞는 공지 {len(notices)}건")
            for notice in notices[:20]:
                st.markdown(f"**{notice['title']}**")
                st.caption(notice.get("date") or "날짜 정보 없음")
                st.link_button("원문 보기", notice["link"])
        except Exception as error:
            st.error(f"공지 확인에 실패했습니다: {error}")

st.divider()
st.caption("등록된 이메일과 구독 설정은 공지 알림 목적으로만 사용됩니다. 이 파일럿은 2026년 10월 30일까지 운영되며, 종료 후 구독 데이터는 삭제합니다.")
