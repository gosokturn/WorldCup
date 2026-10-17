
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
