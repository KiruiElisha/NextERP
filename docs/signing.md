# Signed installers and signed updates

The release workflow (`.github/workflows/release-desktop.yml`) signs everything it can. Each kind of
signature switches on by itself once its secrets are in the repository (**Settings → Secrets and
variables → Actions**), and is skipped until then: a release without them still builds, unsigned, and
its notes say which parts are signed. Nothing below goes in the code; keys and passwords live only in
GitHub secrets.

There are three separate signatures. You can add them in any order.

| What | Who it convinces | Cost | Secrets |
|---|---|---|---|
| macOS Developer ID + notarization | Gatekeeper: the app opens with no warning | Apple Developer Program, USD 99 a year | `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID` |
| Windows Authenticode | SmartScreen: "unknown publisher" goes away | Azure Trusted Signing (about USD 10 a month) or a code-signing certificate | Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` + variables `TRUSTED_SIGNING_ENDPOINT`, `TRUSTED_SIGNING_ACCOUNT`, `TRUSTED_SIGNING_PROFILE`. Or a .pfx: `WINDOWS_CERTIFICATE`, `WINDOWS_CERTIFICATE_PASSWORD` |
| Update signature | The installed app: it installs only updates signed by you | Free | `TAURI_SIGNING_PRIVATE_KEY`, `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` + variable `UPDATER_PUBKEY` |

## 1. Signed updates (free; do this first)

Installed apps check this repository's latest release every six hours, and offer **Restart and update**
when there is a newer one. They install it only if its signature matches the public key built into
them, so nobody else can push an update to your customers.

1. On your own computer (not in CI), make the key pair:

   ```bash
   cd desktop && npx tauri signer generate -w ~/.tauri/nexterp-updater.key
   ```

   Give it a password when asked. Keep `~/.tauri/nexterp-updater.key` and the password safe, and back
   them up: **if the key is lost, installed apps can't be updated any more** (people would have to
   download a new installer once).
2. Add the secret `TAURI_SIGNING_PRIVATE_KEY` with the contents of `~/.tauri/nexterp-updater.key`, and
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` with its password.
3. Add the **variable** (not a secret: it's public) `UPDATER_PUBKEY` with the contents of
   `~/.tauri/nexterp-updater.key.pub`.

The next release then carries `latest.json` and signed update bundles. Apps installed from releases made
before this step don't have the public key, so they update by downloading the new installer once.

## 2. macOS

1. Join the Apple Developer Program (developer.apple.com/programs). As a company you need a D-U-N-S
   number; as an individual, the certificate shows your own name.
2. In Xcode or at developer.apple.com, create a **Developer ID Application** certificate, then export it
   from Keychain Access as a `.p12` with a password.
3. Secrets:
   - `APPLE_CERTIFICATE`: the `.p12` in base64 (`base64 -i cert.p12 | pbcopy`)
   - `APPLE_CERTIFICATE_PASSWORD`: its export password
   - `APPLE_SIGNING_IDENTITY`: the certificate's name, like `Developer ID Application: Nergaa Ltd (TEAMID1234)`
4. Notarization (so Gatekeeper doesn't warn at all):
   - `APPLE_ID`: the Apple account email
   - `APPLE_PASSWORD`: an **app-specific password** from account.apple.com (not the account password)
   - `APPLE_TEAM_ID`: the 10-character team ID

Signed without the three notarization secrets, the workflow warns: the app is signed, but Gatekeeper
still asks on first open.

## 3. Windows

Since June 2023, publicly trusted code-signing keys must live in hardware (a USB token or a cloud HSM),
so a plain `.pfx` file from a certificate authority is no longer issued. For signing in CI, use a cloud
service:

- **Azure Trusted Signing** (supported here). Cheapest, and the reputation SmartScreen needs builds
  quickly. Eligibility depends on where your organisation is registered; check Microsoft's current list
  first. Create a Trusted Signing account and a certificate profile, then an app registration (service
  principal) with the *Trusted Signing Certificate Profile Signer* role. Secrets: `AZURE_CLIENT_ID`,
  `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`. Variables: `TRUSTED_SIGNING_ENDPOINT` (for example
  `https://weu.codesigning.azure.net`), `TRUSTED_SIGNING_ACCOUNT`, `TRUSTED_SIGNING_PROFILE`.
- **A certificate authority's cloud signing** (SSL.com eSigner, DigiCert KeyLocker, Certum SimplySign),
  if Azure isn't open to you. Each signs through its own command-line tool; tell us which one you buy
  and the workflow gets a step for it.
- **A `.pfx` file** (supported here) works for an older certificate you already hold, or a self-signed
  one for testing: `WINDOWS_CERTIFICATE` (the `.pfx` in base64) and `WINDOWS_CERTIFICATE_PASSWORD`.

An OV certificate removes "unknown publisher" at once, but SmartScreen may still warn until enough
people have installed the app; signing every release with the same identity builds that reputation.

## Linux

AppImage, `.deb` and `.rpm` aren't code-signed by any store; nothing to do.

## Check a release

The release notes list what was signed. On a Mac: `codesign -dv --verbose=4 /Applications/ERPNext.app`
and `spctl -a -vv /Applications/ERPNext.app` (should say *Notarized Developer ID*). On Windows: the
installer's Properties → Digital Signatures tab.
