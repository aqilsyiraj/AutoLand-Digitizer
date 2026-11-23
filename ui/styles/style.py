"""
AutoLand Digitizer - Design System v2

Satu sistem visual untuk aplikasi desktop: permukaan bersih, tipografi jelas,
satu warna aksen (teal pertanahan), dan tombol yang tingginya mengikuti konteks
(xs/sm/md/lg). Tidak ada gradien ungu, glow, atau dekorasi yang mengganggu
membaca.

Catatan teknis:
- Qt Style Sheets hanya menerima SATU nama font pada properti font-family.
  Daftar dipisah koma membuat Qt memakai font fallback yang salah (glyph kotak),
  jadi di sini hanya dipakai "Segoe UI".
- Motion memakai QPropertyAnimation lewat ui/motion/qt_motion.py sebagai
  padanan GSAP/ScrollTrigger/Lenis untuk widget Qt.
"""

from config import THEME_COLORS

C = THEME_COLORS

# ---------------------------------------------------------------------------
# Token warna
# ---------------------------------------------------------------------------
P = {
    # Permukaan
    "bg": "#F3F6F8",
    "surface": "#FFFFFF",
    "surface_alt": "#F7F9FB",
    "surface_sunken": "#EDF1F5",
    "surface_dark": "#0F172A",

    # Teks
    "ink": "#0B1220",
    "ink_soft": "#334155",
    "muted": "#64748B",
    "muted_light": "#94A3B8",

    # Garis
    "line": "#E4E9EF",
    "line_strong": "#CBD5E1",

    # Aksen utama: teal pertanahan
    "brand": "#0F766E",
    "brand_hover": "#0C5F59",
    "brand_ink": "#0B4A45",
    "brand_soft": "#E7F4F1",
    "brand_border": "#B7DED7",
    "brand_bright": "#14B8A6",

    # Status
    "success": "#15803D",
    "success_hover": "#116B33",
    "success_ink": "#14532D",
    "success_soft": "#E3F6E9",
    "success_border": "#BFE8CC",

    "warn": "#B45309",
    "warn_hover": "#92400E",
    "warn_ink": "#92400E",
    "warn_soft": "#FEF3C7",
    "warn_border": "#F6D98A",

    "danger": "#B42318",
    "danger_hover": "#96190F",
    "danger_ink": "#7A1A12",
    "danger_soft": "#FEE4E2",
    "danger_border": "#F6C4BF",

    "info": "#1D4ED8",
    "info_soft": "#E6EEFB",
    "info_ink": "#1E3A8A",
    "info_border": "#BFD3F7",

    # Sidebar
    "sidebar": "#0A1220",
    "sidebar_hover": "#152033",
    "sidebar_line": "#1B2A3D",
    "sidebar_text": "#93A4B8",
    "sidebar_muted": "#64748B",
    "sidebar_active": "#123330",
    "sidebar_active_text": "#7DE3D2",
}

