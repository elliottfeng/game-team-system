import streamlit as st
import pandas as pd
import hashlib
import os
import json
import requests
import base64
import io
from datetime import datetime
from typing import List, Dict

# ========================
# 配置部分
# ========================
DATA_DIR = "data"
PLAYERS_FILE = os.path.join(DATA_DIR, "players.csv")
TEAMS_FILE = os.path.join(DATA_DIR, "teams.json")
os.makedirs(DATA_DIR, exist_ok=True)

# GitHub 配置
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]  # 替换为你的token
GITHUB_REPO = "elliottfeng/game-team-system"  # 替换为你的仓库名
GITHUB_BRANCH = "main"

# 游戏职业列表
GAME_CLASSES = [
    '大理', '峨眉', '丐帮', '明教', '天山',
    '无尘', '武当', '逍遥', '星宿', '玄机'
]

ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

# ========================
# GitHub 持久化模块
# ========================
def update_github_file(file_path: str, content: str, message: str):
    """通过GitHub API更新文件"""
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 1. 获取文件当前SHA（必须）
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        response = requests.get(url, headers=headers)
        sha = response.json().get("sha", "") if response.status_code == 200 else ""
        
        # 2. 更新文件
        data = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
            "sha": sha,
            "branch": GITHUB_BRANCH
        }
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code not in [200, 201]:
            st.error(f"GitHub同步失败: {response.json().get('message', '未知错误')}")
            return False
        return True
    except Exception as e:
        st.error(f"GitHub同步异常: {str(e)}")
        return False

def save_data_to_github():
    """保存所有数据到GitHub"""
    # 保存players.csv
    players_csv = st.session_state.players.to_csv(index=False, encoding='utf-8-sig')
    if not update_github_file(PLAYERS_FILE, players_csv, "Update players data"):
        return False
    
    # 保存teams.json
    teams_json = json.dumps(st.session_state.teams, ensure_ascii=False, indent=2)
    if not update_github_file(TEAMS_FILE, teams_json, "Update teams data"):
        return False
    
    st.success("数据已同步到GitHub!")
    return True

# ========================
# 数据加载模块
# ========================
def load_from_github(file_path: str):
    """从GitHub加载文件内容"""
    try:
        url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{file_path}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        st.error(f"加载{file_path}失败: {str(e)}")
    return None

def load_players() -> pd.DataFrame:
    """加载玩家数据"""
    content = load_from_github(PLAYERS_FILE)
    if content:
        try:
            df = pd.read_csv(io.StringIO(content))
            if '已选择' not in df.columns:
                df['已选择'] = False
            return df
        except Exception as e:
            st.error(f"解析玩家数据失败: {str(e)}")
    
    # 默认数据
    return pd.DataFrame(columns=['游戏ID', '游戏职业', '已选择'])

def load_teams() -> List[Dict]:
    """加载队伍数据"""
    content = load_from_github(TEAMS_FILE)
    if content:
        try:
            return json.loads(content)
        except Exception as e:
            st.error(f"解析队伍数据失败: {str(e)}")
    return []

# ========================
# 核心功能模块
# ========================
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

def create_team(team_members: List[str], captain: str) -> bool:
    """创建队伍"""
    try:
        if len(team_members) != 6:
            st.error("队伍需要6名成员!")
            return False
        
        # 验证所有成员存在
        for member in team_members:
            if member not in st.session_state.players['游戏ID'].values:
                st.error(f"玩家 {member} 不存在!")
                return False
        
        # 检查是否已被选择
        selected_players = {m for team in st.session_state.teams for m in team['成员']}
        if any(m in selected_players for m in team_members):
            st.error("有成员已被其他队伍选中!")
            return False
        
        # 添加到队伍列表
        st.session_state.teams.append({
            '队长': captain,
            '成员': team_members
        })
        
        # 更新选择状态
        mask = st.session_state.players['游戏ID'].isin(team_members)
        st.session_state.players.loc[mask, '已选择'] = True
        
        # 同步到GitHub
        if save_data_to_github():
            st.success("组队成功!")
            return True
        return False
    except Exception as e:
        st.error(f"组队失败: {str(e)}")
        return False

# ========================
# 管理员后台模块
# ========================
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
                    if save_data_to_github():
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
            save_data_to_github()
        
        if st.button("重置选择状态"):
            st.session_state.players['已选择'] = False
            save_data_to_github()
    
    with tab2:
        st.subheader("队伍管理")
        if not st.session_state.teams:
            st.info("暂无队伍")
            return
            
        for i, team in enumerate(st.session_state.teams, 1):
            with st.expander(f"队伍{i}-队长:{team['队长']}"):
                # 安全获取成员信息
                members_info = []
                for member in team['成员']:
                    player = st.session_state.players[
                        st.session_state.players['游戏ID'] == member
                    ]
                    members_info.append({
                        '游戏ID': member,
                        '游戏职业': player['游戏职业'].values[0] if not player.empty else "未知"
                    })
                
                # 确保数据一致性
                df = pd.DataFrame({
                    '角色': ['队长'] + ['队员']*(len(team['成员'])-1),
                    '游戏ID': [m['游戏ID'] for m in members_info],
                    '游戏职业': [m['游戏职业'] for m in members_info]
                })
                st.dataframe(df, hide_index=True)
                
                if st.button(f"解散队伍{i}", key=f"disband_{i}"):
                    try:
                        # 解除成员选择状态
                        mask = st.session_state.players['游戏ID'].isin(team['成员'])
                        st.session_state.players.loc[mask, '已选择'] = False
                        
                        # 移除队伍
                        st.session_state.teams.pop(i-1)
                        save_data_to_github()
                        st.rerun()
                    except Exception as e:
                        st.error(f"解散队伍失败: {str(e)}")

# ========================
# 主页面模块
# ========================
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
        try:
            # 安全构建队伍数据
            team_members = [captain] + selected
            roles = ['队长'] + ['队员'] * len(selected)
            
            # 获取职业信息
            classes = []
            for member in team_members:
                player_data = st.session_state.players[
                    st.session_state.players['游戏ID'] == member
                ]
                classes.append(
                    player_data['游戏职业'].values[0] 
                    if not player_data.empty 
                    else '未知职业'
                )
            
            team_df = pd.DataFrame({
                '角色': roles,
                '游戏ID': team_members,
                '游戏职业': classes
            })
            st.dataframe(team_df, hide_index=True)
            
        except Exception as e:
            st.error(f"创建预览失败: {str(e)}")
    
    # 提交按钮
    if st.button("✅ 确认组队"):
        if len(selected) > 0:  # 至少选择1人
            if create_team([captain] + selected, captain):
                st.rerun()
        else:
            st.error("请至少选择1名队员!")

# ========================
# 主程序
# ========================
def main():
    initialize_data()
    check_admin_password()
    
    if st.session_state.admin_logged_in:
        admin_panel()
    else:
        main_page()

if __name__ == "__main__":
    main()
