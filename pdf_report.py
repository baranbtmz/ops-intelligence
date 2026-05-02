"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 6: PDF Rapor Üretici

Kurulum:
pip install reportlab --break-system-packages
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable

# ── Türkçe karakter desteği için DejaVu fontlarını kaydet
_FONT_PATHS = {
    "DejaVu":         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu-Bold":    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVu-Oblique": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "DejaVu-Mono":    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
}

# macOS fallback (system font)
_MAC_PATHS = {
    "DejaVu":         "/System/Library/Fonts/Helvetica.ttc",
    "DejaVu-Bold":    "/System/Library/Fonts/Helvetica.ttc",
    "DejaVu-Oblique": "/System/Library/Fonts/Helvetica.ttc",
    "DejaVu-Mono":    "/System/Library/Fonts/Courier.ttc",
}

import os as _os

def _register_fonts():
    """DejaVu fontlarını kaydet (Türkçe karakter desteği)"""
    registered = []
    for name, path in _FONT_PATHS.items():
        if _os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered.append(name)
            except Exception:
                pass

    # Hiç font yoksa (örn. macOS) — unicode encoding ile Helvetica kullan
    return len(registered) > 0

_HAS_DEJAVU = _register_fonts()
_FONT_NORMAL = "DejaVu"      if _HAS_DEJAVU else "Helvetica"
_FONT_BOLD   = "DejaVu-Bold" if _HAS_DEJAVU else "Helvetica-Bold"
_FONT_MONO   = "DejaVu-Mono" if _HAS_DEJAVU else "Courier"


# ─────────────────────────────────────────────
# RENK PALETİ
# ─────────────────────────────────────────────

C_BG      = colors.HexColor("#0f0f0f")
C_SURFACE = colors.HexColor("#1a1a1a")
C_BORDER  = colors.HexColor("#2a2a2a")
C_ACCENT  = colors.HexColor("#c9a84c")   # Gold
C_ACCENT2 = colors.HexColor("#e8c97a")   # Light gold
C_WARN    = colors.HexColor("#d4a017")
C_DANGER  = colors.HexColor("#c0392b")
C_TEXT    = colors.HexColor("#f0ece4")
C_MUTED   = colors.HexColor("#888880")
C_WHITE   = colors.white
C_BLACK   = colors.black


# ─────────────────────────────────────────────
# ÖZEL FLOWABLE: Renkli arka plan bloğu
# ─────────────────────────────────────────────

class ColorBox(Flowable):
    """Renkli arka planlı blok"""
    def __init__(self, width, height, fill_color, border_color=None):
        super().__init__()
        self.width      = width
        self.height     = height
        self.fill_color = fill_color
        self.border_color = border_color

    def draw(self):
        self.canv.setFillColor(self.fill_color)
        if self.border_color:
            self.canv.setStrokeColor(self.border_color)
            self.canv.setLineWidth(0.5)
            self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=1)
        else:
            self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)


class AccentLine(Flowable):
    """Renkli yatay çizgi"""
    def __init__(self, width, color=C_ACCENT, thickness=2):
        super().__init__()
        self.width     = width
        self.color     = color
        self.thickness = thickness
        self.height    = thickness + 4

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.thickness/2, self.width, self.thickness/2)


# ─────────────────────────────────────────────
# STİL SİSTEMİ
# ─────────────────────────────────────────────

