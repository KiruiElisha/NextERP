//! Getting Docker onto the computer for the local ERPNext: install it when it's missing, start it when
//! it's installed but stopped, and run `docker` so it works right after installing.
//!
//! Only after the user agreed in the app (the sign-in screen says what will be installed, from where,
//! and that the system will ask for permission): SignPath's terms and plain courtesy both want a
//! program to announce changes to the system before making them.
//!
//! - Windows: Docker Desktop through winget, or Docker's own installer when winget is missing; WSL 2
//!   first when Windows doesn't have it (that one may need a restart).
//! - macOS: Docker Desktop from Docker's disk image, installed with the administrator password.
//! - Linux: Docker Engine and its Compose plugin with Docker's install script, run through pkexec
//!   (the desktop's own password prompt); the user joins the docker group.

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};
use std::time::{Duration, Instant};

use nexterp_core::Error;

type Result<T> = std::result::Result<T, Error>;

fn err(msg: impl Into<String>) -> Error {
    Error::Server(msg.into())
}

/// A process without a console window flashing up on Windows.
pub fn hidden(program: &str) -> Command {
    #[allow(unused_mut)]
    let mut cmd = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd
}

fn quiet_ok(cmd: &mut Command) -> bool {
    cmd.stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn on_path(program: &str) -> bool {
    quiet_ok(hidden(program).arg("--version"))
}

/// Single-quoted for `sh -c`, so a path with spaces or quotes stays one argument.
fn sh_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', r"'\''"))
}

/// `docker` with these arguments. On Linux, right after installing, the user's session isn't in the
/// docker group yet (that needs a new login); `sg docker` runs the command in that group meanwhile.
pub fn docker(args: &[&str]) -> Command {
    if cfg!(target_os = "linux") && needs_group() {
        let line = std::iter::once("docker")
            .chain(args.iter().copied())
            .map(sh_quote)
            .collect::<Vec<_>>()
            .join(" ");
        let mut cmd = hidden("sg");
        cmd.args(["docker", "-c", &line]);
        return cmd;
    }
    let mut cmd = match docker_dir() {
        Some(dir) => {
            let mut cmd = hidden(&dir.join(exe("docker")).to_string_lossy());
            cmd.env("PATH", path_with(&dir));
            cmd
        }
        None => hidden("docker"),
    };
    cmd.args(args);
    cmd
}

fn exe(name: &str) -> String {
    if cfg!(windows) {
        format!("{name}.exe")
    } else {
        name.to_string()
    }
}

/// Where Docker puts its command-line tools. The app can't count on PATH for them: right after
/// Docker installs, PATH is still the one the app started with (Windows), and an app opened from
/// the Dock gets a short PATH without /usr/local/bin (macOS). Without this, `docker` stays "not
/// found" until NextERP is closed and opened again.
fn bin_dirs() -> Vec<PathBuf> {
    if cfg!(windows) {
        let base = std::env::var("ProgramFiles").unwrap_or_else(|_| r"C:\Program Files".into());
        vec![Path::new(&base).join(r"Docker\Docker\resources\bin")]
    } else if cfg!(target_os = "macos") {
        let mut dirs = vec![
            PathBuf::from("/usr/local/bin"),
            PathBuf::from("/opt/homebrew/bin"),
            PathBuf::from("/Applications/Docker.app/Contents/Resources/bin"),
        ];
        if let Some(home) = std::env::var_os("HOME") {
            dirs.push(Path::new(&home).join(".docker/bin"));
        }
        dirs
    } else {
        vec![PathBuf::from("/usr/bin"), PathBuf::from("/usr/local/bin")]
    }
}

/// The folder Docker's tools are in, when there is one.
fn docker_dir() -> Option<PathBuf> {
    bin_dirs()
        .into_iter()
        .find(|d| d.join(exe("docker")).is_file())
}

/// PATH with `dir` first, so `docker` finds its helpers (credentials, compose) the same way.
fn path_with(dir: &Path) -> OsString {
    let current = std::env::var_os("PATH").unwrap_or_default();
    let dirs = std::iter::once(dir.to_path_buf()).chain(std::env::split_paths(&current));
    std::env::join_paths(dirs).unwrap_or(current)
}

