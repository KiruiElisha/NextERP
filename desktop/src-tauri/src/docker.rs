//! Local ERPNext in Docker: status, first-run setup, and start of the compose stack
//! shipped with the app (ERPNext v16 + nexterp).

use std::fs;
use std::path::{Path, PathBuf};

use crate::docker_install;

use nexterp_core::Error;
use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, Manager};

type Result<T> = std::result::Result<T, Error>;

const PROJECT: &str = "nexterp-local";
const LOCAL_URL: &str = "http://localhost:8000";
/// Sites set up before passwords were generated kept this one.
const LEGACY_PASSWORD: &str = "admin";
const ERPNEXT_VERSION: &str = "v16.54.0";

fn err(msg: impl Into<String>) -> Error {
    Error::Server(msg.into())
}

fn docker_available() -> bool {
    docker_install::running()
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
                res.join("_up_").join("_up_").join("docker").join(&*name),
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
            // tauri.conf.json bundles "../../nexterp": each "../" becomes "_up_"
            res.join("_up_").join("_up_").join("nexterp"),
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
        if entry.file_name() == "__pycache__" {
            continue;
        }
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

/// The local site's Administrator (and MariaDB root) password: made once per computer and kept in the
/// workspace, readable only by this user. A workspace from before (an .env, no password file) keeps
/// the old fixed one, or its site would refuse it.
fn admin_password(dir: &Path) -> Result<String> {
    let file = dir.join("admin-password");
    if let Ok(saved) = fs::read_to_string(&file) {
        if !saved.trim().is_empty() {
            return Ok(saved.trim().to_string());
        }
    }
    let password = if dir.join(".env").exists() {
        LEGACY_PASSWORD.to_string()
    } else {
        const ALPHABET: &[u8] = b"abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        let mut bytes = [0u8; 20];
        getrandom::getrandom(&mut bytes).map_err(|e| err(e.to_string()))?;
        bytes
            .iter()
            .map(|b| ALPHABET[*b as usize % ALPHABET.len()] as char)
            .collect()
    };
    fs::write(&file, &password).map_err(|e| err(e.to_string()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(&file, fs::Permissions::from_mode(0o600));
    }
    Ok(password)
}

/// Empty a folder but keep it: running containers have it mounted, and a new folder in its place
/// would leave them looking at the old, deleted one.
fn clear_dir(dir: &Path) -> Result<()> {
    for entry in fs::read_dir(dir).map_err(|e| err(e.to_string()))? {
        let path = entry.map_err(|e| err(e.to_string()))?.path();
        let gone = if path.is_dir() {
            fs::remove_dir_all(&path)
        } else {
            fs::remove_file(&path)
        };
        gone.map_err(|e| err(format!("Could not replace {}: {e}", path.display())))?;
    }
    Ok(())
}

/// Copy the nexterp app this version of NextERP ships into the workspace, as `apps/nexterp/nexterp`
/// (the folder Docker mounts holds the package, which PYTHONPATH in the compose file points at).
/// Copied again whenever NextERP was updated, so the local site gets the server side that goes with
/// it. Returns whether the code changed.
fn place_app(app: &AppHandle, dir: &Path) -> Result<(PathBuf, bool)> {
    let app_dir = dir.join("apps").join("nexterp");
    let stamp = dir.join("apps").join(".nexterp-version");
    let version = app.package_info().version.to_string();
    let current = app_dir.join("nexterp").join("hooks.py").exists()
        && fs::read_to_string(&stamp)
            .map(|s| s.trim() == version)
            .unwrap_or(false);
    if current && !cfg!(debug_assertions) {
        return Ok((app_dir, false));
    }
    let src = find_nexterp(app)?;
    fs::create_dir_all(&app_dir).map_err(|e| err(e.to_string()))?;
    // also clears the layout of earlier versions, which put the package's files straight in here
    clear_dir(&app_dir)?;
    copy_dir(&src, &app_dir.join("nexterp"))?;
    fs::write(&stamp, &version).map_err(|e| err(e.to_string()))?;
    Ok((app_dir, true))
}

/// Place compose files and the nexterp app under app data so Docker can mount them. Also says
/// whether the app's code changed (NextERP was updated), so the site can be brought up to date.
fn ensure_workspace(app: &AppHandle) -> Result<(PathBuf, bool)> {
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

    let (nexterp_dest, changed) = place_app(app, &dir)?;

    let nexterp_path = nexterp_dest
        .canonicalize()
        .unwrap_or_else(|_| nexterp_dest.clone())
        .to_string_lossy()
        .replace('\\', "/");

    let password = admin_password(&dir)?;
    let env = format!(
        "HTTP_PORT=8000\n\
         MYSQL_ROOT_PASSWORD={pw}\n\
         ADMIN_PASSWORD={pw}\n\
         SITE_NAME=localhost\n\
         ERPNEXT_VERSION={ver}\n\
         NEXTERP_APP_PATH={app}\n",
        pw = password,
        ver = ERPNEXT_VERSION,
        app = nexterp_path,
    );
    fs::write(dir.join(".env"), env).map_err(|e| err(e.to_string()))?;
    Ok((dir, changed))
}

fn compose(dir: &Path, args: &[&str]) -> Result<std::process::Output> {
    let mut all = vec!["compose", "-p", PROJECT, "-f", "docker-compose.yml"];
    all.extend_from_slice(args);
    docker_install::docker(&all)
        .current_dir(dir)
        .output()
        .map_err(|e| {
            err(format!(
                "Could not run Docker Compose ({e}). Install Docker Desktop and try again."
            ))
        })
}

/// What a failed command printed, for an error message: its last lines, where the reason is.
fn tail(out: &std::process::Output) -> String {
    let text = format!(
        "{}\n{}",
        String::from_utf8_lossy(&out.stdout),
        String::from_utf8_lossy(&out.stderr)
    );
    let lines: Vec<&str> = text.lines().filter(|l| !l.trim().is_empty()).collect();
    lines[lines.len().saturating_sub(12)..].join("\n")
}

/// `bench` in the backend container; an error with what it printed when it fails.
fn bench(dir: &Path, args: &[&str], what: &str) -> Result<std::process::Output> {
    let mut all = vec!["exec", "-T", "backend", "bench"];
    all.extend_from_slice(args);
    let out = compose(dir, &all)?;
    if out.status.success() {
        Ok(out)
    } else {
        Err(err(format!("{what} failed:\n{}", tail(&out))))
    }
}

/// The Python processes (web, workers, scheduler) load the app once: after new code, restart them.
fn restart_python(dir: &Path) -> Result<()> {
    let out = compose(
        dir,
        &[
            "restart",
            "backend",
            "queue-short",
            "queue-long",
            "scheduler",
        ],
    )?;
    if out.status.success() {
        Ok(())
    } else {
        Err(err(format!("Could not restart ERPNext:\n{}", tail(&out))))
    }
}

fn wait_backend(dir: &Path) -> bool {
    for _ in 0..90 {
        if compose(dir, &["exec", "-T", "backend", "bench", "--version"])
            .map(|o| o.status.success())
            .unwrap_or(false)
        {
            return true;
        }
        std::thread::sleep(std::time::Duration::from_secs(2));
    }
    false
}

/// Install nexterp on the site, or bring it up to date when NextERP brought new code. Checked: a
/// site without it answers every call from the app with "App nexterp is not installed".
fn install_or_update_app(app: &AppHandle, dir: &Path, changed: bool) -> Result<()> {
    let done = install_or_update(app, dir, changed);
    if done.is_err() {
        // try again next time, rather than take the site as up to date
        let _ = fs::remove_file(dir.join("apps").join(".nexterp-version"));
    }
    done
}

fn install_or_update(app: &AppHandle, dir: &Path, changed: bool) -> Result<()> {
    let apps = bench(
        dir,
        &["--site", "localhost", "list-apps"],
        "Listing the site's apps",
    )?;
    let installed = String::from_utf8_lossy(&apps.stdout)
        .lines()
        .any(|l| l.split_whitespace().next() == Some("nexterp"));
    if !installed {
        emit(app, "nexterp", "Installing NextERP on the site…");
        bench(
            dir,
            &["--site", "localhost", "install-app", "nexterp"],
            "Installing NextERP on the site",
        )?;
    } else if changed {
        emit(
            app,
            "nexterp",
            "Updating the site for this version of NextERP…",
        );
        bench(
            dir,
            &["--site", "localhost", "migrate"],
            "Updating the site",
        )?;
    }
    Ok(())
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
        "installed": docker || docker_install::installed(),
        "prepared": prepared,
        "running": running,
        "reachable": site_reachable(),
        "url": LOCAL_URL,
        "user": "Administrator",
        "password": dir.as_ref().and_then(|d| fs::read_to_string(d.join("admin-password")).ok())
            .map(|p| p.trim().to_string()),
        "version": ERPNEXT_VERSION,
    }))
}

