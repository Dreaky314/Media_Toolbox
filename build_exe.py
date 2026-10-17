# -*- coding: utf-8 -*-
"""用 PyInstaller 打包影音工具箱。

    .venv\\Scripts\\python.exe build_exe.py
    .venv\\Scripts\\python.exe build_exe.py --with-ffmpeg "D:\\ffmpeg\\bin\\ffmpeg.exe"

会连带打包 Qt 运行库，产物约 120 MB；ffmpeg 体积也很大（约 100 MB/个），
默认**不**打进包里，程序会按 README 写的顺序去别处找。
"""

import argparse
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SEP = ";" if sys.platform == "win32" else ":"

# Qt 里用不到但体积很大的模块，排除掉能省不少
QT_EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtQuick",
    "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtBluetooth",
    "PySide6.QtDesigner", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtOpenGL",
    "PySide6.QtSerialPort", "PySide6.QtSensors", "PySide6.QtPositioning",
    "PySide6.QtNfc", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtStateMachine", "PySide6.QtSpatialAudio", "PySide6.QtHttpServer",
    "PySide6.QtLocation", "PySide6.QtWebSockets",
]


VERSION_FILE_TEMPLATE = """VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({a}, {b}, {c}, 0),
    prodvers=({a}, {b}, {c}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable("080404b0", [
        StringStruct("CompanyName", "{company}"),
        StringStruct("FileDescription", "{desc}"),
        StringStruct("FileVersion", "{version}"),
        StringStruct("InternalName", "MediaToolkit"),
        StringStruct("LegalCopyright", "{copyright}"),
        StringStruct("OriginalFilename", "{exe_name}"),
        StringStruct("ProductName", "{product}"),
        StringStruct("ProductVersion", "{version}")
      ])
    ]),
    VarFileInfo([VarStruct("Translation", [2052, 1200])])
  ]
)
"""


def write_version_file(target: str, product: str) -> str:
    """生成 PyInstaller 的 VERSIONINFO 文件。

    没有版本资源的 exe 在文件属性里是一片空白，更容易被当成「不明应用」；
    补上产品名/版本/版权后至少是个正常登记的应用程序。
    """
    version = "1.0.0.0"
    parts = version.split(".")
    text = VERSION_FILE_TEMPLATE.format(
        a=int(parts[0]), b=int(parts[1]), c=int(parts[2]),
        version=version,
        product=product,
        company=product,
        desc=f"{product} - 番剧整理与 TS 分片合并",
        copyright=f"Copyright (C) {product}",
        exe_name=f"{product}.exe",
    )
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fp:
        fp.write(text)
    return target


def main():
    parser = argparse.ArgumentParser(description="打包影音工具箱")
    parser.add_argument("--with-ffmpeg", metavar="FFMPEG_EXE",
                        help="把 ffmpeg（同目录下的 ffprobe 也会一起带上）打进包里")
    parser.add_argument("--onefile", action="store_true",
                        help="打成单个 exe（启动慢）")
    parser.add_argument("--name", default="影音工具箱", help="产物名称")
    args = parser.parse_args()

    entry = "app_qt.py"

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("没有安装 PyInstaller，请先执行：")
        print(f"    {sys.executable} -m pip install pyinstaller")
        return 1

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", args.name,
        "--icon", os.path.join(PROJECT_DIR, "assets", "app.ico"),
        "--add-data", f"{os.path.join(PROJECT_DIR, 'assets')}{SEP}assets",
        "--distpath", os.path.join(PROJECT_DIR, "dist"),
        "--workpath", os.path.join(PROJECT_DIR, "build"),
        "--specpath", os.path.join(PROJECT_DIR, "build"),
    ]

    version_file = write_version_file(
        os.path.join(PROJECT_DIR, "build", "version_info.txt"), args.name)
    cmd += ["--version-file", version_file]

    if args.onefile:
        cmd.append("--onefile")
    for mod in QT_EXCLUDES:
        cmd += ["--exclude-module", mod]

    if args.with_ffmpeg:
        exe = os.path.abspath(args.with_ffmpeg)
        if not os.path.isfile(exe):
            print(f"找不到 ffmpeg：{exe}")
            return 1
        bundled = [exe]
        folder = os.path.dirname(exe)
        for probe in ("ffprobe.exe", "ffprobe"):
            candidate = os.path.join(folder, probe)
            if os.path.isfile(candidate):
                bundled.append(candidate)
                break
        for path in bundled:
            cmd += ["--add-binary", f"{path}{SEP}ffmpeg/bin"]
        print("已加入 ffmpeg：" + "、".join(os.path.basename(p) for p in bundled))

    cmd.append(os.path.join(PROJECT_DIR, entry))

    print("入口：" + entry)
    print("$ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print("打包失败")
        return result.returncode

    out_dir = os.path.join(PROJECT_DIR, "dist", args.name)
    exe_path = os.path.join(out_dir, args.name + ".exe")
    if os.path.isfile(exe_path):
        # 去掉「来自 Internet」标记（下载过的文件才需要，顺手做掉）
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Unblock-File -LiteralPath '{exe_path}'"],
                           capture_output=True)
        except Exception:
            pass

    total = 0
    for root, _dirs, files in os.walk(out_dir):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass

    print("\n打包完成：")
    print("  " + out_dir)
    print(f"  体积约 {total / 1024 / 1024:.0f} MB")
    print("\n注意：exe 没有代码签名，第一次运行可能弹 SmartScreen。")
    print("      想完全避开就用项目根目录的 启动.bat（跑源码，零提示）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
