import streamlit as st
import pandas as pd
import hashlib
import os
import json
from typing import List, Dict

# 数据文件路径
DATA_DIR = "data"
PLAYERS_FILE = os.path.join(DATA_DIR, "players.csv")
TEAMS_FILE = os.path.join(DATA_DIR, "teams.json")
os.makedirs(DATA_DIR, exist_ok=True)

# 游戏职业列表（根据您的CSV文件）
GAME_CLASSES = [
    '大理', '峨眉', '丐帮', '明教', '天山',
    '无尘', '武当', '逍遥', '星宿', '玄机'
]

# 管理员密码
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()


# ----------------------------
# 数据持久化函数
# ----------------------------
def load_players() -> pd.DataFrame:
    """加载玩家数据"""
    if os.path.exists(PLAYERS_FILE):
        df = pd.read_csv(PLAYERS_FILE, encoding='utf-8-sig')
        if '已选择' not in df.columns:
            df['已选择'] = False
        return df
    return pd.DataFrame(columns=['游戏ID', '游戏职业', '已选择'])


def load_teams() -> List[Dict]:
    """加载队伍数据"""
    if os.path.exists(TEAMS_FILE):
        with open(TEAMS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_data():
    """保存所有数据"""
    st.session_state.players.to_csv(PLAYERS_FILE, index=False, encoding='utf-8-sig')
    with open(TEAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.teams, f, ensure_ascii=False)


# ----------------------------
# 核心功能函数
# ----------------------------
def initialize_data():
    """初始化数据"""
    if 'players' not in st.session_state:
        st.session_state.players = load_players()
    if 'teams' not in st.session_state:
        st.session_state.teams = load_teams()
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False


def check_admin_password():
    """管理员登录验证"""
    with st.sidebar:
        st.header("管理员登录")
        password = st.text_input("密码:", type="password", key="admin_pwd")
        if st.button("登录"):
            if hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD_HASH:
                st.session_state.admin_logged_in = True
                st.success("登录成功!")
                st.rerun()
            else:
                st.error("密码错误!")
        if st.session_state.admin_logged_in and st.button("退出"):
            st.session_state.admin_logged_in = False
            st.rerun()


def update_player_selection(selected_indices: List[int]):
    """更新玩家选择状态"""
    st.session_state.players['已选择'] = False
    for idx in selected_indices:
        st.session_state.players.at[idx, '已选择'] = True
    save_data()


def create_team(team_members: List[str], captain: str) -> bool:
    """创建队伍"""
    if len(team_members) != 6:
        st.error("队伍需要6名成员!")
        return False

    # 检查成员是否已被选择
    selected_players = {m for team in st.session_state.teams for m in team['成员']}
    if any(m in selected_players for m in team_members):
        st.error("有成员已被其他队伍选中!")
        return False

    st.session_state.teams.append({
        '队长': captain,
        '成员': team_members
    })

    selected_indices = st.session_state.players[
        st.session_state.players['游戏ID'].isin(team_members)
    ].index.tolist()
    update_player_selection(selected_indices)
    st.success("组队成功!")
    return True


# ----------------------------
# 管理员后台
# ----------------------------
def admin_panel():
    """管理员界面"""
    st.header("📊 管理员后台")

    tab1, tab2 = st.tabs(["玩家管理", "队伍管理"])

    with tab1:
        st.subheader("玩家名单管理")

        # 添加新玩家
        with st.expander("添加玩家", expanded=True):
            cols = st.columns(2)
            with cols[0]:
                new_id = st.text_input("游戏ID", key="new_id")
            with cols[1]:
                new_class = st.selectbox("职业", GAME_CLASSES, key="new_class")
            if st.button("添加"):
                if new_id:
                    new_player = pd.DataFrame({
                        '游戏ID': [new_id],
                        '游戏职业': [new_class],
                        '已选择': [False]
                    })
                    st.session_state.players = pd.concat(
                        [st.session_state.players, new_player],
                        ignore_index=True
                    )
                    save_data()
                    st.success(f"已添加: {new_id}")
                    st.rerun()

        # 玩家列表编辑
        st.subheader("当前玩家")
        edited_df = st.data_editor(
            st.session_state.players,
            num_rows="dynamic",
            column_config={
                "游戏ID": st.column_config.TextColumn(width="medium"),
                "游戏职业": st.column_config.SelectboxColumn(options=GAME_CLASSES),
                "已选择": st.column_config.CheckboxColumn(disabled=True)
            }
        )

        if st.button("保存修改"):
            st.session_state.players = edited_df
            save_data()
            st.success("已保存!")

        if st.button("重置选择状态"):
            st.session_state.players['已选择'] = False
            save_data()
            st.success("已重置!")

    with tab2:
        st.subheader("队伍管理")
        if not st.session_state.teams:
            st.info("暂无队伍")
            return

        for i, team in enumerate(st.session_state.teams, 1):
            with st.expander(f"队伍{i}-队长:{team['队长']}"):
                members_info = []
                for member in team['成员']:
                    player = st.session_state.players[
                        st.session_state.players['游戏ID'] == member
                        ]
                    members_info.append({
                        '游戏ID': member,
                        '游戏职业': player['游戏职业'].values[0] if not player.empty else "未知"
                    })

                df = pd.DataFrame(members_info)
                df.insert(0, '角色', ['队长'] + ['队员'] * (len(members_info) - 1))
                st.dataframe(df, hide_index=True)

                if st.button(f"解散队伍{i}", key=f"disband_{i}"):
                    for member in team['成员']:
                        mask = st.session_state.players['游戏ID'] == member
                        st.session_state.players.loc[mask, '已选择'] = False
                    st.session_state.teams.pop(i - 1)
                    save_data()
                    st.rerun()


# ----------------------------
# 主页面
# ----------------------------
def main_page():
    """主界面"""
    st.title("🎮 游戏组队系统")

    # 玩家列表
    st.header("👥 玩家名单")
    st.dataframe(
        st.session_state.players.style.apply(
            lambda row: ['background: #f5f5f5'] * len(row) if row['已选择'] else [''] * len(row),
            axis=1
        ),
        hide_index=True,
        use_container_width=True
    )

    # 组队表单
    st.header("🛠️ 创建队伍")

    # 队长选择
    captain = st.selectbox(
        "选择队长:",
        options=st.session_state.players[~st.session_state.players['已选择']]['游戏ID'],
        key='captain'
    )

    # 队员选择
    available = st.session_state.players[
        (~st.session_state.players['已选择']) &
        (st.session_state.players['游戏ID'] != captain)
        ]['游戏ID']
    selected = st.multiselect("选择5名队员:", options=available, key='members')

    # 显示队伍预览
    if captain and selected:
        st.subheader("队伍预览")
        team = pd.DataFrame({
            '角色': ['队长'] + ['队员'] * 5,
            '游戏ID': [captain] + selected,
            '游戏职业': [
                st.session_state.players[
                    st.session_state.players['游戏ID'] == id
                    ]['游戏职业'].values[0] for id in [captain] + selected
            ]
        })
        st.dataframe(team, hide_index=True)

    # 提交按钮
    if st.button("✅ 确认组队"):
        if len(selected) == 5:
            if create_team([captain] + selected, captain):
                st.rerun()
        else:
            st.error("请选择5名队员!")


# ----------------------------
# 主程序
# ----------------------------
def main():
    initialize_data()
    check_admin_password()

    if st.session_state.admin_logged_in:
        admin_panel()
    else:
        main_page()


if __name__ == "__main__":
    main()