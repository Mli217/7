# app.py
import streamlit as st
from functions import *
import time
from datetime import datetime, timedelta
import pandas as pd

def main():
    init_comm_log()
    st.title("🏫 无人机地面站系统 - 平行偏移绕行")
    st.markdown("---")

    # 初始化所有会话状态
    if "points_gcj" not in st.session_state:
        st.session_state.points_gcj = {'A': DEFAULT_A_GCJ.copy(), 'B': DEFAULT_B_GCJ.copy()}
    if "obstacles_gcj" not in st.session_state:
        st.session_state.obstacles_gcj = []
    if "saved_obstacles" not in st.session_state:
        st.session_state.saved_obstacles = []
    if "heartbeat_sim" not in st.session_state:
        st.session_state.heartbeat_sim = HeartbeatSimulator(st.session_state.points_gcj['A'].copy())
    if "simulation_running" not in st.session_state:
        st.session_state.simulation_running = False
    if "flight_altitude" not in st.session_state:
        st.session_state.flight_altitude = 50
    if "flight_history" not in st.session_state:
        st.session_state.flight_history = []
    if "planned_path" not in st.session_state:
        st.session_state.planned_path = None
    if "pending_polygon" not in st.session_state:
        st.session_state.pending_polygon = None
    if "pending_height" not in st.session_state:
        st.session_state.pending_height = 20

    # 新增：与飞行任务绑定的心跳数据（仅在开始任务后生成）
    if "flight_hb_seq_list" not in st.session_state:
        st.session_state.flight_hb_seq_list = []
        st.session_state.flight_hb_time_list = []
        st.session_state.flight_hb_last_time = time.time()
        st.session_state.flight_hb_seq = 0

    # 侧边栏菜单
    st.sidebar.title("🎛️ 导航菜单")
    page = st.sidebar.radio("选择功能模块", ["🗺️ 航线规划", "📡 飞行监控", "🚧 障碍物管理"])
    map_type_choice = st.sidebar.radio("🗺️ 地图类型", ["卫星影像", "矢量街道"], index=0)
    map_type = "satellite" if map_type_choice == "卫星影像" else "vector"

    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ 无人机参数")
    drone_speed = st.sidebar.slider("飞行速度系数", min_value=10, max_value=100, value=50, step=5)
    safe_radius = st.sidebar.number_input("安全半径 (米)", min_value=1, max_value=30, value=5, step=1)
    flight_alt = st.sidebar.number_input("飞行高度 (米)", min_value=0, max_value=200, value=st.session_state.flight_altitude, step=5)
    st.session_state.flight_altitude = flight_alt

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 绕行策略")
    strategy = st.sidebar.radio("选择避障方式", ["最佳航线 (A*)", "向左绕行", "向右绕行"], index=0)
    strategy_map = {"最佳航线 (A*)": "best", "向左绕行": "left", "向右绕行": "right"}
    selected_strategy = strategy_map[strategy]

    st.sidebar.markdown("---")
    obs_count = len(st.session_state.obstacles_gcj)
    straight_blocked = is_path_blocked(
        st.session_state.points_gcj['A'],
        st.session_state.points_gcj['B'],
        st.session_state.obstacles_gcj,
        st.session_state.flight_altitude
    )
    st.sidebar.info(f"🏫 校园区域\n🚧 障碍物: {obs_count}\n📌 直线: {'🚫 被阻挡' if straight_blocked else '✅ 畅通'}")

    if st.sidebar.button("🔄 刷新数据", use_container_width=True):
        st.session_state.planned_path = create_avoidance_path(
            st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
            st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
        )
        st.rerun()

    # ==================== 航线规划页面 ====================
    if page == "🗺️ 航线规划":
        st.header("🗺️ 航线规划 - 智能避障")
        if straight_blocked:
            st.warning(f"⚠️ 直线航线被建筑物阻挡！障碍物高度 > 当前飞行高度 {flight_alt}m")
        else:
            st.success(f"✅ 直线航线畅通无阻 (飞行高度 {flight_alt}m)")

        col1, col2 = st.columns([1, 1.5])
        with col1:
            st.subheader("🎮 控制面板")
            st.markdown("#### 🟢 起点 A")
            a_lat = st.number_input("纬度", value=st.session_state.points_gcj['A'][1], format="%.6f", key="a_lat")
            a_lng = st.number_input("经度", value=st.session_state.points_gcj['A'][0], format="%.6f", key="a_lng")
            if st.button("📍 设置 A 点", use_container_width=True):
                st.session_state.points_gcj['A'] = [a_lng, a_lat]
                st.session_state.planned_path = create_avoidance_path(
                    st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
                    st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
                )
                st.rerun()

            st.markdown("#### 🔴 终点 B")
            b_lat = st.number_input("纬度", value=st.session_state.points_gcj['B'][1], format="%.6f", key="b_lat")
            b_lng = st.number_input("经度", value=st.session_state.points_gcj['B'][0], format="%.6f", key="b_lng")
            if st.button("📍 设置 B 点", use_container_width=True):
                st.session_state.points_gcj['B'] = [b_lng, b_lat]
                st.session_state.planned_path = create_avoidance_path(
                    st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
                    st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
                )
                st.rerun()

            st.markdown("#### 🏗️ 新障碍物高度")
            new_obs_height = st.number_input("高度 (米)", min_value=1, max_value=200, value=st.session_state.pending_height, step=5)
            st.session_state.pending_height = new_obs_height

            if st.button("➕ 添加障碍物（从当前圈选）", use_container_width=True):
                if st.session_state.pending_polygon and len(st.session_state.pending_polygon) >= 3:
                    st.session_state.obstacles_gcj.append({
                        "name": f"建筑物{len(st.session_state.obstacles_gcj)+1}",
                        "polygon": st.session_state.pending_polygon,
                        "height": st.session_state.pending_height
                    })
                    st.success(f"已添加障碍物（高度{st.session_state.pending_height}m）")
                    st.session_state.pending_polygon = None
                    st.session_state.planned_path = create_avoidance_path(
                        st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
                        st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
                    )
                    st.rerun()
                else:
                    st.warning("请先在地图绘制多边形")

            if st.button("🔄 重新规划路径", use_container_width=True):
                st.session_state.planned_path = create_avoidance_path(
                    st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
                    st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
                )
                st.rerun()

            st.markdown("#### ✈️ 飞行控制")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("▶️ 开始飞行", use_container_width=True):
                    path = st.session_state.planned_path or [st.session_state.points_gcj['A'], st.session_state.points_gcj['B']]
                    st.session_state.heartbeat_sim.set_path(path, st.session_state.flight_altitude, drone_speed)
                    st.session_state.simulation_running = True
                    st.session_state.flight_history = []
                    st.success("已开始飞行")
            with c2:
                if st.button("⏹️ 停止飞行", use_container_width=True):
                    st.session_state.simulation_running = False
                    st.session_state.heartbeat_sim.stop()
                    st.success("已停止飞行")

        with col2:
            st.subheader("🗺️ 规划地图")
            center = st.session_state.points_gcj['A'] or SCHOOL_CENTER_GCJ
            if st.session_state.planned_path is None:
                st.session_state.planned_path = create_avoidance_path(
                    st.session_state.points_gcj['A'], st.session_state.points_gcj['B'],
                    st.session_state.obstacles_gcj, st.session_state.flight_altitude, safe_radius, selected_strategy
                )
            m = create_planning_map(center, st.session_state.points_gcj, st.session_state.obstacles_gcj,
                                   st.session_state.flight_history, st.session_state.planned_path, map_type, straight_blocked, safe_radius)
            output = st_folium(m, width=700, height=550, returned_objects=["last_active_drawing"])

            if output and output.get("last_active_drawing"):
                last = output["last_active_drawing"]
                if last and last.get("geometry") and last["geometry"]["type"] == "Polygon":
                    coords = last["geometry"]["coordinates"]
                    if coords:
                        poly = [[p[0], p[1]] for p in coords[0]]
                        if len(poly) >= 3:
                            st.session_state.pending_polygon = poly
                            st.success("已捕获多边形")

    # ==================== 飞行监控页面 ====================
    elif page == "📡 飞行监控":
        st.header("🛸 飞行实时画面 - 任务执行监控")

        # 自动刷新（每秒一次，用于更新飞行状态和心跳）
        st_autorefresh(interval=1000, key="flight_refresh")

        # 如果飞行模拟正在运行且未暂停，则生成新的心跳包并更新飞行位置
        current_time = time.time()
        if st.session_state.simulation_running and not st.session_state.heartbeat_sim.paused:
            # 更新飞行模拟（位置、进度等）
            sim_data = st.session_state.heartbeat_sim.update_and_generate()
            # 记录飞行轨迹
            pos_gcj = [sim_data["lng"], sim_data["lat"]]
            st.session_state.flight_history.append(pos_gcj)
            
            # 生成新的心跳序号（绑定飞行任务）
            st.session_state.flight_hb_seq += 1
            time_str = datetime.now().strftime("%H:%M:%S")
            st.session_state.flight_hb_seq_list.append(st.session_state.flight_hb_seq)
            st.session_state.flight_hb_time_list.append(time_str)
            st.session_state.flight_hb_last_time = current_time
            # 限制列表长度
            if len(st.session_state.flight_hb_seq_list) > 100:
                st.session_state.flight_hb_seq_list = st.session_state.flight_hb_seq_list[-100:]
                st.session_state.flight_hb_time_list = st.session_state.flight_hb_time_list[-100:]
            
            # 触发页面刷新以更新地图和折线图
            st.rerun()

        # 心跳超时检测（基于飞行任务的心跳）
        time_since_last = current_time - st.session_state.flight_hb_last_time
        if st.session_state.simulation_running and not st.session_state.heartbeat_sim.paused and time_since_last > 3.0:
            st.error("🚨 连接超时！超过3秒未收到心跳包")
        elif st.session_state.simulation_running and not st.session_state.heartbeat_sim.paused:
            st.success(f"✅ 连接正常 | 距上次心跳: {time_since_last:.1f} 秒")
        else:
            st.info("⏳ 飞行任务未开始或已暂停，无心跳数据")

        # 显示最新心跳序号
        st.metric("📶 最新心跳序号", st.session_state.flight_hb_seq if st.session_state.simulation_running else 0)

        # 绘制折线图（仅当有心跳数据时）
        if len(st.session_state.flight_hb_seq_list) >= 2:
            df_hb = pd.DataFrame({
                "时间": st.session_state.flight_hb_time_list,
                "序号": st.session_state.flight_hb_seq_list
            })
            st.line_chart(df_hb.set_index("时间"))

        st.markdown("---")

        # 飞行控制按钮
        col_ctrl, col_status = st.columns([3, 1])
        with col_ctrl:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("开始任务", type="primary", use_container_width=True):
                    # 清空之前的任务数据
                    st.session_state.heartbeat_sim.reset()
                    st.session_state.flight_history = []
                    # 重置心跳数据
                    st.session_state.flight_hb_seq_list = []
                    st.session_state.flight_hb_time_list = []
                    st.session_state.flight_hb_seq = 0
                    st.session_state.flight_hb_last_time = time.time()
                    # 设置新路径
                    path = st.session_state.planned_path or [st.session_state.points_gcj['A'], st.session_state.points_gcj['B']]
                    st.session_state.heartbeat_sim.set_path(path, st.session_state.flight_altitude, drone_speed)
                    st.session_state.simulation_running = True
                    st.rerun()
            with c2:
                if st.button("暂停", use_container_width=True):
                    st.session_state.heartbeat_sim.pause()
                    st.session_state.simulation_running = False  # 飞行暂停，心跳也暂停
                    st.rerun()
            with c3:
                if st.button("停止", use_container_width=True):
                    st.session_state.simulation_running = False
                    st.session_state.heartbeat_sim.stop()
                    # 停止任务后不再生成心跳，但保留已生成的心跳数据（不清空）
                    st.rerun()
            with c4:
                if st.button("重置", use_container_width=True):
                    # 重置飞行模拟
                    st.session_state.heartbeat_sim.reset()
                    st.session_state.simulation_running = False
                    st.session_state.flight_history = []
                    # 重置所有心跳数据（清空）
                    st.session_state.flight_hb_seq_list = []
                    st.session_state.flight_hb_time_list = []
                    st.session_state.flight_hb_seq = 0
                    st.session_state.flight_hb_last_time = time.time()
                    st.rerun()
        with col_status:
            status = "飞行中" if st.session_state.simulation_running and not st.session_state.heartbeat_sim.paused else "已停止"
            st.info(f"飞行状态：{status}")

        # 实时飞行数据显示
        if st.session_state.heartbeat_sim.history:
            latest = st.session_state.heartbeat_sim.history[0]
            cols = st.columns(6)
            cols[0].metric("当前航点", f"{latest['current_waypoint']}/{latest['total_waypoints']}")
            cols[1].metric("飞行速度", f"{latest['speed']} m/s")
            cols[2].metric("已用时间", str(timedelta(seconds=latest['elapsed_time'])))
            cols[3].metric("剩余距离", f"{latest['remaining_distance']} m")
            cols[4].metric("预计到达", str(timedelta(seconds=latest['remaining_time'])) if latest['remaining_time']>0 else "00:00")
            cols[5].metric("电量模拟", f"{latest['battery']}%")
            st.progress(latest['progress'], text=f"任务进度：{latest['progress']*100:.0f}%")
        else:
            st.info("等待飞行任务开始...")

        st.markdown("---")
        map_col, comm_col = st.columns([2, 1])
        with map_col:
            st.subheader("实时飞行地图")
            center = st.session_state.points_gcj['A'] or SCHOOL_CENTER_GCJ
            m = create_planning_map(center, st.session_state.points_gcj, st.session_state.obstacles_gcj,
                                   st.session_state.flight_history, st.session_state.planned_path, map_type, straight_blocked, safe_radius)
            folium_static(m, width=600, height=400)
        with comm_col:
            st.subheader("📡 通信链路拓扑与数据流")
            topo_html = '''
            <div style="display:flex; justify-content:space-around; text-align:center; margin-top:10px;">
                <div style="width:28%; padding:12px; background:#e3f2fd; border:2px solid #1976d2; border-radius:8px;">
                    <div style="font-weight:bold; font-size:16px; color:#1976d2;">GCS</div>
                    <div style="font-size:12px;">地面站<br/>192.168.1.100</div>
                    <div style="color:green; font-size:13px;">✅在线</div>
                </div>
                <div style="display:flex;align-items:center;">⬇️UDP:14550⬆️</div>
                <div style="width:28%; padding:12px; background:#fff8e1; border:2px solid #f57c00; border-radius:8px;">
                    <div style="font-weight:bold; font-size:16px; color:#f57c00;">OBC</div>
                    <div style="font-size:12px;">机载计算机<br/>Raspberry Pi4</div>
                    <div style="color:green; font-size:13px;">✅在线</div>
                </div>
                <div style="display:flex;align-items:center;">⬇️MAVLink⬆️</div>
                <div style="width:28%; padding:12px; background:#fce4ec; border:2px solid #c2185b; border-radius:8px;">
                    <div style="font-weight:bold; font-size:16px; color:#c2185b;">FCU</div>
                    <div style="font-size:12px;">飞控<br/>PX4/ArduPilot</div>
                    <div style="color:green; font-size:13px;">✅在线</div>
                </div>
            </div>
            <div style="margin-top:15px; padding:8px; background:#f5f5f5; border-radius:6px; font-size:13px;">
            📊链路统计：GCS↔OBC:正常｜OBC↔FCU:正常｜延迟:~25ms｜丢包率:0.1%
            </div>
            '''
            st.markdown(topo_html, unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["📤GCS→OBC→FCU下发日志", "📥FCU→OBC→GCS回传日志"])
            with tab1:
                log_text1 = "\n".join(st.session_state.gcs2fcu_log[-30:]) if st.session_state.gcs2fcu_log else "暂无航线下发日志"
                st.text_area("", log_text1, height=220)
            with tab2:
                log_text2 = "\n".join(st.session_state.fcu2gcs_log[-30:]) if st.session_state.fcu2gcs_log else "暂无飞控回传日志"
                st.text_area("", log_text2, height=220)

    # ==================== 障碍物管理页面 ====================
    elif page == "🚧 障碍物管理":
        st.header("🚧 障碍物管理")
        st.info(f"当前共 {len(st.session_state.obstacles_gcj)} 个障碍物")
        col1, col2 = st.columns([1, 1.5])
        with col1:
            for i, obs in enumerate(st.session_state.obstacles_gcj):
                na, h, btn = st.columns([2,1,1])
                na.write(f"🚧 {obs.get('name', f'障碍物{i+1}')}")
                h.write(f"{obs.get('height',20)}m")
                if btn.button("删除", key=f"del{i}"):
                    st.session_state.obstacles_gcj.pop(i)
                    st.rerun()
            st.columns(2)[0].button("💾 保存到缓存", on_click=save_obstacles_to_cache)
            st.columns(2)[1].button("📂 从缓存加载", on_click=load_obstacles_from_cache)
            if st.button("🗑️ 全部清除"):
                st.session_state.obstacles_gcj = []
                st.rerun()

if __name__ == "__main__":
    main()
