# dispersion_metrics_models.py
# Contains the data class for storing dispersion metrics.

import math # Used in __repr__ via format_value if a metric can be NaN/inf
import numpy as np # Potentially for type hints if used, though not strictly necessary here

class DispersionMetrics:
    """
    存储所有计算出的分布指标的简单类。
    A simple class to hold all calculated dispersion metrics.
    """
    def __init__(
        self,
        range_val=0,
        sd_population=None,
        vc_population=None,
        juilland_d=None,
        carroll_d2=None,
        roschengren_s_adj=None,
        dp=None,
        dp_norm=None,
        kl_divergence=None,
        jsd_dispersion=None,
        hellinger_dispersion=None,
        mean_text_frequency_FT=None,
        pervasiveness_PT=None,
        evenness_DA=None,
        ft_adjusted_by_PT=None,
        ft_adjusted_by_DA=None,
    ):
        # Basic metrics
        self.range = range_val
        self.sd_population = sd_population
        self.vc_population = vc_population
        
        # Gries & other established metrics
        self.juilland_d = juilland_d
        self.carroll_d2 = carroll_d2
        self.roschengren_s_adj = roschengren_s_adj
        self.dp = dp
        self.dp_norm = dp_norm
        self.kl_divergence = kl_divergence
        self.jsd_dispersion = jsd_dispersion
        self.hellinger_dispersion = hellinger_dispersion
        
        # Egbert & Burch (2023) framework metrics
        self.mean_text_frequency_FT = mean_text_frequency_FT
        self.pervasiveness_PT = pervasiveness_PT
        self.evenness_DA = evenness_DA
        self.ft_adjusted_by_PT = ft_adjusted_by_PT
        self.ft_adjusted_by_DA = ft_adjusted_by_DA

    def __repr__(self):
        def format_value(val):
            if val is None:
                return "None"
            if isinstance(val, (int, float)):
                if math.isinf(val) or math.isnan(val):
                    return str(val)
                return f"{val:.4f}" # Increased precision for better detail
            return str(val)

        return (
            f"DispersionMetrics(\n"
            f"  范围 (Range)={self.range},\n"
            f"  频次总体标准差 (SD Population)={format_value(self.sd_population)},\n"
            f"  频次总体变异系数 (VC Population)={format_value(self.vc_population)},\n"
            f"  Juilland's D={format_value(self.juilland_d)},\n"
            f"  Carroll's D2={format_value(self.carroll_d2)},\n"
            f"  Rosengren's S_adj={format_value(self.roschengren_s_adj)},\n"
            f"  DP (比例偏离度)={format_value(self.dp)},\n"
            f"  DP_norm (标准化DP)={format_value(self.dp_norm)},\n"
            f"  KL 散度 (KL Divergence)={format_value(self.kl_divergence)},\n"
            f"  JSD 分布度 (JSD Dispersion)={format_value(self.jsd_dispersion)},\n"
            f"  Hellinger 分布度 (Hellinger Dispersion)={format_value(self.hellinger_dispersion)},\n"
            f"  --- Egbert & Burch (2023) Framework ---\n"
            f"  平均文本频率 (Mean Text Freq FT)={format_value(self.mean_text_frequency_FT)},\n"
            f"  普遍度 (Pervasiveness PT)={format_value(self.pervasiveness_PT)},\n"
            f"  均匀度 (Evenness DA)={format_value(self.evenness_DA)},\n"
            f"  FT (经PT调整)={format_value(self.ft_adjusted_by_PT)},\n"
            f"  FT (经DA调整)={format_value(self.ft_adjusted_by_DA)}\n)"
        )
