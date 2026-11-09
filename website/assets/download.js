// Fills the download lists from the latest GitHub release, and points the main button at the installer
// for this visitor's system. Without JavaScript, or if GitHub doesn't answer, every link still goes to
// the release page.
(function () {
  var REPO = 'KiruiElisha/NextERP'
  var LATEST = 'https://github.com/' + REPO + '/releases/latest'

  // Which files belong to which system, in the order they're offered.
  var KINDS = [
    { os: 'windows', test: /-setup\.exe$/i, label: 'Installer (.exe)', note: 'Windows 10 and 11' },
    { os: 'windows', test: /\.msi$/i, label: 'Windows Installer (.msi)', note: 'for managed installs' },
    { os: 'mac', test: /\.dmg$/i, label: 'Disk image (.dmg)', note: 'Apple silicon and Intel' },
    { os: 'linux', test: /\.AppImage$/i, label: 'AppImage', note: 'most distributions' },
    { os: 'linux', test: /\.deb$/i, label: 'Debian, Ubuntu (.deb)', note: '' },
    { os: 'linux', test: /\.rpm$/i, label: 'Fedora, openSUSE (.rpm)', note: '' },
  ]
  var NAMES = { windows: 'Windows', mac: 'macOS', linux: 'Linux' }

  function detect() {
    var p = ((navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || '') + ' ' + navigator.userAgent
    if (/android|iphone|ipad/i.test(p)) return null
    if (/win/i.test(p)) return 'windows'
    if (/mac/i.test(p)) return 'mac'
    if (/linux|x11/i.test(p)) return 'linux'
    return null
  }

  function size(bytes) {
    return bytes > 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.round(bytes / 1024) + ' KB'
  }

  function el(tag, attrs, text) {
    var e = document.createElement(tag)
    for (var k in attrs) e.setAttribute(k, attrs[k])
    if (text != null) e.textContent = text
    return e
  }

  var mine = detect()
  if (mine) {
    var card = document.querySelector('[data-os="' + mine + '"]')
    if (card) card.classList.add('mine')
    document.getElementById('hero-label').textContent = 'Download for ' + NAMES[mine]
  }

  fetch('https://api.github.com/repos/' + REPO + '/releases/latest', { headers: { Accept: 'application/vnd.github+json' } })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json() })
    .then(function (rel) {
      var version = String(rel.tag_name || '').replace(/^desktop-v/, '')
      var date = rel.published_at ? new Date(rel.published_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : ''
      var line = document.getElementById('release-line')
      line.textContent = 'Version ' + version + (date ? ', released ' + date + '. ' : '. ')
      line.appendChild(el('a', { href: rel.html_url }, "What's new"))

      var byOs = { windows: [], mac: [], linux: [] }
      KINDS.forEach(function (k) {
        ;(rel.assets || []).forEach(function (a) {
          if (k.test.test(a.name)) byOs[k.os].push({ kind: k, asset: a })
        })
      })
      Object.keys(byOs).forEach(function (os) {
        var list = document.querySelector('[data-files="' + os + '"]')
        if (!list || !byOs[os].length) return
        list.textContent = ''
        byOs[os].forEach(function (f) {
          var li = el('li')
          var a = el('a', { href: f.asset.browser_download_url })
          a.appendChild(document.createTextNode(f.kind.label))
          a.appendChild(el('small', {}, size(f.asset.size)))
          li.appendChild(a)
          if (f.asset.digest) li.appendChild(el('div', { class: 'sha' }, f.asset.digest.replace(/^sha256:/, 'SHA-256 ')))
          list.appendChild(li)
        })
      })

      var first = mine && byOs[mine][0]
      if (first) {
        document.getElementById('hero-download').setAttribute('href', first.asset.browser_download_url)
        document.getElementById('hero-fine').firstChild.textContent =
          'Version ' + version + ' · ' + first.asset.name + ' · ' + size(first.asset.size) + '. '
      }
    })
    .catch(function () {
      // Rate-limited or offline: the static links to the release page stay.
      if (mine) document.getElementById('hero-download').setAttribute('href', LATEST)
    })
})()
