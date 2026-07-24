use tauri::Manager;
use std::io::Write;

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! May is ready.", name)
}

/// Check if --minimized was passed (used by autostart to start hidden)
fn started_from_autostart() -> bool {
    std::env::args().any(|a| a == "--minimized")
}

/// Backend sidecar PID for cleanup on app exit.
static SIDECAR_PID: std::sync::OnceLock<u32> = std::sync::OnceLock::new();

#[tauri::command]
async fn start_backend(app: tauri::AppHandle) -> Result<String, String> {
    #[cfg(not(debug_assertions))]
    use tauri_plugin_shell::ShellExt;
    let _ = &app; // Suppress unused variable warning in debug cfg branch

    // In release mode, use the bundled sidecar binary
    #[cfg(not(debug_assertions))]
    {
        // Log to file for debugging (release mode has no console)
        let log_path = std::env::var("LOCALAPPDATA")
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|_| std::env::temp_dir())
            .join("May")
            .join("sidecar.log");
        let _ = std::fs::create_dir_all(log_path.parent().unwrap());
        let mut log_file = std::fs::OpenOptions::new()
            .create(true).append(true)
            .open(&log_path)
            .ok();

        if let Some(ref mut f) = log_file {
            let _ = writeln!(f, "\n=== start_backend called at {:?} ===", std::time::Instant::now());
            let _ = writeln!(f, "Log path: {:?}", log_path);
        }

        let sidecar_command = match app.shell().sidecar("may-backend") {
            Ok(cmd) => {
                if let Some(ref mut f) = log_file {
                    let _ = writeln!(f, "Sidecar command created successfully");
                }
                cmd
            }
            Err(e) => {
                let msg = format!("Failed to create sidecar command: {}", e);
                if let Some(ref mut f) = log_file {
                    let _ = writeln!(f, "ERROR: {}", msg);
                }
                return Err(msg);
            }
        };

        let (mut rx, child) = match sidecar_command.spawn() {
            Ok(result) => {
                if let Some(ref mut f) = log_file {
                    let _ = writeln!(f, "Sidecar spawned with PID: {}", result.1.pid());
                }
                result
            }
            Err(e) => {
                let msg = format!("Failed to spawn sidecar: {}", e);
                if let Some(ref mut f) = log_file {
                    let _ = writeln!(f, "ERROR: {}", msg);
                }
                return Err(msg);
            }
        };

        // Store PID for cleanup on exit
        let _ = SIDECAR_PID.set(child.pid());

        // Wait for backend to be ready (up to 30 seconds) in background thread
        tauri::async_runtime::spawn_blocking(move || {
            for _ in 0..60 {
                if std::net::TcpStream::connect("127.0.0.1:8080").is_ok() {
                    let _ = writeln!(std::io::stderr(), "Backend sidecar ready on port 8080");
                    return;
                }
                std::thread::sleep(std::time::Duration::from_millis(500));
            }
            let _ = writeln!(std::io::stderr(), "Warning: Backend did not become ready within 30s");
        });

        // Handle sidecar stdout/stderr output — log to file
        tauri::async_runtime::spawn(async move {
            use tauri_plugin_shell::process::CommandEvent;
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line) => {
                        let text = String::from_utf8_lossy(&line);
                        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
                            let _ = writeln!(f, "[stdout] {}", text);
                        }
                    }
                    CommandEvent::Stderr(line) => {
                        let text = String::from_utf8_lossy(&line);
                        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
                            let _ = writeln!(f, "[stderr] {}", text);
                        }
                    }
                    CommandEvent::Terminated(status) => {
                        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&log_path) {
                            let _ = writeln!(f, "[terminated] status: {:?}", status);
                        }
                        break;
                    }
                    _ => {}
                }
            }
        });

        Ok("Backend sidecar started".to_string())
    }

    // In debug mode, launch Python directly
    #[cfg(debug_assertions)]
    {
        let backend_path = std::path::PathBuf::from("../backend");
        let main_py = backend_path.join("main.py");

        if !main_py.exists() {
            return Err(format!("Backend not found at {:?}", backend_path));
        }

        #[cfg(target_os = "windows")]
        let child = {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            std::process::Command::new("python")
                .arg(main_py.to_str().unwrap_or_default())
                .current_dir(&backend_path)
                .creation_flags(CREATE_NO_WINDOW)
                .spawn()
                .map_err(|e| e.to_string())?
        };

        #[cfg(not(target_os = "windows"))]
        let child = std::process::Command::new("python3")
            .arg(main_py.to_str().unwrap_or_default())
            .current_dir(&backend_path)
            .spawn()
            .map_err(|e| e.to_string())?;

        // Store PID for cleanup
        let _ = SIDECAR_PID.set(child.id());

        Ok(format!("Backend started (dev mode, PID: {})", child.id()))
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--minimized"]),
        ))
        .setup(move |app| {
            // ── System Tray ──────────────────────────────────────────────────
            use tauri::menu::{MenuBuilder, MenuItemBuilder};

            let show_item = MenuItemBuilder::with_id("show", "Open May")
                .build(app)?;
            let autostart_item = MenuItemBuilder::with_id("toggle_autostart", "Start at Login")
                .build(app)?;
            let quit_item = MenuItemBuilder::with_id("quit", "Quit May")
                .build(app)?;

            let menu = MenuBuilder::new(app)
                .item(&show_item)
                .separator()
                .item(&autostart_item)
                .separator()
                .item(&quit_item)
                .build()?;

            // ── Set initial autostart menu state (before closure moves autostart_item) ──
            {
                use tauri_plugin_autostart::ManagerExt;
                if let Ok(enabled) = app.autolaunch().is_enabled() {
                    let label = if enabled {
                        "Stop at Login"
                    } else {
                        "Start at Login"
                    };
                    let _ = autostart_item.set_text(label);
                }
            }

            // ── Start hidden if launched from autostart ──────────────────────────
            if started_from_autostart() {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }

            let tray_icon = app.default_window_icon()
                .cloned()
                .expect("No default window icon found");

            let _tray = tauri::tray::TrayIconBuilder::new()
                .icon(tray_icon)
                .menu(&menu)
                .tooltip("May — Your AI Companion")
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {
                        "show" => {
                            if let Some(window) = app.get_webview_window("main") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        "toggle_autostart" => {
                            use tauri_plugin_autostart::ManagerExt;
                            let autostart = app.autolaunch();
                            match autostart.is_enabled() {
                                Ok(enabled) => {
                                    let _ = if enabled {
                                        autostart.disable()
                                    } else {
                                        autostart.enable()
                                    };
                                    let new_label = if enabled {
                                        "Start at Login"
                                    } else {
                                        "Stop at Login"
                                    };
                                    let _ = autostart_item.set_text(new_label);
                                }
                                Err(e) => {
                                    eprintln!("Failed to toggle autostart: {}", e);
                                }
                            }
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    }
                    | tauri::tray::TrayIconEvent::DoubleClick {
                        button: tauri::tray::MouseButton::Left,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            // ── Minimize to tray on window close ──────────────────────────────
            if let Some(window) = app.get_webview_window("main") {
                let w = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        let _ = w.hide();
                        api.prevent_close();
                    }
                    if let tauri::WindowEvent::Destroyed = event {
                        // Kill the sidecar/backend process when the app exits
                        if let Some(&pid) = SIDECAR_PID.get() {
                            #[cfg(target_os = "windows")]
                            let _ = std::process::Command::new("taskkill")
                                .args(["/F", "/PID", &pid.to_string()])
                                .output();
                            #[cfg(not(target_os = "windows"))]
                            let _ = std::process::Command::new("kill")
                                .args(["-9", &pid.to_string()])
                                .output();
                        }
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, start_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
