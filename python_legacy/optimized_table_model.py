# optimized_table_model.py
# Optimized table model for handling large datasets with virtual scrolling

import math
import sys  # For memory usage calculation
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, QVariant, pyqtSignal
from PyQt6.QtGui import QFont


class VirtualTableModel(QAbstractTableModel):
    """
    Optimized table model with virtual scrolling for large datasets.
    Only loads visible data into memory.
    Handles dynamic calculation of 'num_chars' and fetching metrics from 'metrics_obj'.
    """

    data_loading = pyqtSignal(int, int)  # current, total
    data_loaded = pyqtSignal()

    def __init__(
        self, headers_keys: List[str], header_labels_map: Dict[str, str], parent=None
    ):
        super().__init__(parent)
        self._headers = headers_keys  # Internal keys for data access, e.g., "word", "mean_text_frequency_FT"
        self._header_labels_map = (
            header_labels_map  # Map of keys to display names, e.g., {"word": "Word"}
        )

        self._data: List[Dict[str, Any]] = []
        self._filtered_indices: List[
            int
        ] = []  # Indices of filtered data relative to self._data
        self._sort_column_key: Optional[str] = None  # Store key of sort column
        self._sort_order = Qt.SortOrder.AscendingOrder

        # Chunking attributes (can be adjusted based on performance)
        self._chunk_size = 500
        self._loaded_chunks = {}  # chunk_index -> chunk_data_list for faster access
        self._all_data_loaded_into_chunks = False

    def set_data(self, data: List[Dict[str, Any]]):
        """Set the full dataset. Data is not immediately loaded into chunks."""
        self.beginResetModel()
        self._data = data
        self._filtered_indices = list(range(len(data)))
        self._loaded_chunks.clear()
        self._all_data_loaded_into_chunks = False
        # If data is small, could pre-load all chunks here. For now, lazy load.
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._filtered_indices)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """Return header data using the display labels map."""
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                if 0 <= section < len(self._headers):
                    key = self._headers[section]
                    return self._header_labels_map.get(
                        key, key.replace("_", " ").title()
                    )
            elif role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
        elif orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(section + 1)  # Row numbers
        return QVariant()

    def _get_item_data_by_filtered_row(
        self, filtered_row_index: int
    ) -> Optional[Dict[str, Any]]:
        """Gets the original data item for a row in the filtered view."""
        if not (0 <= filtered_row_index < len(self._filtered_indices)):
            return None

        original_data_index = self._filtered_indices[filtered_row_index]

        # Chunking logic:
        # For simplicity in this version, we'll access _data directly.
        # A more advanced chunking would load/unload from self._loaded_chunks.
        # This model assumes _data is always available, chunking is for future optimization.
        if 0 <= original_data_index < len(self._data):
            return self._data[original_data_index]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """Return data for the given index, handling metrics and 'num_chars'."""
        if not index.isValid():
            return QVariant()

        row = index.row()
        col = index.column()

        item_data = self._get_item_data_by_filtered_row(row)
        if item_data is None:
            return QVariant()

        header_key = self._headers[col]  # This is the internal key

        if role == Qt.ItemDataRole.DisplayRole:
            value_to_display = None
            if header_key == "num_chars":
                word = item_data.get("word", "")
                value_to_display = len(str(word))
            elif (
                header_key in item_data
            ):  # Base keys like 'word', 'pos', 'total_frequency_in_analysis'
                value_to_display = item_data.get(header_key)
            else:  # Assumed to be a metric from metrics_obj
                metrics_obj = item_data.get("metrics_obj")
                if metrics_obj and hasattr(metrics_obj, header_key):
                    value_to_display = getattr(metrics_obj, header_key, None)

            # Formatting the display value
            if isinstance(value_to_display, float):
                if math.isinf(value_to_display):
                    return "inf" if value_to_display > 0 else "-inf"
                elif math.isnan(value_to_display):
                    return "nan"
                else:
                    return f"{value_to_display:.4f}"  # Consistent float formatting
            return str(value_to_display) if value_to_display is not None else ""

        elif role == Qt.ItemDataRole.UserRole:  # For sorting
            value_for_sorting = None
            if header_key == "num_chars":
                value_for_sorting = len(str(item_data.get("word", "")))
            elif header_key in item_data:
                value_for_sorting = item_data.get(header_key)
            else:  # Metric
                metrics_obj = item_data.get("metrics_obj")
                if metrics_obj and hasattr(metrics_obj, header_key):
                    value_for_sorting = getattr(metrics_obj, header_key, None)

            # Ensure sortable type, especially for None or complex objects (though metrics should be numeric/str)
            if value_for_sorting is None:
                return -float("inf")  # Sort None values consistently
            if isinstance(value_for_sorting, (list, dict, set)):
                return str(value_for_sorting)  # Fallback for complex types
            return value_for_sorting

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # Determine alignment based on likely data type (simple heuristic)
            # This part can be refined if more specific type information is available per column
            potential_value = None
            if header_key == "num_chars":
                potential_value = 0  # It's numeric
            elif header_key in item_data:
                potential_value = item_data.get(header_key)
            else:
                metrics_obj = item_data.get("metrics_obj")
                if metrics_obj and hasattr(metrics_obj, header_key):
                    potential_value = getattr(metrics_obj, header_key, None)

            if isinstance(potential_value, (int, float)) and not isinstance(
                potential_value, bool
            ):
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return QVariant()

    def sort(
        self, column_index: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ):
        if not (0 <= column_index < len(self._headers)):
            return

        self.layoutAboutToBeChanged.emit()

        self._sort_column_key = self._headers[column_index]
        self._sort_order = order
        is_reverse = order == Qt.SortOrder.DescendingOrder

        # Create a list of (sort_value, original_data_index) for sorting
        # This ensures that we sort based on the raw data values
        sortable_list = []
        for (
            original_data_idx
        ) in self._filtered_indices:  # Iterate over currently filtered items
            item = self._data[original_data_idx]
            sort_val = None
            if self._sort_column_key == "num_chars":
                sort_val = len(str(item.get("word", "")))
            elif self._sort_column_key in item:
                sort_val = item.get(self._sort_column_key)
            else:  # Metric
                metrics_obj = item.get("metrics_obj")
                if metrics_obj and hasattr(metrics_obj, self._sort_column_key):
                    sort_val = getattr(metrics_obj, self._sort_column_key, None)

            # Handle None for sorting: place them at the beginning or end consistently
            if sort_val is None:
                sort_val = -float("inf") if not is_reverse else float("inf")

            # Attempt to convert to float if possible for numeric sort, otherwise use string
            try:
                numeric_sort_val = float(sort_val)
                sortable_list.append((numeric_sort_val, original_data_idx))
            except (ValueError, TypeError):
                sortable_list.append(
                    (str(sort_val).lower(), original_data_idx)
                )  # Case-insensitive string sort

        try:
            sortable_list.sort(key=lambda x: x[0], reverse=is_reverse)
        except TypeError:  # Fallback if mixed types still cause issues (e.g. comparing numbers and strings after float conversion failed)
            sortable_list.sort(key=lambda x: str(x[0]), reverse=is_reverse)

        self._filtered_indices = [original_idx for _, original_idx in sortable_list]

        self.layoutChanged.emit()

    def apply_filters(self, filters: Dict[str, Any]):
        self.beginResetModel()
        new_filtered_indices = []
        for i, item in enumerate(self._data):  # Iterate over the original full dataset
            include_item = True
            for filter_key, filter_value in filters.items():
                if not include_item:
                    break  # Already excluded by a previous filter

                if filter_key == "exclude_punctuation" and filter_value:
                    pos = item.get("pos", "").lower()
                    if pos == "wp":  # Assuming 'wp' is the POS tag for punctuation
                        include_item = False
                elif (
                    filter_key == "char_length" and filter_value
                ):  # filter_value is a set of allowed lengths
                    word = item.get("word", "")
                    char_count = len(word)
                    if char_count not in filter_value:
                        include_item = False
                # Add more filter conditions here as needed

            if include_item:
                new_filtered_indices.append(i)

        self._filtered_indices = new_filtered_indices
        # After filtering, if a sort was active, re-apply it to the new filtered list
        if self._sort_column_key is not None:
            try:
                sort_col_idx = self._headers.index(self._sort_column_key)
                self.sort(
                    sort_col_idx, self._sort_order
                )  # This will re-sort self._filtered_indices
            except ValueError:  # Should not happen if _sort_column_key is valid
                pass

        self.endResetModel()

    def get_item_data(self, filtered_row: int) -> Optional[Dict[str, Any]]:
        """Get the full original data dictionary for a row in the filtered view."""
        return self._get_item_data_by_filtered_row(filtered_row)

    def get_filtered_data(self) -> List[Dict[str, Any]]:
        """Get all data items that are currently part of the filtered view."""
        return [
            self._data[idx]
            for idx in self._filtered_indices
            if 0 <= idx < len(self._data)
        ]

    # Chunk-related methods (conceptual, not fully implemented for lazy loading/unloading here)
    def _load_chunk(self, chunk_idx: int):  # Placeholder
        pass

    def clear_cache(self):  # Placeholder
        self._loaded_chunks.clear()

    def get_memory_usage(self) -> Dict[str, float]:  # Basic version
        total_data_size = sys.getsizeof(self._data) + sum(
            sys.getsizeof(x) for x in self._data
        )
        return {"total_data_mb": total_data_size / (1024 * 1024)}