MAIN_STYLESHEET = f"""
/* ======================================================================
   BASE
   ====================================================================== */
* {{
    font-family: "Segoe UI";
    font-size: 13px;
    color: {P['ink']};
}}
QMainWindow, QDialog {{
    background-color: {P['bg']};
}}
QWidget {{
    outline: none;
}}
QToolTip {{
    background-color: {P['ink']};
    color: #FFFFFF;
    border: 1px solid {P['ink']};
    border-radius: 6px;
    padding: 6px 9px;
    font-size: 11px;
}}

/* ======================================================================
   SIDEBAR
   ====================================================================== */
#Sidebar {{
    background-color: {P['sidebar']};
    min-width: 244px;
    max-width: 244px;
    border: none;
    border-right: 1px solid {P['sidebar_line']};
}}
#SidebarHeader {{
    background-color: transparent;
    border: none;
}}
#BrandMark {{
    background-color: {P['brand']};
    color: #FFFFFF;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 800;
}}
#SidebarTitle {{
    color: #FFFFFF;
    font-size: 16px;
    font-weight: 700;
}}
#SidebarSubtitle {{
    color: {P['sidebar_muted']};
    font-size: 11px;
}}
#SidebarSection {{
    color: {P['sidebar_muted']};
    font-size: 10px;
    font-weight: 700;
    padding: 14px 16px 4px 16px;
    background: transparent;
}}
QPushButton[role="nav"] {{
    text-align: left;
    min-height: 20px;
    padding: 8px 12px;
    margin: 2px 10px;
    border: 1px solid transparent;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    color: {P['sidebar_text']};
    background-color: transparent;
}}
QPushButton[role="nav"]:hover {{
    color: #FFFFFF;
    background-color: {P['sidebar_hover']};
}}
QPushButton[role="nav"]:checked {{
    color: {P['sidebar_active_text']};
    background-color: {P['sidebar_active']};
    border: 1px solid #1C4A46;
    font-weight: 600;
}}
#ActiveBatchCard {{
    background-color: #101B2B;
    border: 1px solid {P['sidebar_line']};
    border-radius: 10px;
}}
#ActiveBatchLabel {{
    color: {P['sidebar_muted']};
    font-size: 10px;
    font-weight: 700;
}}
#ActiveBatchValue {{
    color: #E6F6F3;
    font-size: 12px;
    font-weight: 600;
}}
#AcadStatusCard {{
    background-color: #101B2B;
    border: 1px solid {P['sidebar_line']};
    border-radius: 10px;
}}
#AcadStatusLabel {{
    color: {P['sidebar_text']};
    font-size: 11px;
    font-weight: 600;
}}
#AcadStatusLabel[tone="ok"] {{ color: #6EE7B7; }}
#AcadStatusLabel[tone="off"] {{ color: {P['sidebar_muted']}; }}
#SidebarFoot {{
    color: {P['sidebar_muted']};
    font-size: 10px;
}}

/* ======================================================================
   TIPOGRAFI HALAMAN
   ====================================================================== */
QLabel#PageEyebrow {{
    color: {P['brand']};
    font-size: 10px;
    font-weight: 800;
}}
QLabel#PageTitle {{
    font-size: 23px;
    font-weight: 700;
    color: {P['ink']};
}}
QLabel#PageSubtitle {{
    font-size: 12px;
    color: {P['muted']};
}}
QLabel#SectionTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {P['ink']};
}}
QLabel#SectionSubtitle {{
    font-size: 12px;
    color: {P['muted']};
}}
QLabel#MutedText {{
    font-size: 12px;
    color: {P['muted']};
}}
QLabel#MicroLabel {{
    font-size: 10px;
    font-weight: 700;
    color: {P['muted']};
}}

/* ======================================================================
   KARTU
   ====================================================================== */
QFrame#SectionCard,
QFrame#Card,
QFrame#PanelCard {{
    background-color: {P['surface']};
    border: 1px solid {P['line']};
    border-radius: 10px;
}}
QFrame#SubCard {{
    background-color: {P['surface_alt']};
    border: 1px solid {P['line']};
    border-radius: 8px;
}}
QFrame#StatCard {{
    background-color: {P['surface']};
    border: 1px solid {P['line']};
    border-radius: 10px;
}}
QLabel#StatTitle {{
    font-size: 11px;
    font-weight: 600;
    color: {P['muted']};
}}
QLabel#StatValue {{
    font-size: 25px;
    font-weight: 700;
    color: {P['ink']};
}}
QLabel#StatValue[tone="brand"] {{ color: {P['brand']}; }}
QLabel#StatValue[tone="success"] {{ color: {P['success']}; }}
QLabel#StatValue[tone="warn"] {{ color: {P['warn']}; }}
QLabel#StatValue[tone="info"] {{ color: {P['info']}; }}
QLabel#StatValue[tone="muted"] {{ color: {P['ink_soft']}; }}
QLabel#StatSubtitle {{
    font-size: 11px;
    color: {P['muted']};
}}
QFrame#StatCard[compact="true"] QLabel#StatValue {{
    font-size: 19px;
}}
QLabel#ProgressPercent {{
    font-size: 20px;
    font-weight: 700;
    color: {P['brand']};
}}
QLabel#StepBadge {{
    background-color: {P['brand_soft']};
    color: {P['brand_ink']};
    border: 1px solid {P['brand_border']};
    border-radius: 12px;
    font-size: 11px;
    font-weight: 800;
}}
QLabel#StepTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {P['ink']};
}}
QLabel#StepDesc {{
    font-size: 11px;
    color: {P['muted']};
}}
QLabel#ActiveSummaryName {{
    font-size: 14px;
    font-weight: 700;
    color: {P['ink']};
}}

QFrame#Notice {{
    background-color: {P['brand_soft']};
    border: 1px solid {P['brand_border']};
    border-left: 3px solid {P['brand']};
    border-radius: 8px;
}}
QFrame#DoneCard {{
    background-color: #F2FBF5;
    border: 1px solid {P['success_border']};
    border-radius: 12px;
}}
QFrame#IdentityPreview {{
    background-color: {P['surface_alt']};
    border: 1px solid {P['line']};
    border-radius: 9px;
}}
QFrame#ReadinessCard {{
    background-color: {P['warn_soft']};
    border: 1px solid {P['warn_border']};
    border-radius: 9px;
}}
QFrame#ReadinessCard[tone="ok"] {{
    background-color: {P['success_soft']};
    border-color: {P['success_border']};
}}
QLabel#ReadinessText {{
    font-size: 12px;
    font-weight: 600;
    color: {P['warn_ink']};
}}
QLabel#ReadinessText[tone="ok"] {{ color: {P['success_ink']}; }}

QFrame#CanvasToolbar {{
    background-color: {P['surface_alt']};
    border: 1px solid {P['line']};
    border-radius: 9px;
}}
QLabel#CanvasHint {{
    font-size: 12px;
    color: {P['ink_soft']};
}}
QLabel#CanvasLegend {{
    font-size: 11px;
    color: {P['muted']};
}}
QScrollArea#PreviewScroll {{
    background-color: #0F172A;
    border: 1px solid {P['line_strong']};
    border-radius: 9px;
}}

/* ======================================================================
   PETUNJUK (GUIDE BANNER)
   ====================================================================== */
QFrame#GuideBanner {{
    background-color: #F2F9F7;
    border: 1px solid {P['brand_border']};
    border-left: 3px solid {P['brand']};
    border-radius: 8px;
}}
QLabel#GuideTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {P['brand_ink']};
}}
QLabel#GuideItem {{
    font-size: 12px;
    color: {P['ink_soft']};
}}
QPushButton#GuideToggle {{
    background-color: transparent;
    border: none;
    color: {P['brand']};
    font-size: 11px;
    font-weight: 700;
    min-height: 18px;
    padding: 3px 7px;
    border-radius: 6px;
}}
QPushButton#GuideToggle:hover {{
    background-color: {P['brand_soft']};
}}

/* ======================================================================
   TOMBOL
   ====================================================================== */
QPushButton {{
    border: 1px solid {P['line_strong']};
    border-radius: 7px;
    font-weight: 600;
    min-height: 18px;
    padding: 6px 14px;
    font-size: 12px;
    color: {P['ink_soft']};
    background-color: {P['surface']};
}}
QPushButton:hover:!disabled {{
    background-color: {P['surface_alt']};
    border-color: {P['muted_light']};
    color: {P['ink']};
}}
QPushButton:pressed:!disabled {{
    background-color: {P['surface_sunken']};
}}
QPushButton:disabled {{
    color: {P['muted_light']};
    background-color: {P['surface_alt']};
    border-color: {P['line']};
}}
QPushButton:focus {{
    border: 1px solid {P['brand']};
}}

/* Ukuran kontekstual: xs / sm / md / lg */
QPushButton[btn-size="xs"] {{
    min-height: 16px;
    padding: 3px 9px;
    font-size: 11px;
    border-radius: 6px;
}}
QPushButton[btn-size="sm"] {{
    min-height: 17px;
    padding: 4px 11px;
    font-size: 11px;
    border-radius: 6px;
}}
QPushButton[btn-size="md"] {{
    min-height: 18px;
    padding: 6px 14px;
    font-size: 12px;
    border-radius: 7px;
}}
QPushButton[btn-size="lg"] {{
    min-height: 20px;
    padding: 9px 18px;
    font-size: 13px;
    border-radius: 8px;
}}

/* Warna tombol */
QPushButton[tone="primary"] {{
    background-color: {P['brand']};
    color: #FFFFFF;
    border: 1px solid {P['brand']};
}}
QPushButton[tone="primary"]:hover:!disabled {{
    background-color: {P['brand_hover']};
    border-color: {P['brand_hover']};
    color: #FFFFFF;
}}
QPushButton[tone="primary"]:pressed:!disabled {{
    background-color: {P['brand_ink']};
    border-color: {P['brand_ink']};
}}
QPushButton[tone="primary"]:disabled {{
    background-color: {P['surface_alt']};
    color: {P['muted_light']};
    border-color: {P['line']};
}}

QPushButton[tone="secondary"] {{
    background-color: {P['surface']};
    color: {P['ink_soft']};
    border: 1px solid {P['line_strong']};
}}
QPushButton[tone="secondary"]:hover:!disabled {{
    background-color: {P['surface_alt']};
    border-color: {P['muted_light']};
    color: {P['ink']};
}}

QPushButton[tone="ghost"] {{
    background-color: transparent;
    color: {P['ink_soft']};
    border: 1px solid {P['line']};
}}
QPushButton[tone="ghost"]:hover:!disabled {{
    background-color: {P['surface_alt']};
    border-color: {P['line_strong']};
    color: {P['ink']};
}}

QPushButton[tone="quiet"] {{
    background-color: transparent;
    color: {P['brand']};
    border: 1px solid transparent;
}}
QPushButton[tone="quiet"]:hover:!disabled {{
    background-color: {P['brand_soft']};
    color: {P['brand_ink']};
}}

QPushButton[tone="success"] {{
    background-color: {P['success']};
    color: #FFFFFF;
    border: 1px solid {P['success']};
}}
QPushButton[tone="success"]:hover:!disabled {{
    background-color: {P['success_hover']};
    border-color: {P['success_hover']};
    color: #FFFFFF;
}}
QPushButton[tone="success"]:disabled {{
    background-color: {P['success_soft']};
    color: {P['success_ink']};
    border-color: {P['success_border']};
}}

QPushButton[tone="danger"] {{
    background-color: {P['danger']};
    color: #FFFFFF;
    border: 1px solid {P['danger']};
}}
QPushButton[tone="danger"]:hover:!disabled {{
    background-color: {P['danger_hover']};
    border-color: {P['danger_hover']};
    color: #FFFFFF;
}}
QPushButton[tone="danger"]:disabled {{
    background-color: {P['danger_soft']};
    color: {P['danger_ink']};
    border-color: {P['danger_border']};
}}

QPushButton[tone="warn"],
QPushButton[tone="warning"] {{
    background-color: {P['warn']};
    color: #FFFFFF;
    border: 1px solid {P['warn']};
}}
QPushButton[tone="warn"]:hover:!disabled,
QPushButton[tone="warning"]:hover:!disabled {{
    background-color: {P['warn_hover']};
    border-color: {P['warn_hover']};
    color: #FFFFFF;
}}
QPushButton[tone="warn"]:disabled {{
    background-color: {P['warn_soft']};
    color: {P['warn_ink']};
    border-color: {P['warn_border']};
}}

QPushButton[tone="info"] {{
    background-color: {P['info']};
    color: #FFFFFF;
    border: 1px solid {P['info']};
}}
QPushButton[tone="info"]:hover:!disabled {{
    background-color: #1A45BE;
    border-color: #1A45BE;
    color: #FFFFFF;
}}

QPushButton[tone="dark"] {{
    background-color: {P['ink']};
    color: #FFFFFF;
    border: 1px solid {P['ink']};
}}
QPushButton[tone="dark"]:hover:!disabled {{
    background-color: #1E293B;
    border-color: #1E293B;
    color: #FFFFFF;
}}

QPushButton[tone="link"] {{
    background-color: transparent;
    color: {P['brand']};
    border: none;
    padding: 4px 6px;
    min-height: 16px;
    text-decoration: underline;
}}
QPushButton[tone="link"]:hover:!disabled {{
    color: {P['brand_hover']};
    background-color: transparent;
}}

/* Kompatibilitas class= gaya lama (kanvas, dll.) */
QPushButton[class="btn-primary"] {{
    background-color: {P['brand']};
    color: #FFFFFF;
    border: 1px solid {P['brand']};
}}
QPushButton[class="btn-primary"]:hover:!disabled {{
    background-color: {P['brand_hover']};
    border-color: {P['brand_hover']};
}}
QPushButton[class="btn-secondary"] {{
    background-color: {P['surface']};
    color: {P['ink_soft']};
    border: 1px solid {P['line_strong']};
}}
QPushButton[class="btn-secondary"]:hover:!disabled {{
    background-color: {P['surface_alt']};
}}
QPushButton[class="btn-warning"] {{
    background-color: {P['warn']};
    color: #FFFFFF;
    border: 1px solid {P['warn']};
}}
QPushButton[class="btn-warning"]:hover:!disabled {{
    background-color: {P['warn_hover']};
}}
QPushButton[class="sidebar-btn"] {{
    text-align: left;
    min-height: 20px;
    padding: 8px 12px;
    margin: 2px 10px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    color: {P['sidebar_text']};
    background-color: transparent;
}}
QPushButton[class="sidebar-btn"]:hover {{
    color: #FFFFFF;
    background-color: {P['sidebar_hover']};
}}
QPushButton[class="sidebar-btn"]:checked {{
    color: {P['sidebar_active_text']};
    background-color: {P['sidebar_active']};
}}

/* Tombol aksi baris tabel */
QPushButton[role="row-action"] {{
    min-height: 16px;
    padding: 3px 5px;
    font-size: 10px;
    border-radius: 5px;
}}

/* Tombol langkah wizard */
QPushButton[role="step"] {{
    min-height: 20px;
    padding: 7px 12px;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid {P['line']};
    border-radius: 8px;
    background-color: {P['surface']};
    color: {P['muted']};
}}
QPushButton[role="step"]:hover:!disabled {{
    border-color: {P['line_strong']};
    background-color: {P['surface_alt']};
    color: {P['ink_soft']};
}}
QPushButton[role="step"][state="active"] {{
    background-color: {P['brand']};
    color: #FFFFFF;
    border-color: {P['brand']};
}}
QPushButton[role="step"][state="done"] {{
    background-color: {P['success_soft']};
    color: {P['success_ink']};
    border-color: {P['success_border']};
}}
QPushButton[role="step"]:disabled {{
    background-color: {P['surface_alt']};
    color: {P['muted_light']};
    border-color: {P['line']};
}}
QLabel#StepArrow {{
    color: {P['line_strong']};
    font-size: 15px;
    font-weight: 700;
}}

/* ======================================================================
   INPUT
   ====================================================================== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {{
    background-color: {P['surface']};
    border: 1px solid {P['line_strong']};
    border-radius: 7px;
    padding: 6px 10px;
    min-height: 18px;
    color: {P['ink']};
    font-size: 12px;
    selection-background-color: {P['brand_soft']};
    selection-color: {P['brand_ink']};
}}
QTextEdit {{
    padding: 8px 10px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QDateEdit:focus, QTextEdit:focus {{
    border: 1px solid {P['brand']};
    background-color: #FCFEFD;
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QTextEdit:disabled {{
    background-color: {P['surface_alt']};
    color: {P['muted_light']};
    border-color: {P['line']};
}}
QLineEdit[echoMode="2"] {{
    lineedit-password-character: 9679;
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {P['surface']};
    border: 1px solid {P['line_strong']};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: {P['brand_soft']};
    selection-color: {P['brand_ink']};
}}
QComboBox QAbstractItemView::item {{
    min-height: 26px;
    padding: 3px 8px;
    border-radius: 5px;
}}
QLabel#FormFieldLabel {{
    font-size: 12px;
    font-weight: 600;
    color: {P['ink_soft']};
}}
QLabel#FormFieldHint {{
    font-size: 11px;
    color: {P['muted']};
}}

/* ======================================================================
   TABEL
   ====================================================================== */
QTableWidget, QTableView {{
    background-color: {P['surface']};
    alternate-background-color: #FAFCFD;
    border: 1px solid {P['line']};
    border-radius: 9px;
    gridline-color: transparent;
    selection-background-color: {P['brand_soft']};
    selection-color: {P['brand_ink']};
    font-size: 12px;
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #F0F3F7;
}}
QTableWidget::item:hover, QTableView::item:hover {{
    background-color: #F4F8F7;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {P['brand_soft']};
    color: {P['brand_ink']};
}}
QHeaderView::section {{
    background-color: {P['surface_alt']};
    color: {P['muted']};
    font-weight: 700;
    font-size: 10px;
    padding: 9px 10px;
    border: none;
    border-bottom: 1px solid {P['line']};
}}
QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}
QHeaderView::section:last {{
    border-top-right-radius: 8px;
}}
QTableCornerButton::section {{
    background-color: {P['surface_alt']};
    border: none;
}}
QTableWidget#DataTable {{
    min-height: 120px;
}}
QWidget#RowActions {{
    background: transparent;
    border: none;
}}

/* ======================================================================
   BADGE STATUS
   ====================================================================== */
QLabel#StatusPill {{
    border-radius: 9px;
    padding: 3px 9px;
    font-size: 11px;
    font-weight: 700;
    background-color: {P['surface_alt']};
    color: {P['ink_soft']};
    border: 1px solid {P['line']};
}}
QLabel#StatusPill[tone="neutral"] {{
    background-color: {P['surface_sunken']};
    color: {P['ink_soft']};
    border-color: {P['line']};
}}
QLabel#StatusPill[tone="info"] {{
    background-color: {P['info_soft']};
    color: {P['info_ink']};
    border-color: {P['info_border']};
}}
QLabel#StatusPill[tone="success"] {{
    background-color: {P['success_soft']};
    color: {P['success_ink']};
    border-color: {P['success_border']};
}}
QLabel#StatusPill[tone="warn"] {{
    background-color: {P['warn_soft']};
    color: {P['warn_ink']};
    border-color: {P['warn_border']};
}}
QLabel#StatusPill[tone="danger"] {{
    background-color: {P['danger_soft']};
    color: {P['danger_ink']};
    border-color: {P['danger_border']};
}}
QLabel#StatusPill[tone="brand"] {{
    background-color: {P['brand_soft']};
    color: {P['brand_ink']};
    border-color: {P['brand_border']};
}}

/* ======================================================================
   HALAMAN DIGITASI
   ====================================================================== */
QLabel#DigitTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {P['ink']};
}}
QLabel#DigitMeta {{
    font-size: 11px;
    color: {P['muted']};
}}
QLabel#DetectionStatus {{
    font-size: 11px;
    font-weight: 700;
    color: {P['muted']};
}}
QLabel#DetectionStatus[tone="ok"] {{ color: {P['success']}; }}
QLabel#DetectionStatus[tone="error"] {{ color: {P['danger']}; }}
QFrame#DetectionInfo, QLabel#DetectionInfo {{
    background-color: {P['surface_alt']};
    border: 1px solid {P['line']};
    border-radius: 8px;
    padding: 9px 10px;
    color: {P['ink_soft']};
    font-size: 11px;
}}
QLabel#ReviewSummary {{
    background-color: {P['success_soft']};
    border: 1px solid {P['success_border']};
    border-radius: 8px;
    padding: 9px 11px;
    color: {P['success_ink']};
    font-size: 12px;
}}
QLabel#DoneTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {P['success']};
}}
QLabel#DoneBody {{
    font-size: 14px;
    font-weight: 600;
    color: {P['ink']};
}}
QLabel#IdentityEyebrow {{
    font-size: 9px;
    font-weight: 800;
    color: {P['brand']};
}}
QLabel#IdentityValue {{
    font-size: 17px;
    font-weight: 700;
    color: {P['brand_ink']};
}}
QLabel#IdentityValue[tone="empty"] {{
    color: {P['danger']};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#IdentityFile {{
    font-size: 11px;
    color: {P['muted']};
}}
QLabel#DoneKey {{
    font-size: 11px;
    color: {P['muted']};
    font-weight: 600;
}}
QLabel#DoneValue {{
    font-size: 12px;
    color: {P['ink']};
    font-weight: 600;
}}
QTextEdit#ProcessLog {{
    background-color: #0B1220;
    color: #D7E3F0;
    border-radius: 9px;
    padding: 12px;
    font-family: "Consolas";
    font-size: 11px;
    border: 1px solid #1E293B;
    selection-background-color: #1E3A5F;
}}

/* ======================================================================
   PROGRESS & SCROLLBAR
   ====================================================================== */
QProgressBar {{
    border: none;
    border-radius: 5px;
    background-color: {P['surface_sunken']};
    height: 8px;
    text-align: center;
    font-size: 9px;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {P['brand']};
    border-radius: 5px;
}}
QScrollBar:vertical {{
    border: none;
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {P['line_strong']};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {P['muted_light']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    border: none;
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {P['line_strong']};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {P['muted_light']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QSplitter::handle {{
    background-color: {P['line']};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ======================================================================
   MENU & LAIN-LAIN
   ====================================================================== */
QMenu {{
    background-color: {P['surface']};
    border: 1px solid {P['line']};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {P['brand_soft']};
    color: {P['brand_ink']};
}}
QMessageBox {{
    background-color: {P['surface']};
}}
QWidget#StepTracker {{
    background: transparent;
    border: none;
}}
"""
