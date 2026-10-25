// Landblick - RLP – Desktop-Hülle.
// Zweck:  Startet den lokalen Dienst (Sidecar "landblick-core", Python), wartet auf "LANDBLICK_READY port=N" und öffnet dann ein Fenster
//         auf http://127.0.0.1:N/. Die Oberfläche ist dieselbe wie im Web; gezeichnet wird mit der GPU des System-WebViews
//         (WebView2, WKWebView, WebKitGTK). Beim Beenden wird der Dienst mit beendet.
// Daten:  app_data_dir (z. B. ~/Library/Application Support/de.thorin.landblick, %APPDATA%\de.thorin.landblick, ~/.local/share/de.thorin.landblick).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::Mutex;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::{process::{CommandChild, CommandEvent}, ShellExt};

struct Core(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Core(Mutex::new(None)))
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            // pmtiles liegt als zweites Sidecar neben der Programmdatei
            let exe_dir = std::env::current_exe()?.parent().map(|p| p.to_path_buf()).unwrap_or_default();
            let pm = exe_dir.join(if cfg!(windows) { "pmtiles.exe" } else { "pmtiles" });
            // mitgelieferte Kachelpakete (Relief, Felswände, Hangneigung, Gebäude) und Suchindex: Installer-Ressourcen, nur lesbar
            let pakete = app.path().resource_dir()?.join("pakete");
            let (mut rx, child) = app
                .shell()
                .sidecar("landblick-core")?
                .args(["--data-dir", &data_dir.to_string_lossy(), "--pmtiles", &pm.to_string_lossy(), "--pack-dir", &pakete.to_string_lossy()])
                .spawn()?;
            *app.state::<Core>().0.lock().unwrap() = Some(child);

            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                while let Some(ev) = rx.recv().await {
                    match ev {
                        CommandEvent::Stdout(line) => {
                            let s = String::from_utf8_lossy(&line);
                            if let Some(p) = s.trim().strip_prefix("LANDBLICK_READY port=") {
                                if let Ok(port) = p.trim().parse::<u16>() {
                                    let url = format!("http://127.0.0.1:{port}/");
                                    let _ = WebviewWindowBuilder::new(&handle, "main", WebviewUrl::External(url.parse().unwrap()))
                                        .title("Landblick - RLP")
                                        .inner_size(1360.0, 860.0)
                                        .min_inner_size(900.0, 600.0)
                                        .build();
                                }
                            }
                        }
                        CommandEvent::Stderr(line) => eprintln!("[core] {}", String::from_utf8_lossy(&line).trim_end()),
                        CommandEvent::Terminated(t) => { eprintln!("[core] beendet: {:?}", t.code); handle.exit(1); }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Tauri konnte nicht starten")
        .run(|app, ev| {
            if let tauri::RunEvent::Exit = ev {
                if let Some(c) = app.state::<Core>().0.lock().unwrap().take() { let _ = c.kill(); }
            }
        });
}
