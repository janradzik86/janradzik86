/* Czarne Wilki Prawdy — logika strony + Wilcze Radio (pętla) */
(function () {
  'use strict';

  var DATA = null, PLAY = [], idx = 0, player = null, ready = false, shuffle = false, playing = false;

  var $ = function (s) { return document.querySelector(s); };
  document.getElementById('y').textContent = new Date().getFullYear();

  /* menu mobilne */
  var burger = document.querySelector('.burger');
  burger && burger.addEventListener('click', function () {
    document.querySelector('.nav nav').classList.toggle('open');
  });

  /* ---------- ładowanie katalogu ---------- */
  fetch('tracks.json?v=' + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (d) { DATA = d; render(); loadYT(); })
    .catch(function () { $('#grid').innerHTML = '<p style="color:#9a9aa4">Nie udało się wczytać listy utworów.</p>'; });

  function render() {
    var t = DATA.tracks || [];
    PLAY = t.filter(function (x) { return x.source === 'youtube' && x.videoId; });

    /* wyróżniony */
    var f = t.find(function (x) { return x.featured; }) || t[0];
    if (f) {
      $('#featured').innerHTML =
        '<div class="fcard">' +
          '<img src="' + esc(f.cover) + '" alt="' + esc(f.title) + '">' +
          '<div>' +
            '<span class="badge">NAJNOWSZA PREMIERA</span>' +
            '<h3>' + esc(f.title) + '</h3>' +
            '<p>' + esc(f.description || '') + '</p>' +
            (f.videoId ? '<div class="fembed"><iframe src="https://www.youtube-nocookie.com/embed/' +
              esc(f.videoId) + '" title="' + esc(f.title) + '" loading="lazy" allowfullscreen ' +
              'allow="accelerometer;clipboard-write;encrypted-media;picture-in-picture"></iframe></div>' : '') +
          '</div>' +
        '</div>';
    }

    /* siatka */
    $('#grid').innerHTML = t.map(function (x, i) {
      return '<article class="card">' +
        '<div class="th"><img src="' + esc(x.cover) + '" alt="' + esc(x.title) + '" loading="lazy">' +
        '<div class="pl">▶</div></div>' +
        '<div class="body">' +
          '<h4>' + esc(x.title) + '</h4>' +
          '<div class="meta">' + esc(x.type || 'utwór') + ' • ' + esc(x.year || '') + '</div>' +
          '<p>' + esc(x.description || '') + '</p>' +
          '<div class="acts">' +
            (x.videoId ? '<button data-radio="' + esc(x.id) + '">▶ w radiu</button>' +
              '<a href="https://youtu.be/' + esc(x.videoId) + '" target="_blank" rel="noopener">YouTube</a>' : '') +
            (x.spotify ? '<a href="' + esc(x.spotify) + '" target="_blank" rel="noopener">Spotify</a>' : '') +
          '</div>' +
        '</div></article>';
    }).join('');

    $('#grid').addEventListener('click', function (e) {
      var b = e.target.closest('[data-radio]'); if (!b) return;
      var i = PLAY.findIndex(function (p) { return p.id === b.getAttribute('data-radio'); });
      if (i < 0) return;
      idx = i; document.getElementById('radio').scrollIntoView({ behavior: 'smooth' }); play();
    });

    /* playlista radia */
    $('#rList').innerHTML = PLAY.map(function (x, i) {
      return '<li data-i="' + i + '"><span class="n">' + String(i + 1).padStart(2, '0') +
        '</span><span class="t">' + esc(x.title) + '</span><span>' + esc(x.year || '') + '</span></li>';
    }).join('');
    $('#rList').addEventListener('click', function (e) {
      var li = e.target.closest('li'); if (!li) return;
      idx = +li.dataset.i; play();
    });
    paint();

    /* koncerty */
    var g = DATA.concerts || [];
    $('#gigs').innerHTML = g.length ? g.map(function (c) {
      var d = new Date(c.date + 'T20:00:00');
      var m = ['STY','LUT','MAR','KWI','MAJ','CZE','LIP','SIE','WRZ','PAŹ','LIS','GRU'][d.getMonth()];
      return '<div class="gig"><div class="d">' + d.getDate() + ' ' + m + '<small>' + d.getFullYear() + '</small></div>' +
        '<div><div class="c">' + esc(c.city) + '</div><div class="v">' + esc(c.venue) + '</div></div>' +
        '<a class="b" href="' + (c.ticket || '#kontakt') + '">' + (c.ticket ? 'Bilety' : 'Info') + '</a></div>';
    }).join('') : '<p style="color:#9a9aa4">Brak zaplanowanych koncertów — wracaj tu wkrótce.</p>';
  }

  /* ---------- YouTube IFrame API jako silnik radia ---------- */
  function loadYT() {
    if (!PLAY.length) return;
    var s = document.createElement('script');
    s.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(s);
  }

  window.onYouTubeIframeAPIReady = function () {
    player = new YT.Player('ytPlayer', {
      height: '1', width: '1',
      videoId: PLAY[0].videoId,
      playerVars: { autoplay: 0, controls: 0, playsinline: 1, rel: 0 },
      events: {
        onReady: function () { ready = true; },
        onStateChange: function (e) {
          if (e.data === YT.PlayerState.ENDED) next();      // pętla
          if (e.data === YT.PlayerState.PLAYING) { playing = true; $('#rPlay').textContent = '❚❚'; }
          if (e.data === YT.PlayerState.PAUSED) { playing = false; $('#rPlay').textContent = '▶'; }
        },
        onError: function () { next(); }
      }
    });
  };

  function play() {
    if (!ready || !player) { setTimeout(play, 400); return; }
    player.loadVideoById(PLAY[idx].videoId);
    player.playVideo(); playing = true; paint();
  }
  function toggle() {
    if (!ready) { play(); return; }
    playing ? player.pauseVideo() : player.playVideo();
  }
  function next() { idx = shuffle ? Math.floor(Math.random() * PLAY.length) : (idx + 1) % PLAY.length; play(); }
  function prev() { idx = (idx - 1 + PLAY.length) % PLAY.length; play(); }

  function paint() {
    var c = PLAY[idx]; if (!c) return;
    $('#rTitle').textContent = c.title;
    $('#rDesc').textContent = c.description || '';
    $('#rArt').src = c.cover;
    Array.prototype.forEach.call(document.querySelectorAll('#rList li'), function (li, i) {
      li.classList.toggle('on', i === idx);
    });
  }

  $('#rPlay').addEventListener('click', toggle);
  $('#rNext').addEventListener('click', next);
  $('#rPrev').addEventListener('click', prev);
  $('#rShuffle').addEventListener('click', function () {
    shuffle = !shuffle; this.classList.toggle('on', shuffle);
  });
  $('#heroRadio').addEventListener('click', function () {
    document.getElementById('radio').scrollIntoView({ behavior: 'smooth' });
    setTimeout(play, 500);
  });

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
})();
