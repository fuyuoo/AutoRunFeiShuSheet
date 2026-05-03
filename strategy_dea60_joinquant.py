"""
DEA上穿0轴 + 60日均线回归策略 — 聚宽回测框架 v3.8
=================================================
基于 trading-plan-dea60.md 最新规则

架构：
  before_open → morning_prepare（过滤ST/停牌）
  open        → morning_execute（执行昨日队列中的买卖订单）
  after_close → evening_scan（信号分析 + 队列 + 扫描候选股 + 记录）

关键改动：
  v3.0: 买卖订单在 open 时段执行（而非 after_close），确保订单成交
  v3.0: after_close 只做信号分析，将交易指令存入 g.pending_buys / g.pending_sells
  v3.1: 过滤科创板（688xxx）— 市价单需保护限价，容易下单失败
  v3.2: get_technical_data 改用 attribute_history，dropna 后转 numpy
  v3.3: 彻底重写 get_technical_data — 改用 get_price（不前复权）+ 纯 numpy 计算
  v3.4: 修复 NaN 问题 — get_technical_data 改用 attribute_history（与 scan_candidates 同一API）
         修复幽灵持仓 — 建仓订单不立即写入 positions_info，等 confirm_fills 确认成交后再创建
  v3.5: check_exit_signals 添加独立备用路径（get_price API），确保卖出检查不受 NaN 影响
         get_technical_data 添加详细诊断日志（🔍DBG 前缀）
  v3.6: 止盈卖出前检查剩余持仓是否≥100股，不足则改为清仓
         morning_execute 添加买入金额按比例缩放，确保所有建仓信号都能买入（不出现资金不足）
  v3.7: 买入缩放增加最低100股过滤循环，缩放后不足100股的信号自动移除
         最低100股优先级 > 仓位比例
         建议初始资金1000万，确保每只股票仓位充足
  v3.8: DEA_LOOKBACK 从 5 改为 10（上水后10日内）
         check_entry_signals 完整重新验证：DEA>0 + DEA近期上水 + 收盘>MA60 + 阴线
         修复T日条件满足但T+1日已破位/DEA下水仍买入的问题

策略逻辑：
  1. 选股池：沪深300 + 中证500
  2. 入场：日线DEA刚上穿0轴 + 价格在MA60上方 + 真阴线买入
  3. 建仓：首次1/3，距MA60≤1%则全仓，最多加仓3次（各1/3）
  4. 止盈：总成本盈利5%卖1/3，15%再卖1/3（按原始成本计算）
  5. 止损：收盘跌破MA60 → 次日观察 → 仍未收回则清仓
  6. 清仓：收盘下穿MA25 → 次日观察 → 仍未收回则清仓
  7. 时间止损：30个交易日盈利未超过3%清仓，60日无止盈清仓
  8. 涨停不买，跌停卖不出则次日再卖

使用方法：
  1. 登录 joinquant.com
  2. 新建策略 → 粘贴本代码
  3. 设置回测区间（建议2019-01-01至2025-12-31）
  4. 初始资金建议100万
  5. 运行回测

=================================================
"""
from jqdata import *
import numpy as np
import pandas as pd
from collections import OrderedDict


# ============================================================
# 全局参数
# ============================================================
P = {
    # 仓位控制
    'MAX_POSITIONS': 8,            # 最大同时持仓数
    'POSITION_RATIO': 0.10,        # 单票计划仓位占总资金比例
    'TOTAL_POSITION_CAP': 0.80,    # 总仓位上限

    # 建仓规则
    'FIRST_BUY_RATIO': 1.0 / 3.0,  # 首次建仓比例
    'MA60_FULL_PCT': 0.01,         # 距MA60≤1%则全仓

    # 加仓规则
    'MAX_ADD_TIMES': 3,            # 最大买入次数（含首次）
    'ADD_RATIO': 1.0 / 3.0,        # 每次加仓比例

    # 真阴线定义
    'BEARISH_MIN_PCT': 0.001,      # 阴线最低跌幅 0.1%

    # 止盈
    'TP1_PCT': 0.05,               # 第一次止盈 5%
    'TP2_PCT': 0.15,               # 第二次止盈 15%
    'TP_SELL_RATIO': 1.0 / 3.0,    # 止盈卖出比例（计划仓位的1/3）

    # 时间止损
    'TIME_STOP_30': 30,            # 30个交易日时间止损
    'TIME_STOP_30_PROFIT': 0.03,   # 30日盈利阈值（历史最高）
    'TIME_STOP_60': 60,            # 60个交易日时间止损

    # DEA判定
    'DEA_LOOKBACK': 10,            # "刚上穿"回看天数（上水后10日内）
}


