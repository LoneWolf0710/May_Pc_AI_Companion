use tauri::Manager;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! May is ready.", name)
}

#[tauri::command]
async fn start_backend(app: tauri::AppHandle) -> Result<String, String> {
    let resource_path = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("backend");

    #[cfg(debug_assertions)]
    let backend_path = std::path::PathBuf::from("../backend");

    #[cfg(not(debug_assertions))]
    let backend_path = resource_path;

    let main_py = backend_path.join("main.py");

    if !main_py.exists() {
        return Err(format!("Backend not found at {:?}", backend_path));
    }

    #[cfg(target_os = "windows")]
    std::process::Command::new("python")
        .arg(main_py.to_str().unwrap_or_default())
        .current_dir(&backend_path)
        .spawn()
        .map_err(|e| e.to_string())?;

    #[cfg(not(target_os = "windows"))]
    std::process::Command::new("python3")
        .arg(main_py.to_str().unwrap_or_default())
        .current_dir(&backend_path)
        .spawn()
        .map_err(|e| e.to_string())?;

    Ok("Backend started".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![greet, start_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
