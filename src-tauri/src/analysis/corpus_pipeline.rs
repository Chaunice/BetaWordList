// corpus_pipeline.rs
// 语料批量处理主流程，负责文件读取、NLP分析、停用词过滤、分布指标计算

use std::fs;

use crate::analysis::{nlp::LtpNlp, word_analyzer::CorpusWordAnalyzer, dispersion_metrics::DispersionMetrics};
use tauri::Emitter;

/// 进度事件结构体
#[derive(serde::Serialize, Clone)]
pub struct ProgressEvent {
    pub current: usize,
    pub total: usize,
    pub file: String,
}

/// 处理单个文本文件，返回 (词, 词性) 二元组
fn process_file(
    nlp: &LtpNlp,
    file_path: &str,
) -> Vec<(String, String)> {
    let content = fs::read_to_string(file_path).unwrap_or_default();
    nlp.segment_pos(&content)
}

/// 主流程：批量处理文件，统计词频，计算分布指标
pub fn analyze_corpus(
    nlp: &LtpNlp,
    file_paths: &[String],
    app_handle: Option<&tauri::AppHandle>,
) -> Vec<(String, String, DispersionMetrics)> {
    let mut vocab_map = std::collections::HashMap::<(String, String), Vec<f64>>::new();
    let mut part_sizes = Vec::new();

    // 1. 逐文件分词与统计
    let total_files = file_paths.len();
    for (i, file) in file_paths.iter().enumerate() {
        let word_pos = process_file(nlp, file);
        if let Some(handle) = app_handle {
            let progress = ProgressEvent {
                current: i + 1,
                total: total_files,
                file: file.to_string(),
            };
            handle.emit("progress", progress).ok();
        }
        let mut local_counter = std::collections::HashMap::<(String, String), f64>::new();
        for (w, p) in word_pos {
            *local_counter.entry((w, p)).or_insert(0.0) += 1.0;
        }
        
        // 统计当前文件词频并更新全局词频表
        let idx = part_sizes.len();
        let mut file_sum = 0.0;
        for (k, v) in local_counter.iter() {
            vocab_map.entry(k.clone()).or_insert_with(|| vec![0.0; file_paths.len()])[idx] = *v;
            file_sum += v;
        }
        part_sizes.push(file_sum);
    }

    let total_words: f64 = part_sizes.iter().sum();

    // 2. 计算分布指标
    vocab_map
        .into_iter()
        .map(|((w, p), freq_vec)| {
            let analyzer = CorpusWordAnalyzer::new(freq_vec.clone(), part_sizes.clone(), total_words);
            let metrics = analyzer.calculate_all_metrics();
            (w, p, metrics)
        })
        .collect()
}