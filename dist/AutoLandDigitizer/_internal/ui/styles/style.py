"""
AutoLand Digitizer - UI Stylesheet & Design System
Menyediakan tema tampilan desktop modern, bersih, profesional, dan elegan.
"""

from config import THEME_COLORS

MAIN_STYLESHEET = f"""
/* ==================== GLOBAL STYLES ==================== */
* {{
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    color: {THEME_COLORS['text_dark']};
}}

QMainWindow, QDialog {{
    background-color: {THEME_COLORS['bg_main']};
}}

QWidget {{
    outline: none;
}}

/* ==================== SIDEBAR ==================== */
#Sidebar {{
    background-color: {THEME_COLORS['bg_sidebar']};
    min-width: 240px;
    max-width: 240px;
    border-right: 1px solid #1E293B;
}}

#SidebarHeader {{
    padding: 20px 16px 16px 16px;
    border-bottom: 1px solid #1E293B;
}}

#SidebarTitle {{
    color: #FFFFFF;
    font-size: 17px;
    font-weight: 700;
    letter-spacing: 0.5px;
}}

#SidebarSubtitle {{
    color: #94A3B8;
    font-size: 11px;
    margin-top: 4px;
}}

#SidebarMenu {{
    padding-top: 12px;
}}

QPushButton.sidebar-btn {{
    text-align: left;
    padding: 11px 18px;
    border: none;
    border-radius: 8px;
    margin: 3px 12px;
    font-size: 13px;
    font-weight: 500;
    color: #94A3B8;
    background-color: transparent;
}}

QPushButton.sidebar-btn:hover {{
    color: #FFFFFF;
    background-color: #1E293B;
}}

QPushButton.sidebar-btn:checked, QPushButton.sidebar-btn.active {{
    color: #FFFFFF;
    background-color: {THEME_COLORS['primary']};
    font-weight: 600;
}}

#ActiveBatchCard {{
    background-color: #1E293B;
    border-radius: 8px;
    padding: 12px;
    margin: 12px;
    border: 1px solid #334155;
}}

#ActiveBatchLabel {{
    color: #94A3B8;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

#ActiveBatchValue {{
    color: #38BDF8;
    font-size: 13px;
    font-weight: 700;
    margin-top: 2px;
}}

/* ==================== HEADER BAR ==================== */
#TopHeader {{
    background-color: #FFFFFF;
    border-bottom: 1px solid {THEME_COLORS['border']};
    padding: 12px 24px;
    min-height: 56px;
}}

#PageTitle {{
    font-size: 18px;
    font-weight: 700;
    color: {THEME_COLORS['text_dark']};
}}

#PageSubtitle {{
    font-size: 12px;
    color: {THEME_COLORS['text_muted']};
}}

/* ==================== CARDS & CONTAINERS ==================== */
QFrame.card {{
    background-color: {THEME_COLORS['bg_card']};
    border-radius: 10px;
    border: 1px solid {THEME_COLORS['border']};
    padding: 16px;
}}

QFrame.card-header {{
    border-bottom: 1px solid {THEME_COLORS['border']};
    padding-bottom: 10px;
    margin-bottom: 12px;
}}

QLabel.card-title {{
    font-size: 15px;
    font-weight: 700;
    color: {THEME_COLORS['text_dark']};
}}

/* ==================== BUTTONS ==================== */
QPushButton {{
    padding: 8px 16px;
    border-radius: 6px;
    font-weight: 600;
    border: 1px solid transparent;
}}

QPushButton.btn-primary {{
    background-color: {THEME_COLORS['primary']};
    color: #FFFFFF;
}}
QPushButton.btn-primary:hover {{
    background-color: {THEME_COLORS['primary_hover']};
}}
QPushButton.btn-primary:disabled {{
    background-color: #93C5FD;
    color: #F8FAFC;
}}

QPushButton.btn-secondary {{
    background-color: #F1F5F9;
    color: #334155;
    border: 1px solid #CBD5E1;
}}
QPushButton.btn-secondary:hover {{
    background-color: #E2E8F0;
    color: #0F172A;
}}

QPushButton.btn-success {{
    background-color: {THEME_COLORS['success']};
    color: #FFFFFF;
}}
QPushButton.btn-success:hover {{
    background-color: #059669;
}}

QPushButton.btn-danger {{
    background-color: {THEME_COLORS['danger']};
    color: #FFFFFF;
}}
QPushButton.btn-danger:hover {{
    background-color: #DC2626;
}}

QPushButton.btn-warning {{
    background-color: {THEME_COLORS['warning']};
    color: #FFFFFF;
}}
QPushButton.btn-warning:hover {{
    background-color: #D97706;
}}

/* ==================== INPUT FIELDS ==================== */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit, QTextEdit {{
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 8px 12px;
    color: {THEME_COLORS['text_dark']};
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{
    border: 1.5px solid {THEME_COLORS['primary']};
    background-color: #FFFFFF;
}}

QLineEdit:disabled, QComboBox:disabled {{
    background-color: #F8FAFC;
    color: #94A3B8;
}}

QLabel.field-label {{
    font-weight: 600;
    color: #334155;
    font-size: 12px;
    margin-bottom: 4px;
}}

/* ==================== TABLES ==================== */
QTableWidget, QTableView {{
    background-color: #FFFFFF;
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 8px;
    gridline-color: #F1F5F9;
    selection-background-color: #EFF6FF;
    selection-color: {THEME_COLORS['primary']};
}}

QHeaderView::section {{
    background-color: #F8FAFC;
    color: #475569;
    font-weight: 700;
    font-size: 12px;
    padding: 10px 8px;
    border: none;
    border-bottom: 2px solid #E2E8F0;
}}

QTableWidget::item {{
    padding: 8px;
    border-bottom: 1px solid #F1F5F9;
}}

/* ==================== STATUS PILLS ==================== */
QLabel.status-pill {{
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}

/* ==================== SCROLLBARS ==================== */
QScrollBar:vertical {{
    border: none;
    background: #F1F5F9;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: #CBD5E1;
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #94A3B8;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
