
import random
import uuid

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


@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


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
    """대결 한 건을 저장하고 반환된 행을 검증한다."""
    payload = {
        "game_id": st.session_state.game_id,
        "round": round_name,
        "left_menu": left_menu,
        "right_menu": right_menu,
        "winner": winner,
    }

    try:
        client = get_supabase()

        # 기존 public.menu_duels 테이블에만 INSERT한다.
        # id와 created_at은 데이터베이스 기본값에 맡긴다.
        response = (
            client.table("menu_duels")
            .insert(payload)
            .execute()
        )

        rows = response.data

        # 반환된 저장 결과가 없거나, 저장한 내용과 다르면
        # 성공으로 간주하지 않는다.
        if not isinstance(rows, list) or len(rows) != 1:
            return False, "저장된 행을 확인할 수 없습니다."

        saved = rows[0]

        for column, expected in payload.items():
            if saved.get(column) != expected:
                return False, f"저장 결과의 '{column}' 값이 일치하지 않습니다."

        return True, None

    except Exception:
        # 오류 세부 정보나 접속 정보는 화면에 노출하지 않는다.
        return False, "데이터베이스 오류로 저장 결과를 확인하지 못했습니다."


def choose_menu(winner):
    """저장이 확인된 경우에만 다음 대결로 이동한다."""
    if st.session_state.blocked or st.session_state.finished:
        return

    pool = st.session_state.pool
    match_index = st.session_state.match_index
    round_index = st.session_state.round_index

    left_menu = pool[match_index * 2]
    right_menu = pool[match_index * 2 + 1]

    # 현재 화면에 제시된 두 후보 중 하나인지 검증한다.
    if winner not in (left_menu, right_menu):
        st.session_state.blocked = True
        st.session_state.error_message = (
            "선택 결과를 확인할 수 없습니다. 교사의 확인이 필요합니다."
        )
        return

    round_name = ROUND_NAMES[round_index]

    # 먼저 저장하고, 성공이 확인된 후에만 승자를 반영한다.
    success, error = save_duel(
        left_menu,
        right_menu,
        winner,
        round_name,
    )

    if not success:
        st.session_state.blocked = True
        st.session_state.error_message = (
            f"{error} 대결을 중단했습니다. "
            "재선택할 수 없으며 교사의 확인이 필요합니다."
        )
        return

    # 저장이 확인된 대결만 진행 상황에 반영한다.
    st.session_state.confirmed_matches += 1
    st.session_state.winners.append(winner)

    if match_index + 1 < len(pool) // 2:
        st.session_state.match_index += 1
        return

    # 현재 라운드가 끝났으면 다음 라운드로 진출한다.
    if round_index < len(ROUND_NAMES) - 1:
        st.session_state.pool = st.session_state.winners
        st.session_state.winners = []
        st.session_state.round_index += 1
        st.session_state.match_index = 0
    else:
        st.session_state.champion = winner
        st.session_state.finished = True


# ---------- 화면 ----------

st.title("🍱 급식 월드컵")
st.write("오늘의 급식 반찬 최강자를 뽑아 보자!")

st.caption(
    "8강 4경기 · 4강 2경기 · 결승 1경기 | 총 7번 선택"
)

# 비밀 금고 설정 확인
try:
    if not st.secrets["SUPABASE_URL"] or not st.secrets["SUPABASE_KEY"]:
        raise ValueError("Supabase 설정이 비어 있습니다.")
except Exception:
    st.error(
        "Supabase 접속 설정을 확인할 수 없습니다. "
        "교사가 secrets 설정을 확인해 주세요."
    )
    st.stop()

if "game_id" not in st.session_state:
    initialize_game()

# 차단 상태에서는 어떤 대결도 더 진행하지 않는다.
if st.session_state.blocked:
    st.error("⛔ 대결이 중단되었습니다.")
    st.warning(
        st.session_state.error_message
        or "저장 결과 확인이 필요합니다. 교사에게 문의해 주세요."
    )
    st.info(
        "중복 저장을 방지하기 위해 이 화면에서는 재선택할 수 없습니다. "
        "교사가 데이터베이스 기록을 확인해야 합니다."
    )
    st.stop()

