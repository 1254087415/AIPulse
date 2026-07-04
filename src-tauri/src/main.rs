// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use anyhow::Result;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() > 1 && args[1] == "--native-messaging" {
        if let Err(error) = run_native_messaging_host() {
            eprintln!("native messaging host failed: {error:#}");
            std::process::exit(1);
        }
        return;
    }

    app_lib::run();
}

fn run_native_messaging_host() -> Result<()> {
    tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()?
        .block_on(app_lib::native_messaging::run_native_messaging_loop())
}
