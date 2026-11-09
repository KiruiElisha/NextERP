# Website

The project's home and download page (served at https://nexterp.nergaa.cloud by the Press host; the
`app_site` role in nergaa-cloud copies this folder from `main` on every deploy). Plain HTML and CSS,
no build step. `assets/download.js` reads the latest GitHub release to fill the download lists; without
it, every link goes to the release page.

`code-signing.html` and the "Code signing policy" section are what SignPath Foundation asks of a project
it signs for (https://signpath.org/terms). Keep the roles table and the privacy policy true when the
team or the app's network use changes.

Preview: `python3 -m http.server -d website 8000`.