# 우승 결과
if st.session_state.finished:
    st.balloons()
    st.success("🏆 오늘의 급식 월드컵 우승!")
    st.markdown(
        f"<h1 style='text-align:center; font-size:42px;'>"
        f"🍽️ {st.session_state.champion}</h1>",
        unsafe_allow_html=True,
    )
    st.write("총 7경기의 저장 결과가 모두 확인되었습니다.")
    st.button(
        "🔄 새 월드컵 시작하기",
        use_container_width=True,
        on_click=initialize_game,
    )
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
col3.metric("저장 확인된 경기", f"{st.session_state.confirmed_matches} / 7")

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
        key=f"left_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(left_menu,),
    )

with vs_col:
    st.markdown("<div style='height:95px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align:center;'>VS</h2>",
        unsafe_allow_html=True,
    )

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
        key=f"right_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(right_menu,),
    )

st.divider()
st.caption(
    "선택 결과는 데이터베이스에 저장되고, "
    "저장 여부가 확인된 경우에만 다음 경기로 넘어갑니다."
)

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

COLUMNS = [
    "id",
    "game_id",
    "round",
    "left_menu",
    "right_menu",
    "winner",
]


@st.cache_resource
def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def load_all_duels():
    """기존 테이블의 전체 기록을 페이지 단위로 조회한다."""
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

    return pd.DataFrame(all_rows, columns=COLUMNS)


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
    """저장된 행과 입력값이 일치하는지 검증한다."""
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
    """저장이 확인된 뒤에만 다음 경기로 진행한다."""
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