# ============================================================
# 初始化
# ============================================================
def initialize(context):
    """初始化"""
    log.info('========== 策略v3.5启动 ==========')
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    # 手续费
    set_order_cost(
        OrderCost(
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5,
        ),
        type='stock',
    )

    # 滑点
    set_slippage(PriceRelatedSlippage(0.002))

    # 股票池：沪深300 + 中证500，排除科创板（需保护限价，市价单易失败）
    all_stocks = list(set(
        get_index_stocks('000300.XSHG') +
        get_index_stocks('000905.XSHG')
    ))
    g.security_pool = [s for s in all_stocks if not s.startswith('688')]
    log.info(f'选股池初始化：{len(all_stocks)}只 → 排除科创板后{len(g.security_pool)}只')

    # 持仓状态跟踪
    g.positions_info = OrderedDict()

    # 昨日选股结果（收盘后扫描，次日使用）
    g.yesterday_candidates = []

    # 待执行交易队列（after_close分析 → open执行）
    g.pending_buys = []
    g.pending_sells = []

    # 今日待确认的新建仓订单（open下单后，evening确认成交时才创建 g.positions_info）
    g.pending_new_buys = []

    # 注册每日函数
    run_daily(morning_prepare, time='before_open')
    run_daily(morning_execute, time='open', reference_security='000300.XSHG')
    run_daily(evening_scan, time='after_close')


# ============================================================
# 盘前准备：过滤ST、停牌
# ============================================================
def morning_prepare(context):
    """盘前：过滤不可交易的标的"""
    g.tradeable = []
    for sec in g.security_pool:
        try:
            info = get_security_info(sec)
            if info is None:
                continue
            if 'ST' in info.display_name:
                continue
            # 检查停牌（前日有成交量）
            df = get_price(sec, end_date=context.previous_date, count=1,
                          fields=['volume'])
            if df is None or len(df) == 0 or df['volume'].iloc[-1] <= 0:
                continue
            g.tradeable.append(sec)
        except Exception:
            continue


# ============================================================
# 买入资金缩放：确保所有信号都能买入（最低100股优先）
# ============================================================
def _scale_pending_buys(context):
    """
    1. 过滤掉缩放后不足100股的买入信号
    2. 剩余信号按比例缩放，确保所有信号都能执行
    3. 最低100股优先级 > 仓位比例
    """
    if not g.pending_buys:
        return

    # 卖出会释放资金，先估算卖出回笼金额
    sell_release = 0.0
    for s in g.pending_sells:
        sec = s['sec']
        if sec in context.portfolio.positions:
            pos = context.portfolio.positions[sec]
            if s['type'] == 'full':
                sell_release += pos.value
            elif s['type'] == 'partial':
                sell_release += pos.value - s.get('target_value', 0)

    available = context.portfolio.available_cash + sell_release

    # 循环过滤 + 缩放：每轮去掉不满足100股最低的，重新计算
    for _ in range(5):
        if not g.pending_buys:
            break

        total_buy = sum(o['buy_value'] for o in g.pending_buys)
        if total_buy <= 0:
            break

        # 先过滤：不足100股最低金额的信号移除
        filtered = []
        removed = 0
        for o in g.pending_buys:
            sec = o['sec']
            min_val = 0.0
            try:
                df = get_price(sec, end_date=context.current_dt, count=1,
                               fields=['close'])
                if df is not None and len(df) > 0:
                    min_val = float(df['close'].iloc[-1]) * 100
            except Exception:
                min_val = 0.0
            if o['buy_value'] >= min_val:
                filtered.append(o)
            else:
                removed += 1
                log.info(f'⚠️ {sec} 买入金额{o["buy_value"]:.0f}元 < '
                         f'最低{min_val:.0f}元(100股)，移除信号')

        g.pending_buys = filtered
        if removed == 0 and total_buy <= available:
            return  # 全部满足，无需缩放

        total_buy = sum(o['buy_value'] for o in g.pending_buys)
        if total_buy <= available or total_buy <= 0:
            return

        scale = available / total_buy * 0.95  # 5%缓冲
        for o in g.pending_buys:
            o['buy_value'] *= scale

    # 最终检查：仍然超出可用资金则打印警告
    total_buy = sum(o['buy_value'] for o in g.pending_buys)
    if total_buy > available:
        log.info(f'⚠️ 缩放后仍超出: 需求{total_buy:.0f}元 > 可用{available:.0f}元')