def make_styles():
    N = _FONT_NORMAL
    B = _FONT_BOLD
    M = _FONT_MONO
    return {
        "cover_title": ParagraphStyle(
            "cover_title", fontName=B, fontSize=34,
            textColor=C_TEXT, leading=40, letterSpacing=1,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName=N, fontSize=10,
            textColor=C_MUTED, leading=16, letterSpacing=0.5,
        ),
        "cover_shop": ParagraphStyle(
            "cover_shop", fontName=B, fontSize=14,
            textColor=C_ACCENT, leading=20,
        ),
        "section_head": ParagraphStyle(
            "section_head", fontName=B, fontSize=13,
            textColor=C_TEXT, leading=18, spaceBefore=8, spaceAfter=6,
        ),
        "label": ParagraphStyle(
            "label", fontName=N, fontSize=8,
            textColor=C_MUTED, leading=12, letterSpacing=0.3,
        ),
        "body": ParagraphStyle(
            "body", fontName=N, fontSize=9,
            textColor=C_MUTED, leading=14,
        ),
        "body_white": ParagraphStyle(
            "body_white", fontName=N, fontSize=9,
            textColor=C_TEXT, leading=14,
        ),
        "kpi_value": ParagraphStyle(
            "kpi_value", fontName=B, fontSize=22,
            textColor=C_TEXT, leading=26,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label", fontName=N, fontSize=7,
            textColor=C_MUTED, leading=10, letterSpacing=0.5,
        ),
        "finding_title": ParagraphStyle(
            "finding_title", fontName=B, fontSize=10,
            textColor=C_TEXT, leading=14,
        ),
        "finding_body": ParagraphStyle(
            "finding_body", fontName=N, fontSize=8,
            textColor=C_MUTED, leading=12,
        ),
        "action": ParagraphStyle(
            "action", fontName=B, fontSize=8,
            textColor=C_ACCENT, leading=12,
        ),
        "tag": ParagraphStyle(
            "tag", fontName=B, fontSize=7,
            textColor=C_BLACK, leading=10, letterSpacing=0.3,
        ),
        "footer": ParagraphStyle(
            "footer", fontName=N, fontSize=7,
            textColor=C_MUTED, leading=10, alignment=TA_CENTER,
        ),
        "quick_win": ParagraphStyle(
            "quick_win", fontName=N, fontSize=9,
            textColor=C_TEXT, leading=13,
        ),
        "qw_num": ParagraphStyle(
            "qw_num", fontName=B, fontSize=14,
            textColor=C_ACCENT, leading=18,
        ),
    }


# ─────────────────────────────────────────────
# SAYFA ARKA PLANI (her sayfa için)
# ─────────────────────────────────────────────

