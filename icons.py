"""
Ícones vetoriais desenhados com QPainter (sem depender de arquivos externos).

Usados na sidebar do Screvo — linhas brancas e limpas sobre o fundo rosa.
Também gera o ícone/monograma do app.
"""

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QPen, QColor, QPainterPath, QBrush,
    QLinearGradient, QPolygonF, QFont
)


def _new_pixmap(size):
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    return pm


def make_icon(name, size=22, color="#FFFFFF"):
    """Retorna um QIcon desenhado para o nome pedido."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(max(1.6, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    s = size
    m = s * 0.18  # margem

    if name == "geral":  # casa
        path = QPainterPath()
        path.moveTo(m, s * 0.45)
        path.lineTo(s / 2, m)
        path.lineTo(s - m, s * 0.45)
        p.drawPath(path)
        p.drawRect(QRectF(s * 0.26, s * 0.45, s * 0.48, s * 0.37))

    elif name == "audio":  # alto-falante + ondas
        spk = QPolygonF([
            QPointF(m, s * 0.40), QPointF(s * 0.34, s * 0.40),
            QPointF(s * 0.52, s * 0.24), QPointF(s * 0.52, s * 0.76),
            QPointF(s * 0.34, s * 0.60), QPointF(m, s * 0.60),
        ])
        p.drawPolygon(spk)
        p.drawArc(QRectF(s * 0.45, s * 0.30, s * 0.30, s * 0.40), -60 * 16, 120 * 16)
        p.drawArc(QRectF(s * 0.45, s * 0.20, s * 0.48, s * 0.60), -55 * 16, 110 * 16)

    elif name == "avancado":  # sliders
        for i, y in enumerate((0.30, 0.50, 0.70)):
            yy = s * y
            p.drawLine(QPointF(m, yy), QPointF(s - m, yy))
            cx = s * (0.35 + 0.20 * i)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(cx, yy), s * 0.06, s * 0.06)
            p.setBrush(Qt.BrushStyle.NoBrush)

    elif name == "transcricao":  # documento com linhas de texto
        p.drawRoundedRect(QRectF(s * 0.24, m, s * 0.52, s - 2 * m), s * 0.06, s * 0.06)
        for y in (0.36, 0.50, 0.64):
            p.drawLine(QPointF(s * 0.33, s * y), QPointF(s * 0.67, s * y))

    elif name == "ia":  # brilho / sparkle
        cx, cy, r = s / 2, s / 2, s * 0.34
        star = QPainterPath()
        star.moveTo(cx, cy - r)
        star.cubicTo(cx + r * 0.18, cy - r * 0.18, cx + r * 0.18, cy - r * 0.18, cx + r, cy)
        star.cubicTo(cx + r * 0.18, cy + r * 0.18, cx + r * 0.18, cy + r * 0.18, cx, cy + r)
        star.cubicTo(cx - r * 0.18, cy + r * 0.18, cx - r * 0.18, cy + r * 0.18, cx - r, cy)
        star.cubicTo(cx - r * 0.18, cy - r * 0.18, cx - r * 0.18, cy - r * 0.18, cx, cy - r)
        p.setBrush(QColor(color))
        p.drawPath(star)
        p.setBrush(Qt.BrushStyle.NoBrush)

    elif name == "videos":  # play dentro de retângulo (tela)
        p.drawRoundedRect(QRectF(m, s * 0.24, s - 2 * m, s * 0.52), s * 0.08, s * 0.08)
        tri = QPolygonF([
            QPointF(s * 0.42, s * 0.38), QPointF(s * 0.42, s * 0.62),
            QPointF(s * 0.62, s * 0.50),
        ])
        p.setBrush(QColor(color))
        p.drawPolygon(tri)
        p.setBrush(Qt.BrushStyle.NoBrush)

    elif name == "sobre":  # info
        p.drawEllipse(QRectF(m, m, s - 2 * m, s - 2 * m))
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(s / 2, s * 0.34), s * 0.045, s * 0.045)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(s / 2, s * 0.46), QPointF(s / 2, s * 0.68))

    p.end()
    return QIcon(pm)


def make_app_icon_pixmap(size):
    """Ícone do app Screvo: quadro de tela rosa com ponto REC e traços de texto."""
    pm = _new_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size

    # Fundo arredondado com degradê rosa
    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor("#FFB6C1"))
    grad.setColorAt(0.5, QColor("#FF91A4"))
    grad.setColorAt(1.0, QColor("#FF69B4"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.PenStyle.NoPen)
    radius = s * 0.22
    p.drawRoundedRect(QRectF(0, 0, s, s), radius, radius)

    # "Tela" branca
    p.setBrush(QColor(255, 255, 255))
    screen = QRectF(s * 0.22, s * 0.28, s * 0.56, s * 0.40)
    p.drawRoundedRect(screen, s * 0.05, s * 0.05)

    # Linhas de texto (transcrição) dentro da tela
    pen = QPen(QColor("#FF69B4"))
    pen.setWidthF(max(1.2, s * 0.03))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for i, y in enumerate((0.40, 0.48, 0.56)):
        x2 = s * (0.68 if i < 2 else 0.58)
        p.drawLine(QPointF(s * 0.29, s * y), QPointF(x2, s * y))

    # Ponto REC (vermelho) no canto da tela
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#FF1744"))
    p.drawEllipse(QPointF(s * 0.70, s * 0.36), s * 0.045, s * 0.045)

    p.end()
    return pm


def make_app_icon(size=256):
    return QIcon(make_app_icon_pixmap(size))
