// word_analyzer.rs
// 单词/词性分布指标计算核心，参考 word_analyzer_ref.rs 进行全面实现与注释

use crate::analysis::dispersion_metrics::DispersionMetrics;
use std::f64::consts::LN_2;

/// 语料库单词分布指标分析器
pub struct CorpusWordAnalyzer {
    pub v: Vec<f64>,
    n: usize,
    f: f64,
    s: Vec<f64>,
    p: Vec<f64>,
}

impl CorpusWordAnalyzer {
    /// 构造函数，预计算 s（各部分占比）和 p（各部分归一化频率）
    pub fn new(v: Vec<f64>, corpus_part_sizes_words: Vec<f64>, total_corpus_words: f64) -> Self {
        let n = v.len();
        let f = v.iter().sum();
        let s: Vec<f64> = corpus_part_sizes_words
            .iter()
            .map(|&size| {
                if total_corpus_words > 0.0 {
                    size / total_corpus_words
                } else {
                    0.0
                }
            })
            .collect();
        let p: Vec<f64> = v
            .iter()
            .zip(corpus_part_sizes_words.iter())
            .map(|(&freq, &size)| if size > 0.0 { freq / size } else { 0.0 })
            .collect();
        Self { v, n, f, s, p }
    }

    /// 范围：出现次数大于0的文本部分数量
    pub fn get_range(&self) -> usize {
        self.v.iter().filter(|&&x| x > 1e-9).count()
    }

    /// 频次总体标准差
    pub fn get_sd_population(&self) -> Option<f64> {
        if self.n == 0 {
            return None;
        }
        if self.f == 0.0 {
            return Some(0.0);
        }
        let mean_v = self.f / self.n as f64;
        let variance = self.v.iter().map(|&x| (x - mean_v).powi(2)).sum::<f64>() / self.n as f64;
        Some(variance.sqrt())
    }

    /// 频次总体变异系数
    pub fn get_vc_population(&self) -> Option<f64> {
        let mean_v = self.f / self.n as f64;
        if mean_v.abs() < 1e-12 {
            return Some(0.0);
        }
        self.get_sd_population().map(|sd| sd / mean_v)
    }

    /// Juilland's D
    pub fn get_juilland_d(&self) -> Option<f64> {
        if self.n <= 1 {
            return Some(if self.f > 0.0 { 1.0 } else { 0.0 });
        }
        if self.f == 0.0 {
            return Some(0.0);
        }
        let mean_p = self.p.iter().sum::<f64>() / self.n as f64;
        if mean_p.abs() < 1e-12 {
            return Some(0.0);
        }
        let variance_p = self.p.iter().map(|&x| (x - mean_p).powi(2)).sum::<f64>() / self.n as f64;
        let sd_p = variance_p.sqrt();
        let vc_p = sd_p / mean_p;
        Some(1.0 - vc_p / ((self.n - 1) as f64).sqrt())
    }

    /// Carroll's D2（基于熵）
    pub fn get_carroll_d2(&self) -> Option<f64> {
        if self.n <= 1 {
            return Some(if self.f > 0.0 { 1.0 } else { 0.0 });
        }
        let sum_p = self.p.iter().sum::<f64>();
        if sum_p.abs() < 1e-12 {
            return Some(0.0);
        }
        let entropy = self
            .p
            .iter()
            .map(|&p_i| {
                let norm_prop = p_i / sum_p;
                if norm_prop > 1e-12 {
                    -norm_prop * norm_prop.ln()
                } else {
                    0.0
                }
            })
            .sum::<f64>();
        let log2_n = (self.n as f64).ln() / LN_2;
        Some(entropy / (log2_n * LN_2))
    }

    /// Roschengren's S_adj
    pub fn get_roschengren_s_adj(&self) -> Option<f64> {
        if self.f == 0.0 {
            return Some(0.0);
        }
        let sum_sqrt = self
            .s
            .iter()
            .zip(self.v.iter())
            .map(|(&s_i, &v_i)| (s_i * v_i).sqrt())
            .sum::<f64>();
        Some((sum_sqrt * sum_sqrt) / self.f)
    }

    /// DP（比例偏离度）
    pub fn get_dp(&self) -> Option<f64> {
        if self.f == 0.0 {
            return Some(0.0);
        }
        let sum_abs_diff = self
            .v
            .iter()
            .zip(self.s.iter())
            .map(|(&v_i, &s_i)| (v_i / self.f - s_i).abs())
            .sum::<f64>();
        Some(0.5 * sum_abs_diff)
    }

    /// DP_norm（标准化DP）
    pub fn get_dp_norm(&self) -> Option<f64> {
        let dp = self.get_dp()?;
        let min_s = self.s.iter().cloned().fold(f64::INFINITY, f64::min);
        let denom = 1.0 - min_s;
        if denom.abs() < 1e-12 {
            return Some(0.0);
        }
        Some(dp / denom)
    }