# ============================================================
# 开盘时：执行昨日队列中的买卖订单
# ============================================================
def morning_execute(context):
    """
    开盘时执行：
    1. 执行昨日分析出的卖出信号（g.pending_sells）
    2. 执行昨日分析出的买入信号（g.pending_buys）
    订单在当日开盘价成交
    """
    # ========== 预处理：按比例缩放买入金额，确保所有信号都能买入 ==========
    _scale_pending_buys(context)

    # ========== 执行卖出 ==========
    for order_info in g.pending_sells:
        sec = order_info['sec']
        sell_type = order_info['type']

        if sell_type == 'full':
            # 清仓卖出
            order_target(sec, 0)
            g.positions_info.pop(sec, None)
            log.info(f'🔴 开盘清仓 {sec}（{order_info.get("reason", "")}）')

        elif sell_type == 'partial':
            # 部分止盈卖出
            target_value = order_info['target_value']
            # 安全检查：目标市值 ≥ 100股 × 当前价，否则跳过
            if sec in context.portfolio.positions:
                cur_amount = context.portfolio.positions[sec].total_amount
                cur_price = context.portfolio.positions[sec].price
                if cur_price > 0 and target_value < cur_price * 100:
                    log.info(f'⚠️ {sec} 部分卖出后不足100股，改为清仓')
                    order_target(sec, 0)
                    g.positions_info.pop(sec, None)
                    continue
            order_target_value(sec, target_value)
            # 标记等待确认止盈卖出
            if sec in g.positions_info:
                g.positions_info[sec]['pending_partial_sell'] = True
                g.positions_info[sec]['pending_sell_count'] = order_info['new_sell_count']
            log.info(f'🟡 开盘部分卖出 {sec} 目标持仓{target_value:.0f}元'
                     f'（{order_info.get("reason", "")}）')

    g.pending_sells = []

    # ========== 执行买入 ==========
    g.pending_new_buys = []  # 待确认的建仓订单
    for order_info in g.pending_buys:
        sec = order_info['sec']
        buy_value = order_info['buy_value']

        # 检查可用资金
        if context.portfolio.available_cash < buy_value * 0.5:
            log.info(f'⚠️ {sec} 可用资金不足，跳过买入')
            continue

        order_target_value(sec, buy_value)

        if order_info['is_new']:
            # 新建仓 — 不立即创建 positions_info，等 confirm_fills 确认
            g.pending_new_buys.append({
                'sec': sec,
                'entry_date': context.current_dt.date(),
                'is_full_position': order_info.get('is_full', False),
            })
            log.info(f'🟢 开盘建仓 {sec} 目标{buy_value:.0f}元')
        else:
            # 加仓 — 检查持仓仍存在（可能在卖出阶段已被清仓）
            if sec not in g.positions_info:
                log.info(f'⚠️ {sec} 加仓订单跳过：持仓已被清仓')
                continue
            info = g.positions_info[sec]
            info['buy_count'] += 1
            info['pending_fill'] = True
            log.info(f'🟢 开盘加仓{info["buy_count"]} {sec} 目标{buy_value:.0f}元')

    g.pending_buys = []


# ============================================================
# 盘后：核心逻辑（信号分析 + 队列 + 扫描）
# ============================================================
def evening_scan(context):
    """
    盘后执行：
    1. 更新持仓天数
    2. 确认今日订单成交
    3. 卖出信号分析 → g.pending_sells（次日open执行）
    4. 买入信号分析 → g.pending_buys（次日open执行）
    5. 扫描候选股（留给下个交易日用）
    6. 记录
    """
    today = context.current_dt.date()

    # ========== 第一步：更新持仓元数据 ==========
    update_positions_meta(today)

    # ========== 第二步：确认今日订单成交 ==========
    confirm_fills(context)

    # ========== 第三步：卖出信号分析 ==========
    check_exit_signals(context, today)

    # ========== 第四步：买入信号分析 ==========
    check_entry_signals(context, today)

    # ========== 第五步：扫描候选股 ==========
    g.yesterday_candidates = scan_candidates(context, today)

    # ========== 第六步：记录 ==========
    record_data(context)


# ============================================================
# 更新持仓元数据：交易日计数
# ============================================================
def update_positions_meta(_today):
    """每日更新持仓的交易日计数"""
    for _sec, info in g.positions_info.items():
        info['holding_days'] = info.get('holding_days', 0) + 1


