"""Plain-language status for the read-only live assistant."""
import math


def format_advice_blockers(counts):
    """A diagnostic priority summary, not an accuracy or counterfactual claim."""
    if counts is None:
        return '向听暂停原因：未统计（旧版报告）'
    labels = {'hand_boundary': '局号未确认', 'geometry': '画面/牌面位置未稳定',
              'stability': '等待多帧确认', 'hand_identity': '手牌未确认',
              'gold': '金牌未确认', 'meld_count': '手牌/副露数量',
              'display_policy': '显示模式限制', 'state_conflict': '牌面状态冲突',
              'other_state_or_policy': '其他状态或策略限制'}
    details = '；'.join(f'{labels.get(key, "其他状态或策略限制")} {count}窗'
                       for key, count in counts.items())
    return '向听暂停原因：' + (details or '无')


def blocked_guidance(issues, *, geometry_untrusted=False, promotion_blocked=False):
    if geometry_untrusted:
        return '画面或牌面位置尚未稳定。请保持投屏画面完整，等待重新识别。'
    issues = set(issues)
    if 'live_hand_boundary_unconfirmed' in issues:
        return '局号尚未确认，已暂停向听和弃牌建议；等待当前局重新确认。'
    if any(x.startswith('live_identity_') or x == 'live_hand_meld_waiting_confirmation' for x in issues):
        return '正在确认当前手牌，请等待画面稳定。'
    messages = []
    if issues & {'gold_untrusted', 'gold_identity_unknown', 'runtime_gold_not_fully_trusted'}:
        messages.append('金牌未确认；可使用“手动选金牌”。')
    if issues & {'hand_untrusted', 'hand_identity_unknown', 'runtime_hand_not_fully_trusted'}:
        messages.append('手牌未识别完整；请保持牌面清晰并等待。')
    if issues & {'player_meld_count_untrusted', 'player_meld_count_invalid', 'concealed_hand_count_invalid'}:
        messages.append('手牌或副露数量尚未确认；请等待画面稳定。')
    if messages:
        return '\n'.join(messages)
    if promotion_blocked:
        return '当前处于严格识别模式；内测时可勾选“试用识别”。'
    return '当前状态尚未确认，请查看诊断信息并等待画面稳定。'


def capture_to_hint_text(captured, updated, *, displayed):
    """Capture timestamp to UI text update; excludes upstream mirror and display paint."""
    if not displayed or not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (captured, updated)) or updated < captured:
        return '本次提示耗时：暂无'
    return f'本次提示耗时：{(updated-captured)*1000:.0f} 毫秒（采集到文字更新）'