    /// KL 散度
    pub fn get_kl_divergence(&self) -> Option<f64> {
        if self.f == 0.0 {
            return Some(0.0);
        }
        let mut kl = 0.0;
        for (&v_i, &s_i) in self.v.iter().zip(self.s.iter()) {
            let p = if self.f > 0.0 { v_i / self.f } else { 0.0 };
            let q = s_i;
            if p > 0.0 && q > 0.0 {
                kl += p * (p / q).ln() / LN_2;
            }
        }
        Some(kl)
    }

    /// JSD 分布度
    pub fn get_jsd_dispersion(&self) -> Option<f64> {
        if self.f == 0.0 {
            return Some(0.0);
        }
        let p_dist: Vec<f64> = self.v.iter().map(|&v_i| v_i / self.f).collect();
        let q_dist: &Vec<f64> = &self.s;
        let m_dist: Vec<f64> = p_dist
            .iter()
            .zip(q_dist.iter())
            .map(|(&p, &q)| 0.5 * (p + q))
            .collect();
        let mut kl_pm: f64 = 0.0;
        let mut kl_qm: f64 = 0.0;
        for i in 0..self.n {
            let p = p_dist[i];
            let q = q_dist[i];
            let m = m_dist[i];
            if p > 1e-12 && m > 1e-12 {
                kl_pm += p * (p / m).ln();
            }
            if q > 1e-12 && m > 1e-12 {
                kl_qm += q * (q / m).ln();
            }
        }
        let jsd = 0.5 * (kl_pm + kl_qm);
        Some(1.0 - (jsd / LN_2).min(1.0))
    }

    /// Hellinger 分布度
    pub fn get_hellinger_dispersion(&self) -> Option<f64> {
        if self.f == 0.0 {
            return Some(0.0);
        }
        let p_dist: Vec<f64> = self.v.iter().map(|&v_i| v_i / self.f).collect();
        let q_dist: &Vec<f64> = &self.s;
        let mut bc: f64 = 0.0;
        for i in 0..self.n {
            bc += (p_dist[i] * q_dist[i]).sqrt();
        }
        let bc = bc.clamp(0.0, 1.0);
        let hellinger_distance = (1.0 - bc).sqrt();
        Some(1.0 - hellinger_distance)
    }

    /// 均匀度（Evenness DA）
    pub fn get_evenness_da(&self) -> Option<f64> {
        if self.n == 0 {
            return None;
        }
        if self.f == 0.0 {
            return Some(0.0);
        }
        if self.n == 1 {
            return Some(1.0);
        }
        let mean_p = self.p.iter().sum::<f64>() / self.n as f64;
        if mean_p.abs() < 1e-12 {
            let all_same = self.p.iter().all(|&p| (p - mean_p).abs() < 1e-12);
            return Some(if all_same { 1.0 } else { 0.0 });
        }
        let mut sum_abs_diff = 0.0;
        for i in 0..self.n {
            for j in (i + 1)..self.n {
                sum_abs_diff += (self.p[i] - self.p[j]).abs();
            }
        }
        let num_pairs = (self.n * (self.n - 1)) / 2;
        if num_pairs == 0 {
            return Some(1.0);
        }
        let avg_abs_diff = sum_abs_diff / num_pairs as f64;
        let da = 1.0 - (avg_abs_diff / (2.0 * mean_p));
        Some(da.clamp(0.0, 1.0))
    }

    /// 平均文本频率（FT）
    pub fn get_mean_text_frequency_ft(&self) -> Option<f64> {
        if self.n == 0 {
            return None;
        }
        Some(self.p.iter().sum::<f64>() / self.n as f64)
    }

    /// 普遍度（PT）
    pub fn get_pervasiveness_pt(&self) -> Option<f64> {
        if self.n == 0 {
            return None;
        }
        Some(self.get_range() as f64 / self.n as f64)
    }

    /// 计算所有分布指标，返回 DispersionMetrics 结构体
    pub fn calculate_all_metrics(&self) -> DispersionMetrics {
        let ft = self.get_mean_text_frequency_ft();
        let pt = self.get_pervasiveness_pt();
        let da = self.get_evenness_da();
        DispersionMetrics {
            range: self.get_range(),
            sd_population: self.get_sd_population(),
            vc_population: self.get_vc_population(),
            juilland_d: self.get_juilland_d(),
            carroll_d2: self.get_carroll_d2(),
            roschengren_s_adj: self.get_roschengren_s_adj(),
            dp: self.get_dp(),
            dp_norm: self.get_dp_norm(),
            kl_divergence: self.get_kl_divergence(),
            jsd_dispersion: self.get_jsd_dispersion(),
            hellinger_dispersion: self.get_hellinger_dispersion(),
            mean_text_frequency_ft: ft,
            pervasiveness_pt: pt,
            evenness_da: da,
            ft_adjusted_by_pt: match (ft, pt) {
                (Some(f), Some(p)) => Some(f * p),
                _ => None,
            },
            ft_adjusted_by_da: match (ft, da) {
                (Some(f), Some(d)) => Some(f * d),
                _ => None,
            },
        }
    }
}
