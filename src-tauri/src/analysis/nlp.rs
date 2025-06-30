// nlp.rs
// 中文分词、词性标注、命名实体识别模块，基于 ltp-rs

use std::fs::File;
use ltp::{CWSModel, POSModel, ModelSerde, Format, Codec};

/// NLP模型结构体，包含分词、词性、实体模型
pub struct LtpNlp {
    pub cws: CWSModel,
    pub pos: POSModel,
}

impl LtpNlp {
    /// 加载模型
    pub fn load(cws_path: &str, pos_path: &str) -> Result<Self, Box<dyn std::error::Error>> {
        let cws_file = File::open(cws_path)?;
        let cws = ModelSerde::load(cws_file, Format::AVRO(Codec::Deflate))?;
        let pos_file = File::open(pos_path)?;
        let pos = ModelSerde::load(pos_file, Format::AVRO(Codec::Deflate))?;
        Ok(Self { cws, pos })
    }

    /// 仅分词与词性标注，返回 (词, 词性) 二元组
    pub fn segment_pos(&self, text: &str) -> Vec<(String, String)> {
        let words = self.cws.predict(text).unwrap_or_default();
        let pos = self.pos.predict(&words).unwrap_or_default();
        words.into_iter()
            .zip(pos.into_iter())
            .map(|(w, p)| (w.to_string(), p.to_string()))
            .collect()
    }
}