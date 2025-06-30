# main_GUI_enhanced.py
# Enhanced GUI with PyQt6-Fluent-Widgets and performance optimizations - Multi-Page Layout

import csv
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from PyQt6.QtCore import QMutex, QMutexLocker, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QSizePolicy,  # Added for size policy
    QTableView,
    QVBoxLayout,
    QWidget,
)

# Fluent UI imports
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    CheckBox,
    FluentIcon,
    FluentWindow,
    InfoBar,
    LineEdit,
    MessageBox,
    ProgressBar,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    Theme,
    TitleLabel,
    setTheme,
)

# Layout compatibility aliases
VBoxLayout = QVBoxLayout
HBoxLayout = QHBoxLayout
FluentMessageBox = MessageBox

try:
    import psutil
except ImportError:
    psutil = None
    print(
        "Warning: psutil library not found. Memory usage monitoring will be limited. "
        "To enable full memory monitoring, please install it with: pip install psutil"
    )

import os
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from corpus_pipeline import ChineseCorpusPipeline
from nlp_processors import ChineseLtpProcessor
from optimized_table_model import VirtualTableModel

# Configuration (remains the same)
BASE_METADATA_KEYS = ["word", "pos", "num_chars", "total_frequency_in_analysis"]
METRIC_DISPLAY_ORDER = [
    "mean_text_frequency_FT",
    "pervasiveness_PT",
    "evenness_DA",
    "ft_adjusted_by_DA",
    "ft_adjusted_by_PT",
    "range",
    "dp",
    "dp_norm",
    "kl_divergence",
    "jsd_dispersion",
    "hellinger_dispersion",
    "juilland_d",
    "carroll_d2",
    "roschengren_s_adj",
    "sd_population",
    "vc_population",
]
METRIC_DISPLAY_LABELS_EN = {
    "word": "Word",
    "pos": "POS",
    "num_chars": "Chars",
    "total_frequency_in_analysis": "Total Freq (Analyzed)",
    "range": "Range",
    "sd_population": "SD Population",
    "vc_population": "VC Population",
    "juilland_d": "Juilland's D",
    "carroll_d2": "Carroll's D2",
    "roschengren_s_adj": "Rosengren's S",
    "dp": "DP",
    "dp_norm": "DP_norm",
    "kl_divergence": "KL Divergence",
    "jsd_dispersion": "JSD Dispersion",
    "hellinger_dispersion": "Hellinger Dispersion",
    "mean_text_frequency_FT": "Mean Text Freq (FT)",
    "pervasiveness_PT": "Pervasiveness (PT)",
    "evenness_DA": "Evenness (DA)",
    "ft_adjusted_by_PT": "FT * PT",
    "ft_adjusted_by_DA": "FT * DA",
}


