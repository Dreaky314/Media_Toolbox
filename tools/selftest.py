# -*- coding: utf-8 -*-
"""不依赖界面的自测脚本：验证扫描、命名、复制/移动与 ffmpeg 命令构建。

用法：
    python tools/selftest.py
"""

import contextlib
import os
import shutil
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

TMP_ROOT = os.path.join(ROOT_DIR, ".selftest_tmp")
_counter = [0]


@contextlib.contextmanager
def tempfile_dir():
    """项目内的临时目录（避免沙箱对系统临时目录的限制）。"""
    _counter[0] += 1
    path = os.path.join(TMP_ROOT, f"case{_counter[0]}")
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

from core import merge, m3u8, rename  # noqa: E402

PASS, FAIL = [], []


def check(name, condition, detail=""):
    (PASS if condition else FAIL).append(name)
    print(f"  {'PASS' if condition else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))


def make_file(path, size=1024, content=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fp:
        fp.write(content if content is not None else b"\0" * size)


def build_fixture(base):
    root = os.path.join(base, "某番剧")
    make_file(os.path.join(root, "1", "EP01_[1080p].mp4"), 4096)
    make_file(os.path.join(root, "2", "第02话.mkv"), 2048)
    make_file(os.path.join(root, "3", "readme.txt"), 10)          # 无视频
    make_file(os.path.join(root, "10", "final.mp4"), 8192)
    make_file(os.path.join(root, "10", "extra.mp4"), 512)          # 同目录第二个视频
    make_file(os.path.join(root, "SP", "ova.mp4"), 1024)           # 非数字目录
    make_file(os.path.join(root, "01", "dup.mp4"), 1024)           # 与 1 冲突
    return root


def test_scan_and_copy():
    print("\n[1] 扫描 + 复制")
    with tempfile_dir() as base:
        root = build_fixture(base)
        result = rename.scan(root, action=rename.ACTION_COPY)
        numbers = [e.number for e in result.episodes]
        check("识别出全部数字目录", numbers == [1, 1, 2, 3, 10], str(numbers))
        check("自动补零位数为 2", result.width == 2, str(result.width))
        check("SP 目录被忽略", result.ignored_dirs == ["SP"], str(result.ignored_dirs))

        by_name = {e.folder_name: e for e in result.episodes}
        check("1/ 目标名正确", by_name["1"].target_name == "01.mp4", by_name["1"].target_name)
        check("10/ 目标名正确", by_name["10"].target_name == "10.mp4", by_name["10"].target_name)
        check("10/ 记录了多余视频", len(by_name["10"].other_videos) == 1)
        check("3/ 标记为无视频", by_name["3"].status == rename.ST_NO_VIDEO)
        check("01/ 标记为命名冲突", by_name["01"].status == rename.ST_CONFLICT, by_name["01"].note)
        check("就绪项为 3 条（1/2/10）", len(result.ready) == 3, str(len(result.ready)))

        stats = rename.execute(result, action=rename.ACTION_COPY)
        check("执行成功 3 条", stats["ok"] == 3, str(stats))
        check("根目录出现 01.mp4", os.path.isfile(os.path.join(root, "01.mp4")))
        check("根目录出现 10.mp4", os.path.isfile(os.path.join(root, "10.mp4")))
        check("子文件夹内源文件已重命名",
              os.path.isfile(os.path.join(root, "1", "01.mp4")))
        check("原文件名已不存在",
              not os.path.isfile(os.path.join(root, "1", "EP01_[1080p].mp4")))


def test_move_and_fixed_width():
    print("\n[2] 移动 + 固定三位补零")
    with tempfile_dir() as base:
        root = build_fixture(base)
        out = os.path.join(base, "输出")
        os.makedirs(out)
        result = rename.scan(root, action=rename.ACTION_MOVE, out_dir=out,
                             width_mode="fixed", fixed_width=3)
        check("固定宽度生效", result.width == 3, str(result.width))
        stats = rename.execute(result, action=rename.ACTION_MOVE)
        check("移动成功 3 条", stats["ok"] == 3, str(stats))
        check("输出目录得到 001.mp4", os.path.isfile(os.path.join(out, "001.mp4")))
        check("输出目录得到 010.mp4", os.path.isfile(os.path.join(out, "010.mp4")))
        check("源文件已被移走",
              not os.path.isfile(os.path.join(root, "1", "001.mp4")))


def test_rename_only():
    print("\n[3] 仅重命名模式")
    with tempfile_dir() as base:
        root = build_fixture(base)
        result = rename.scan(root, action=rename.ACTION_RENAME)
        stats = rename.execute(result, action=rename.ACTION_RENAME)
        check("重命名成功 4 条（1/01/2/10 各一个视频）", stats["ok"] == 4, str(stats))
        check("同名目录都按各自集数重命名",
              os.path.isfile(os.path.join(root, "1", "01.mp4"))
              and os.path.isfile(os.path.join(root, "01", "01.mp4")))
        check("2/第02话.mkv -> 02.mkv", os.path.isfile(os.path.join(root, "2", "02.mkv")))
        check("根目录未新增文件", not os.path.isfile(os.path.join(root, "02.mkv")))


def test_largest_pick():
    print("\n[4] 多视频时取体积最大的")
    with tempfile_dir() as base:
        root = build_fixture(base)
        result = rename.scan(root, action=rename.ACTION_COPY, pick="largest")
        ep10 = [e for e in result.episodes if e.folder_name == "10"][0]
        check("选中 extra? (extra 更小，应选 final)", ep10.source_name == "final.mp4", ep10.source_name)


def test_path_clean():
    print("\n[5] 路径清洗")
    check('去掉引号与空白', rename.clean_path('  "D:\\a b\\c"  ') == "D:\\a b\\c")
    check("空字符串安全", rename.clean_path("") == "")


def test_merge_cmd():
    print("\n[6] 合并命令构建")
    with tempfile_dir() as base:
        seg_dir = os.path.join(base, "segs")
        for i in [1, 2, 10]:
            make_file(os.path.join(seg_dir, f"{i}.ts"), 2048)
        files = merge.list_ts_files(seg_dir)
        check("自然排序 1,2,10", [os.path.basename(f) for f in files] == ["1.ts", "2.ts", "10.ts"],
              str([os.path.basename(f) for f in files]))

        out = os.path.join(base, "out.mp4")
        cmd, list_path = merge.build_ffmpeg_cmd(files, out, mode="copy",
                                                ffmpeg_path="ffmpeg")
        check("concat 参数存在", "-f" in cmd and "concat" in cmd)
        check("copy 模式使用 -c copy", "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy")
        check("mp4 追加 aac_adtstoasc", "aac_adtstoasc" in cmd)
        check("输出文件在末尾", cmd[-1] == out, cmd[-1])
        check("列表文件已生成", os.path.isfile(list_path))
        with open(list_path, encoding="utf-8") as fp:
            lines = fp.read().strip().splitlines()
        check("列表文件含 3 条", len(lines) == 3, str(len(lines)))
        check("列表文件用正斜杠", "\\" not in lines[0], lines[0])

        cmd2, lp2 = merge.build_ffmpeg_cmd(files, out, mode="crf", crf=20,
                                           ffmpeg_path="ffmpeg")
        check("crf 模式参数正确", "-crf" in cmd2 and cmd2[cmd2.index("-crf") + 1] == "20")
        cmd3, lp3 = merge.build_ffmpeg_cmd(files, out, mode="bitrate",
                                           video_bitrate="6M", ffmpeg_path="ffmpeg")
        check("bitrate 模式参数正确", "-b:v" in cmd3 and cmd3[cmd3.index("-b:v") + 1] == "6M")

        for p in (list_path, lp2, lp3):
            try:
                os.remove(p)
            except OSError:
                pass

        try:
            merge.build_ffmpeg_cmd([], out)
            check("空列表抛错", False)
        except ValueError as e:
            check("空列表抛错", True, str(e))

        try:
            merge.build_ffmpeg_cmd([os.path.join(seg_dir, "nope.ts")], out)
            check("缺失文件抛错", False)
        except ValueError as e:
            check("缺失文件抛错", True, str(e))

        try:
            merge.build_ffmpeg_cmd(files, "")
            check("空输出抛错", False)
        except ValueError as e:
            check("空输出抛错", True, str(e))


def test_m3u8():
    print("\n[7] m3u8 解析")
    with tempfile_dir() as base:
        for i in range(1, 4):
            make_file(os.path.join(base, f"seg{i}.ts"), 1024)
        path = os.path.join(base, "index.m3u8")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write("#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n")
            fp.write("#EXTINF:9.5,\nseg1.ts\n#EXTINF:9.0,\nseg2.ts\n")
            fp.write("#EXTINF:1.0,\nseg3.ts\n#EXT-X-ENDLIST\n")
        info = m3u8.parse_m3u8(path)
        check("解析出 3 个分片", len(info["segments"]) == 3, str(info["segments"]))
        check("非加密", info["encrypted"] is False)
        check("非 master", info["is_master"] is False)
        check("含 ENDLIST", info["has_endlist"] is True)
        check("总时长约 19.5s", abs(info["duration"] - 19.5) < 0.01, str(info["duration"]))
        segs = m3u8.resolve_segments(info)
        check("分片路径全部存在", all(os.path.isfile(s) for s in segs))
        check("缺失分片为空", m3u8.missing_segments(info) == [])

        enc = os.path.join(base, "enc.m3u8")
        with open(enc, "w", encoding="utf-8") as fp:
            fp.write("#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI=\"k\"\nseg1.ts\n")
        check("能识别加密标签", m3u8.parse_m3u8(enc)["encrypted"] is True)

        bad = os.path.join(base, "bad.m3u8")
        with open(bad, "w", encoding="utf-8") as fp:
            fp.write("not a playlist\n")
        try:
            m3u8.parse_m3u8(bad)
            check("非法 m3u8 抛错", False)
        except m3u8.M3U8Error:
            check("非法 m3u8 抛错", True)


def test_osutil():
    print("\n[8] 打开目录/定位文件的参数校验")
    from core import osutil
    ok, detail = osutil.open_folder("")
    check("空路径被拒绝", ok is False and "空" in detail, detail)
    ok, detail = osutil.open_folder(r"Z:\肯定不存在的目录")
    check("不存在的目录被拒绝", ok is False and "不存在" in detail, detail)
    ok, detail = osutil.reveal_path(r"Z:\不存在\a.json")
    check("定位不存在的文件时优雅失败", ok is False, detail)
    ok, detail = osutil.reveal_path("")
    check("定位空路径被拒绝", ok is False, detail)


def test_osutil_launch_flags():
    """explorer 的启动参数：不能带 CREATE_NO_WINDOW。

    带上它会直接失败并弹「explorer.exe - Application Error (0xc0000142)」。
    """
    print("\n[9] 打开目录的启动参数")
    import subprocess

    from core import osutil

    captured = {}
    real_popen = subprocess.Popen

    class FakeProc:
        def terminate(self):
            pass

    def fake_popen(args, **kw):
        captured["args"] = args
        captured["kw"] = kw
        return FakeProc()

    subprocess.Popen = fake_popen
    try:
        ok, _detail = osutil.open_folder(ROOT_DIR)
    finally:
        subprocess.Popen = real_popen

    check("open_folder 成功返回", ok is True)
    check("启动的是 explorer", captured["args"][0] == "explorer", str(captured["args"][:1]))
    check("没有给 explorer 传 creationflags",
          "creationflags" not in captured["kw"],
          str(sorted(captured["kw"])))
    check("子进程 stdio 已重定向，避免占住调用方管道",
          captured["kw"].get("stdin") is subprocess.DEVNULL
          and captured["kw"].get("stdout") is subprocess.DEVNULL)

    # 定位文件用的 /select, 也一样不能带 flags
    captured.clear()
    subprocess.Popen = fake_popen
    try:
        osutil.reveal_path(os.path.join(ROOT_DIR, "README.md"))
    finally:
        subprocess.Popen = real_popen
    if captured:
        check("reveal_path 同样不带 creationflags",
              "creationflags" not in captured["kw"], str(sorted(captured["kw"])))


def main():
    print("=" * 62)
    print("core 层自测")
    print("=" * 62)
    test_scan_and_copy()
    test_move_and_fixed_width()
    test_rename_only()
    test_largest_pick()
    test_path_clean()
    test_merge_cmd()
    test_m3u8()
    test_osutil()
    test_osutil_launch_flags()
    print("\n" + "=" * 62)
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：" + "，".join(FAIL))
    print("=" * 62)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
