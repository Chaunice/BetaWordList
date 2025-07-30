// dispersion_metrics.rs
// 分布指标数据结构，移植自 dispersion_metrics_models.py

use serde::{Serialize, Deserialize};

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct DispersionMetrics {
    pub range: usize,
    pub sd_population: Option<f64>,
    pub vc_population: Option<f64>,
    pub juilland_d: Option<f64>,
    pub carroll_d2: Option<f64>,
    pub roschengren_s_adj: Option<f64>,
    pub dp: Option<f64>,
    pub dp_norm: Option<f64>,
    pub kl_divergence: Option<f64>,
    pub jsd_dispersion: Option<f64>,
    pub hellinger_dispersion: Option<f64>,
    pub mean_text_frequency_ft: Option<f64>,
    pub pervasiveness_pt: Option<f64>,
    pub evenness_da: Option<f64>,
    pub ft_adjusted_by_pt: Option<f64>,
    pub ft_adjusted_by_da: Option<f64>,
}

impl std::fmt::Display for DispersionMetrics {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "DispersionMetrics {{")?;
        writeln!(f, "  range: {},", self.range)?;
        writeln!(f, "  sd_population: {:?},", self.sd_population)?;
        writeln!(f, "  vc_population: {:?},", self.vc_population)?;
        writeln!(f, "  juilland_d: {:?},", self.juilland_d)?;
        writeln!(f, "  carroll_d2: {:?},", self.carroll_d2)?;
        writeln!(f, "  roschengren_s_adj: {:?},", self.roschengren_s_adj)?;
        writeln!(f, "  dp: {:?},", self.dp)?;
        writeln!(f, "  dp_norm: {:?},", self.dp_norm)?;
        writeln!(f, "  kl_divergence: {:?},", self.kl_divergence)?;
        writeln!(f, "  jsd_dispersion: {:?},", self.jsd_dispersion)?;
        writeln!(f, "  hellinger_dispersion: {:?},", self.hellinger_dispersion)?;
        writeln!(f, "  mean_text_frequency_ft: {:?},", self.mean_text_frequency_ft)?;
        writeln!(f, "  pervasiveness_pt: {:?},", self.pervasiveness_pt)?;
        writeln!(f, "  evenness_da: {:?},", self.evenness_da)?;
        writeln!(f, "  ft_adjusted_by_pt: {:?},", self.ft_adjusted_by_pt)?;
        writeln!(f, "  ft_adjusted_by_da: {:?}", self.ft_adjusted_by_da)?;
        write!(f, "}}")
    }
}