/// The user was added to the docker group but this login session doesn't have it yet.
fn needs_group() -> bool {
    let active = hidden("id")
        .arg("-nG")
        .output()
        .map(|o| {
            String::from_utf8_lossy(&o.stdout)
                .split_whitespace()
                .any(|g| g == "docker")
        })
        .unwrap_or(true);
    if active {
        return false;
    }
    let user = username();
    std::fs::read_to_string("/etc/group")
        .map(|groups| {
            groups.lines().any(|l| {
                l.starts_with("docker:")
                    && l.rsplit(':')
                        .next()
                        .unwrap_or("")
                        .split(',')
                        .any(|m| m == user)
            })
        })
        .unwrap_or(false)
}

fn username() -> String {
    std::env::var("USER")
        .or_else(|_| std::env::var("USERNAME"))
        .unwrap_or_default()
}

/// The Docker daemon answers.
pub fn running() -> bool {
    quiet_ok(&mut docker(&["info"]))
}

/// Docker is on this computer, running or not.
pub fn installed() -> bool {
    if docker_dir().is_some() || on_path("docker") {
        return true;
    }
    if cfg!(windows) {
        return desktop_exe_windows().exists();
    }
    if cfg!(target_os = "macos") {
        return Path::new("/Applications/Docker.app").exists();
    }
    false
}

fn desktop_exe_windows() -> std::path::PathBuf {
    let base = std::env::var("ProgramFiles").unwrap_or_else(|_| r"C:\Program Files".into());
    Path::new(&base).join(r"Docker\Docker\Docker Desktop.exe")
}

/// Ask Docker to start (Docker Desktop, or the Linux service). Doesn't wait.
pub fn start() {
    if cfg!(windows) {
        let exe = desktop_exe_windows();
        if exe.exists() {
            let _ = hidden(&exe.to_string_lossy()).spawn();
        }
    } else if cfg!(target_os = "macos") {
        let _ = hidden("open").args(["-a", "Docker"]).status();
    } else {
        // the service is enabled by the install below; start it now (asks for the password once)
        let _ = hidden("pkexec")
            .args(["systemctl", "start", "docker"])
            .status();
    }
}

/// Wait until the daemon answers, calling `tick` every few seconds with the seconds waited.
pub fn wait_running(limit: Duration, mut tick: impl FnMut(u64)) -> bool {
    let started = Instant::now();
    while started.elapsed() < limit {
        if running() {
            return true;
        }
        tick(started.elapsed().as_secs());
        std::thread::sleep(Duration::from_secs(3));
    }
    running()
}

fn checked(out: std::io::Result<Output>, what: &str) -> Result<Output> {
    let out = out.map_err(|e| err(format!("{what}: {e}")))?;
    if out.status.success() {
        Ok(out)
    } else {
        let msg = String::from_utf8_lossy(&out.stderr);
        let msg = if msg.trim().is_empty() {
            String::from_utf8_lossy(&out.stdout).to_string()
        } else {
            msg.to_string()
        };
        Err(err(format!(
            "{what} failed: {}",
            msg.trim().chars().take(600).collect::<String>()
        )))
    }
}

/// What the install did that the user should know.
#[derive(Default)]
pub struct Installed {
    /// Windows got WSL 2 just now: Docker starts only after a restart.
    pub restart_needed: bool,
}

/// Install Docker for this system. `say` reports progress.
pub fn install(say: impl Fn(&str)) -> Result<Installed> {
    if cfg!(windows) {
        install_windows(say)
    } else if cfg!(target_os = "macos") {
        install_macos(say).map(|_| Installed::default())
    } else {
        install_linux(say).map(|_| Installed::default())
    }
}

/// PowerShell: run a program elevated (Windows asks the user) and wait for it.
fn elevated_windows(file: &str, args: &str) -> std::io::Result<Output> {
    let script = format!(
        "$p = Start-Process -FilePath {} -ArgumentList {} -Verb RunAs -Wait -PassThru; exit $p.ExitCode",
        ps_quote(file),
        ps_quote(args)
    );
    hidden("powershell")
        .args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            &script,
        ])
        .output()
}

fn ps_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "''"))
}