# ============================================================
# 确认订单成交
# ============================================================
def confirm_fills(context):
    """确认今日在open时段执行的订单已成交"""

    # ===== 确认新建仓成交 =====
    for pending in list(g.pending_new_buys):
        sec = pending['sec']
        if sec in context.portfolio.positions and \
           context.portfolio.positions[sec].total_amount > 0:
            pos = context.portfolio.positions[sec]
            g.positions_info[sec] = {
                'total_cost': pos.value,
                'buy_count': 1,
                'entry_date': pending['entry_date'],
                'holding_days': 0,
                'sell_count': 0,
                'highest_profit': 0.0,
                'is_full_position': pending.get('is_full_position', False),
                'original_shares': pos.total_amount,
                'ma60_break_date': None,
                'ma25_break_date': None,
                'pending_fill': False,
            }
            log.info(f'✅ {sec} 建仓已成交 '
                     f'持仓{pos.total_amount}股 均价{pos.avg_cost:.2f} '
                     f'成本{pos.value:.0f}元')
        else:
            log.info(f'⚠️ {sec} 建仓未成交（持仓不存在），丢弃')
        g.pending_new_buys.remove(pending)

    # ===== 确认加仓成交 / 部分止盈卖出成交 =====
    for sec, info in list(g.positions_info.items()):
        # 确认买入/加仓成交
        if info.get('pending_fill', False):
            if sec in context.portfolio.positions and \
               context.portfolio.positions[sec].total_amount > 0:
                pos = context.portfolio.positions[sec]
                info['pending_fill'] = False
                info['total_cost'] = pos.value
                info['original_shares'] = pos.total_amount
                log.info(f'✅ {sec} 买入已成交 '
                         f'持仓{pos.total_amount}股 均价{pos.avg_cost:.2f} '
                         f'成本{pos.value:.0f}元')
            else:
                log.info(f'⚠️ {sec} 买入未成交（持仓不存在）')
                info['pending_fill'] = False

        # 确认部分止盈卖出成交
        if info.get('pending_partial_sell', False):
            if sec in context.portfolio.positions and \
               context.portfolio.positions[sec].total_amount > 0:
                info['sell_count'] = info.get('pending_sell_count', info['sell_count'])
                log.info(f'✅ {sec} 止盈卖出已成交 sell_count={info["sell_count"]}')
            else:
                log.info(f'⚠️ {sec} 止盈卖出后持仓为0，清理')
                g.positions_info.pop(sec, None)
                continue
            info.pop('pending_partial_sell', None)
            info.pop('pending_sell_count', None)


# ============================================================
# 扫描候选股：DEA刚上穿0轴 + 收盘在MA60上方
# ============================================================
def scan_candidates(context, _today=None):
    """
    扫描选股池，找DEA刚上穿0轴 + MA60上方的标的
    不检查阴线（阴线在买入时判断）
    """
    candidates = []

    for sec in g.tradeable:
        try:
            # 使用 attribute_history 确保数据可靠
            df = attribute_history(sec, 150, '1d',
                                  ['close', 'open', 'high', 'low',
                                   'pre_close', 'volume'],
                                  skip_paused=False, fq='pre')
            if df is None or len(df) < 65:
                continue

            close = df['close'].dropna().values
            if len(close) < 65:
                continue

            # 计算 MACD DEA
            ema12 = pd.Series(close).ewm(span=12, adjust=False).mean().values
            ema26 = pd.Series(close).ewm(span=26, adjust=False).mean().values
            dif = ema12 - ema26
            dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values

            # 条件1：DEA 刚上穿0轴（最近N天内从≤0变为>0）
            if dea[-1] <= 0:
                continue
            crossed = any(dea[i] <= 0 for i in
                         range(-min(P['DEA_LOOKBACK'], len(dea)), 0))
            if not crossed:
                continue

            # 条件2：收盘价在MA60上方
            ma60 = pd.Series(close).rolling(60).mean().values
            if np.isnan(ma60[-1]) or close[-1] <= ma60[-1]:
                continue

            candidates.append(sec)

        except Exception:
            continue

    log.info(f'扫描完成，候选股 {len(candidates)} 只')
    return candidates


