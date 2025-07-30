// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod analysis;
use std::env::current_exe;
use std::path::PathBuf;

use std::sync::{Arc, Mutex};
use tauri::{State, AppHandle};
use analysis::{nlp::LtpNlp, corpus_pipeline};

/// 应用状态
struct AppState {
    nlp: Arc<Mutex<Option<LtpNlp>>>,
}

/// 启动分析任务
#[tauri::command]
async fn start_analysis(
    app_handle: AppHandle,
    state: State<'_, AppState>,
    file_paths: Vec<String>,
) -> Result<Vec<(String, String, analysis::dispersion_metrics::DispersionMetrics)>, String> {
    let nlp_guard = state.nlp.lock().unwrap();
    let nlp = nlp_guard.as_ref().ok_or("NLP模型未加载")?;

    Ok(corpus_pipeline::analyze_corpus(
        nlp,
        &file_paths,
        Some(&app_handle),
    ))
}

/// 加载NLP模型
#[tauri::command]
async fn load_models(
    state: State<'_, AppState>,
    cws_path: String,
    pos_path: String,
) -> Result<(), String> {
    // 自动适配多平台模型路径
    let cws = get_model_path(&cws_path).to_string_lossy().to_string();
    let pos = get_model_path(&pos_path).to_string_lossy().to_string();
    let nlp = LtpNlp::load(&cws, &pos)
        .map_err(|e| format!("模型加载失败: {e}"))?;
    *state.nlp.lock().unwrap() = Some(nlp);
    Ok(())
}

/// 获取跨平台模型路径
fn get_model_path(filename: &str) -> PathBuf {
    // 优先查找exe同级/legacy目录（打包后）和开发时legacy目录
    let exe_dir = current_exe().ok().and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let resource = exe_dir.map(|mut p| { p.push("legacy"); p.push(filename); p });
    let dev = {
        let mut p = std::env::current_dir().unwrap();
        p.push("legacy");
        p.push(filename);
        p
    };
    // 使用标准输出，便于在Tauri dev模式下查看
    println!("尝试模型路径: ");
    if let Some(ref r) = resource {
        println!("  exe/legacy: {}", r.display());
        if r.exists() {
            return r.clone();
        }
    }
    println!("  dev/legacy: {}", dev.display());
    if dev.exists() {
        return dev;
    }
    println!("  fallback: {filename}");
    // fallback: just filename
    PathBuf::from(filename)
}


fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AppState {
            nlp: Arc::new(Mutex::new(None)),
        })
        .invoke_handler(tauri::generate_handler![
            start_analysis,
            load_models,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
