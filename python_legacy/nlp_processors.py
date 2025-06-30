# nlp_processors.py
import os
import re
import sys
from pathlib import Path  # Recommended for path operations
from typing import Any, List, Optional, Tuple, Union  # For type hints

# It's good practice to handle potential ImportError for ltp
try:
    from ltp import LTP, StnSplit  # Import StnSplit
except ImportError:
    LTP = None
    StnSplit = None  # Define StnSplit as None if not installed


def get_resource_path(relative_path: str) -> str:  # Added type hint
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not running in a PyInstaller bundle (e.g., development mode)
        base_path = os.path.abspath(
            "."
        )  # Assumes script is run from project root or path is relative to CWD

    # Normalize the relative path for consistency
    normalized_relative_path = str(relative_path).replace("\\", "/")
    if normalized_relative_path.startswith("./"):
        normalized_relative_path = normalized_relative_path[2:]

    return os.path.join(base_path, normalized_relative_path)


class ChineseLtpProcessor:
    """
    使用LTP处理中文文本的封装类，包含分句预处理。
    Encapsulates Chinese text processing using LTP, including sentence splitting.
    """

    def __init__(
        self,
        ltp_model_path_or_instance="legacy",
        user_stop_words_path: Optional[str] = None,
    ):
        self.ltp: Optional[LTP] = None  # Type hint
        self.stnsplit: Optional[StnSplit] = None  # For sentence splitting

        if LTP is None or StnSplit is None:
            print(
                "错误：ltp库或其StnSplit组件未安装或无法导入。请运行 'pip install ltp' 并确保其可用。"
            )
            print("ChineseLtpProcessor 将无法工作。")
            return

        self._initialize_ltp_model(ltp_model_path_or_instance)
        if self.ltp:  # Only initialize StnSplit if LTP model loaded successfully
            try:
                self.stnsplit = StnSplit()
                print("LTP StnSplit (分句器) 初始化成功。")
            except Exception as e:
                print(f"错误：初始化LTP StnSplit失败: {e}")
                self.stnsplit = None  # Ensure it's None on failure

        self._initialize_stopwords(user_stop_words_path)

    def _initialize_ltp_model(
        self, ltp_model_path_or_instance: Union[str, Any]
    ):  # Type hint for Any LTP instance
        """初始化LTP模型"""
        if hasattr(ltp_model_path_or_instance, "pipeline") and callable(
            ltp_model_path_or_instance.pipeline
        ):
            self.ltp = ltp_model_path_or_instance
            print("已使用预初始化的LTP实例。")
            return

        if not isinstance(ltp_model_path_or_instance, str):
            err_msg = (
                f"错误: 无效的LTP模型路径或实例类型: {type(ltp_model_path_or_instance)}"
            )
            print(err_msg)
            raise TypeError(err_msg)

        model_path_to_try = self._resolve_model_path(ltp_model_path_or_instance)
        self._load_ltp_model(model_path_to_try, ltp_model_path_or_instance)

    def _resolve_model_path(self, model_path_str: str) -> str:
        """解析模型路径"""
        if os.path.isabs(model_path_str):
            return model_path_str
        if model_path_str.startswith("LTP/"):  # Official LTP model IDs
            return model_path_str

        # Assume it's a relative path to be resolved via get_resource_path
        resolved_path = get_resource_path(model_path_str)
        print(
            f"LTP模型路径(相对路径)解析: 原始='{model_path_str}', 解析后尝试='{resolved_path}'"
        )
        # No existence check here; LTP constructor will handle it and raise an error if invalid.
        return resolved_path

    def _load_ltp_model(self, model_path_to_load: str, original_path_ref: str):
        """加载LTP模型"""
        try:
            self.ltp = LTP(model_path_to_load)
            print(f"LTP模型从 '{model_path_to_load}' 加载成功。")
        except Exception as e:
            original_info = (
                f" (原始输入: '{original_path_ref}')"
                if model_path_to_load != original_path_ref
                else ""
            )
            error_message = (
                f"错误：加载LTP模型 '{model_path_to_load}'{original_info} 失败: {e}"
            )
            print(error_message)
            if not model_path_to_load.startswith(
                "LTP/"
            ):  # If it was a local path attempt
                print(
                    "建议检查: 1. 模型文件是否存在于指定路径; 2. 模型文件是否已正确打包到应用中; "
                    "3. 模型文件格式是否正确; 4. 或者尝试使用LTP可自动下载的模型ID (如 'LTP/base')。"
                )
            self.ltp = None
            raise RuntimeError(error_message) from e  # Propagate error

    def _initialize_stopwords(self, user_stop_words_path: Optional[str]):
        """初始化停用词"""
        self.stop_words: Set[str] = set()  # Type hint
        if user_stop_words_path:
            self.load_custom_stopwords(user_stop_words_path)
        else:
            # Per user request, no default internal stopwords, rely on GUI/user to provide.
            print(
                "提示：初始化时未提供停用词表路径。如果勾选“排除停用词”，则需要加载一个停用词表文件才有效。"
            )

    def load_custom_stopwords(self, file_path_str: Optional[str]) -> bool:
        """加载自定义停用词表。会覆盖已有的停用词。"""
        if not file_path_str:
            # This might be called with None if user clears selection in GUI
            self.stop_words = set()  # Ensure it's empty if path is None
            print("提示：停用词表路径未提供或已清除，当前停用词表为空。")
            return False

        file_path = Path(file_path_str)
        if not file_path.is_file():
            print(f"警告：停用词表路径 '{file_path}' 不是有效文件。停用词表未更改。")
            # Do not clear existing stopwords if new path is invalid but old one was loaded
            return False

        new_stopwords = set()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith("#"):
                        new_stopwords.add(word)
            self.stop_words = new_stopwords
            print(f"成功从 '{file_path}' 加载了 {len(self.stop_words)} 个停用词。")
            return True
        except Exception as e:
            print(f"从自定义路径 '{file_path}' 加载停用词表失败: {e}")
            return False  # Indicate failure

    def is_ready(self) -> bool:
        """检查LTP主模型和分句器是否都已就绪。"""
        return self.ltp is not None and self.stnsplit is not None

    def process_text_chinese(
        self, text_content: str, exclude_stop_words: bool = True
    ) -> Tuple[List[Tuple[str, str]], int]:
        """
        使用LTP处理中文文本，包含分句，返回 (词, 词性) 单元列表和原始有效分词数。
        """
        if not self.is_ready():
            raise RuntimeError("LTP处理器或分句器未正确初始化，无法处理文本。")

        if not text_content or not text_content.strip():
            return [], 0

        try:
            # 1. 文本预处理 (主要是规范化空白)
            processed_text = self._preprocess_text(text_content)
            if not processed_text:
                return [], 0

            # 2. 使用 StnSplit 进行分句
            # StnSplit().split() 期望单个字符串，返回句子列表
            sentences: List[str] = self.stnsplit.split(processed_text)
            if not sentences:
                return [], 0

            # 3. 使用 LTP 对句子列表进行分词和词性标注
            # ltp.pipeline(sentences_list, tasks=['cws', 'pos'])
            # Output is dict with 'cws': List[List[str]], 'pos': List[List[str]] for newer LTP
            # Or tuple (List[List[str]], List[List[str]]) for legacy .to_tuple()
            pipeline_output = self.ltp.pipeline(sentences, tasks=["cws", "pos"])

            # 4. 从LTP输出中提取并展平结果
            flat_words, flat_pos_tags = self._extract_and_flatten_ltp_results(
                pipeline_output
            )

            # 5. 清理单个词的空白并统计有效词数 (清理后，停用词过滤前)
            cleaned_word_pos_pairs: List[Tuple[str, str]] = []
            for word, tag in zip(flat_words, flat_pos_tags):
                stripped_word = word.strip()
                if stripped_word:  # 只保留strip后非空的词
                    cleaned_word_pos_pairs.append((stripped_word, tag))

            original_valid_token_count = len(cleaned_word_pos_pairs)

            # 6. 停用词过滤 (如果需要)
            if exclude_stop_words and self.stop_words:
                final_word_pos_units = self._filter_stopwords(cleaned_word_pos_pairs)
            else:
                final_word_pos_units = cleaned_word_pos_pairs

            return final_word_pos_units, original_valid_token_count

        except Exception as e:
            # Log the error with traceback for easier debugging
            print(f"文本处理过程中发生错误 (Error during text processing): {e}")
            traceback.print_exc()
            raise RuntimeError(
                f"文本处理过程中出错 (Error during text processing): {e}"
            ) from e

    def _preprocess_text(self, text_content: str) -> str:
        """预处理文本，主要规范化空白。"""
        # 将各种空白（包括全角）替换为单个半角空格，并去除首尾空格
        text = re.sub(r"[\s\u3000]+", " ", text_content).strip()
        return text

    def _extract_and_flatten_ltp_results(
        self, pipeline_output: Any
    ) -> Tuple[List[str], List[str]]:
        """从LTP的pipeline输出中提取并展平分词和词性标注结果。"""
        flat_words: List[str] = []
        flat_pos_tags: List[str] = []

        if hasattr(pipeline_output, "to_tuple"):  # 旧版本 LTP 的 to_tuple() 风格
            cws_sent_list, pos_sent_list = pipeline_output.to_tuple()
            if cws_sent_list:  # cws_sent_list is List[List[str]]
                for sent_words in cws_sent_list:
                    flat_words.extend(sent_words)
            if pos_sent_list:  # pos_sent_list is List[List[str]]
                for sent_tags in pos_sent_list:
                    flat_pos_tags.extend(sent_tags)
        elif isinstance(pipeline_output, dict):  # 新版本 LTP 返回字典风格
            cws_sent_list = pipeline_output.get("cws", [])
            pos_sent_list = pipeline_output.get("pos", [])
            for sent_words in cws_sent_list:
                flat_words.extend(sent_words)
            for sent_tags in pos_sent_list:
                flat_pos_tags.extend(sent_tags)
        else:
            # Should not happen if LTP initialized correctly and pipeline called
            print(
                f"警告：处理LTP输出时遇到未知格式: {type(pipeline_output)}。可能导致结果不正确。"
            )
            # Fallback or raise error
            # For now, return empty to avoid further issues.
            return [], []

        # 最终验证，确保分词和词性列表长度一致
        if len(flat_words) != len(flat_pos_tags):
            print(
                f"警告：展平后的分词结果数量 ({len(flat_words)}) 与词性标注结果数量 ({len(flat_pos_tags)}) 不匹配。将按最短长度对齐。"
            )
            min_len = min(len(flat_words), len(flat_pos_tags))
            flat_words = flat_words[:min_len]
            flat_pos_tags = flat_pos_tags[:min_len]

        return flat_words, flat_pos_tags

    def _filter_stopwords(
        self, word_pos_pairs: List[Tuple[str, str]]
    ) -> List[Tuple[str, str]]:
        """根据 self.stop_words 过滤 (词, 词性) 对。"""
        if not self.stop_words:  # 如果停用词表为空，则不进行过滤
            return word_pos_pairs
        return [
            (word, pos) for word, pos in word_pos_pairs if word not in self.stop_words
        ]

    def get_stopwords_count(self) -> int:
        """获取当前加载的停用词数量。"""
        return len(self.stop_words)

    # add_stopwords 和 remove_stopwords 方法可以保留，如果GUI需要动态修改停用词集的话，
    # 但更常见的是通过加载文件来完全替换。
    # def add_stopwords(self, words: Union[str, List[str]]): ...
    # def remove_stopwords(self, words: Union[str, List[str]]): ...