def show_analysis():
    st.title("📊 학급 전체 급식 월드컵 분석")
    st.write(
        "저장된 전체 대결 기록을 바탕으로 반찬별 성적을 비교한다."
    )

    st.info(
        "진행 중인 판의 대결도 집계에 포함된다. "
        "대결 기록 수는 참여 인원 수가 아니며, "
        "한 판에서 발생한 여러 대결은 각각 기록으로 계산한다."
    )

    if st.button(
        "🔄 분석 결과 다시 불러오기",
        use_container_width=True,
    ):
        st.session_state.analysis_refreshed = True

    try:
        df = load_all_duels()
    except Exception:
        st.error(
            "대결 기록을 조회하지 못했습니다. "
            "인터넷 연결, Supabase 접속 정보, 테이블 권한을 확인해 주세요."
        )
        st.caption(
            "조회 실패와 기록이 없는 상태는 서로 다릅니다. "
            "조회가 실패한 경우 통계를 0으로 표시하지 않습니다."
        )
        return

    st.success("대결 기록 조회가 완료되었습니다.")

    if df.empty:
        st.warning(
            "아직 저장된 대결 기록이 없습니다. "
            "월드컵 대결이 저장되면 이곳에서 분석할 수 있습니다."
        )
        st.metric("집계 대결 기록 수", 0)
        st.metric("집계 판 수", 0)
        return

    # 한 판의 식별자는 game_id이다.
    # 결측 game_id는 판 수 계산에서 제외한다.
    record_count = len(df)
    game_count = df["game_id"].dropna().nunique()

    col1, col2 = st.columns(2)
    col1.metric("집계 대결 기록 수", f"{record_count:,}건")
    col2.metric("집계 판 수", f"{game_count:,}판")

    st.caption(
        "대결 기록 수와 참여 인원은 다르다. "
        "진행 중인 판에서 저장한 대결도 포함된다."
    )

    # 모든 후보를 먼저 등록해 기록이 없는 반찬도 표시한다.
    duel_counts = Counter()
    win_counts = Counter()
    champion_counts = Counter()

    for _, row in df.iterrows():
        left_menu = row["left_menu"]
        right_menu = row["right_menu"]
        winner = row["winner"]

        # 좌우 양쪽에 나온 반찬 모두 대결 1회로 계산한다.
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

        # 대결이 한 번도 없다면 승률은 0%가 아니라 알 수 없음이다.
        win_rate = wins / duels * 100 if duels > 0 else None

        stats.append({
            "반찬": menu,
            "대결 수": duels,
            "승리 수": wins,
            "승률(%)": win_rate,
            "우승 횟수": champion_counts[menu],
        })

    result = pd.DataFrame(stats)

    # 승률이 높은 순서, 동률이면 승리 수와 대결 수 순서로 정렬한다.
    result = result.sort_values(
        by=["승률(%)", "승리 수", "대결 수"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    st.subheader("🏆 반찬별 성적표")

    display_df = result.copy()
    display_df["승률"] = display_df["승률(%)"].apply(
        lambda value: (
            f"{value:.1f}%"
            if pd.notna(value)
            else "아직 알 수 없음"
        )
    )

    display_df = display_df[
        ["반찬", "대결 수", "승리 수", "승률", "우승 횟수"]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "승률 = 승리 수 ÷ 대결 수 × 100. "
        "우승 횟수는 round가 '결승'인 기록의 winner를 센 값이다. "
        "대결 기록이 없는 후보의 승률은 아직 알 수 없다."
    )

    st.subheader("📈 반찬별 승률 비교")

    # 승률을 계산할 수 있는 후보만 그래프에 표시한다.
    chart_df = result[result["승률(%)"].notna()].copy()

    if chart_df.empty:
        st.warning(
            "승률을 계산할 수 있는 대결 기록이 아직 없습니다. "
            "대결 기록이 쌓이면 그래프를 표시합니다."
        )
    else:
        # 수평 막대그래프에서 높은 승률이 위쪽에 오도록 정렬한다.
        chart_df = chart_df.sort_values("승률(%)", ascending=True)

        fig = px.bar(
            chart_df,
            x="승률(%)",
            y="반찬",
            orientation="h",
            text="승률(%)",
            labels={
                "승률(%)": "승률 (%)",
                "반찬": "반찬",
            },
            title="반찬별 승률",
        )

        fig.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="outside",
            cliponaxis=False,
        )

        fig.update_layout(
            xaxis_title="승률 (%)",
            yaxis_title="",
            xaxis=dict(
                range=[
                    0,
                    min(
                        110,
                        max(10, float(chart_df["승률(%)"].max()) * 1.2),
                    ),
                ],
            ),
            yaxis=dict(
                categoryorder="array",
                categoryarray=chart_df["반찬"].tolist(),
            ),
            margin=dict(l=20, r=50, t=60, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

        missing_menus = result.loc[
            result["대결 수"] == 0, "반찬"
        ].tolist()

        if missing_menus:
            st.info(
                "아직 대결 기록이 없어 승률을 알 수 없는 반찬: "
                + ", ".join(missing_menus)
            )

    st.subheader("🥇 결승 우승 횟수")

    champion_df = result[
        ["반찬", "우승 횟수"]
    ].sort_values(
        "우승 횟수",
        ascending=False,
    )

    st.dataframe(
        champion_df,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "우승 횟수는 결승 기록만 집계한다. "
        "현재까지의 기록에 따른 결과이며, "
        "모든 학생이 한 번씩 참여했다는 의미는 아니다."
    )


# ---------- 앱 시작 ----------

try:
    if (
        not st.secrets["SUPABASE_URL"]
        or not st.secrets["SUPABASE_KEY"]
    ):
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

if "analysis_refreshed" not in st.session_state:
    st.session_state.analysis_refreshed = False

st.radio(
    "화면 선택",
    ["월드컵", "학급 전체 기록 분석"],
    horizontal=True,
    key="view",
)

if st.session_state.view == "학급 전체 기록 분석":
    show_analysis()
    st.stop()

# ---------- 월드컵 화면 ----------

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

    if st.button("📊 학급 전체 기록 분석 보기"):
        st.session_state.view = "학급 전체 기록 분석"
        st.rerun()

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
            use_container_width=True,
            on_click=initialize_game,
        )

    with col2:
        if st.button(
            "📊 학급 전체 기록 분석 보기",
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
        key=f"left_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(left_menu,),
    )

with vs_col:
    st.markdown("<div style='height:95px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='text-align:center;'>VS</h2>",
        unsafe_allow_html=True,
    )

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
        key=f"right_{st.session_state.game_id}_{round_index}_{match_index}",
        use_container_width=True,
        on_click=choose_menu,
        args=(right_menu,),
    )

st.divider()
st.caption(
    "선택 결과는 데이터베이스에 저장되고, "
    "저장 여부가 확인된 경우에만 다음 경기로 넘어갑니다."
)
