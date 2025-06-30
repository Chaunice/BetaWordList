# word_analyzer.py
# Contains the CorpusWordAnalyzer class for calculating dispersion metrics for a single word/unit.

import math

import numpy as np

# Assuming dispersion_metrics_models.py is in the same directory or Python path
from dispersion_metrics_models import DispersionMetrics


class CorpusWordAnalyzer:
    """
    计算语料库中一个词（通常是 词+词性）的各种词汇分布指标。
    Calculates various lexical dispersion metrics for a word/unit in a corpus.
    Includes metrics based on Stefan Th. Gries's chapter "Analyzing Dispersion"
    and the lexical prevalence framework by Egbert & Burch (2023).
    """

    def __init__(self, v, corpus_part_sizes_words, total_corpus_words):
        """
        初始化分析器。
        Initializes the analyzer.

        Args:
            v (np.ndarray): 目标词在每个文本部分中的频率列表。
                            Frequencies of the target word in each corpus part.
            corpus_part_sizes_words (np.ndarray): 每个文本部分的大小（词数）列表。
                                                  Total number of words in each corresponding corpus part.
            total_corpus_words (float): 整个语料库的总词数。
                                        Total number of words in the entire corpus.
        """
        if not isinstance(v, np.ndarray) or not isinstance(
            corpus_part_sizes_words, np.ndarray
        ):
            raise TypeError(
                "Inputs 'v' and 'corpus_part_sizes_words' must be NumPy arrays."
            )
        if v.ndim != 1 or corpus_part_sizes_words.ndim != 1:
            raise ValueError(
                "Inputs 'v' and 'corpus_part_sizes_words' must be 1-dimensional arrays."
            )
        if v.shape != corpus_part_sizes_words.shape:
            raise ValueError(
                "Frequency vector (v) and part sizes vector must have the same shape."
            )
        if v.size == 0:  # Check if array is empty
            raise ValueError("Input vectors cannot be empty (n must be > 0).")
        if total_corpus_words <= 1e-9:  # Use epsilon for float comparison
            raise ValueError(
                "语料库总词数必须为正 (Total corpus words must be positive)."
            )
        if np.any(corpus_part_sizes_words < 0):
            raise ValueError(
                "语料库各部分的大小不能为负 (Corpus part sizes cannot be negative)."
            )
        if (
            abs(np.sum(corpus_part_sizes_words) - total_corpus_words)
            > 1e-9 * total_corpus_words
        ):  # Relative tolerance
            # Looser tolerance for sum check, can be strict if inputs are precise
            # print(f"Warning: Sum of part sizes {np.sum(corpus_part_sizes_words)} vs total {total_corpus_words}")
            pass  # Allow small discrepancies due to potential float arithmetic from upstream processing

        self.v = v.astype(float)
        self.corpus_part_sizes_words = corpus_part_sizes_words.astype(float)
        self.total_corpus_words = float(total_corpus_words)

        self.n = v.size  # 文本部分的数量 (Number of corpus parts)
        self.f = np.sum(
            self.v
        )  # 词在整个语料库中的总频率 (Overall frequency of the word)

        # s_i: 各文本部分大小占总语料库大小的比例
        # Proportions of the n corpus part sizes (s_i = size_of_part_i / total_corpus_words)
        self.s = np.divide(
            self.corpus_part_sizes_words,
            self.total_corpus_words,
            out=np.zeros_like(self.corpus_part_sizes_words, dtype=float),
            where=self.total_corpus_words > 1e-12,
        )

        # p_i: 词在每个文本部分中所占的比例 (v_i / size_of_part_i)
        # Proportions the word makes up of each corpus part (p_i = v_i / size_of_part_i)
        # 如果某部分的 corpus_part_sizes_words 为0 (或极小)，则 p_i 也为0
        self.p = np.zeros_like(self.v, dtype=float)
        # Mask for parts with a meaningful size (avoid division by zero or very small numbers)
        meaningful_size_mask = self.corpus_part_sizes_words > 1e-9
        self.p[meaningful_size_mask] = (
            self.v[meaningful_size_mask]
            / self.corpus_part_sizes_words[meaningful_size_mask]
        )

    def _log2_safe(self, n_val):
        """Helper for log base 2. Convention: 0 * log2(0) = 0."""
        if n_val <= 1e-12:  # Using a small epsilon for float comparisons
            return 0.0
        return math.log2(n_val)

    def _kl_term(self, p_val, q_val):
        """Helper for a single term in KL divergence: p * log2(p/q)."""
        if p_val <= 1e-12:  # p = 0 term
            return 0.0
        if q_val <= 1e-12:  # p > 0 and q = 0 (or very small) term (infinite divergence)
            return float("inf")
        ratio = p_val / q_val
        if ratio <= 1e-12:  # Avoid log2(0) if ratio is extremely small due to precision
            return 0.0
        return p_val * self._log2_safe(ratio)

    def get_range(self):
        """范围：包含该词的文本部分数量 (即 v_i > 0)。
        Range: number of parts containing the word (i.e., v_i > 0)."""
        return int(np.sum(self.v > 1e-9))  # Use epsilon for float comparison

    def get_sd_population(self):
        """频次总体标准差 (v_i)。
        Standard Deviation (population) of frequencies v_i."""
        if self.n == 0:
            return None  # Should be caught by __init__ if v is empty
        if self.f < 1e-9:
            return 0.0  # If total frequency is effectively zero, SD is 0
        mean_v = self.f / self.n
        return np.sqrt(np.sum((self.v - mean_v) ** 2) / self.n)

    def get_vc_population(self):
        """频次总体变异系数 (基于 v_i)。
        Variation Coefficient (population) based on v_i."""
        if self.n == 0:
            return None
        mean_v = self.f / self.n
        if abs(mean_v) < 1e-12:  # If mean_v is effectively zero
            return (
                0.0 if self.f < 1e-9 else None
            )  # If f is also 0, VC is 0. If f>0 but mean_v=0 (e.g. n is huge), VC is undefined.
        sd = self.get_sd_population()
        if sd is None:
            return None
        return sd / mean_v

    def get_juilland_d(self):
        """Juilland's D (适用于不同大小的语料库部分) - 已修正。
        Juilland's D (version for differently large corpus parts) - Corrected."""
        if self.n <= 1:
            return 1.0 if self.f > 1e-9 else 0.0
        if self.f < 1e-9:
            return 0.0  # If no occurrences, dispersion is minimal/zero.

        mean_p = np.mean(self.p)

        if abs(mean_p) < 1e-12:
            # If all p_i are effectively zero (e.g., word only in zero-size parts, or f=0)
            # and f > 0, this implies word occurs but its density is ~0 everywhere.
            # If all p_i are identical (e.g., all 0), sd_p will be 0, vc_p will be 0, D=1.
            # This path is taken if f > 0 but mean_p is ~0.
            # If sd_p is also ~0, then D=1. If sd_p > 0, then vc_p is large, D is small/negative.
            pass  # Fall through to standard calculation

        # Population standard deviation of p_i
        sd_population_p = np.sqrt(np.sum((self.p - mean_p) ** 2) / self.n)

        if abs(mean_p) < 1e-12:  # Re-check for division by zero for vc_p
            return (
                1.0 if abs(sd_population_p) < 1e-12 else 0.0
            )  # If mean_p=0, D=1 if sd_p=0, else D=0 (max clump)

        vc_p = sd_population_p / mean_p

        # Denominator sqrt(n-1) requires n > 1, which is true here.
        return 1.0 - vc_p * (1.0 / math.sqrt(self.n - 1))

    def get_carroll_d2(self):
        """Carroll's D₂ (基于熵)。
        Carroll's D₂ (entropy-based)."""
        if self.n <= 1:
            return 1.0 if self.f > 1e-9 else 0.0

        sum_p_values = np.sum(self.p)
        if (
            abs(sum_p_values) < 1e-12
        ):  # sum_p_values is 0 if f=0 or word only in zero-size parts
            return 0.0

        norm_proportions = self.p / sum_p_values  # p_i / sum(p_k)
        entropy_sum = 0.0
        for norm_prop_i in norm_proportions:
            if norm_prop_i > 1e-12:  # only sum for positive proportions
                entropy_sum -= norm_prop_i * self._log2_safe(norm_prop_i)

        log2_n = self._log2_safe(self.n)
        return (
            entropy_sum / log2_n if abs(log2_n) > 1e-12 else 0.0
        )  # If n=1, log2_n=0, D2 is undefined (conventionally 0 or 1)

    def get_roschengren_s_adj(self):
        """Rosengren's S_adj."""
        if self.f < 1e-9:
            return 0.0
        # self.s and self.v are already arrays. np.sqrt handles element-wise.
        sum_sqrt_s_v = np.sum(np.sqrt(self.s * self.v))
        return (sum_sqrt_s_v**2) / self.f

    def get_dp(self):
        """DP (比例偏离度)。
        DP (Deviation of Proportions)."""
        if self.f < 1e-9:
            return 0.0
        observed_proportions = self.v / self.f  # This is P_obs
        # self.s is Q (expected proportions based on part sizes)
        sum_abs_diff = np.sum(np.abs(observed_proportions - self.s))
        return 0.5 * sum_abs_diff

    def get_dp_norm(self):
        """DP_norm (标准化DP)。
        DP_norm (Normalized DP)."""
        dp_val = self.get_dp()
        if self.s.size == 0:
            return None  # Should not happen if n > 0

        min_s = np.min(self.s) if self.s.size > 0 else 0.0
        denominator = 1.0 - min_s

        if (
            abs(denominator) < 1e-9
        ):  # Denominator is effectively zero (e.g., n=1, min_s=1)
            return 0.0 if abs(dp_val) < 1e-9 else 1.0  # If dp_val is also 0, then 0.0.
        return dp_val / denominator

    def get_kl_divergence(self):
        """Kullback-Leibler (KL) 散度 D_KL(P_obs||S)。
        Kullback-Leibler (KL) Divergence D_KL(P_obs||S)."""
        if self.f < 1e-9:
            return 0.0

        kl_sum = 0.0
        observed_probs_p_obs = self.v / self.f  # P_obs
        expected_probs_s = self.s  # S

        for i in range(self.n):
            term = self._kl_term(observed_probs_p_obs[i], expected_probs_s[i])
            if term == float("inf"):
                return float("inf")
            kl_sum += term
        return kl_sum

    def get_jsd_dispersion(self):
        """JSD 分布度 (1 - JSD(P_obs||S))。
        JSD Dispersion, calculated as 1 - JSD(P_obs||S)."""
        if self.f < 1e-9:
            return 0.0  # If f=0, P_obs is all zeros. JSD(0||S) depends on S.
            # If S has non-zero terms, JSD is max (1 for log2). 1-JSD = 0. Correct.

        P_obs = self.v / self.f
        S = self.s
        M = 0.5 * (P_obs + S)

        d_kl_p_m = 0.0
        for i in range(self.n):
            term = self._kl_term(P_obs[i], M[i])
            # If P_obs[i] > 0 and M[i] is 0 (only if S[i] also 0), term is inf.
            if term == float("inf"):
                return 0.0  # Max divergence -> JSD = 1 -> 1-JSD = 0
            d_kl_p_m += term

        d_kl_q_m = 0.0  # Here Q is S
        for i in range(self.n):
            term = self._kl_term(S[i], M[i])
            if term == float("inf"):
                return 0.0  # Max divergence
            d_kl_q_m += term

        jsd_val = 0.5 * (d_kl_p_m + d_kl_q_m)
        jsd_val = max(0.0, min(1.0, jsd_val))  # JSD(P||Q) is in [0,1] for log2
        return 1.0 - jsd_val

    def get_hellinger_dispersion(self):
        """Hellinger 分布度 (1 - H(P_obs,S))。
        Hellinger Dispersion, calculated as 1 - H(P_obs,S)."""
        if self.f < 1e-9:
            return 0.0  # If f=0, P_obs is all zeros. BC=0, H=1, 1-H=0. Correct.

        P_obs = self.v / self.f
        S = self.s

        # Bhattacharyya coefficient: sum(sqrt(P_obs_i * S_i))
        bhattacharyya_coefficient = np.sum(np.sqrt(P_obs * S))

        # Clamp BC to [0,1] to avoid math domain error with sqrt due to precision
        bhattacharyya_coefficient = min(1.0, max(0.0, bhattacharyya_coefficient))

        hellinger_distance = math.sqrt(1.0 - bhattacharyya_coefficient)
        return 1.0 - hellinger_distance

    # --- New methods based on Egbert & Burch (2023) ---
    def get_mean_text_frequency_FT(self):
        """计算平均文本频率 (FT)，即每个文本归一化频率 (p_i) 的平均值。
        Calculates Mean Text Frequency (FT) as the mean of per-text normalized frequencies (p_i)."""
        if self.n == 0:
            return None
        return np.mean(self.p)

    def get_pervasiveness_PT(self):
        """计算普遍度 (PT)，即包含该词的文本所占的比例。
        Calculates Pervasiveness (PT) as the proportion of texts containing the word."""
        if self.n == 0:
            return None
        return self.get_range() / self.n if self.n > 0 else 0.0

    def get_evenness_DA(self):
        """
        计算均匀度 (DA)，依据 Egbert & Burch (2023) / Burch et al. (2016)。
        DA = 1 - (AverageAbsolutePairwiseDifference_of_p_i / (2 * Mean_of_p_i))
        范围 [0,1]: 1 表示完美均匀，0 表示词仅出现在一个文本中 (当 n>1 时)。
        Calculates Evenness (DA) based on Egbert & Burch (2023) / Burch et al. (2016).
        Ranges [0,1]: 1 for perfect evenness, 0 if word in only one text (for n>1).
        """
        if self.f < 1e-9:
            return 0.0  # If word doesn't appear, DA is 0.
        if self.n == 0:
            return None  # Should not happen if __init__ checks v.size
        if self.n == 1:
            return 1.0  # Perfectly even in a single part if present.

        normed_frequencies_p = self.p  # This is the array of p_i values
        mean_normed_frequency_ft = (
            self.get_mean_text_frequency_FT()
        )  # This is mean(p_i)

        # If mean_normed_frequency_ft is (close to) zero:
        # This implies all p_i are (close to) zero.
        # If all p_i are identical (e.g., all 0), DA should be 1 (perfectly even, albeit at zero level).
        # If f > 0 but all p_i are ~0 (e.g., v_i are tiny compared to part_sizes),
        # this indicates extremely low density everywhere.
        if abs(mean_normed_frequency_ft) < 1e-12:
            # Check if all p_i values are effectively the same (i.e., all zero or all some tiny identical value)
            is_all_same_or_zero = np.all(
                np.abs(normed_frequencies_p - mean_normed_frequency_ft) < 1e-12
            )
            return 1.0 if is_all_same_or_zero else 0.0
            # If not all same but mean is zero, implies some p_i > 0 and others < 0 if mean is exactly 0,
            # but p_i >= 0. So this means some p_i are positive and others are zero, making it uneven.
            # Thus, if mean is ~0 and not all p_i are ~0 (which is contradictory unless f=0, handled),
            # it's maximally uneven.

        # Optimization for DA calculation: O(N log N) instead of O(N^2)
        # Sum of absolute differences of all pairs = sum_{i=1 to N} (2i - N - 1) * p_sorted[i]
        # This requires sorting p_i first.
        # For N < ~50-100, the O(N^2) might be acceptable or even faster due to Python overhead.
        # For larger N, O(N log N) is much better.
        # Let's implement the O(N^2) first for clarity, then consider optimization.

        sum_abs_pairwise_diff = 0.0
        num_pairs = 0
        if self.n >= 2:  # Pairwise comparisons only make sense for n >= 2
            # Original O(N^2) calculation:
            for i in range(self.n):
                for j in range(i + 1, self.n):
                    sum_abs_pairwise_diff += abs(
                        normed_frequencies_p[i] - normed_frequencies_p[j]
                    )
                    num_pairs += 1

        if num_pairs == 0:  # This will be true if n < 2.
            # If n=1, DA=1 (handled at start). If n=0, error (handled at start).
            # This path should ideally not be reached if n=0 or n=1.
            return 1.0  # Default to 1 if no pairs (e.g. n=1 was already handled)

        average_abs_pairwise_diff = sum_abs_pairwise_diff / num_pairs

        denominator = 2 * mean_normed_frequency_ft
        # Denominator should not be zero here due to earlier check on mean_normed_frequency_ft
        if (
            abs(denominator) < 1e-12
        ):  # Should be redundant given prior checks, but as a safeguard
            return 1.0 if abs(average_abs_pairwise_diff) < 1e-12 else 0.0

        da_val = 1.0 - (average_abs_pairwise_diff / denominator)

        # DA is defined to be in [0,1]
        return max(0.0, min(1.0, da_val))

    def get_ft_adjusted_by_PT(self):
        """经普遍度调整的频率得分 (FT * PT)。
        Frequency score adjusted for Pervasiveness (FT * PT)."""
        ft = self.get_mean_text_frequency_FT()
        pt = self.get_pervasiveness_PT()
        if ft is None or pt is None:
            return None
        return ft * pt

    def get_ft_adjusted_by_DA(self):
        """经均匀度调整的频率得分 (FT * DA)。
        Frequency score adjusted for Evenness (FT * DA)."""
        ft = self.get_mean_text_frequency_FT()
        da = self.get_evenness_DA()
        if ft is None or da is None:
            return None
        return ft * da

    def calculate_all_metrics(self):
        """计算并返回所有分布指标。
        Calculates and returns all dispersion metrics."""
        return DispersionMetrics(
            range_val=self.get_range(),
            sd_population=self.get_sd_population(),
            vc_population=self.get_vc_population(),
            juilland_d=self.get_juilland_d(),
            carroll_d2=self.get_carroll_d2(),
            roschengren_s_adj=self.get_roschengren_s_adj(),
            dp=self.get_dp(),
            dp_norm=self.get_dp_norm(),
            kl_divergence=self.get_kl_divergence(),
            jsd_dispersion=self.get_jsd_dispersion(),
            hellinger_dispersion=self.get_hellinger_dispersion(),
            mean_text_frequency_FT=self.get_mean_text_frequency_FT(),
            pervasiveness_PT=self.get_pervasiveness_PT(),
            evenness_DA=self.get_evenness_DA(),
            ft_adjusted_by_PT=self.get_ft_adjusted_by_PT(),
            ft_adjusted_by_DA=self.get_ft_adjusted_by_DA(),
        )
