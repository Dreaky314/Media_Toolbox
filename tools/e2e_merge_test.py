# -*- coding: utf-8 -*-
"""端到端合并测试：用 ffmpeg 现场生成分片，再走一遍完整的合并流程。

需要能定位到 ffmpeg（本机自带或项目内）。
    python tools/e2e_merge_test.py
"""

import os
import shutil
import subprocess
import sys
import time

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from core import ffmpeg as ff     # noqa: E402
from core import merge, m3u8      # noqa: E402

TMP = os.path.join(ROOT_DIR, ".selftest_tmp", "e2e")
ok_all = True


def say(name, ok, detail=""):
    global ok_all
    ok_all = ok_all and ok
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def run_quiet(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW
                          if sys.platform == "win32" else 0)


def make_segment(ffmpeg_exe, out_path, seconds, color, with_audio=True):
    args = [ffmpeg_exe, "-y", "-f", "lavfi", "-i",
            f"testsrc=size=320x240:rate=25:duration={seconds}"]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
                 "-c:a", "aac", "-b:a", "64k"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
             "-f", "mpegts", out_path]
    return run_quiet(args)


def main():
    print("=" * 62)
    print("端到端合并测试")
    print("=" * 62)

    ffmpeg_exe = ff.get_ffmpeg_path()
    available, info = ff.test_ffmpeg(ffmpeg_exe)
    print(f"\nffmpeg: {ffmpeg_exe}")
    print(f"状态  : {info}")
    if not available:
        print("\n未找到可用的 ffmpeg，跳过端到端测试。")
        return 2

    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)

    print("\n[1] 生成测试分片")
    segs = []
    for i in range(1, 4):
        path = os.path.join(TMP, f"seg{i}.ts")
        r = make_segment(ffmpeg_exe, path, 2, "red")
        if r.returncode != 0 or not os.path.isfile(path):
            say(f"生成 seg{i}.ts", False, (r.stderr or "")[-300:])
            return 1
        segs.append(path)
    say("生成 3 个 ts 分片", len(segs) == 3)
    say("ffprobe 能读到时长", ff.probe_duration(segs[0]) > 0,
        f"{ff.probe_duration(segs[0]):.2f}s")
    say("体积格式化", ff.format_size(os.path.getsize(segs[0])).endswith(("B", "KB", "MB")))
    say("时长格式化", ff.format_duration(65) == "00:01:05", ff.format_duration(65))

    print("\n[2] m3u8 导入链路")
    m3u8_path = os.path.join(TMP, "index.m3u8")
    with open(m3u8_path, "w", encoding="utf-8") as fp:
        fp.write("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:3\n")
        for i in range(1, 4):
            fp.write(f"#EXTINF:2.0,\nseg{i}.ts\n")
        fp.write("#EXT-X-ENDLIST\n")
    info2 = m3u8.parse_m3u8(m3u8_path)
    resolved = m3u8.resolve_segments(info2)
    say("m3u8 解析出 3 个分片", len(resolved) == 3)
    say("m3u8 累计时长 6s", abs(info2["duration"] - 6.0) < 0.01, str(info2["duration"]))

    print("\n[3] copy 模式合并 + 进度回调")
    output = os.path.join(TMP, "out_copy.mp4")
    list_path = os.path.join(TMP, "concat.txt")
    cmd, list_path = merge.build_ffmpeg_cmd(
        resolved, output, mode="copy", list_path=list_path, ffmpeg_path=ffmpeg_exe)

    total = ff.probe_duration(list_path)
    say("（已知限制）ffprobe 对 TS 的 concat 列表返回 0", total == 0, f"{total:.2f}s")

    total, how = ff.total_duration(resolved)
    say("total_duration 精确求和", how == "exact" and abs(total - 6.0) < 0.6,
        f"{total:.2f}s / {how}")
    m3u8_total, how2 = ff.total_duration(resolved, m3u8_seconds=info2["duration"])
    say("m3u8 时长优先采用", how2 == "m3u8" and abs(m3u8_total - 6.0) < 0.01,
        f"{m3u8_total:.2f}s / {how2}")

    progress_events = []
    logs = []
    done = {}

    runner = merge.MergerRunner(
        on_log=lambda line, err: logs.append((line, err)),
        on_progress=lambda sec, pct, spd: progress_events.append((sec, pct, spd)),
        on_done=lambda ok, msg: done.update({"ok": ok, "msg": msg}),
    )
    runner.start(cmd, cleanup_path=list_path, duration=total)
    while runner.is_running():
        time.sleep(0.1)
    time.sleep(0.2)

    say("合并成功", done.get("ok") is True, done.get("msg", ""))
    say("输出文件已生成", os.path.isfile(output),
        ff.format_size(os.path.getsize(output)) if os.path.isfile(output) else "缺失")
    say("输出时长约 6s", abs(ff.probe_duration(output) - 6.0) < 0.6,
        f"{ff.probe_duration(output):.2f}s")
    say("捕获到进度回调", len(progress_events) > 0, f"{len(progress_events)} 次")
    say("进度百分比落在 0~1 区间",
        all(0 <= p <= 1 for _s, p, _sp in progress_events if p >= 0))
    say("日志有内容", len(logs) > 0, f"{len(logs)} 行")
    say("临时列表文件已清理", not os.path.isfile(list_path))

    print("\n[4] 重编码模式（crf）小片段验证")
    out2 = os.path.join(TMP, "out_crf.mp4")
    cmd2, lp2 = merge.build_ffmpeg_cmd(
        segs, out2, mode="crf", crf=28, list_path=os.path.join(TMP, "concat2.txt"),
        ffmpeg_path=ffmpeg_exe)
    done2 = {}
    r2 = merge.MergerRunner(on_done=lambda ok, msg: done2.update({"ok": ok, "msg": msg}))
    r2.start(cmd2, cleanup_path=lp2, duration=ff.total_duration(segs)[0])
    while r2.is_running():
        time.sleep(0.1)
    time.sleep(0.2)
    say("crf 模式合并成功", done2.get("ok") is True, done2.get("msg", ""))
    say("crf 输出存在", os.path.isfile(out2) and os.path.getsize(out2) > 0)

    print("\n[5] 停止任务")
    # 重复引用同一分片 120 次，重编码耗时足够让我们中途打断
    listed = []
    for _ in range(40):
        listed.extend(segs)
    cmd3, lp3 = merge.build_ffmpeg_cmd(
        listed, os.path.join(TMP, "out_slow.mp4"), mode="crf", crf=18,
        list_path=os.path.join(TMP, "concat3.txt"), ffmpeg_path=ffmpeg_exe)
    done3 = {}
    r3 = merge.MergerRunner(on_done=lambda ok, msg: done3.update({"ok": ok, "msg": msg}))
    r3.start(cmd3, cleanup_path=lp3)
    time.sleep(1.5)
    r3.stop()
    while r3.is_running():
        time.sleep(0.1)
    time.sleep(0.3)
    say("停止后回调为失败并带说明",
        done3.get("ok") is False and "停止" in done3.get("msg", ""), done3.get("msg", ""))

    print("\n" + "=" * 62)
    print("端到端测试" + ("全部通过" if ok_all else "存在失败项"))
    print("=" * 62)
    shutil.rmtree(TMP, ignore_errors=True)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