/// Install Docker on this computer. The UI calls this only after the user agreed to what it will
/// install (see docker_install.rs). Emits `local-docker` progress.
#[tauri::command]
pub async fn local_docker_install(app: AppHandle) -> Result<Value> {
    let app2 = app.clone();
    tauri::async_runtime::spawn_blocking(move || -> Result<Value> {
        if docker_install::running() {
            return Ok(json!({ "ok": true, "restart_needed": false }));
        }
        let done = if docker_install::installed() {
            docker_install::Installed::default()
        } else {
            docker_install::install(|m| emit(&app2, "install", m))?
        };
        if done.restart_needed {
            return Ok(json!({ "ok": false, "restart_needed": true }));
        }
        ensure_running(&app2)?;
        Ok(json!({ "ok": true, "restart_needed": false }))
    })
    .await
    .map_err(|e| err(e.to_string()))?
}

/// Start Docker if it's installed but not running, and wait for it (Docker Desktop's first start can
/// take a couple of minutes).
fn ensure_running(app: &AppHandle) -> Result<()> {
    if docker_install::running() {
        return Ok(());
    }
    if !docker_install::installed() {
        return Err(err("Docker isn't installed on this computer yet."));
    }
    emit(app, "start", "Starting Docker…");
    docker_install::start();
    let up = docker_install::wait_running(std::time::Duration::from_secs(300), |s| {
        emit(app, "start", &format!("Starting Docker… ({s} s)"));
    });
    if up {
        Ok(())
    } else {
        Err(err(
            "Docker is installed but hasn't started. Open Docker Desktop once (it may ask you to accept \
             its terms), then press Set up again.",
        ))
    }
}

