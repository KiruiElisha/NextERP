//! Local ERPNext in Docker: status, first-run setup, and start of the compose stack
//! shipped with the app (ERPNext v16 + nexterp).

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use nexterp_core::Error;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};

type Result<T> = std::result::Result<T, Error>;

const PROJECT: &str = "nexterp-local";
const LOCAL_URL: &str = "http://localhost:8000";
const DEFAULT_ADMIN_PASSWORD: &str = "admin";
const ERPNEXT_VERSION: &str = "v16.54.0";

fn err(msg: impl Into<String>) -> Error {
    Error::Server(msg.into())
}

fn docker_available() -> bool {
    Command::new("docker")
        .args(["info"])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn work_dir(app: &AppHandle) -> Result<PathBuf> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|e| err(e.to_string()))?
        .join("local-erpnext");
    fs::create_dir_all(&dir).map_err(|e| err(e.to_string()))?;
    Ok(dir)
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn find_file(app: &AppHandle, candidates: &[PathBuf]) -> Option<PathBuf> {
    for p in candidates {
        if p.exists() {
            return Some(p.clone());
        }
    }
    if let Ok(res) = app.path().resource_dir() {
        for p in candidates {
            let name = p.file_name()?.to_string_lossy();
            for c in [
                res.join(&*name),
                res.join("docker").join(&*name),
                res.join("_up_").join("docker").join(&*name),
                res.join("_up_").join("NextERP").join("docker").join(&*name),
            ] {
                if c.exists() {
                    return Some(c);
                }
            }
        }
    }
    None
}

fn find_nexterp(app: &AppHandle) -> Result<PathBuf> {
    let root = repo_root();
    let mut candidates = vec![root.join("nexterp")];
    if let Ok(res) = app.path().resource_dir() {
        candidates.extend([
            res.join("nexterp"),
            res.join("_up_").join("nexterp"),
            res.join("_up_").join("NextERP").join("nexterp"),
        ]);
    }
    candidates
        .into_iter()
        .find(|p| p.join("hooks.py").exists())
        .ok_or_else(|| err("nexterp app not found next to the install"))
}

fn copy_dir(from: &Path, to: &Path) -> Result<()> {
    fs::create_dir_all(to).map_err(|e| err(e.to_string()))?;
    for entry in fs::read_dir(from).map_err(|e| err(e.to_string()))? {
        let entry = entry.map_err(|e| err(e.to_string()))?;
        let ty = entry.file_type().map_err(|e| err(e.to_string()))?;
        let dest = to.join(entry.file_name());
        if ty.is_dir() {
            copy_dir(&entry.path(), &dest)?;
        } else if ty.is_file() {
            if let Some(parent) = dest.parent() {
                fs::create_dir_all(parent).map_err(|e| err(e.to_string()))?;
            }
            fs::copy(entry.path(), &dest).map_err(|e| err(e.to_string()))?;
        }
    }
    Ok(())
}

/// Place compose files and the nexterp app under app data so Docker can mount them.
fn ensure_workspace(app: &AppHandle) -> Result<PathBuf> {
    let dir = work_dir(app)?;
    let root = repo_root();
    let compose_src = find_file(
        app,
        &[
            root.join("docker/docker-compose.yml"),
            PathBuf::from("docker-compose.yml"),
        ],
    )
    .ok_or_else(|| err("docker-compose.yml not found"))?;

    fs::copy(&compose_src, dir.join("docker-compose.yml")).map_err(|e| err(e.to_string()))?;

    let nexterp_src = find_nexterp(app)?;
    let nexterp_dest = dir.join("apps").join("nexterp");
    if !nexterp_dest.join("hooks.py").exists() {
        copy_dir(&nexterp_src, &nexterp_dest)?;
    }

    let nexterp_path = nexterp_dest
        .canonicalize()
        .unwrap_or_else(|_| nexterp_dest.clone())
        .to_string_lossy()
        .replace('\\', "/");

    let env = format!(
        "HTTP_PORT=8000\n\
         MYSQL_ROOT_PASSWORD={pw}\n\
         ADMIN_PASSWORD={pw}\n\
         SITE_NAME=localhost\n\
         ERPNEXT_VERSION={ver}\n\
         NEXTERP_APP_PATH={app}\n",
        pw = DEFAULT_ADMIN_PASSWORD,
        ver = ERPNEXT_VERSION,
        app = nexterp_path,
    );
    fs::write(dir.join(".env"), env).map_err(|e| err(e.to_string()))?;
    Ok(dir)
}

fn compose(dir: &Path, args: &[&str]) -> Result<std::process::Output> {
    Command::new("docker")
        .arg("compose")
        .arg("-p")
        .arg(PROJECT)
        .arg("-f")
        .arg("docker-compose.yml")
        .args(args)
        .current_dir(dir)
        .output()
        .map_err(|e| {
            err(format!(
                "Could not run Docker Compose ({e}). Install Docker Desktop and try again."
            ))
        })
}

fn emit(app: &AppHandle, step: &str, detail: &str) {
    let _ = app.emit("local-docker", json!({ "step": step, "detail": detail }));
}

fn site_reachable() -> bool {
    std::net::TcpStream::connect_timeout(
        &"127.0.0.1:8000".parse().unwrap(),
        std::time::Duration::from_millis(800),
    )
    .is_ok()
}

