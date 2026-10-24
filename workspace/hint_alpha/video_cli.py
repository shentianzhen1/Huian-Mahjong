"""Direct video diagnostics entrypoint for the installed internal Alpha."""
import argparse
from pathlib import Path
import sys
import time

from .video_test import run_video_test


def launch_command(video, *, executable, output_root, dataset_root):
    interpreter = Path(executable)
    if interpreter.name.lower() == 'pythonw.exe':
        interpreter = interpreter.with_name('python.exe')
    output = Path(output_root) / ('video-' + str(time.time_ns()) + '.json')
    return [str(interpreter), '-B', '-m', 'workspace.hint_alpha.video_cli',
            str(video), '--dataset', str(dataset_root), '--output', str(output),
            '--duration', '30', '--pause']


def main(argv=None):
    parser = argparse.ArgumentParser(description='原始录像只读诊断；不代表正式识别验收')
    parser.add_argument('video', type=Path)
    parser.add_argument('--dataset', type=Path, default=Path(__file__).resolve().parents[2] / 'dataset/tiles_runtime_v0_2')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=float, default=0.0)
    parser.add_argument('--duration', type=float, default=30.0)
    parser.add_argument('--source-session', help='已核实的原始会话；用于排除同会话模板')
    parser.add_argument('--pause', action='store_true')
    args = parser.parse_args(argv)
    code = 0
    try:
        print('直接解码原始录像；默认分析前30秒。正在校验文件，请稍候。', flush=True)
        def progress(row):
            runtime = row['runtime']
            state = '可显示结构建议' if runtime['display_allowed'] else 'UNKNOWN / 暂不可用'
            issues = ', '.join(runtime.get('hint', {}).get('issues', []))
            print(f"{row['source_seconds']:.2f}s | {state} | 流水观察 {row['timeline_event_count']} | {issues}", flush=True)
        result = run_video_test(args.video, dataset_root=args.dataset,
                                output_path=args.output, start_seconds=args.start,
                                duration_seconds=args.duration,
                                source_session=args.source_session, on_window=progress)
        print(f"诊断报告：{result['report_path']}\n流水文本：{result['timeline_text_path']}", flush=True)
        print('这是开发诊断，UNKNOWN 保留；不会操作游戏。', flush=True)
    except KeyboardInterrupt:
        print('诊断已中止；本次完整报告未生成。', flush=True)
        code = 130
    except Exception as exc:
        print(f'诊断失败：{type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        code = 1
    if args.pause:
        try:
            input('按 Enter 关闭诊断窗口。')
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == '__main__':
    raise SystemExit(main())
