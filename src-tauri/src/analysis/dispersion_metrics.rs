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
        write!(f, "DispersionMetrics {{\n")?;
        write!(f, "  range: {},\n", self.range)?;
        write!(f, "  sd_population: {:?},\n", self.sd_population)?;
        write!(f, "  vc_population: {:?},\n", self.vc_population)?;
        write!(f, "  juilland_d: {:?},\n", self.juilland_d)?;
        write!(f, "  carroll_d2: {:?},\n", self.carroll_d2)?;
        write!(f, "  roschengren_s_adj: {:?},\n", self.roschengren_s_adj)?;
        write!(f, "  dp: {:?},\n", self.dp)?;
        write!(f, "  dp_norm: {:?},\n", self.dp_norm)?;
        write!(f, "  kl_divergence: {:?},\n", self.kl_divergence)?;
        write!(f, "  jsd_dispersion: {:?},\n", self.jsd_dispersion)?;
        write!(f, "  hellinger_dispersion: {:?},\n", self.hellinger_dispersion)?;
        write!(f, "  mean_text_frequency_ft: {:?},\n", self.mean_text_frequency_ft)?;
        write!(f, "  pervasiveness_pt: {:?},\n", self.pervasiveness_pt)?;
        write!(f, "  evenness_da: {:?},\n", self.evenness_da)?;
        write!(f, "  ft_adjusted_by_pt: {:?},\n", self.ft_adjusted_by_pt)?;
        write!(f, "  ft_adjusted_by_da: {:?}\n", self.ft_adjusted_by_da)?;
        write!(f, "}}")
    }
}