# ============================================================
# 卖出信号分析（不执行交易，只生成队列）
# ============================================================
def check_exit_signals(context, today):
    """检查所有持仓的卖出/止损/清仓信号，存入 g.pending_sells"""
    if g.positions_info:
        log.info(f'===== 卖出检查 持仓{len(g.positions_info)}只 =====')

    for sec, info in list(g.positions_info.items()):
        # 跳过等待成交的持仓
        if info.get('pending_fill', False):
            log.info(f'⏳ {sec} 等待买入成交，跳过卖出检查')
            continue

        # 跳过等待确认止盈的持仓
        if info.get('pending_partial_sell', False):
            log.info(f'⏳ {sec} 等待止盈卖出确认，跳过本轮TP检查')
            continue

        # ===== 持仓有效性检查 =====
        if sec not in context.portfolio.positions:
            log.info(f'🗑️ {sec} 不在持仓中，清理记录')
            g.positions_info.pop(sec, None)
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount == 0:
            log.info(f'🗑️ {sec} 持仓为0，清理记录')
            g.positions_info.pop(sec, None)
            continue

        # ===== 获取技术数据（主路径 + 独立备用路径）=====
        tech = get_technical_data(sec, today)
        close_now = None
        ma25_now = None
        ma60_now = None

        if tech is not None and not np.isnan(tech.get('close_now', np.nan)) \
           and not np.isnan(tech.get('ma25_now', np.nan)) \
           and not np.isnan(tech.get('ma60_now', np.nan)):
            close_now = tech['close_now']
            ma25_now = tech['ma25_now']
            ma60_now = tech['ma60_now']
        else:
            # 独立备用路径：用 get_price（不同API）计算MA
            log.info(f'🔄 {sec} 主路径数据异常，启用备用路径')
            try:
                df_fb = get_price(sec, end_date=today, count=80,
                                  frequency='daily', fields=['close'],
                                  fq='pre')
                if df_fb is not None and len(df_fb) >= 60:
                    fb_close = df_fb['close'].dropna()
                    if len(fb_close) >= 60:
                        close_now = float(fb_close.iloc[-1])
                        ma25_now = float(fb_close.rolling(25).mean().iloc[-1])
                        ma60_now = float(fb_close.rolling(60).mean().iloc[-1])
                        if not np.isnan(close_now) and not np.isnan(ma25_now) \
                           and not np.isnan(ma60_now):
                            log.info(f'✅ {sec} 备用路径成功 收盘{close_now:.2f} '
                                     f'MA25={ma25_now:.2f} MA60={ma60_now:.2f}')
                        else:
                            log.info(f'⚠️ {sec} 备用路径MA仍为NaN')
                            continue
                    else:
                        log.info(f'⚠️ {sec} 备用路径有效close不足{len(fb_close)}')
                        continue
                else:
                    log.info(f'⚠️ {sec} 备用路径数据不足')
                    continue
            except Exception as e:
                log.error(f'⚠️ {sec} 备用路径异常: {e}')
                continue

        # ===== 计算盈亏 =====
        total_cost = info['total_cost']
        current_value = pos.total_amount * close_now
        original_shares = info.get('original_shares', 0)
        if original_shares <= 0 and pos.avg_cost > 0:
            original_shares = int(total_cost / pos.avg_cost)
        if original_shares > 0 and total_cost > 0:
            hypothetical_value = original_shares * close_now
            profit_pct = (hypothetical_value / total_cost - 1)
        else:
            profit_pct = 0

        # 更新历史最高盈利
        info['highest_profit'] = max(info.get('highest_profit', 0), profit_pct)
        holding_days = info.get('holding_days', 0)

        # 日志输出持仓状态
        log.info(f'📊 {sec} 持仓{holding_days}日 收盘{close_now:.2f} '
                 f'MA60{ma60_now:.2f} MA25{ma25_now:.2f} '
                 f'盈亏{profit_pct:.2%} 最高{info["highest_profit"]:.2%} '
                 f'买入{info["buy_count"]}次 卖出{info["sell_count"]}次')

        # ===== 优先级1：硬止损 — MA60次日确认 =====
        if close_now < ma60_now:
            if info.get('ma60_break_date') is None:
                info['ma60_break_date'] = today
                log.info(f'⚠️ {sec} 收盘{close_now:.2f} < MA60{ma60_now:.2f}，标记破位')
            elif info['ma60_break_date'] != today:
                if is_limit_down(sec, today):
                    log.info(f'⚠️ {sec} MA60破位确认但跌停，次日再卖')
                    continue
                log.info(f'🔴 止损信号 {sec} MA60连续2日未收回，加入清仓队列')
                g.pending_sells.append({
                    'sec': sec,
                    'type': 'full',
                    'reason': 'MA60止损',
                })
                continue
        else:
            if info.get('ma60_break_date') is not None:
                log.info(f'✅ {sec} 收回MA60上方，取消止损标记')
            info['ma60_break_date'] = None

        # ===== 优先级2：清仓信号 — MA25次日确认 =====
        if close_now < ma25_now:
            if info.get('ma25_break_date') is None:
                info['ma25_break_date'] = today
                log.info(f'⚠️ {sec} 收盘{close_now:.2f} < MA25{ma25_now:.2f}，标记破位')
            elif info['ma25_break_date'] != today:
                if is_limit_down(sec, today):
                    log.info(f'⚠️ {sec} MA25破位确认但跌停，次日再卖')
                    continue
                log.info(f'🔴 清仓信号 {sec} MA25连续2日未收回，加入清仓队列')
                g.pending_sells.append({
                    'sec': sec,
                    'type': 'full',
                    'reason': 'MA25清仓',
                })
                continue
        else:
            if info.get('ma25_break_date') is not None:
                log.info(f'✅ {sec} 收回MA25上方，取消清仓标记')
            info['ma25_break_date'] = None

        # ===== 优先级3：时间止损 =====
        # 30个交易日历史最高盈利<3% → 清仓
        if holding_days >= P['TIME_STOP_30'] and \
           info.get('highest_profit', 0) < P['TIME_STOP_30_PROFIT']:
            log.info(f'⚠️ 时间止损信号 {sec} 持仓{holding_days}日 '
                     f'最高盈利{info["highest_profit"]:.2%} < 3%，加入清仓队列')
            g.pending_sells.append({
                'sec': sec,
                'type': 'full',
                'reason': '30日时间止损',
            })
            continue

        # 60个交易日无止盈 → 清仓
        if holding_days >= P['TIME_STOP_60'] and info['sell_count'] == 0:
            log.info(f'⚠️ 时间止损信号 {sec} 持仓{holding_days}日未止盈，加入清仓队列')
            g.pending_sells.append({
                'sec': sec,
                'type': 'full',
                'reason': '60日时间止损',
            })
            continue

        # ===== 优先级4：分批止盈 =====
        # 第一次止盈：5% → 卖1/3计划仓位
        if profit_pct >= P['TP1_PCT'] and info['sell_count'] == 0:
            plan_value = context.portfolio.total_value * P['POSITION_RATIO']
            sell_value = plan_value * P['TP_SELL_RATIO']
            if sell_value > 0 and current_value > sell_value:
                target_value = current_value - sell_value
                # 检查卖出后剩余市值是否 ≥ 100股（A股最小交易单位）
                min_remain = close_now * 100
                if target_value < min_remain:
                    log.info(f'⚠️ {sec} 止盈1卖出后持仓不足100股（{target_value:.0f}元 < '
                             f'{min_remain:.0f}元），跳过止盈')
                    continue
                g.pending_sells.append({
                    'sec': sec,
                    'type': 'partial',
                    'target_value': target_value,
                    'new_sell_count': 1,
                    'reason': '止盈1(5%)',
                })
                log.info(f'✅ 止盈1信号 {sec} 盈利{profit_pct:.2%} '
                         f'卖1/3 目标持仓{target_value:.0f}元')
            continue

        # 第二次止盈：15% → 再卖1/3计划仓位
        if profit_pct >= P['TP2_PCT'] and info['sell_count'] == 1:
            plan_value = context.portfolio.total_value * P['POSITION_RATIO']
            sell_value = plan_value * P['TP_SELL_RATIO']
            if sell_value > 0 and current_value > sell_value:
                target_value = current_value - sell_value
                # 检查卖出后剩余市值是否 ≥ 100股
                min_remain = close_now * 100
                if target_value < min_remain:
                    # 剩余太少，改为清仓
                    log.info(f'🔴 {sec} 止盈2卖出后持仓不足100股'
                             f'（{target_value:.0f}元 < {min_remain:.0f}元），改为清仓')
                    g.pending_sells.append({
                        'sec': sec,
                        'type': 'full',
                        'reason': '止盈2清仓(剩余不足100股)',
                    })
                    continue
                g.pending_sells.append({
                    'sec': sec,
                    'type': 'partial',
                    'target_value': target_value,
                    'new_sell_count': 2,
                    'reason': '止盈2(15%)',
                })
                log.info(f'✅ 止盈2信号 {sec} 盈利{profit_pct:.2%} '
                         f'再卖1/3 目标持仓{target_value:.0f}元')
            continue