def dark_background(canvas, doc):
    """Her sayfaya koyu arka plan uygular"""
    canvas.saveState()
    canvas.setFillColor(C_BG)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)

    # Alt footer çizgisi
    canvas.setStrokeColor(C_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(20*mm, 14*mm, A4[0]-20*mm, 14*mm)

    # Footer metni
    canvas.setFillColor(C_MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(20*mm, 10*mm, "OPS·INTELLIGENCE — Confidential Analysis Report")
    canvas.drawRightString(A4[0]-20*mm, 10*mm,
                           f"Page {doc.page} | {datetime.now().strftime('%d.%m.%Y')}")

    # Üst accent çizgi (kapak hariç)
    if doc.page > 1:
        canvas.setStrokeColor(C_ACCENT)
        canvas.setLineWidth(1.5)
        canvas.line(20*mm, A4[1]-18*mm, 60*mm, A4[1]-18*mm)

    canvas.restoreState()


# ─────────────────────────────────────────────
# PDF ÜRETEC
# ─────────────────────────────────────────────

class PDFReportGenerator:
    """
    Analiz sonuçlarını profesyonel PDF rapora dönüştürür.
    Koyu tema, markalı tasarım, müşteriye gönderilebilir format.
    """

    def __init__(self, analysis_result: dict, meta_result: dict = None,
                 shop_name: str = "Demo Mağaza"):
        self.result    = analysis_result
        self.meta      = meta_result
        self.shop_name = shop_name
        self.analysis  = analysis_result.get("analysis", {})
        self.metrics   = analysis_result.get("metrics", {})
        self.styles    = make_styles()
        self.W         = A4[0] - 40*mm  # kullanılabilir genişlik

    def _sp(self, name) -> ParagraphStyle:
        return self.styles[name]

    def _spacer(self, h=6) -> Spacer:
        return Spacer(1, h*mm)

    def _hr(self, color=C_BORDER, thickness=0.5) -> HRFlowable:
        return HRFlowable(width="100%", thickness=thickness,
                          color=color, spaceAfter=4*mm, spaceBefore=4*mm)

    # ── KAPAK SAYFASI ────────────────────────
    def _cover(self) -> list:
        story = []
        story.append(Spacer(1, 30*mm))

        # Logo / başlık
        story.append(Paragraph("OPS·INTELLIGENCE", self._sp("cover_title")))
        story.append(AccentLine(self.W, C_ACCENT, 3))
        story.append(self._spacer(4))

        story.append(Paragraph(
            "E-COMMERCE OPERATIONAL ANALYSIS REPORT",
            self._sp("cover_sub")
        ))
        story.append(self._spacer(12))

        # Mağaza bilgisi kutusu
        ft  = self.metrics.get("fulfillment_time", {})
        rev = self.metrics.get("revenue", {})
        score = self.analysis.get("overall_health_score", 0)

        cover_data = [
            [Paragraph("STORE", self._sp("label")),
             Paragraph("ANALYSIS DATE", self._sp("label")),
             Paragraph("ORDER COUNT", self._sp("label")),
             Paragraph("HEALTH SCORE", self._sp("label"))],
            [Paragraph(f"<b>{self.shop_name}</b>", self._sp("body_white")),
             Paragraph(datetime.now().strftime("%d.%m.%Y"), self._sp("body_white")),
             Paragraph(f"{rev.get('total_orders',0):,}", self._sp("body_white")),
             Paragraph(f"{score}/100", self._sp("body_white"))],
        ]
        cover_table = Table(cover_data, colWidths=[self.W/4]*4)
        cover_table.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,-1), C_SURFACE),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [C_SURFACE, C_SURFACE]),
            ("BOX",         (0,0), (-1,-1), 0.5, C_BORDER),
            ("INNERGRID",   (0,0), (-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",  (0,0), (-1,-1), 8),
            ("BOTTOMPADDING",(0,0), (-1,-1), 8),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
        ]))
        story.append(cover_table)
        story.append(self._spacer(8))

        # Yönetici özeti
        story.append(Paragraph("EXECUTIVE SUMMARY", self._sp("label")))
        story.append(self._spacer(2))
        summary_box = Table(
            [[Paragraph(self.analysis.get("executive_summary",""), self._sp("body_white"))]],
            colWidths=[self.W],
        )
        summary_box.setStyle(TableStyle([
            ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
            ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
            ("LEFTPADDING",  (0,0), (-1,-1), 12),
            ("RIGHTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING",   (0,0), (-1,-1), 10),
            ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ]))
        story.append(summary_box)
        story.append(self._spacer(10))

        # Sağlık skoru göstergesi
        score_color = C_ACCENT if score >= 75 else C_WARN if score >= 50 else C_DANGER
        score_data = [[
            Paragraph("OPERATIONAL HEALTH SCORE", self._sp("label")),
            Paragraph(f"{score}", ParagraphStyle("big_score",
                fontName=_FONT_BOLD, fontSize=48,
                textColor=score_color, leading=52)),
            Paragraph(self.analysis.get("overall_health_label",""), ParagraphStyle("label2",
                fontName=_FONT_BOLD, fontSize=14,
                textColor=score_color, leading=18)),
        ]]
        score_table = Table(score_data, colWidths=[50*mm, 35*mm, self.W-85*mm])
        score_table.setStyle(TableStyle([
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0,0), (-1,-1), 12),
            ("BOTTOMPADDING",(0,0), (-1,-1), 12),
        ]))
        story.append(score_table)

        story.append(PageBreak())
        return story

    # ── KPI ÖZETİ ────────────────────────────
    def _kpi_section(self) -> list:
        story = []
        story.append(Paragraph("KEY PERFORMANCE INDICATORS", self._sp("section_head")))
        story.append(AccentLine(self.W, C_ACCENT, 1.5))
        story.append(self._spacer(3))

        ft  = self.metrics.get("fulfillment_time", {})
        rev = self.metrics.get("revenue", {})
        inv = self.metrics.get("inventory", {})

        kpis = [
            ("TOTAL REVENUE",       f"€{rev.get('total_revenue',0):,.0f}", f"{rev.get('total_orders',0)} orders"),
            ("AVG. BASKET (AOV)",   f"€{rev.get('aov',0):.0f}",          "Target: €250"),
            ("CANCELLATION RATE",   f"%{rev.get('cancellation_rate',0)}", "Target: <2.5%"),
            ("REFUND RATE",         f"%{rev.get('refund_rate',0)}",       "Industry: 5-8%"),
            ("FULFILLMENT MEDIAN",  f"{ft.get('median',0)}s",            "Target: <24s"),
            ("P95 FULFILLMENT",     f"{ft.get('p95',0)}s",               f">72s: {ft.get('orders_over_72h',0)} orders"),
        ]

        rows = []
        row  = []
        for i, (label, value, note) in enumerate(kpis):
            cell = Table([[
                Paragraph(label, self._sp("kpi_label")),
                Paragraph(value, self._sp("kpi_value")),
                Paragraph(note,  self._sp("body")),
            ]], colWidths=[(self.W/3 - 4*mm)])
            cell.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("TOPPADDING",   (0,0), (-1,-1), 8),
                ("BOTTOMPADDING",(0,0), (-1,-1), 8),
            ]))
            row.append(cell)
            if len(row) == 3:
                rows.append(row)
                row = []

        if row:
            while len(row) < 3:
                row.append(Spacer(1,1))
            rows.append(row)

        grid = Table(rows, colWidths=[self.W/3]*3,
                     rowHeights=[28*mm]*len(rows))
        grid.setStyle(TableStyle([
            ("VALIGN",  (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0), (-1,-1), 2),
            ("RIGHTPADDING", (0,0), (-1,-1), 2),
            ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ]))
        story.append(grid)
        story.append(self._spacer(6))
        return story

    # ── BULGULAR ─────────────────────────────
    def _findings_section(self) -> list:
        story = []
        story.append(Paragraph("OPERATIONAL FINDINGS & ACTION PLAN", self._sp("section_head")))
        story.append(AccentLine(self.W, C_ACCENT, 1.5))
        story.append(self._spacer(3))

        findings = sorted(self.analysis.get("findings",[]), key=lambda x: x["priority"])
        sev_colors = {"critical": C_DANGER, "warning": C_WARN, "ok": C_ACCENT}
        pri_labels = {1:"CRITICAL",2:"HIGH",3:"MEDIUM",4:"LOW",5:"MONITOR"}

        for f in findings:
            sc  = sev_colors.get(f["severity"], C_MUTED)
            pri = pri_labels.get(f["priority"], str(f["priority"]))

            # Başlık satırı
            header_data = [[
                Paragraph(f"{'●'} {pri}", ParagraphStyle("pri",
                    fontName=_FONT_BOLD, fontSize=8,
                    textColor=sc, leading=11)),
                Paragraph(f["area"].upper(), self._sp("label")),
                Paragraph(
                    f"Efor: {f.get('estimated_effort','—')}  |  Etki: {f.get('estimated_impact','—')}",
                    self._sp("label")
                ),
            ]]
            header = Table(header_data,
                           colWidths=[25*mm, 50*mm, self.W-75*mm])
            header.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                ("TOPPADDING",   (0,0), (-1,-1), 6),
                ("BOTTOMPADDING",(0,0), (-1,-1), 4),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("LINEBELOW",    (0,0), (-1,-1), 0.5, sc),
            ]))

            # İçerik
            content_data = [
                [Paragraph(f["title"], self._sp("finding_title"))],
                [Spacer(1, 2*mm)],
                [Paragraph(f"Root Cause: {f['root_cause']}", self._sp("finding_body"))],
                [Spacer(1, 1*mm)],
                [Paragraph(f"Business Impact: {f.get('impact','—')}", self._sp("finding_body"))],
                [Spacer(1, 2*mm)],
                [Paragraph(f"→ Action: {f['recommendation']}", self._sp("action"))],
            ]
            content = Table(content_data, colWidths=[self.W])
            content.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("RIGHTPADDING", (0,0), (-1,-1), 10),
                ("TOPPADDING",   (0,0), (-1,-1), 2),
                ("BOTTOMPADDING",(0,0), (-1,-1), 2),
                ("LINEAFTER",    (0,0), (0,-1), 2, sc),
                ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
            ]))

            story.append(KeepTogether([header, content, self._spacer(3)]))

        return story

    # ── HIZLI KAZANIMLAR ────────────────────
    def _quick_wins_section(self) -> list:
        story = []
        story.append(PageBreak())
        story.append(Paragraph("THIS WEEK'S ACTION ITEMS", self._sp("section_head")))
        story.append(AccentLine(self.W, C_ACCENT, 1.5))
        story.append(self._spacer(3))

        qws = self.analysis.get("quick_wins", [])
        for i, qw in enumerate(qws, 1):
            row_data = [[
                Paragraph(f"{i:02d}", self._sp("qw_num")),
                Paragraph(qw, self._sp("quick_win")),
            ]]
            row = Table(row_data, colWidths=[15*mm, self.W-15*mm])
            row.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
                ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
                ("TOPPADDING",   (0,0), (-1,-1), 10),
                ("BOTTOMPADDING",(0,0), (-1,-1), 10),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("LINEBEFORE",   (1,0), (1,-1), 2, C_ACCENT),
            ]))
            story.append(row)
            story.append(self._spacer(2))

        # KPI Hedefleri
        story.append(self._spacer(4))
        story.append(Paragraph("TARGET KPI TABLE", self._sp("section_head")))
        story.append(AccentLine(self.W, C_MUTED, 0.5))

        kpi = self.analysis.get("kpi_targets", {})
        ft  = self.metrics.get("fulfillment_time", {})
        rev = self.metrics.get("revenue", {})

        kpi_data = [
            [Paragraph("KPI", self._sp("label")),
             Paragraph("TARGET", self._sp("label")),
             Paragraph("CURRENT", self._sp("label")),
             Paragraph("STATUS", self._sp("label"))],
            ["Fulfillment Time",
             f"{kpi.get('fulfillment_target_hours',24)}h",
             f"{ft.get('median',0)}h",
             "✅" if ft.get('median',0) <= kpi.get('fulfillment_target_hours',24) else "⚠️"],
            ["Cancellation Rate",
             f"{kpi.get('target_cancellation_rate_pct',2.5)}%",
             f"{rev.get('cancellation_rate',0)}%",
             "✅" if rev.get('cancellation_rate',0) <= kpi.get('target_cancellation_rate_pct',2.5) else "⚠️"],
            ["Reorder Point",
             f"{kpi.get('inventory_reorder_point',30)} units",
             "Not defined",
             "🔴"],
        ]

        kpi_table = Table(kpi_data, colWidths=[60*mm, 35*mm, 35*mm, 20*mm])
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), C_SURFACE),
            ("BACKGROUND",    (0,1), (-1,-1), C_BG),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_SURFACE, C_BG]),
            ("TEXTCOLOR",     (0,0), (-1,0), C_MUTED),
            ("TEXTCOLOR",     (0,1), (-1,-1), C_TEXT),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica"),
            ("FONTNAME",      (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("BOX",           (0,0), (-1,-1), 0.5, C_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ]))
        story.append(kpi_table)
        return story

    # ── META ADS ÖZET (varsa) ────────────────
    def _meta_section(self) -> list:
        if not self.meta:
            return []

        story = []
        story.append(PageBreak())
        story.append(Paragraph("META ADS PERFORMANCE ANALYSIS", self._sp("section_head")))
        story.append(AccentLine(self.W, C_ACCENT2, 1.5))
        story.append(self._spacer(3))

        ra = self.meta.get("roas_analysis", {})

        # ROAS özet satırı
        meta_kpis = [
            ("TOTAL SPEND",    f"€{ra.get('total_spend',0):,.0f}"),
            ("TOTAL REVENUE",  f"€{ra.get('total_revenue',0):,.0f}"),
            ("BLENDED ROAS",   f"{ra.get('blended_roas',0)}x"),
            ("GOOD CAMPAIGNS", f"{ra.get('good_campaigns',0)}/{ra.get('total_campaigns',0)}"),
        ]
        meta_row = []
        for label, value in meta_kpis:
            cell_data = [[
                Paragraph(label, self._sp("kpi_label")),
                Paragraph(value, ParagraphStyle("mv", fontName=_FONT_BOLD,
                    fontSize=18, textColor=C_TEXT, leading=22)),
            ]]
            cell = Table(cell_data, colWidths=[self.W/4 - 3*mm])
            cell.setStyle(TableStyle([
                ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
                ("LEFTPADDING",  (0,0), (-1,-1), 10),
                ("TOPPADDING",   (0,0), (-1,-1), 8),
                ("BOTTOMPADDING",(0,0), (-1,-1), 8),
            ]))
            meta_row.append(cell)

        meta_grid = Table([meta_row], colWidths=[self.W/4]*4)
        meta_grid.setStyle(TableStyle([
            ("LEFTPADDING",  (0,0), (-1,-1), 2),
            ("RIGHTPADDING", (0,0), (-1,-1), 2),
        ]))
        story.append(meta_grid)
        story.append(self._spacer(4))

        # Kampanya tablosu
        camp_df = self.meta.get("campaign_summary")
        if camp_df is not None and len(camp_df) > 0:
            story.append(Paragraph("CAMPAIGN PERFORMANCE", self._sp("label")))
            story.append(self._spacer(2))

            headers = ["Campaign", "Spend €", "Revenue €", "ROAS", "CPC €", "Status"]
            table_data = [headers]
            for _, row in camp_df.iterrows():
                table_data.append([
                    row["campaign_name"][:35],
                    f"€{row['spend']:,.0f}",
                    f"€{row['revenue']:,.0f}",
                    f"{row['roas']}x",
                    f"€{row['cpc']}",
                    row["durum"],
                ])

            camp_table = Table(table_data,
                               colWidths=[65*mm, 22*mm, 22*mm, 18*mm, 18*mm, 25*mm])
            camp_table.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,0), C_SURFACE),
                ("TEXTCOLOR",     (0,0), (-1,0), C_MUTED),
                ("FONTNAME",      (0,0), (-1,0), "Helvetica"),
                ("FONTSIZE",      (0,0), (-1,-1), 8),
                ("ROWBACKGROUNDS",(0,1), (-1,-1), [C_SURFACE, C_BG]),
                ("TEXTCOLOR",     (0,1), (-1,-1), C_TEXT),
                ("BOX",           (0,0), (-1,-1), 0.5, C_BORDER),
                ("INNERGRID",     (0,0), (-1,-1), 0.5, C_BORDER),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ]))
            story.append(camp_table)
            story.append(self._spacer(4))

        # Çapraz alarmlar
        alarms = self.meta.get("cross_alarms", [])
        if alarms:
            story.append(Paragraph("CROSS ALARMS", self._sp("label")))
            story.append(self._spacer(2))
            for a in alarms:
                sc = C_DANGER if a["severity"] == "critical" else C_WARN
                icon = "🔴" if a["severity"] == "critical" else "⚠️"
                alarm_data = [
                    [Paragraph(f"{icon} {a['title']}", ParagraphStyle("at",
                        fontName=_FONT_BOLD, fontSize=9,
                        textColor=sc, leading=12))],
                    [Paragraph(a["description"][:180], self._sp("finding_body"))],
                    [Paragraph(f"→ {a['action'][:150]}", self._sp("action"))],
                ]
                alarm_table = Table(alarm_data, colWidths=[self.W])
                alarm_table.setStyle(TableStyle([
                    ("BACKGROUND",   (0,0), (-1,-1), C_SURFACE),
                    ("BOX",          (0,0), (-1,-1), 0.5, C_BORDER),
                    ("LINEBEFORE",   (0,0), (0,-1), 2, sc),
                    ("LEFTPADDING",  (0,0), (-1,-1), 10),
                    ("RIGHTPADDING", (0,0), (-1,-1), 10),
                    ("TOPPADDING",   (0,0), (-1,-1), 6),
                    ("BOTTOMPADDING",(0,0), (-1,-1), 6),
                ]))
                story.append(alarm_table)
                story.append(self._spacer(2))

        return story

    # ── PDF OLUŞTUR ──────────────────────────
    def generate(self) -> bytes:
        """
        PDF'i oluştur ve bytes olarak döndür.
        Streamlit'in download_button'ı için ideal.
        """
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=22*mm, bottomMargin=20*mm,
            title=f"OPS Intelligence — {self.shop_name}",
            author="OPS Intelligence Platform",
        )

        story = []
        story += self._cover()
        story += self._kpi_section()
        story.append(self._spacer(4))
        story += self._findings_section()
        story += self._quick_wins_section()
        story += self._meta_section()

        doc.build(story, onFirstPage=dark_background, onLaterPages=dark_background)
        buffer.seek(0)
        return buffer.read()


# ─────────────────────────────────────────────
# KOLAYLAŞTIRICI FONKSİYON
# ─────────────────────────────────────────────

def generate_pdf_report(
    analysis_result: dict,
    meta_result: dict = None,
    shop_name: str = "Demo Store",
) -> bytes:
    """Dashboard'dan tek satırda çağrılabilir"""
    gen = PDFReportGenerator(analysis_result, meta_result, shop_name)
    return gen.generate()


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from data_layer import ShopifyConfig
    from ai_engine import AIConfig, run_full_analysis
    from meta_ads import MetaConfig, run_meta_analysis

    print("📄 PDF raporu oluşturuluyor...")
    result = run_full_analysis(
        ShopifyConfig(use_mock=True, mock_order_count=200),
        AIConfig(use_mock_ai=True),
    )
    meta_result = run_meta_analysis(MetaConfig(use_mock=True),
                                    result.get("products_df"))

    pdf_bytes = generate_pdf_report(result, meta_result, "Demo Mağaza")

    with open("ops_report_test.pdf", "wb") as f:
        f.write(pdf_bytes)

    print(f"✅ PDF oluşturuldu: ops_report_test.pdf ({len(pdf_bytes):,} byte)")
