"""Public subscription form for Notice Monitor Agent."""
import streamlit as st

from src.database import save_subscription
from src.fetchers import fetch_notices
from src.filters import filter_notices

st.set_page_config(page_title="Notice Monitor Agent", page_icon="🔔")
st.title("🔔 Notice Monitor Agent")
st.caption("학과·대학·외부기관 공지에서 관심 있는 새 공지만 이메일로 알려드립니다.")


def words(value: str) -> list[str]:
    return [word.strip() for word in value.split(",") if word.strip()]


with st.form("subscription"):
    st.subheader("새 공지 알림 등록")
    email = st.text_input("알림을 받을 이메일", placeholder="you@example.com")
    site_name = st.text_input("추적할 채널 이름", placeholder="예: 학과 공지사항, 대학 장학금 게시판, 기관 사업공고")
    site_url = st.text_input("공지 페이지 또는 RSS 주소", placeholder="https://...")
    site_type = st.radio("공지 형식", ["RSS", "일반 웹 게시판"], horizontal=True)
    any_keywords = st.text_input("관심 키워드", placeholder="장학, 대학원, 연구비, 공모")
    all_keywords = st.text_input("반드시 포함할 키워드 (선택)", placeholder="예: 장학")
    frequency_label = st.selectbox("알림 주기", ["정기 실행마다 확인", "하루 한 번 확인"])
    with st.expander("일반 웹 게시판의 고급 설정"):
        st.caption("사이트별 HTML 구조가 다른 경우 CSS 선택자를 입력하세요. RSS에는 필요하지 않습니다.")
        item_selector = st.text_input("게시글 묶음 선택자", value="tr")
        title_selector = st.text_input("제목·링크 선택자", value="a")
        date_selector = st.text_input("날짜 선택자", value="time, .date")
    submitted = st.form_submit_button("알림 등록", type="primary")

if submitted:
    if not email or "@" not in email:
        st.error("알림을 받을 유효한 이메일 주소를 입력하세요.")
    elif not site_name or not site_url.startswith(("https://", "http://")):
        st.error("채널 이름과 올바른 공지 주소를 입력하세요.")
    else:
        subscription = {
            "email": email.strip(), "site_name": site_name.strip(), "site_url": site_url.strip(),
            "site_type": "rss" if site_type == "RSS" else "html",
            "keywords": {"any": words(any_keywords), "all": words(all_keywords)},
            "selectors": {"item": item_selector, "title": title_selector, "date": date_selector},
            "frequency": "every_run" if frequency_label == "정기 실행마다 확인" else "daily",
        }
        save_subscription(subscription)
        st.success("알림을 등록했습니다. 첫 정기 실행은 현재 공지를 기준 목록으로 저장하고, 다음 실행부터 새 공지만 이메일로 보냅니다.")

st.divider()
st.subheader("등록 전 공지 미리보기")
st.caption("등록하려는 주소와 키워드가 잘 작동하는지 확인할 수 있습니다. 미리보기는 구독 기록을 저장하지 않습니다.")
if st.button("입력한 조건으로 확인하기"):
    if not site_url.startswith(("https://", "http://")):
        st.warning("먼저 공지 주소를 입력하세요.")
    else:
        site = {
            "url": site_url, "type": "rss" if site_type == "RSS" else "html",
            "selectors": {"item": item_selector, "title": title_selector, "date": date_selector},
        }
        try:
            with st.spinner("공지사항을 불러오고 있습니다..."):
                notices = filter_notices(fetch_notices(site), {"any": words(any_keywords), "all": words(all_keywords)})
            st.write(f"조건에 맞는 공지 {len(notices)}건")
            for notice in notices[:20]:
                st.markdown(f"**{notice['title']}**")
                st.caption(notice.get("date") or "날짜 정보 없음")
                st.link_button("원문 보기", notice["link"])
        except Exception as error:
            st.error(f"공지 확인에 실패했습니다: {error}")

st.divider()
st.caption("등록된 이메일과 구독 설정은 공지 알림 목적으로만 사용됩니다. 구독 해지·관리 기능은 다음 버전에서 제공합니다.")