class OptimizedAnalysisWorker(QThread):
    """Enhanced worker thread with parallel processing and performance monitoring."""

    progress_text_signal = pyqtSignal(int, int, str)
    progress_vocab_signal = pyqtSignal(int, int, str)
    status_update_signal = pyqtSignal(str)
    results_ready_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)
    performance_update_signal = pyqtSignal(dict)

    def __init__(
        self,
        corpus_path: str,
        ltp_model_id: str,
        stopwords_path: Optional[str],
        exclude_stopwords: bool,
        max_workers: Optional[int] = None,
    ):
        super().__init__()
        self.corpus_path = Path(corpus_path)
        self.ltp_model_id = ltp_model_id
        self.stopwords_path = Path(stopwords_path) if stopwords_path else None
        self.exclude_stopwords = exclude_stopwords
        self.max_workers = max_workers or min(4, os.cpu_count() or 1)
        self.pipeline: Optional[ChineseCorpusPipeline] = None
        self._mutex = QMutex()
        self._should_stop = False
        self.process_start_time = 0
        self.current_pass_start_time = 0
        self.items_processed_in_current_pass = 0
        self.psutil_process = psutil.Process(os.getpid()) if psutil else None

    def run(self):
        self.process_start_time = time.time()
        try:
            self._initialize_pipeline()
            with QMutexLocker(self._mutex):
                if self._should_stop:
                    return
            self._process_corpus_optimized()
        except Exception as e:
            self._handle_error(e)
        finally:
            self._cleanup()

    def _emit_performance_update(
        self, current_items: int, total_items: int, pass_name: str = "Overall"
    ):
        if not self.isRunning() or self._should_stop:
            return
        elapsed_time_total = time.time() - self.process_start_time
        elapsed_time_pass = time.time() - self.current_pass_start_time
        throughput = 0
        if elapsed_time_pass > 1e-6 and self.items_processed_in_current_pass > 0:
            throughput = self.items_processed_in_current_pass / elapsed_time_pass
        elif elapsed_time_total > 1e-6 and current_items > 0:
            throughput = current_items / elapsed_time_total
        memory_mb = -1.0
        if self.psutil_process:
            try:
                memory_mb = self.psutil_process.memory_info().rss / (1024 * 1024)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                memory_mb = -2.0  # type: ignore
        current_task_progress = (
            (current_items / total_items) * 100 if total_items > 0 else 0
        )
        self.performance_update_signal.emit(
            {
                "memory_mb": memory_mb,
                "throughput": throughput,
                "current_task_progress": current_task_progress,
                "pass_name": pass_name,
            }
        )

    def _initialize_pipeline(self):
        with QMutexLocker(self._mutex):
            if self._should_stop:
                raise RuntimeError("Initialization cancelled by user.")
        self.status_update_signal.emit(
            f"Initializing LTP Processor (Model: {self.ltp_model_id})..."
        )
        self.current_pass_start_time = time.time()
        self.items_processed_in_current_pass = 0
        nlp_proc = ChineseLtpProcessor(
            ltp_model_path_or_instance=self.ltp_model_id,
            user_stop_words_path=str(self.stopwords_path)
            if self.stopwords_path
            else None,
        )
        if nlp_proc.ltp is None:
            raise RuntimeError(
                f"LTP model '{self.ltp_model_id}' initialization failed."
            )
        self.pipeline = ChineseCorpusPipeline(
            nlp_processor=nlp_proc,
            exclude_stop_words_from_analysis=self.exclude_stopwords,
        )
        self.status_update_signal.emit("LTP Processor initialized successfully.")
        self._emit_performance_update(1, 1, "Initialization")

    def _process_corpus_optimized(self):
        if not self.pipeline:
            raise RuntimeError("Pipeline not initialized.")
        final_results_list: List[Dict[str, Any]] = []
        self.current_pass_start_time = time.time()
        self.items_processed_in_current_pass = 0
        for progress_data in self.pipeline.process_corpus(
            str(self.corpus_path), yield_progress=True
        ):
            with QMutexLocker(self._mutex):
                if self._should_stop:
                    self.status_update_signal.emit("Analysis cancelled.")
                    return
            ptype = progress_data.get("type")
            if ptype == "pass1_progress":
                self.items_processed_in_current_pass = progress_data.get("current", 0)
            elif ptype == "pass3_progress":
                self.items_processed_in_current_pass = progress_data.get("current", 0)
            elif ptype in ["pass1_complete", "pass2_complete"]:
                self.current_pass_start_time = time.time()
                self.items_processed_in_current_pass = 0
            self._handle_progress_data(progress_data, final_results_list)
        with QMutexLocker(self._mutex):
            if not self._should_stop:
                self.results_ready_signal.emit(final_results_list or [])

    def _handle_progress_data(
        self, progress_data: Dict[str, Any], final_results_list: List[Dict[str, Any]]
    ):
        ptype = progress_data.get("type")
        current_val, total_val = (
            progress_data.get("current", 0),
            progress_data.get("total", 0),
        )
        if ptype == "pass1_progress":
            self.progress_text_signal.emit(
                current_val, total_val, progress_data.get("filename", "...")
            )
            self._emit_performance_update(
                current_val, total_val, "Pass 1: Text Processing"
            )
        elif ptype == "pass3_progress":
            unit_tuple = progress_data.get("unit", ("Unknown", "Word"))
            unit_str = f"{str(unit_tuple[0])}({str(unit_tuple[1])})"
            self.progress_vocab_signal.emit(current_val, total_val, unit_str)
            self._emit_performance_update(
                current_val, total_val, "Pass 3: Metrics Calc"
            )
        elif ptype in [
            "status",
            "pass1_complete",
            "pass2_complete",
            "analysis_complete",
        ]:
            self.status_update_signal.emit(
                progress_data.get("message", "Status update.")
            )
            if ptype == "analysis_complete":
                self._emit_performance_update(1, 1, "Analysis Complete")
        elif ptype == "warning":
            self.warning_signal.emit(progress_data.get("message", "Pipeline warning."))
        elif ptype == "error":
            self.error_signal.emit(
                f"Pipeline error: {progress_data.get('message', 'Unknown error.')}"
            )
        elif ptype == "final_results":
            data = progress_data.get("data")
            if isinstance(data, list):
                final_results_list.clear()
                final_results_list.extend(data)

    def _handle_error(self, error: Exception):
        with QMutexLocker(self._mutex):
            if self._should_stop:
                return
        self.error_signal.emit(f"Analysis error: {str(error)}")
        self.performance_update_signal.emit(
            {
                "memory_mb": -1,
                "throughput": -1,
                "current_task_progress": 0,
                "pass_name": "Error",
            }
        )

    def _cleanup(self):
        self.pipeline = None

    def stop(self):
        with QMutexLocker(self._mutex):
            if not self._should_stop:
                self.status_update_signal.emit("Cancelling analysis...")
            self._should_stop = True
            if self.pipeline and hasattr(self.pipeline, "stop_processing"):
                self.pipeline.stop_processing()


