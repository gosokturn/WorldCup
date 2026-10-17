import random
import uuid
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client


st.set_page_config(
    page_title="급식 월드컵",
    page_icon="🍱",
    layout="wide",
)

MENUS = [
    "제육볶음",
    "간장찜닭",
    "가자미순살튀김",
    "돈육불백",
    "미트볼데리야끼볶음",
    "수육",
    "진미채고추장볶음",
    "치즈떡닭갈비",
]
ROUND_NAMES = ["8강", "4강", "결승"]
PAGE_SIZE = 1000
DUEL_COLUMNS = [
    "id", "game_id", "round", "left_menu",
    "right_menu", "winner",
]


@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def initialize_game():
    st.session_state.game_id = str(uuid.uuid4())
    st.session_state.pool = random.sample(MENUS, len(MENUS))
    st.session_state.round_index = 0
    st.session_state.match_index = 0
    st.session_state.winners = []
    st.session_state.champion = None
    st.session_state.finished = False
    st.session_state.blocked = False
    st.session_state.error_message = None
    st.session_state.confirmed_matches = 0


def save_duel(left_menu, right_menu, winner, round_name):
    payload = {
        "game_id": st.session_state.game_id,
        "round": round_name,
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    try:
        response = (
            get_supabase()
            .table("menu_duels")
            .insert(payload)
            .execute()
        )
        rows = response.data

        if not isinstance(rows, list) or len(rows) != 1:
            return False, "저장된 행을 확인할 수 없습니다."

        saved = rows[0]
        for column, expected in payload.items():
            if saved.get(column) != expected:
                return False, "저장 결과가 입력값과 일치하지 않습니다."

        return True, None
    except Exception:
        return False, (
            "데이터베이스 오류로 저장 결과를 확인하지 못했습니다."
        )


def choose_menu(winner):
    if st.session_state.blocked or st.session_state.finished:
        return

    pool = st.session_state.pool
    match_index = st.session_state.match_index
    round_index = st.session_state.round_index
    left_menu = pool[match_index * 2]
    right_menu = pool[match_index * 2 + 1]

    if winner not in (left_menu, right_menu):
        st.session_state.blocked = True
        st.session_state.error_message = (
            "선택 결과를 확인할 수 없습니다. 교사의 확인이 필요합니다."
        )
        return

    success, error = save_duel(
        left_menu,
        right_menu,
        winner,
        ROUND_NAMES[round_index],
    )

    if not success:
        st.session_state.blocked = True
        st.session_state.error_message = (
            f"{error} 재선택하지 말고 교사의 확인을 받아 주세요."
        )
        return

    st.session_state.confirmed_matches += 1
    st.session_state.winners.append(winner)

    if match_index + 1 < len(pool) // 2:
        st.session_state.match_index += 1
        return

    if round_index < len(ROUND_NAMES) - 1:
        st.session_state.pool = st.session_state.winners
        st.session_state.winners = []
        st.session_state.round_index += 1
        st.session_state.match_index = 0
    else:
        st.session_state.champion = winner
        st.session_state.finished = True


def load_all_duels():
    """Read all existing duel rows in pages; do not modify the table."""
    client = get_supabase()
    all_rows = []
    offset = 0

    while True:
        response = (
            client.table("menu_duels")
            .select("id,game_id,round,left_menu,right_menu,winner")
            .order("id")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = response.data

        if not isinstance(rows, list):
            raise RuntimeError("조회 결과 형식이 올바르지 않습니다.")

        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return pd.DataFrame(all_rows, columns=DUEL_COLUMNS)


def show_analysis():
    st.title("📊 학급 전체 급식 월드컵 분석")
    st.write("저장된 전체 대결 기록으로 반찬별 성적을 비교한다.")

    st.info(
        "진행 중인 판의 대결도 집계에 포함된다. 대결 기록 수는 "
        "참여 인원 수가 아니며, 한 판의 각 대결은 별도 기록으로 계산한다."
    )

    # 버튼을 누르면 Streamlit이 다시 실행되고 아래에서 DB를 다시 조회한다.
    st.button(
        "🔄 분석 결과 다시 불러오기",
        key="refresh_analysis",
        use_container_width=True,
    )

    try:
        df = load_all_duels()
    except Exception:
        st.error(
            "대결 기록을 조회하지 못했습니다. 인터넷 연결, Supabase "
            "접속 정보, 테이블 권한을 확인해 주세요."
        )
        st.caption(
            "조회 실패와 기록이 없는 상태는 서로 다르므로, "
            "조회 실패 시 통계를 0으로 표시하지 않습니다."
        )
        return

    record_count = len(df)
    game_count = df["game_id"].dropna().nunique() if record_count else 0

    col1, col2 = st.columns(2)
    col1.metric("집계 대결 기록 수", f"{record_count:,}건")
    col2.metric("집계 판 수", f"{game_count:,}판")

    st.caption(
        "기록 수와 참여 인원은 다르며, 진행 중에 저장한 대결도 집계된다."
    )

    if df.empty:
        st.warning(
            "아직 저장된 대결 기록이 없습니다. 대결이 저장되면 "
            "이 화면에서 반찬별 성적을 확인할 수 있습니다."
        )
        return

    duel_counts = Counter()
    win_counts = Counter()
    champion_counts = Counter()

    for _, row in df.iterrows():
        left_menu = row["left_menu"]
        right_menu = row["right_menu"]
        winner = row["winner"]

        if left_menu in MENUS:
            duel_counts[left_menu] += 1
        if right_menu in MENUS:
            duel_counts[right_menu] += 1
        if winner in MENUS:
            win_counts[winner] += 1
            if row["round"] == "결승":
                champion_counts[winner] += 1

    stats = []
    for menu in MENUS:
        duels = duel_counts[menu]
        wins = win_counts[menu]
        rate = wins / duels * 100 if duels else None
        stats.append({
            "반찬": menu,
            "대결 수": duels,
            "승리 수": wins,
            "승률(%)": rate,
            "우승 횟수": champion_counts[menu],
        })

    result = pd.DataFrame(stats).sort_values(
        by=["승률(%)", "승리 수", "대결 수"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    st.subheader("🏆 반찬별 성적표")
    display_df = result.copy()
    display_df["승률"] = display_df["승률(%)"].map(
        lambda value: f"{value:.1f}%" if pd.notna(value) else "아직 알 수 없음"
    )
    display_df = display_df[
        ["반찬", "대결 수", "승리 수", "승률", "우승 횟수"]
    ]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.caption(
        "승률 = 승리 수 ÷ 대결 수 × 100. 우승 횟수는 round가 "
        "'결승'인 기록의 winner를 집계한다. 대결 기록이 없는 후보의 "
        "승률은 0%가 아니라 아직 알 수 없음으로 표시한다."
    )

    st.subheader("📈 반찬별 승률 비교")
    chart_df = result[result["승률(%)"].notna()].copy()

    if chart_df.empty:
        st.warning("승률을 계산할 수 있는 대결 기록이 아직 없습니다.")
    else:
        chart_df = chart_df.sort_values("승률(%)", ascending=True)
        fig = px.bar(
            chart_df,
            x="승률(%)",
            y="반찬",
            orientation="h",
            text="승률(%)",
            labels={"승률(%)": "승률 (%)", "반찬": "반찬"},
            title="반찬별 승률",
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            cliponaxis=False,
        )
        max_rate = float(chart_df["승률(%)"].max())
        fig.update_layout(
            xaxis_title="승률 (%)",
            yaxis_title="",
            xaxis=dict(range=[0, min(110, max(10, max_rate * 1.2))]),
            yaxis=dict(
                categoryorder="array",
                categoryarray=chart_df["반찬"].tolist(),
            ),
            margin=dict(l=20, r=50, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    missing = result.loc[result["대결 수"] == 0, "반찬"].tolist()
    if missing:
        st.info(
            "아직 대결 기록이 없어 승률을 알 수 없는 반찬: "
            + ", ".join(missing)
        )

    st.subheader("🥇 결승 우승 횟수")
    champion_df = result[["반찬", "우승 횟수"]].sort_values(
        "우승 횟수", ascending=False
    )
    st.dataframe(champion_df, use_container_width=True, hide_index=True)


# ---------- 초기화 및 화면 선택 ----------

try:
    if not st.secrets["SUPABASE_URL"] or not st.secrets["SUPABASE_KEY"]:
        raise ValueError("Supabase 설정이 비어 있습니다.")
except Exception:
    st.error(
        "Supabase 접속 설정을 확인할 수 없습니다. "
        "교사가 Secrets 설정을 확인해 주세요."
    )
    st.stop()

if "game_id" not in st.session_state:
    initialize_game()

if "view" not in st.session_state:
    st.session_state.view = "월드컵"

# 화면 선택은 한 번만 표시한다. 아래에서 선택한 화면 하나만 렌더링한다.
st.radio(
    "화면 선택",
    ["월드컵", "학급 전체 기록 분석"],
    horizontal=True,
    key="view",
)

if st.session_state.view == "학급 전체 기록 분석":
    show_analysis()
    st.stop()

# ---------- 월드컵 화면만 렌더링 ----------

st.title("🍱 급식 월드컵")
st.write("오늘의 급식 반찬 최강자를 뽑아 보자!")
st.caption("8강 4경기 · 4강 2경기 · 결승 1경기 | 총 7번 선택")

if st.session_state.blocked:
    st.error("⛔ 대결이 중단되었습니다.")
    st.warning(
        st.session_state.error_message
        or "저장 결과 확인이 필요합니다. 교사에게 문의해 주세요."
    )
    st.info(
        "중복 저장을 방지하기 위해 재선택할 수 없습니다. "
        "교사가 데이터베이스 기록을 확인해야 합니다."
    )
    st.stop()

if st.session_state.finished:
    st.balloons()
    st.success("🏆 오늘의 급식 월드컵 우승!")
    st.markdown(
        f"<h1 style='text-align:center; font-size:42px;'>"
        f"🍽️ {st.session_state.champion}</h1>",
        unsafe_allow_html=True,
    )
    st.write("이번 판의 7경기는 모두 저장 결과가 확인되었습니다.")

    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "🔄 새 월드컵 시작하기",
            key="start_new_game",
            use_container_width=True,
            on_click=initialize_game,
        )
    with col2:
        if st.button(
            "📊 학급 전체 기록 분석 보기",
            key="open_analysis_from_champion",
            use_container_width=True,
        ):
            st.session_state.view = "학급 전체 기록 분석"
            st.rerun()
    st.stop()

round_index = st.session_state.round_index
match_index = st.session_state.match_index
pool = st.session_state.pool
round_name = ROUND_NAMES[round_index]
total_matches = len(pool) // 2
left_menu = pool[match_index * 2]
right_menu = pool[match_index * 2 + 1]

st.divider()
col1, col2, col3 = st.columns(3)
col1.metric("현재 라운드", round_name)
col2.metric("현재 경기", f"{match_index + 1} / {total_matches}")
col3.metric(
    "저장 확인된 경기",
    f"{st.session_state.confirmed_matches} / 7",
)
st.progress(st.session_state.confirmed_matches / 7)

st.subheader(f"⚔️ {round_name} {match_index + 1}경기")
st.write("더 먹고 싶은 반찬 하나를 선택해 줘!")

left_col, vs_col, right_col = st.columns([5, 1, 5])

with left_col:
    st.markdown(
        "<div style='text-align:center; font-size:68px;'>🍚</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; font-size:25px;"
        f"font-weight:bold; min-height:70px;'>{left_menu}</div>",
        unsafe_allow_html=True,
    )
    st.button(
        f"🍴 {left_menu} 선택",
        key=f"choose_left_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(left_menu,),
    )

with vs_col:
    st.markdown("<div style='height:95px;'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align:center;'>VS</h2>", unsafe_allow_html=True)

with right_col:
    st.markdown(
        "<div style='text-align:center; font-size:68px;'>🍱</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='text-align:center; font-size:25px;"
        f"font-weight:bold; min-height:70px;'>{right_menu}</div>",
        unsafe_allow_html=True,
    )
    st.button(
        f"🍴 {right_menu} 선택",
        key=f"choose_right_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(right_menu,),
    )

st.divider()
st.caption(
    "선택 결과는 데이터베이스에 저장되고, "
    "저장 여부가 확인된 경우에만 다음 경기로 넘어갑니다."
)
