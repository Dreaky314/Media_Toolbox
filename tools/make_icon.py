# -*- coding: utf-8 -*-
"""生成 assets/app.ico：与界面内左上角品牌标识同一套绘制，多尺寸、正方形。

    .venv\\Scripts\\python.exe tools\\make_icon.py

原来的 app.ico 是 256x241 的非正方形图，任务栏/标题栏里缩放会变形，
而且只有单一尺寸，小图标会糊。这里用 Qt 重新渲染 16~256 共 7 个尺寸，
按 ICO 规范（PNG 压缩条目）打包成一个多尺寸图标。
"""

import io
import os
import struct
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt        # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication                         # noqa: E402

PRIMARY = "#3D6DF6"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(size: int) -> QPixmap:
    """蓝色圆角方块 + 白色播放三角（与 qtui.widgets.make_brand_mark 一致）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(PRIMARY))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.29, size * 0.29)

    p.setBrush(QColor("#FFFFFF"))
    cx, cy, r = size / 2.0, size / 2.0, size * 0.21
    path = QPainterPath()
    path.moveTo(cx - r * 0.55, cy - r)
    path.lineTo(cx - r * 0.55, cy + r)
    path.lineTo(cx + r, cy)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return pm


def png_bytes(pm: QPixmap) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.WriteOnly)
    pm.toImage().save(buf, "PNG")
    buf.close()
    return bytes(data)


def build_ico(images: list) -> bytes:
    """按 ICO 规范拼装：ICONDIR + ICONDIRENTRY[] + 各尺寸 PNG 数据。"""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)          # reserved, type=icon, count
    entries = b""
    payload = b""
    offset = 6 + 16 * count
    for size, blob in images:
        dim = 0 if size >= 256 else size               # 0 表示 256
        entries += struct.pack(
            "<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(payload))
        payload += blob
    return header + entries + payload


def main():
    out = os.path.join(PROJECT_DIR, "assets", "app.ico")

    # QPixmap/QPainter 需要 QGuiApplication
    app = QApplication.instance() or QApplication(sys.argv)

    images = []
    for size in SIZES:
        images.append((size, png_bytes(render(size))))

    blob = build_ico(images)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fp:
        fp.write(blob)

    # 回读校验
    from PySide6.QtGui import QIcon
    icon = QIcon(out)
    got = sorted({(s.width(), s.height()) for s in icon.availableSizes()})
    print(f"已写出 {out}")
    print(f"  {len(blob)} 字节，包含尺寸: {got}")
    print(f"  QIcon.isNull() = {icon.isNull()}")
    del app
    return 0


if __name__ == "__main__":
    sys.exit(main())