class AnalysisSetupInterface(ScrollArea):
    """Interface for analysis setup, controls, and monitoring."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("analysisSetupInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)

        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        self.main_layout = QVBoxLayout(self.content_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)

        # Attributes for UI elements
        self.corpus_dir_edit: Optional[LineEdit] = None
        self.corpus_dir_button: Optional[PushButton] = None
        self.ltp_model_edit: Optional[LineEdit] = None
        self.stopwords_checkbox: Optional[CheckBox] = None
        self.stopwords_file_edit: Optional[LineEdit] = None
        self.stopwords_file_button: Optional[PushButton] = None
        self.clear_stopwords_button: Optional[PushButton] = None
        self.start_button: Optional[PushButton] = None
        self.cancel_button: Optional[PushButton] = None
        self.status_label: Optional[BodyLabel] = None
        self.progress_bar: Optional[ProgressBar] = None
        self.memory_label: Optional[BodyLabel] = None
        self.throughput_label: Optional[BodyLabel] = None
        self.task_progress_label: Optional[BodyLabel] = None

        self.current_corpus_path = ""
        self.current_ltp_model_id = "legacy"
        self.current_stopwords_path: Optional[str] = None

        self._build_ui()

    def _build_ui(self):
        page_title = TitleLabel("Analysis Setup & Monitoring")
        page_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(page_title)

        self.main_layout.addWidget(self._create_input_section())
        self.main_layout.addWidget(self._create_control_section())
        self.main_layout.addWidget(self._create_performance_monitor_section())
        self.main_layout.addStretch(1)  # Add stretch to push content up if space allows

    def _create_input_section(self) -> CardWidget:
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        title = SubtitleLabel("Input Configuration")
        layout.addWidget(title)

        corpus_layout = QHBoxLayout()
        corpus_layout.addWidget(BodyLabel("Corpus Directory:"))
        self.corpus_dir_edit = LineEdit(self)
        self.corpus_dir_edit.setPlaceholderText(
            "Select directory containing .txt files"
        )
        self.corpus_dir_edit.setReadOnly(True)
        corpus_layout.addWidget(self.corpus_dir_edit, 1)
        self.corpus_dir_button = PushButton("Browse", card, FluentIcon.FOLDER)
        corpus_layout.addWidget(self.corpus_dir_button)
        layout.addLayout(corpus_layout)

        ltp_layout = QHBoxLayout()
        ltp_layout.addWidget(BodyLabel("LTP Model:"))
        self.ltp_model_edit = LineEdit(self)
        self.ltp_model_edit.setText(self.current_ltp_model_id)
        self.ltp_model_edit.setPlaceholderText(
            "e.g., 'LTP/legacy', 'LTP/base', or local path"
        )
        ltp_layout.addWidget(self.ltp_model_edit, 1)
        layout.addLayout(ltp_layout)

        self.stopwords_checkbox = CheckBox("Exclude Stop Words from Analysis", self)
        self.stopwords_checkbox.setChecked(True)
        layout.addWidget(self.stopwords_checkbox)

        stopwords_layout = QHBoxLayout()
        stopwords_layout.addWidget(BodyLabel("Custom Stopwords File:"))
        self.stopwords_file_edit = LineEdit(self)
        self.stopwords_file_edit.setPlaceholderText(
            "Optional: .txt file with one stopword per line"
        )
        self.stopwords_file_edit.setReadOnly(True)
        stopwords_layout.addWidget(self.stopwords_file_edit, 1)
        self.stopwords_file_button = PushButton("Load", card, FluentIcon.DOCUMENT)
        stopwords_layout.addWidget(self.stopwords_file_button)
        self.clear_stopwords_button = PushButton("Clear", card, FluentIcon.CANCEL)
        stopwords_layout.addWidget(self.clear_stopwords_button)
        layout.addLayout(stopwords_layout)
        return card

    def _create_control_section(self) -> CardWidget:
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        title = SubtitleLabel("Analysis Controls")
        layout.addWidget(title)

        button_layout = QHBoxLayout()
        self.start_button = PushButton("Start Analysis", card, FluentIcon.PLAY)
        self.start_button.setProperty("class", "accent")
        button_layout.addWidget(self.start_button)
        self.cancel_button = PushButton("Cancel Analysis", card, FluentIcon.CANCEL)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.status_label = BodyLabel("Status: Ready", self)
        layout.addWidget(self.status_label)
        self.progress_bar = ProgressBar(self)
        layout.addWidget(self.progress_bar)
        return card

    def _create_performance_monitor_section(self) -> CardWidget:
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        title = SubtitleLabel("Performance Monitor")
        layout.addWidget(title)

        perf_layout = QHBoxLayout()
        self.memory_label = BodyLabel("Memory: -- MB", self)
        perf_layout.addWidget(self.memory_label)
        self.throughput_label = BodyLabel("Throughput: -- items/sec", self)
        perf_layout.addWidget(self.throughput_label)
        self.task_progress_label = BodyLabel("Task: --%", self)
        perf_layout.addWidget(self.task_progress_label)
        perf_layout.addStretch()
        layout.addLayout(perf_layout)
        return card


class ResultsViewerInterface(ScrollArea):
    """Interface for viewing and filtering analysis results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("resultsViewerInterface")
        self.setWidgetResizable(True)
        self.setFrameShape(ScrollArea.Shape.NoFrame)

        self.content_widget = QWidget()
        self.setWidget(self.content_widget)
        self.main_layout = QVBoxLayout(self.content_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(15)

        # Attributes for UI elements
        self.filter_punctuation_checkbox: Optional[CheckBox] = None
        self.char_length_filter_edit: Optional[LineEdit] = None
        self.apply_filters_button: Optional[PushButton] = None
        self.reset_filters_button: Optional[PushButton] = None
        self.results_title_label: Optional[TitleLabel] = None
        self.results_info_label: Optional[BodyLabel] = None
        self.export_all_button: Optional[PushButton] = None
        self.export_filtered_button: Optional[PushButton] = None
        self.auto_adjust_cols_button: Optional[PushButton] = None
        self.results_table: Optional[QTableView] = None
        self.table_model: Optional[VirtualTableModel] = None

        self._build_ui()

    def _build_ui(self):
        page_title = TitleLabel("Analysis Results & Filtering")
        page_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(page_title)

        self.main_layout.addWidget(self._create_filter_section())

        results_display_card = self._create_results_display_section()
        # Allow the results card to take up more vertical space
        self.main_layout.addWidget(results_display_card, 1)  # Stretch factor of 1

    def _create_filter_section(self) -> CardWidget:
        card = CardWidget(self)
        layout = QVBoxLayout(card)
        title = SubtitleLabel("Filter Results")
        layout.addWidget(title)

        filter_controls_layout = QHBoxLayout()
        self.filter_punctuation_checkbox = CheckBox("Hide Punctuation", self)
        self.filter_punctuation_checkbox.setChecked(True)
        filter_controls_layout.addWidget(self.filter_punctuation_checkbox)

        filter_controls_layout.addWidget(BodyLabel("Word Length:", self))
        self.char_length_filter_edit = LineEdit(self)
        self.char_length_filter_edit.setPlaceholderText("e.g., '2-4', '3', '1,5'")
        filter_controls_layout.addWidget(self.char_length_filter_edit)

        filter_controls_layout.addStretch(1)
        self.apply_filters_button = PushButton("Apply Filters", card, FluentIcon.FILTER)
        filter_controls_layout.addWidget(self.apply_filters_button)
        self.reset_filters_button = PushButton("Reset Filters", card, FluentIcon.SYNC)
        filter_controls_layout.addWidget(self.reset_filters_button)
        layout.addLayout(filter_controls_layout)
        return card

    def _create_results_display_section(self) -> CardWidget:
        card = CardWidget(self)
        # Make the card itself expand vertically
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)

        title_layout = QHBoxLayout()
        self.results_title_label = TitleLabel("Results Table", self)
        title_layout.addWidget(self.results_title_label)
        title_layout.addStretch()
        self.results_info_label = BodyLabel("No results yet", self)
        title_layout.addWidget(self.results_info_label)
        layout.addLayout(title_layout)

        controls_layout = QHBoxLayout()
        self.export_all_button = PushButton("Export All", card, FluentIcon.SAVE)
        self.export_all_button.setEnabled(False)
        controls_layout.addWidget(self.export_all_button)
        self.export_filtered_button = PushButton(
            "Export Filtered", card, FluentIcon.SAVE_AS
        )
        self.export_filtered_button.setEnabled(False)
        controls_layout.addWidget(self.export_filtered_button)
        self.auto_adjust_cols_button = PushButton(
            "Auto-Adjust Columns", card, FluentIcon.ALIGNMENT
        )
        self.auto_adjust_cols_button.setEnabled(False)
        controls_layout.addWidget(self.auto_adjust_cols_button)
        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.results_table = QTableView(self)
        self.results_table.setAlternatingRowColors(True)
        # Set size policy for the table to expand within the card
        self.results_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.results_table, 1)  # Add table with stretch factor 1

        self._setup_table_model()
        return card

    def _setup_table_model(self):
        raw_headers = BASE_METADATA_KEYS + METRIC_DISPLAY_ORDER
        self.table_model = VirtualTableModel(raw_headers, METRIC_DISPLAY_LABELS_EN)
        if self.results_table:
            self.results_table.setModel(self.table_model)
            header = self.results_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(False)
            self.results_table.setSortingEnabled(True)

    def update_results_display(self, data: List[Dict[str, Any]]):
        if not self.table_model or not self.results_table:
            return
        self.table_model.set_data(data)
        self._update_results_info_label()
        has_data = bool(data)
        if self.export_all_button:
            self.export_all_button.setEnabled(has_data)
        if self.export_filtered_button:
            self.export_filtered_button.setEnabled(has_data)
        if self.auto_adjust_cols_button:
            self.auto_adjust_cols_button.setEnabled(has_data)
        if has_data:
            self.results_table.resizeColumnsToContents()

    def _update_results_info_label(self):
        if (
            not self.table_model
            or not self.results_info_label
            or not self.results_title_label
        ):
            return
        total_rows = (
            len(self.table_model._data) if hasattr(self.table_model, "_data") else 0
        )
        filtered_rows = self.table_model.rowCount()
        if total_rows == 0:
            self.results_info_label.setText("No results")
            self.results_title_label.setText("Results Table")
        else:
            self.results_info_label.setText(
                f"Showing {filtered_rows:,} of {total_rows:,} items"
            )
            self.results_title_label.setText(f"Results Table ({filtered_rows:,} items)")

    def apply_filters_to_table(self, filters: Dict[str, Any]):
        if not self.table_model:
            return
        self.table_model.apply_filters(filters)
        self._update_results_info_label()
        if self.results_table:
            self.results_table.resizeColumnsToContents()


class EnhancedMainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BetaWordList - Corpus Analysis Tool")
        self.setGeometry(100, 100, 1300, 800)

        self.analysis_thread: Optional[OptimizedAnalysisWorker] = None
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.timeout.connect(self._cleanup_finished_thread)
        self.analysis_results_data: List[Dict[str, Any]] = []

        self._init_navigation_panes()
        self._connect_signals()

        if hasattr(self, "navigationInterface") and self.analysis_setup_page:
            self.navigationInterface.setCurrentItem(
                self.analysis_setup_page.objectName()
            )

    def _init_navigation_panes(self):
        self.analysis_setup_page = AnalysisSetupInterface(self)
        self.results_viewer_page = ResultsViewerInterface(self)

        self.addSubInterface(
            self.analysis_setup_page, FluentIcon.SETTING, "Analysis Setup"
        )
        self.addSubInterface(
            self.results_viewer_page, FluentIcon.DOCUMENT, "Results & Filtering"
        )

    def _connect_signals(self):
        setup_ui = self.analysis_setup_page
        setup_ui.corpus_dir_button.clicked.connect(self._select_corpus_dir)
        setup_ui.stopwords_file_button.clicked.connect(self._select_stopwords_file)
        setup_ui.clear_stopwords_button.clicked.connect(self._clear_stopwords_file)
        setup_ui.start_button.clicked.connect(self._start_analysis)
        setup_ui.cancel_button.clicked.connect(self._cancel_analysis)

        results_ui = self.results_viewer_page
        results_ui.apply_filters_button.clicked.connect(
            self._apply_filters_from_results_page
        )
        results_ui.reset_filters_button.clicked.connect(
            self._reset_filters_on_results_page
        )
        results_ui.export_all_button.clicked.connect(
            lambda: self._export_results(export_all=True)
        )
        results_ui.export_filtered_button.clicked.connect(
            lambda: self._export_results(export_all=False)
        )
        results_ui.auto_adjust_cols_button.clicked.connect(
            self._auto_adjust_table_columns
        )

    def _select_corpus_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Corpus Directory")
        if dir_path and Path(dir_path).is_dir():
            self.analysis_setup_page.corpus_dir_edit.setText(dir_path)
            self.analysis_setup_page.current_corpus_path = dir_path
            self._show_info_bar(
                "Corpus Directory Selected", f"Path: {Path(dir_path).name}", "success"
            )

    def _select_stopwords_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Stopwords File", "", "Text Files (*.txt)"
        )
        if file_path and Path(file_path).is_file():
            self.analysis_setup_page.stopwords_file_edit.setText(file_path)
            self.analysis_setup_page.current_stopwords_path = file_path
            self._show_info_bar(
                "Stopwords File Loaded", f"File: {Path(file_path).name}", "success"
            )

    def _clear_stopwords_file(self):
        self.analysis_setup_page.stopwords_file_edit.clear()
        self.analysis_setup_page.current_stopwords_path = None
        self._show_info_bar(
            "Stopwords Cleared", "Default (or no) stopwords will be used.", "info"
        )

    def _start_analysis(self):
        if not self._validate_inputs_on_setup_page():
            return
        self._prepare_ui_for_analysis_start()
        self.analysis_thread = OptimizedAnalysisWorker(
            self.analysis_setup_page.current_corpus_path,
            self.analysis_setup_page.ltp_model_edit.text(),
            self.analysis_setup_page.current_stopwords_path,
            self.analysis_setup_page.stopwords_checkbox.isChecked(),
        )
        self._connect_worker_signals(self.analysis_thread)
        self.analysis_thread.start()

    def _connect_worker_signals(self, worker: OptimizedAnalysisWorker):
        worker.status_update_signal.connect(self._update_status_display)
        worker.progress_text_signal.connect(self._update_text_progress_display)
        worker.progress_vocab_signal.connect(self._update_vocab_progress_display)
        worker.results_ready_signal.connect(self._handle_analysis_finished)
        worker.error_signal.connect(self._handle_analysis_error)
        worker.warning_signal.connect(self._handle_analysis_warning)
        worker.performance_update_signal.connect(
            self._update_performance_metrics_display
        )
        worker.finished.connect(self._handle_thread_finished)

    def _validate_inputs_on_setup_page(self) -> bool:
        ui = self.analysis_setup_page
        corpus_path = ui.corpus_dir_edit.text().strip()
        ltp_model = ui.ltp_model_edit.text().strip()
        if not corpus_path or not Path(corpus_path).is_dir():
            FluentMessageBox(
                "Input Error", "Please select a valid corpus directory.", self
            ).exec()
            return False
        if not ltp_model:
            FluentMessageBox(
                "Input Error", "Please enter an LTP model path/ID.", self
            ).exec()
            return False
        return True

    def _prepare_ui_for_analysis_start(self):
        ui = self.analysis_setup_page
        ui.start_button.setEnabled(False)
        ui.cancel_button.setEnabled(True)
        ui.progress_bar.setValue(0)
        ui.status_label.setText("Status: Preparing analysis...")
        ui.memory_label.setText("Memory: -- MB")
        ui.throughput_label.setText("Throughput: -- items/sec")
        ui.task_progress_label.setText("Task: --%")
        self.analysis_results_data.clear()
        self.results_viewer_page.update_results_display([])

    def _cancel_analysis(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_setup_page.cancel_button.setEnabled(False)
            self._show_info_bar(
                "Cancellation Requested", "Attempting to stop analysis...", "info"
            )

    def _apply_filters_from_results_page(self):
        ui = self.results_viewer_page
        filters = {}
        if ui.filter_punctuation_checkbox.isChecked():
            filters["exclude_punctuation"] = True
        char_filter_text = ui.char_length_filter_edit.text().strip()
        if char_filter_text:
            parsed_lengths = self._parse_char_length_filter(char_filter_text)
            if isinstance(parsed_lengths, set):
                filters["char_length"] = parsed_lengths
            else:
                FluentMessageBox("Filter Error", parsed_lengths, self).exec()
                return
        ui.apply_filters_to_table(filters)
        self._show_info_bar(
            "Filters Applied", "Results table has been updated.", "success"
        )

    def _reset_filters_on_results_page(self):
        ui = self.results_viewer_page
        ui.filter_punctuation_checkbox.setChecked(True)
        ui.char_length_filter_edit.clear()
        self._apply_filters_from_results_page()
        self._show_info_bar("Filters Reset", "Showing all available results.", "info")

    def _parse_char_length_filter(self, filter_text: str) -> Union[Set[int], str]:
        if not filter_text.strip():
            return set()
        allowed_lengths = set()
        parts = [part.strip() for part in filter_text.split(",") if part.strip()]
        for part in parts:
            try:
                if "-" in part:
                    range_parts = part.split("-", 1)
                    if len(range_parts) != 2:
                        return f"Invalid range format: '{part}'"
                    start, end = int(range_parts[0]), int(range_parts[1])
                    if start < 1 or end < 1 or start > end:
                        return f"Invalid range (min 1, start <= end): '{part}'"
                    allowed_lengths.update(range(start, end + 1))
                else:
                    length = int(part)
                    if length < 1:
                        return f"Length must be positive: '{part}'"
                    allowed_lengths.add(length)
            except ValueError:
                return f"Invalid number in filter: '{part}'"
        return allowed_lengths

    def _auto_adjust_table_columns(self):
        if self.results_viewer_page.results_table:
            self.results_viewer_page.results_table.resizeColumnsToContents()
            self._show_info_bar(
                "Table View Updated", "Column widths adjusted to content.", "info"
            )

    def _export_results(self, export_all: bool = True):
        data_to_export = (
            self.analysis_results_data
            if export_all
            else self.results_viewer_page.table_model.get_filtered_data()
        )
        default_filename = (
            f"corpus_analysis_{'all' if export_all else 'filtered'}_results.csv"
        )
        title = f"Export {'All' if export_all else 'Filtered'} Results"
        if not data_to_export:
            FluentMessageBox("No Data", "There are no results to export.", self).exec()
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, title, default_filename, "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return
        try:
            self._write_csv_file(file_path, data_to_export)
            self._show_info_bar(
                "Export Successful",
                f"Results saved to {Path(file_path).name}",
                "success",
            )
        except Exception as e:
            FluentMessageBox(
                "Export Failed", f"An error occurred during export: {str(e)}", self
            ).exec()

    def _write_csv_file(self, file_path: str, data: List[Dict[str, Any]]):
        if not data:
            return
        model_headers = self.results_viewer_page.table_model._headers
        header_labels_map = self.results_viewer_page.table_model._header_labels_map
        display_csv_headers = [
            header_labels_map.get(k, k.replace("_", " ").title()) for k in model_headers
        ]
        with open(file_path, "w", newline="", encoding="utf-8-sig") as csvfile:
            csv_writer_obj = csv.writer(csvfile)
            csv_writer_obj.writerow(display_csv_headers)
            dict_writer = csv.DictWriter(
                csvfile, fieldnames=model_headers, extrasaction="ignore"
            )
            for entry in data:
                row_data = {}
                metrics_obj = entry.get("metrics_obj")
                for key in model_headers:
                    if key == "num_chars":
                        row_data[key] = len(str(entry.get("word", "")))
                    elif key in BASE_METADATA_KEYS:
                        row_data[key] = entry.get(key, "")
                    elif metrics_obj and hasattr(metrics_obj, key):
                        value = getattr(metrics_obj, key, None)
                        if isinstance(value, float):
                            if math.isinf(value) or math.isnan(value):
                                row_data[key] = str(value)
                            else:
                                row_data[key] = f"{value:.6f}"
                        else:
                            row_data[key] = value if value is not None else ""
                    else:
                        row_data[key] = ""
                dict_writer.writerow(row_data)

    def _update_status_display(self, message: str):
        self.analysis_setup_page.status_label.setText(f"Status: {message}")

    def _update_text_progress_display(self, current: int, total: int, filename: str):
        ui = self.analysis_setup_page
        if total > 0:
            ui.progress_bar.setValue(int((current / total) * 100))
        self._update_status_display(f"Processing file {current}/{total}: {filename}")

    def _update_vocab_progress_display(self, current: int, total: int, unit_str: str):
        ui = self.analysis_setup_page
        if total > 0:
            ui.progress_bar.setValue(int((current / total) * 100))
        self._update_status_display(
            f"Calculating metrics {current}/{total}: {unit_str}"
        )

    def _update_performance_metrics_display(self, perf_data: Dict[str, Any]):
        ui = self.analysis_setup_page
        memory_mb = perf_data.get("memory_mb", -1.0)
        throughput = perf_data.get("throughput", 0.0)
        task_progress = perf_data.get("current_task_progress", 0.0)
        pass_name = perf_data.get("pass_name", "N/A")
        mem_text = f"Memory: {memory_mb:.1f} MB" if memory_mb >= 0 else "Memory: N/A"
        if memory_mb == -2.0:
            mem_text = "Memory: Error"  # type: ignore
        ui.memory_label.setText(mem_text)
        ui.throughput_label.setText(
            f"Throughput: {throughput:.1f} items/s ({pass_name})"
        )
        ui.task_progress_label.setText(f"Task ({pass_name}): {task_progress:.0f}%")

    def _handle_analysis_finished(self, results: List[Dict[str, Any]]):
        self.analysis_results_data = results or []
        self.results_viewer_page.update_results_display(self.analysis_results_data)
        self._update_status_display("Analysis completed successfully!")
        self.analysis_setup_page.progress_bar.setValue(100)
        count = len(self.analysis_results_data)
        self._show_info_bar(
            "Analysis Complete",
            f"Successfully processed {count:,} unique word units.",
            "success",
        )
        self.switchTo(self.results_viewer_page)  # Switch to results view

    def _handle_analysis_error(self, error_message: str):
        self._update_status_display("Analysis failed!")
        self.analysis_setup_page.progress_bar.setValue(0)
        FluentMessageBox("Analysis Error", error_message, self).exec()
        self._reset_ui_after_thread_actions()

    def _handle_analysis_warning(self, warning_message: str):
        self._show_info_bar(
            "Analysis Warning", warning_message, "warning", duration=5000
        )

    def _handle_thread_finished(self):
        self._reset_ui_after_thread_actions()
        if self.analysis_thread:
            self._cleanup_timer.start(100)

    def _reset_ui_after_thread_actions(self):
        ui = self.analysis_setup_page
        ui.start_button.setEnabled(True)
        ui.cancel_button.setEnabled(False)

    def _cleanup_finished_thread(self):
        if self.analysis_thread:
            self.analysis_thread.quit()
            self.analysis_thread.wait(1000)
            if self.analysis_thread.isRunning():
                self.analysis_thread.terminate()
                self.analysis_thread.wait(500)
            del self.analysis_thread
            self.analysis_thread = None
            print("Analysis thread cleaned up.")

    def _show_info_bar(
        self, title: str, content: str, severity: str = "info", duration: int = 3000
    ):
        if severity == "success":
            InfoBar.success(title, content, duration=duration, parent=self)
        elif severity == "warning":
            InfoBar.warning(title, content, duration=duration, parent=self)
        elif severity == "error":
            InfoBar.error(title, content, duration=duration, parent=self)
        else:
            InfoBar.info(title, content, duration=duration, parent=self)

    def closeEvent(self, event):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self._show_info_bar(
                "Closing",
                "Attempting to stop ongoing analysis...",
                "info",
                duration=3000,
            )
            self.analysis_thread.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    setTheme(Theme.AUTO)
    window = EnhancedMainWindow()
    window.show()
    sys.exit(app.exec())