fn install_windows(say: impl Fn(&str)) -> Result<Installed> {
    let mut done = Installed::default();
    let wsl_ready = quiet_ok(hidden("wsl").args(["--status"]));
    if !wsl_ready {
        say("Turning on WSL 2, which Docker needs (Windows will ask for permission)…");
        checked(
            elevated_windows("wsl.exe", "--install --no-distribution"),
            "Installing WSL 2",
        )?;
        done.restart_needed = true;
    }
    say("Installing Docker Desktop (about 600 MB; Windows will ask for permission)…");
    if on_path("winget") {
        let out = hidden("winget")
            .args([
                "install",
                "-e",
                "--id",
                "Docker.DockerDesktop",
                "--accept-package-agreements",
                "--accept-source-agreements",
                "--silent",
            ])
            .output();
        // winget answers "already installed" with a non-zero code: fine
        if !installed() {
            checked(out, "Installing Docker Desktop with winget")?;
        }
    } else {
        let file = std::env::temp_dir().join("DockerDesktopInstaller.exe");
        let file_s = file.to_string_lossy().to_string();
        let download = format!(
            "Invoke-WebRequest -UseBasicParsing -Uri 'https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe' -OutFile {}",
            ps_quote(&file_s)
        );
        checked(
            hidden("powershell")
                .args([
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    &download,
                ])
                .output(),
            "Downloading Docker Desktop",
        )?;
        checked(
            elevated_windows(&file_s, "install --quiet --accept-license --backend=wsl-2"),
            "Installing Docker Desktop",
        )?;
        let _ = std::fs::remove_file(&file);
    }
    if !installed() {
        return Err(err(
            "Docker Desktop did not install. Install it from docker.com, then try again.",
        ));
    }
    Ok(done)
}

fn install_macos(say: impl Fn(&str)) -> Result<()> {
    let arch = if cfg!(target_arch = "aarch64") {
        "arm64"
    } else {
        "amd64"
    };
    let dmg = std::env::temp_dir().join("Docker.dmg");
    let dmg_s = dmg.to_string_lossy().to_string();
    say("Downloading Docker Desktop (about 600 MB)…");
    checked(
        hidden("curl")
            .args(["-fL", "--retry", "3", "-o", &dmg_s])
            .arg(format!(
                "https://desktop.docker.com/mac/main/{arch}/Docker.dmg"
            ))
            .output(),
        "Downloading Docker Desktop",
    )?;
    say("Installing Docker Desktop (macOS will ask for your password)…");
    checked(
        hidden("hdiutil")
            .args(["attach", "-nobrowse", "-quiet", &dmg_s])
            .output(),
        "Opening the Docker disk image",
    )?;
    let script = format!(
        "do shell script \"/Volumes/Docker/Docker.app/Contents/MacOS/install --accept-license --user={}\" with administrator privileges",
        username().replace(['"', '\\'], "")
    );
    let result = checked(
        hidden("osascript").args(["-e", &script]).output(),
        "Installing Docker Desktop",
    );
    let _ = hidden("hdiutil")
        .args(["detach", "-quiet", "/Volumes/Docker"])
        .status();
    let _ = std::fs::remove_file(&dmg);
    result.map(|_| ())
}

fn install_linux(say: impl Fn(&str)) -> Result<()> {
    if !on_path("pkexec") {
        return Err(err(
            "Installing Docker needs administrator rights, and this computer has no pkexec to ask for \
             them. Install Docker Engine (docs.docker.com/engine/install), then try again.",
        ));
    }
    if !on_path("curl") {
        return Err(err(
            "Installing Docker needs curl. Install curl, then try again.",
        ));
    }
    say("Installing Docker Engine with Docker's install script (you'll be asked for your password)…");
    let user = username();
    let script = format!(
        "set -e; curl -fsSL https://get.docker.com | sh; systemctl enable --now docker; usermod -aG docker {}",
        sh_quote(&user)
    );
    checked(
        hidden("pkexec").args(["sh", "-c", &script]).output(),
        "Installing Docker Engine",
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn docker_found_outside_path_goes_first_on_its_path() {
        let dir = std::env::temp_dir().join("nexterp-docker-bin");
        let path = path_with(&dir);
        assert_eq!(std::env::split_paths(&path).next(), Some(dir));
    }

    #[test]
    fn quoting_keeps_each_argument_whole() {
        assert_eq!(sh_quote("a b"), "'a b'");
        assert_eq!(sh_quote("it's"), r"'it'\''s'");
        assert_eq!(
            ps_quote("C:\\Users\\O'Neil\\x.exe"),
            "'C:\\Users\\O''Neil\\x.exe'"
        );
    }
}