fn site_exists(dir: &Path) -> bool {
    compose(
        dir,
        &[
            "exec",
            "-T",
            "backend",
            "test",
            "-f",
            "sites/localhost/site_config.json",
        ],
    )
    .map(|o| o.status.success())
    .unwrap_or(false)
}

/// Docker presence, stack state, and whether the local site answers.
#[tauri::command]
pub fn local_docker_status(app: AppHandle) -> Result<Value> {
    let docker = docker_available();
    let dir = work_dir(&app).ok();
    let prepared = dir
        .as_ref()
        .map(|d| d.join("docker-compose.yml").exists())
        .unwrap_or(false);
    let running = docker
        && dir
            .as_ref()
            .map(|d| {
                compose(d, &["ps", "-q", "frontend"])
                    .map(|o| o.status.success() && !o.stdout.is_empty())
                    .unwrap_or(false)
            })
            .unwrap_or(false);
    Ok(json!({
        "docker": docker,
        "prepared": prepared,
        "running": running,
        "reachable": site_reachable(),
        "url": LOCAL_URL,
        "user": "Administrator",
        "password": DEFAULT_ADMIN_PASSWORD,
        "version": ERPNEXT_VERSION,
    }))
}

/// Pull images, start the stack, create the site and install nexterp. Emits `local-docker` progress.
#[tauri::command]
pub async fn local_docker_setup(app: AppHandle) -> Result<Value> {
    if !docker_available() {
        return Err(err(
            "Docker is not available. Install Docker Desktop, start it, then try again.",
        ));
    }
    let app2 = app.clone();
    tauri::async_runtime::spawn_blocking(move || setup_blocking(&app2))
        .await
        .map_err(|e| err(e.to_string()))?
}

fn setup_blocking(app: &AppHandle) -> Result<Value> {
    emit(app, "prepare", "Preparing local ERPNext files…");
    let dir = ensure_workspace(app)?;

    emit(
        app,
        "pull",
        "Downloading ERPNext v16 images (first time can take several minutes)…",
    );
    let _ = compose(&dir, &["pull"]);

    emit(app, "up", "Starting containers…");
    let up = compose(&dir, &["up", "-d"])?;
    if !up.status.success() {
        let stderr = String::from_utf8_lossy(&up.stderr);
        return Err(err(format!("Docker Compose failed to start:\n{stderr}")));
    }

    emit(app, "wait", "Waiting for the backend…");
    let mut ready = false;
    for _ in 0..90 {
        if compose(&dir, &["exec", "-T", "backend", "bench", "--version"])
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            ready = true;
            break;
        }
        std::thread::sleep(std::time::Duration::from_secs(2));
    }
    if !ready {
        return Err(err(
            "The backend did not become ready. Check Docker Desktop and try again.",
        ));
    }

    let _ = compose(
        &dir,
        &[
            "exec",
            "-T",
            "backend",
            "bash",
            "-c",
            "ls -1 apps > sites/apps.txt",
        ],
    );

    if !site_exists(&dir) {
        emit(app, "site", "Creating the site and installing ERPNext…");
        let new_site = compose(
            &dir,
            &[
                "exec",
                "-T",
                "backend",
                "bench",
                "new-site",
                "localhost",
                "--mariadb-root-password",
                DEFAULT_ADMIN_PASSWORD,
                "--admin-password",
                DEFAULT_ADMIN_PASSWORD,
                "--no-mariadb-socket",
                "--install-app",
                "erpnext",
            ],
        )?;
        if !new_site.status.success() {
            let stderr = String::from_utf8_lossy(&new_site.stderr);
            return Err(err(format!("Could not create the site:\n{stderr}")));
        }
    } else {
        emit(app, "site", "Site already exists.");
    }

    emit(app, "nexterp", "Installing NextERP…");
    let _ = compose(
        &dir,
        &[
            "exec",
            "-T",
            "backend",
            "bench",
            "--site",
            "localhost",
            "install-app",
            "nexterp",
        ],
    );
    let _ = compose(
        &dir,
        &[
            "exec",
            "-T",
            "backend",
            "bench",
            "--site",
            "localhost",
            "set-config",
            "host_name",
            LOCAL_URL,
        ],
    );
    let _ = compose(&dir, &["exec", "-T", "backend", "bench", "use", "localhost"]);

    emit(app, "ready", "Local ERPNext is ready.");
    for _ in 0..30 {
        if site_reachable() {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(500));
    }

    Ok(json!({
        "ok": true,
        "url": LOCAL_URL,
        "user": "Administrator",
        "password": DEFAULT_ADMIN_PASSWORD,
        "reachable": site_reachable(),
        "version": ERPNEXT_VERSION,
    }))
}

/// Start containers that were set up earlier (no site create).
#[tauri::command]
pub async fn local_docker_start(app: AppHandle) -> Result<Value> {
    if !docker_available() {
        return Err(err("Docker is not available."));
    }
    let dir = ensure_workspace(&app)?;
    let up = compose(&dir, &["up", "-d"])?;
    if !up.status.success() {
        return Err(err(String::from_utf8_lossy(&up.stderr).to_string()));
    }
    Ok(json!({ "ok": true, "url": LOCAL_URL, "reachable": site_reachable() }))
}
