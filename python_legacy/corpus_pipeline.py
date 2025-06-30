# corpus_pipeline.py
# Contains the ChineseCorpusPipeline class for orchestrating the full corpus analysis.

import os
from collections import Counter

import numpy as np

# Assuming other modules are in the same directory or Python path,
# or the Python environment is set up to find them (e.g., by installing your package).
from word_analyzer import CorpusWordAnalyzer

# from nlp_processors import ChineseLtpProcessor # For type hinting if desired


class ChineseCorpusPipeline:
    """
    处理中文语料库的文本文件，为所有词（词+词性）计算分布指标。
    Processes Chinese text files from a corpus to calculate dispersion metrics for all (word, POS) units.
    """

    def __init__(self, nlp_processor, exclude_stop_words_from_analysis=True):
        """
        初始化 Pipeline。
        Initializes the Pipeline.

        Args:
            nlp_processor (object): 一个配置好的NLP处理器实例，期望它有一个
                                   `process_text_chinese(text_content, exclude_stop_words)` 方法。
                                   A configured instance of an NLP processor (e.g., ChineseLtpProcessor)
                                   expected to have a `process_text_chinese` method.
            exclude_stop_words_from_analysis (bool): 是否在频率统计和分布分析中排除停用词。
                                                     文本大小的归一化仍然基于原始分词后的词数。
                                                     Whether to exclude stopwords from frequency counts
                                                     and dispersion analysis. Text size for normalization
                                                     is still based on original segmented word count.
        """
        if (
            nlp_processor is None
            or not hasattr(nlp_processor, "process_text_chinese")
            or not callable(getattr(nlp_processor, "process_text_chinese"))
        ):
            raise TypeError(
                "必须提供一个有效的NLP处理器，该处理器需要有 'process_text_chinese' 方法。"
                "(A valid NLP processor with a 'process_text_chinese' method must be provided.)"
            )
        self.nlp_processor = nlp_processor
        self.exclude_stop_words_from_analysis = exclude_stop_words_from_analysis

        self.corpus_part_sizes_words = np.array([], dtype=float)
        self.total_corpus_words = 0.0
        self.master_vocabulary_data = {}
        self.num_texts = 0

    def _read_file(self, file_path):
        """
        读取文件内容，尝试多种常用中文编码。
        Reads file content, trying multiple common Chinese encodings.
        """
        encodings_to_try = [
            "utf-8",
            "gbk",
            "gb2312",
            "utf-16",
        ]  # utf-16 is less common for .txt but possible
        for encoding in encodings_to_try:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                # print(f"成功使用 {encoding} 编码读取文件 {file_path}") # Optional: for debugging
                return content
            except UnicodeDecodeError:
                # print(f"使用 {encoding} 编码读取文件 {file_path} 失败，尝试下一种编码...") # Optional: for debugging
                continue
            except Exception as e:  # Catch other potential errors like PermissionError
                print(
                    f"读取文件 {file_path} 时发生非编码错误 (Non-encoding error while reading file {file_path}): {e}"
                )
                return ""  # Return empty on other errors too

        # If all encodings fail
        print(
            f"读取文件 {file_path} 失败：尝试所有常用编码后仍无法解码。(Error reading file {file_path}: Failed to decode with common encodings.)"
        )
        return ""

    def process_corpus(self, file_paths_or_dir, yield_progress=False):
        """
        处理指定路径列表或目录中的所有 .txt 文件。
        Processes all .txt files in a given list of paths or a directory.

        Args:
            file_paths_or_dir (str or list): 语料库目录路径或文件路径列表。
            yield_progress (bool): If True, this method becomes a generator yielding progress updates.
        Returns:
            list or generator: List of results or a generator yielding progress dicts.
        """
        if isinstance(file_paths_or_dir, str) and os.path.isdir(file_paths_or_dir):
            file_paths = [
                os.path.join(file_paths_or_dir, f)
                for f in os.listdir(file_paths_or_dir)
                if f.lower().endswith(".txt")
                and os.path.isfile(os.path.join(file_paths_or_dir, f))
            ]
        elif isinstance(file_paths_or_dir, list):
            file_paths = [
                fp
                for fp in file_paths_or_dir
                if os.path.isfile(fp) and fp.lower().endswith(".txt")
            ]
        else:
            err_msg = "输入必须是目录路径或 .txt 文件路径列表。 (Input must be a directory path or a list of .txt file paths.)"
            if yield_progress:
                yield {"type": "error", "message": err_msg}
                return
            else:
                raise ValueError(err_msg)

        self.num_texts = len(file_paths)
        if self.num_texts == 0:
            message = "未找到要处理的 .txt 文件。(No .txt files found to process.)"
            if yield_progress:
                yield {"type": "status", "message": message}
                yield {"type": "final_results", "data": []}
                return
            else:
                print(message)
                return []

        # Reset instance variables for fresh processing
        self.corpus_part_sizes_words = np.zeros(self.num_texts, dtype=float)
        self.total_corpus_words = 0.0
        self.master_vocabulary_data = {}

        per_text_word_pos_counts_list = []

        pass1_message = (
            f"第1阶段：处理 {self.num_texts} 个文本（分词、词性标注、计数）..."
        )
        if yield_progress:
            yield {"type": "status", "message": pass1_message}
        else:
            print(pass1_message)

        for i, file_path in enumerate(file_paths):
            if yield_progress:
                yield {
                    "type": "pass1_progress",
                    "current": i + 1,
                    "total": self.num_texts,
                    "filename": os.path.basename(file_path),
                }
            else:
                progress_bar_length = 30
                filled_length = (
                    int(progress_bar_length * (i + 1) // self.num_texts)
                    if self.num_texts > 0
                    else 0
                )
                bar = "█" * filled_length + "-" * (progress_bar_length - filled_length)
                print(
                    f"  处理中 (Processing): |{bar}| {i + 1}/{self.num_texts} - {os.path.basename(file_path)}",
                    end="\r",
                )

            text_content = self._read_file(file_path)  # Uses the updated _read_file
            if not text_content.strip():
                per_text_word_pos_counts_list.append(Counter())
                self.corpus_part_sizes_words[i] = 0.0
                # Silently skip empty files, or yield a warning if yield_progress is True
                if yield_progress:
                    yield {
                        "type": "warning",
                        "message": f"文件 {os.path.basename(file_path)} 为空或读取失败，已跳过。",
                    }
                continue

            word_pos_units, text_size_segmented = (
                self.nlp_processor.process_text_chinese(
                    text_content, self.exclude_stop_words_from_analysis
                )
            )

            self.corpus_part_sizes_words[i] = float(text_size_segmented)
            per_text_word_pos_counts_list.append(Counter(word_pos_units))

        pass1_complete_msg = "\n第1阶段完成。(Pass 1 complete.)"
        if yield_progress:
            yield {"type": "pass1_complete", "message": pass1_complete_msg.strip()}
        else:
            print(pass1_complete_msg)

        self.total_corpus_words = np.sum(self.corpus_part_sizes_words)
        if self.total_corpus_words < 1e-9:
            message = (
                "警告：整个语料库的总词数（分词后）为0或接近0。无法进行有效的分布分析。"
                "(Warning: Total word count of the corpus (after segmentation) is 0 or near zero. "
                "Effective dispersion analysis is not possible.)"
            )
            if yield_progress:
                yield {"type": "status", "message": message}
                yield {"type": "final_results", "data": []}
                return
            else:
                print(message)
                return []

        pass2_message = "第2阶段：为所有唯一的 (词, 词性) 单元聚合频率..."
        if yield_progress:
            yield {"type": "status", "message": pass2_message}
        else:
            print(pass2_message)

        all_unique_word_pos_units = set()
        for text_counts in per_text_word_pos_counts_list:
            all_unique_word_pos_units.update(text_counts.keys())

        for unit in all_unique_word_pos_units:
            self.master_vocabulary_data[unit] = {
                "f_total": 0.0,
                "v_per_text": np.zeros(self.num_texts, dtype=float),
            }

        for text_idx, text_counts in enumerate(per_text_word_pos_counts_list):
            for word_pos_unit, count in text_counts.items():
                if word_pos_unit in self.master_vocabulary_data:
                    self.master_vocabulary_data[word_pos_unit]["f_total"] += count
                    self.master_vocabulary_data[word_pos_unit]["v_per_text"][
                        text_idx
                    ] = float(count)

        pass2_complete_msg = "第2阶段完成。(Pass 2 complete.)"
        if yield_progress:
            yield {"type": "pass2_complete", "message": pass2_complete_msg}
        else:
            print(pass2_complete_msg)

        num_unique_units = len(self.master_vocabulary_data)
        pass3_message = (
            f"第3阶段：为 {num_unique_units} 个 (词, 词性) 单元计算分布指标..."
        )
        if yield_progress:
            yield {"type": "status", "message": pass3_message}
        else:
            print(pass3_message)

        all_word_metrics_results = []
        processed_count = 0

        for word_pos_unit, data in self.master_vocabulary_data.items():
            processed_count += 1
            unit_processed_for_yield = (
                str(word_pos_unit[0]),
                str(word_pos_unit[1]),
            )  # Ensure serializable for signal

            if yield_progress:
                if (
                    processed_count % 50 == 0 or processed_count == num_unique_units
                ):  # Update periodically
                    yield {
                        "type": "pass3_progress",
                        "current": processed_count,
                        "total": num_unique_units,
                        "unit": unit_processed_for_yield,
                    }
            else:  # CLI progress
                if processed_count % 100 == 0 or processed_count == num_unique_units:
                    progress_bar_length = 30
                    filled_length = (
                        int(progress_bar_length * processed_count // num_unique_units)
                        if num_unique_units > 0
                        else progress_bar_length
                    )
                    bar = "█" * filled_length + "-" * (
                        progress_bar_length - filled_length
                    )
                    print(
                        f"  计算中 (Calculating): |{bar}| {processed_count}/{num_unique_units} - {word_pos_unit}  ",
                        end="\r",
                    )

            v_vector = data["v_per_text"]
            current_word_total_freq = data["f_total"]

            if current_word_total_freq < 1e-9:
                continue

            try:
                # Ensure corpus_part_sizes_words is correctly typed for CorpusWordAnalyzer
                # It is already initialized as np.zeros(self.num_texts, dtype=float)
                analyzer = CorpusWordAnalyzer(
                    v_vector,  # This is already a numpy array
                    self.corpus_part_sizes_words,  # This is already a numpy array
                    self.total_corpus_words,
                )
                metrics = analyzer.calculate_all_metrics()
                all_word_metrics_results.append(
                    {
                        "word": word_pos_unit[0],
                        "pos": word_pos_unit[1],
                        "total_frequency_in_analysis": current_word_total_freq,
                        "metrics_obj": metrics,
                    }
                )
            except ValueError as e:
                err_msg = f"\n无法分析单元 (Could not analyze unit) {word_pos_unit} (总频 {current_word_total_freq}): {e}"
                if yield_progress:
                    yield {"type": "error", "message": err_msg}
                else:
                    print(err_msg)
            except Exception as e_other:
                err_msg = f"\n分析单元 (Error analyzing unit) {word_pos_unit} 时发生未知错误: {e_other}"
                if yield_progress:
                    yield {"type": "error", "message": err_msg}
                else:
                    print(err_msg)

        analysis_complete_msg = "\n语料库分析完成。(Corpus analysis complete.)"
        if yield_progress:
            yield {
                "type": "analysis_complete",
                "message": analysis_complete_msg.strip(),
            }
            yield {"type": "final_results", "data": all_word_metrics_results}
        else:
            print(analysis_complete_msg)
            return all_word_metrics_results