# ============================================================
# 买入信号分析（不执行交易，只生成队列）
# ============================================================
def check_entry_signals(context, today):
    """
    检查买入信号（开新仓 + 加仓），存入 g.pending_buys

    完整验证（每个候选股逐一检查）：
      1. DEA > 0（仍在水上）
      2. DEA 最近N天内刚上穿0轴（上水≤10日）
      3. 收盘价 > MA60
      4. 真阴线（收盘 < 前收盘，跌幅≥0.1%）
      5. 次日观察：信号日(T)生成 → T+1日开盘买入
    """
    portfolio_value = context.portfolio.total_value

    # ---------- 检查加仓 ----------
    for sec in list(g.positions_info.keys()):
        info = g.positions_info[sec]

        if info['buy_count'] >= P['MAX_ADD_TIMES']:
            continue
        if info.get('is_full_position', False):
            continue  # 全仓建仓的不再加仓
        if info.get('pending_fill', False):
            continue  # 上次加仓还未成交，等待
        if info.get('pending_partial_sell', False):
            continue  # 有挂单止盈卖出，暂不加仓

        tech = get_technical_data(sec, today)
        if tech is None:
            continue

        # 必须是真阴线
        if not is_bearish_candle(tech):
            continue

        close_now = tech['close_now']
        ma60_now = tech['ma60_now']
        dea_now = tech['dea_now']

        # 收盘必须在MA60上方
        if np.isnan(ma60_now) or close_now < ma60_now:
            continue

        # DEA必须在水上
        if np.isnan(dea_now) or dea_now <= 0:
            continue

        # 加仓金额 = 1/3 计划仓位
        plan_value = portfolio_value * P['POSITION_RATIO']
        add_value = plan_value * P['ADD_RATIO']

        # 最低买入金额检查：A股最少100股
        if close_now * 100 > add_value:
            continue

        # 目标持仓市值 = 当前持仓市值 + 加仓金额
        cur_value = context.portfolio.positions[sec].value \
            if sec in context.portfolio.positions else 0
        target_value = cur_value + add_value

        if context.portfolio.available_cash < add_value * 0.5:
            continue

        g.pending_buys.append({
            'sec': sec,
            'buy_value': target_value,
            'is_new': False,
        })
        log.info(f'加仓信号{info["buy_count"] + 1} {sec} 目标{target_value:.0f}元')

    # ---------- 检查开新仓（使用昨日候选股，次日观察规则） ----------
    current_positions = len(g.positions_info)
    if current_positions >= P['MAX_POSITIONS']:
        return

    # 总仓位检查
    total_pos_value = sum(
        p.value for p in context.portfolio.positions.values()
    )
    if portfolio_value > 0 and \
       total_pos_value / portfolio_value >= P['TOTAL_POSITION_CAP']:
        return

    # 使用昨日扫描的候选股（次日观察规则）
    for sec in g.yesterday_candidates:
        if sec in g.positions_info:
            continue
        if len(g.positions_info) >= P['MAX_POSITIONS']:
            break

        # 涨停/跌停不买
        if is_limit_up(sec, today):
            log.info(f'⚠️ {sec} 涨停，放弃买入')
            continue
        if is_limit_down(sec, today):
            log.info(f'⚠️ {sec} 跌停，放弃买入')
            continue

        # ===== 完整条件验证（T+1日重新验证所有条件）=====
        tech = get_technical_data(sec, today)
        if tech is None:
            continue

        close_now = tech['close_now']
        ma60_now = tech['ma60_now']
        dea_now = tech['dea_now']
        dea_series = tech['dea'].values

        # 条件1：DEA必须仍在水上
        if np.isnan(dea_now) or dea_now <= 0:
            log.info(f'⚠️ {sec} DEA已下水({dea_now:.4f})，放弃买入')
            continue

        # 条件2：DEA最近N天内刚上穿0轴
        lookback = min(P['DEA_LOOKBACK'], len(dea_series))
        if not any(dea_series[i] <= 0 for i in range(-lookback, 0)):
            log.info(f'⚠️ {sec} DEA非近期上水，放弃买入')
            continue

        # 条件3：收盘价必须在MA60上方
        if np.isnan(ma60_now) or close_now <= ma60_now:
            log.info(f'⚠️ {sec} 收盘{close_now:.2f} ≤ MA60{ma60_now:.2f}，放弃买入')
            continue

        # 条件4：必须是真阴线
        if not is_bearish_candle(tech):
            log.info(f'⚠️ {sec} 非阴线，放弃买入')
            continue

        # ===== 全部条件通过，计算买入金额 =====
        plan_value = portfolio_value * P['POSITION_RATIO']
        distance_pct = (close_now - ma60_now) / ma60_now

        if distance_pct <= P['MA60_FULL_PCT']:
            buy_value = plan_value              # ≤1% → 全仓
            is_full = True
        else:
            buy_value = plan_value * P['FIRST_BUY_RATIO']  # 1/3
            is_full = False

        # 最低买入金额检查：A股最少100股
        if close_now * 100 > buy_value:
            continue

        if context.portfolio.available_cash < buy_value * 0.5:
            continue

        g.pending_buys.append({
            'sec': sec,
            'buy_value': buy_value,
            'is_new': True,
            'is_full': is_full,
        })
        log.info(f'✅ 建仓信号 {sec} 目标{buy_value:.0f}元 距MA60{distance_pct:.1%}'
                 f' DEA={dea_now:.4f}{" 全仓" if is_full else ""}')