/// Pull images, start the stack, create the site and install nexterp. Emits `local-docker` progress.
#[tauri::command]
pub async fn local_docker_setup(app: AppHandle) -> Result<Value> {
    let app2 = app.clone();
    tauri::async_runtime::spawn_blocking(move || setup_blocking(&app2))
        .await
        .map_err(|e| err(e.to_string()))?
}

fn setup_blocking(app: &AppHandle) -> Result<Value> {
    ensure_running(app)?;
    emit(app, "prepare", "Preparing local ERPNext files…");
    let (dir, changed) = ensure_workspace(app)?;
    let password = admin_password(&dir)?;

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
    if changed {
        restart_python(&dir)?;
    }

    emit(app, "wait", "Waiting for the backend…");
    if !wait_backend(&dir) {
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
                &password,
                "--admin-password",
                &password,
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

    install_or_update_app(app, &dir, changed)?;
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
    let _ = compose(
        &dir,
        &["exec", "-T", "backend", "bench", "use", "localhost"],
    );

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
        "password": password,
        "reachable": site_reachable(),
        "version": ERPNEXT_VERSION,
    }))
}

/// Start containers that were set up earlier (no site create).
#[tauri::command]
pub async fn local_docker_start(app: AppHandle) -> Result<Value> {
    let app2 = app.clone();
    tauri::async_runtime::spawn_blocking(move || ensure_running(&app2))
        .await
        .map_err(|e| err(e.to_string()))??;
    let app2 = app.clone();
    tauri::async_runtime::spawn_blocking(move || -> Result<()> {
        let (dir, changed) = ensure_workspace(&app2)?;
        let up = compose(&dir, &["up", "-d"])?;
        if !up.status.success() {
            return Err(err(String::from_utf8_lossy(&up.stderr).to_string()));
        }
        // NextERP was updated since the site last ran: its new server code, then the site's tables
        if changed && site_exists(&dir) {
            restart_python(&dir)?;
            if wait_backend(&dir) {
                install_or_update_app(&app2, &dir, true)?;
            }
        }
        Ok(())
    })
    .await
    .map_err(|e| err(e.to_string()))??;
    Ok(json!({ "ok": true, "url": LOCAL_URL, "reachable": site_reachable() }))
}
