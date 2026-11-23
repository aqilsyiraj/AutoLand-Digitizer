"""
AutoLand Digitizer - UI Stylesheet & Design System

Satu sistem gaya untuk seluruh aplikasi. Ukuran, warna, radius, dan hierarki teks
ditentukan di sini agar setiap halaman konsisten dan mudah dibaca di laptop 1366x768.
Warna ungu/lavender sengaja tidak dipakai: kontrasnya rendah pada layar kantor.
"""

from config import THEME_COLORS

C = THEME_COLORS

MAIN_STYLESHEET = f"""
/* ==================== GLOBAL ==================== */
* {{
    font-family: 'Segoe UI', 'Segoe UI Variable', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: {C['text_dark']};
}}

QMainWindow, QDialog {{ background-color: {C['bg_main']}; }}
QWidget {{ outline: none; }}

QToolTip {{
    background-color: #0F172A;
    color: #FFFFFF;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 12px;
    max-width: 420px;
}}

/* ==================== TYPOGRAPHY ==================== */
QLabel#PageTitle {{
    font-size: 20px;
    font-weight: 800;
    color: {C['text_dark']};
}}
QLabel#PageSubtitle {{
    font-size: 12px;
    color: {C['text_muted']};
}}
QLabel#SectionTitle {{
    font-size: 15px;
    font-weight: 800;
    color: {C['text_dark']};
}}
QLabel#SectionSubtitle {{
    font-size: 12px;
    color: {C['text_muted']};
}}
QLabel#FormFieldLabel, QLabel.field-label {{
    font-size: 13px;
    font-weight: 700;
    color: #1E293B;
}}
QLabel#FormFieldHint {{
    font-size: 11px;
    color: {C['text_muted']};
}}
QLabel#DigitTitle {{
    font-size: 16px;
    font-weight: 800;
    color: {C['text_dark']};
}}
QLabel#DigitMeta {{
    font-size: 12px;
    color: {C['text_muted']};
}}

/* ==================== SIDEBAR ==================== */
#Sidebar {{
    background-color: {C['bg_sidebar']};
    min-width: 224px;
    max-width: 224px;
    border-right: 1px solid #1E293B;
}}
#SidebarHeader {{
    background-color: #0B1220;
    border-bottom: 1px solid #1E293B;
}}
#SidebarTitle {{
    color: #FFFFFF;
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.2px;
}}
#SidebarSubtitle {{
    color: #94A3B8;
    font-size: 11px;
}}
#SidebarSection {{
    color: #64748B;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
    padding: 10px 14px 2px 14px;
}}
QPushButton[class="sidebar-btn"] {{
    text-align: left;
    padding: 8px 12px;
    min-height: 38px;
    border: none;
    border-radius: 8px;
    margin: 2px 8px;
    font-size: 13px;
    font-weight: 600;
    color: #CBD5E1;
    background-color: transparent;
}}
QPushButton[class="sidebar-btn"]:hover {{ color: #FFFFFF; background-color: #1E293B; }}
QPushButton[class="sidebar-btn"]:checked {{
    color: #FFFFFF;
    background-color: {C['primary']};
    font-weight: 800;
    border-left: 4px solid #60A5FA;
}}
#ActiveBatchCard, #AcadStatusCard {{
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
}}
#ActiveBatchLabel {{
    color: #94A3B8;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 0.6px;
}}
#ActiveBatchValue {{
    color: #7DD3FC;
    font-size: 14px;
    font-weight: 800;
}}
#AcadStatusLabel {{
    color: #CBD5E1;
    font-size: 13px;
    font-weight: 700;
}}
#AcadStatusLabel[tone="ok"] {{ color: #34D399; }}
#AcadStatusLabel[tone="off"] {{ color: #94A3B8; }}

/* ==================== CARDS ==================== */
QFrame#SectionCard {{
    background-color: {C['bg_card']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QFrame#StatCard {{
    background-color: {C['bg_card']};
    border: 1px solid {C['border']};
    border-left: 3px solid #2563EB;
    border-radius: 12px;
}}
QLabel#StatTitle {{ font-size: 12px; font-weight: 700; color: #475569; }}
QLabel#StatValue {{ font-size: 23px; font-weight: 800; color: #0F172A; }}
QLabel#StatSubtitle {{ font-size: 11px; color: {C['text_muted']}; }}

/* ==================== BUTTONS ==================== */
QPushButton {{
    min-height: 34px;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    border: 1px solid transparent;
}}
QPushButton:focus-visible {{ border: 2px solid #60A5FA; }}
QPushButton[class="btn-primary"] {{
    background-color: {C['primary']};
    color: #FFFFFF;
}}
QPushButton[class="btn-primary"]:hover {{ background-color: {C['primary_hover']}; }}
QPushButton[class="btn-primary"]:disabled {{ background-color: #93C5FD; color: #EFF6FF; }}

QPushButton[class="btn-secondary"] {{
    background-color: #F1F5F9;
    color: #1E293B;
    border: 1px solid #CBD5E1;
}}
QPushButton[class="btn-secondary"]:hover {{ background-color: #E2E8F0; color: #0F172A; }}

QPushButton[class="btn-success"] {{ background-color: #059669; color: #FFFFFF; }}
QPushButton[class="btn-success"]:hover {{ background-color: #047857; }}
QPushButton[class="btn-success"]:disabled {{ background-color: #6EE7B7; color: #ECFDF5; }}

QPushButton[class="btn-danger"] {{ background-color: #DC2626; color: #FFFFFF; }}
QPushButton[class="btn-danger"]:hover {{ background-color: #B91C1C; }}

QPushButton[class="btn-warning"] {{ background-color: #D97706; color: #FFFFFF; }}
QPushButton[class="btn-warning"]:hover {{ background-color: #B45309; }}

QPushButton[class="btn-quiet"] {{
    background-color: transparent;
    color: #0369A1;
    border: none;
    font-size: 12px;
    padding: 6px 8px;
}}
QPushButton[class="btn-quiet"]:hover {{ background-color: #E0F2FE; }}

/* Tombol aksi di dalam baris tabel: lebih ringkas tetapi tetap jelas */
QPushButton[class="btn-row"] {{
    min-height: 28px;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: 700;
    border-radius: 7px;
    border: 1px solid transparent;
}}
QPushButton[class="btn-row"][role="primary"] {{ background-color: {C['primary']}; color: #FFFFFF; }}
QPushButton[class="btn-row"][role="primary"]:hover {{ background-color: {C['primary_hover']}; }}
QPushButton[class="btn-row"][role="success"] {{ background-color: #059669; color: #FFFFFF; }}
QPushButton[class="btn-row"][role="success"]:hover {{ background-color: #047857; }}
QPushButton[class="btn-row"][role="secondary"] {{
    background-color: #F1F5F9; color: #1E293B; border: 1px solid #CBD5E1;
}}
QPushButton[class="btn-row"][role="secondary"]:hover {{ background-color: #E2E8F0; }}
QPushButton[class="btn-row"][role="danger"] {{ background-color: #DC2626; color: #FFFFFF; }}
QPushButton[class="btn-row"][role="danger"]:hover {{ background-color: #B91C1C; }}
QPushButton[class="btn-row"]:disabled {{ background-color: #E2E8F0; color: #94A3B8; }}

/* Langkah proses */
QFrame#StepTracker {{
    background-color: transparent;
    border: none;
}}
QPushButton[class="step-btn"] {{
    min-height: 40px;
    font-size: 12px;
    padding: 8px 8px;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    background-color: #F8FAFC;
    color: #64748B;
}}
QPushButton[class="step-btn"]:hover {{ background-color: #F1F5F9; color: #334155; }}
QPushButton[class="step-btn"][state="active"] {{
    background-color: {C['primary']};
    color: #FFFFFF;
    border: 2px solid #60A5FA;
    font-weight: 800;
}}
QPushButton[class="step-btn"][state="done"] {{
    background-color: #ECFDF5;
    color: #047857;
    border: 1.5px solid #10B981;
    font-weight: 700;
}}
QPushButton[class="step-btn"][state="done"]:hover {{ background-color: #D1FAE5; }}

/* ==================== INPUTS ==================== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {{
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 7px 10px;
    min-height: 34px;
    color: {C['text_dark']};
    font-size: 13px;
}}
QTextEdit {{ padding: 8px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QDateEdit:focus, QTextEdit:focus {{
    border: 2px solid {C['primary']};
    background-color: #FFFFFF;
}}
QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
    background-color: #F1F5F9;
    color: #94A3B8;
}}

/* ==================== TABLES ==================== */
QTableWidget, QTableView {{
    background-color: #FFFFFF;
    alternate-background-color: #F8FAFC;
    border: 1px solid {C['border']};
    border-radius: 10px;
    gridline-color: #E2E8F0;
    selection-background-color: #DBEAFE;
    selection-color: #1E3A8A;
    font-size: 13px;
}}
QHeaderView::section {{
    background-color: #F1F5F9;
    color: #334155;
    font-weight: 800;
    font-size: 12px;
    padding: 8px 8px;
    border: none;
    border-bottom: 2px solid #CBD5E1;
}}
QTableWidget::item {{
    padding: 7px 8px;
    border-bottom: 1px solid #F1F5F9;
}}

/* ==================== STATUS ==================== */
QLabel#StatusPill {{
    border-radius: 12px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 800;
    background-color: #F1F5F9;
    color: #475569;
    border: 1px solid #CBD5E1;
}}
QLabel#StatusPill[tone="info"] {{ background-color: #EFF6FF; color: #1D4ED8; border-color: #BFDBFE; }}
QLabel#StatusPill[tone="success"] {{ background-color: #ECFDF5; color: #047857; border-color: #A7F3D0; }}
QLabel#StatusPill[tone="warn"] {{ background-color: #FEF3C7; color: #B45309; border-color: #FDE68A; }}
QLabel#StatusPill[tone="cyan"] {{ background-color: #ECFEFF; color: #0E7490; border-color: #A5F3FC; }}
QLabel#StatusPill[tone="danger"] {{ background-color: #FEF2F2; color: #B91C1C; border-color: #FECACA; }}

QFrame#ReadinessCard {{
    border-radius: 10px;
    padding: 10px;
    background-color: #FEF2F2;
    border: 1.5px solid #FCA5A5;
}}
QFrame#ReadinessCard[tone="ok"] {{
    background-color: #ECFDF5;
    border: 1.5px solid #10B981;
}}
QLabel#ReadinessText {{ font-size: 13px; font-weight: 700; color: #B91C1C; }}
QLabel#ReadinessText[tone="ok"] {{ color: #047857; }}

/* ==================== GUIDE BANNER ==================== */
QFrame#GuideBanner {{
    background-color: #F0F9FF;
    border: 1px solid #BAE6FD;
    border-left: 4px solid #0284C7;
    border-radius: 10px;
}}
QLabel#GuideTitle {{ font-size: 13px; font-weight: 800; color: #0369A1; }}
QLabel#GuideItem {{ font-size: 12px; color: #0F172A; }}
QPushButton#GuideToggle {{
    background-color: transparent;
    border: none;
    color: #0284C7;
    font-size: 12px;
    font-weight: 700;
    min-height: 28px;
    padding: 4px 8px;
}}
QPushButton#GuideToggle:hover {{ background-color: #E0F2FE; }}

/* ==================== CANVAS / PREVIEW ==================== */
QFrame#CanvasToolbar {{
    background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
}}
QFrame#CanvasToolbar QPushButton {{
    min-height: 30px;
    padding: 4px 8px;
    font-size: 12px;
}}
QLabel#CanvasHint {{ font-size: 12px; font-weight: 700; color: #334155; }}
QLabel#CanvasLegend {{ font-size: 11px; font-weight: 700; color: #475569; }}
QScrollArea#PreviewScroll {{
    background-color: #334155;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
}}
QFrame#DetectionInfo, QLabel#DetectionInfo {{
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 8px;
    color: #334155;
    font-size: 12px;
}}
QLabel#DetectionStatus {{ font-size: 12px; font-weight: 700; color: #475569; }}
QLabel#DetectionStatus[tone="ok"] {{ color: #059669; }}
QLabel#DetectionStatus[tone="error"] {{ color: #DC2626; }}

QLabel#ReviewSummary {{
    background-color: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-radius: 8px;
    padding: 8px 10px;
    color: #065F46;
    font-size: 12px;
}}
QFrame#DoneCard {{
    background-color: #ECFDF5;
    border: 1.5px solid #A7F3D0;
    border-radius: 12px;
}}
QLabel#DoneTitle {{ font-size: 21px; font-weight: 800; color: #065F46; }}
QLabel#DoneBody {{ font-size: 13px; color: #064E3B; }}

QFrame#IdentityPreview {{
    background-color: #F8FAFC;
    border: 1.5px solid #BFDBFE;
    border-radius: 10px;
}}
QLabel#IdentityEyebrow {{ font-size: 11px; font-weight: 800; color: #1E40AF; letter-spacing: 0.5px; }}
QLabel#IdentityValue {{ font-size: 17px; font-weight: 800; color: #1E3A8A; }}
QLabel#IdentityValue[tone="empty"] {{ color: #DC2626; font-size: 15px; }}
QLabel#IdentityFile {{ font-size: 11px; color: {C['text_muted']}; }}

QTextEdit#ProcessLog {{
    background-color: #0F172A;
    color: #E2E8F0;
    border-radius: 10px;
    padding: 12px;
    font-family: Consolas, 'Cascadia Mono', monospace;
    font-size: 12px;
}}

/* ==================== SCROLLBARS ==================== */
QScrollBar:vertical {{
    border: none;
    background: #E2E8F0;
    width: 12px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #94A3B8;
    min-height: 32px;
    border-radius: 6px;
}}
QScrollBar::handle:vertical:hover {{ background: #64748B; }}
QScrollBar:vertical:hover {{ background: #CBD5E1; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    border: none;
    background: #E2E8F0;
    height: 12px;
}}
QScrollBar::handle:horizontal {{ background: #94A3B8; min-width: 32px; border-radius: 6px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
"""