# ============================================================
# 辅助函数
# ============================================================
def get_technical_data(security, _date=None, lookback=150):
    """获取技术指标数据 — 使用 attribute_history（与 scan_candidates 同一API）+ pandas 计算"""
    try:
        # 使用 attribute_history 获取前复权数据 — 与 scan_candidates 完全相同的API
        df = attribute_history(security, lookback, '1d',
                               ['close', 'open', 'high', 'low',
                                'pre_close', 'volume'],
                               skip_paused=False, fq='pre')

        # ===== 诊断日志：原始数据 =====
        if df is None:
            log.error(f'🔍DBG {security} attribute_history返回None')
            return None
        raw_len = len(df)
        close_nan_count = int(df['close'].isna().sum()) if 'close' in df.columns else -1

        if raw_len < 65:
            log.error(f'🔍DBG {security} 行数不足: {raw_len} (need 65+)')
            return None

        close = df['close'].dropna().values
        close_len = len(close)
        if close_len < 65:
            log.error(f'🔍DBG {security} 有效close不足: raw={raw_len} NaN={close_nan_count} '
                      f'有效={close_len}')
            return None

        # 前收盘价（用于真阴线判断）
        if 'pre_close' in df.columns and df['pre_close'].notna().any():
            pre_close = float(df['pre_close'].dropna().iloc[-1])
        else:
            pre_close = float(close[-2]) if close_len >= 2 else float(close[-1])

        # ===== MACD DEA（与 scan_candidates 完全相同的计算方式）=====
        close_series = pd.Series(close)
        ema12 = close_series.ewm(span=12, adjust=False).mean().values
        ema26 = close_series.ewm(span=26, adjust=False).mean().values
        dif = ema12 - ema26
        dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values

        # ===== MA25 / MA60 =====
        ma25_arr = close_series.rolling(25).mean().values
        ma60_arr = close_series.rolling(60).mean().values

        ma25_now = ma25_arr[-1]
        ma60_now = ma60_arr[-1]

        # ===== 诊断：NaN 检查 =====
        nan_25 = np.isnan(ma25_now)
        nan_60 = np.isnan(ma60_now)
        if nan_25 or nan_60:
            log.error(f'❌🔍DBG {security} MA计算NaN: raw_rows={raw_len} '
                      f'close_nan={close_nan_count} close有效={close_len} '
                      f'ma25={ma25_now} ma60={ma60_now} '
                      f'close[-5:]={close[-5:].tolist()} '
                      f'dtype={close.dtype}')
            return None

        return {
            'close': close_series,
            'close_now': float(close[-1]),
            'pre_close': float(pre_close),
            'ma25': pd.Series(ma25_arr),
            'ma25_now': float(ma25_now),
            'ma60': pd.Series(ma60_arr),
            'ma60_now': float(ma60_now),
            'dea': pd.Series(dea),
            'dea_now': float(dea[-1]),
            'dea_prev': float(dea[-2]) if close_len >= 2 else np.nan,
        }
    except Exception as e:
        log.error(f'获取{security}技术数据异常: {e}')
        import traceback
        log.error(f'🔍DBG traceback: {traceback.format_exc()}')
        return None


def is_bearish_candle(tech):
    """
    真阴线判断：
    - 收盘价 < 前一日收盘价
    - 跌幅 ≥ 0.1%
    - 排除假阴线（高开低走但收盘仍高于前日）
    """
    close_now = tech['close_now']
    pre_close = tech['pre_close']

    if close_now >= pre_close:
        return False

    change_pct = (close_now - pre_close) / pre_close
    if change_pct > -P['BEARISH_MIN_PCT']:
        return False

    return True


def is_limit_up(sec, today):
    """判断是否涨停"""
    try:
        df = get_price(sec, end_date=today, count=1,
                      fields=['close', 'high_limit'])
        if df is None or len(df) == 0:
            return False
        return df['close'].iloc[-1] >= df['high_limit'].iloc[-1]
    except:
        return False


def is_limit_down(sec, today):
    """判断是否跌停"""
    try:
        df = get_price(sec, end_date=today, count=1,
                      fields=['close', 'low_limit'])
        if df is None or len(df) == 0:
            return False
        return df['close'].iloc[-1] <= df['low_limit'].iloc[-1]
    except:
        return False


# ============================================================
# 可视化
# ============================================================
def record_data(context):
    """记录关键指标到回测图表"""
    positions = len(g.positions_info)
    total = context.portfolio.total_value
    cash_pct = context.portfolio.cash / total * 100 if total > 0 else 0

    # 计算总持仓盈亏
    total_profit = 0
    for sec, info in g.positions_info.items():
        if sec in context.portfolio.positions:
            pos = context.portfolio.positions[sec]
            original_shares = info.get('original_shares', 0)
            if original_shares > 0 and pos.price > 0 and info['total_cost'] > 0:
                hypothetical_value = original_shares * pos.price
                total_profit += hypothetical_value - info['total_cost']
            else:
                total_profit += pos.value - info['total_cost']

    record(
        持仓数=positions,
        现金比例=cash_pct,
        总盈亏=total_profit,
    )
