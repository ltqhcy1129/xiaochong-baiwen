(function () {
  // ============ 登录态与接口封装 ============
  var AUTH = { token: '', user: null, mode: 'login' };
  try { AUTH.token = localStorage.getItem('xc_token') || ''; } catch (e) {}
  var authMask = document.getElementById('authMask');
  var authErrEl = document.getElementById('authErr');
  var booted = false;

  // ============ 启动加载页 ============
  // 只画一条细线：速度恒定、不跳格，最短停留 1.3 秒，最快也在 2 秒左右收完。
  var BOOT = { val: 0, target: 0, t0: Date.now(), finished: false, raf: 0, stage: '' };

  function bootText(v) {
    if (v >= 96) return '就绪';
    if (v >= 78) return '正在载入图鉴';
    if (v >= 46) return '正在载入资料';
    return '正在连接';
  }

  function bootPaint() {
    var bar = document.getElementById('bootBar');
    var st = document.getElementById('bootState');
    if (bar) bar.style.width = BOOT.val.toFixed(2) + '%';
    if (st) {
      var t = bootText(BOOT.val);
      if (t !== BOOT.stage) { BOOT.stage = t; st.textContent = t; }
    }
  }

  var bootLast = 0;
  function bootLoop(now) {
    var dt = bootLast ? Math.min(80, now - bootLast) : 16;
    bootLast = now;
    if (BOOT.val < BOOT.target) {
      // 每秒推进 62%：不管机器快慢，看起来都是同一条线匀速往前挪
      BOOT.val = Math.min(BOOT.target, BOOT.val + dt * 0.062);
      bootPaint();
    } else if (!BOOT.finished && BOOT.val < 94) {
      // 接口慢的时候进度会停在原地，再给一点极慢的爬升，别让人以为卡死
      BOOT.val = Math.min(94, BOOT.val + dt * 0.004);
      bootPaint();
    }
    if (!BOOT.finished && BOOT.val < 100) {
      BOOT.raf = requestAnimationFrame(bootLoop);
    } else {
      BOOT.raf = 0;
    }
  }

  function bootStep(v) {
    if (BOOT.finished) return;
    BOOT.target = Math.max(BOOT.target, v);
    document.body.classList.add('boot-js');
    if (!BOOT.raf && BOOT.val < BOOT.target) {
      bootLast = 0;
      BOOT.raf = requestAnimationFrame(bootLoop);
    }
  }

  function bootFinish() {
    if (BOOT.finished) return;
    BOOT.finished = true;
    var el = document.getElementById('boot');
    if (BOOT.raf) { cancelAnimationFrame(BOOT.raf); BOOT.raf = 0; }
    // 上一步没走完也让它走完，否则进度条会在半路被抹掉
    var wait = Math.max(0, 1000 - (Date.now() - BOOT.t0));
    setTimeout(function () {
      var from = BOOT.val, t0 = performance.now();
      (function run() {
        var p = Math.min(1, (performance.now() - t0) / 200);
        BOOT.val = from + (100 - from) * (1 - Math.pow(1 - p, 3));
        bootPaint();
        if (p < 1) { requestAnimationFrame(run); return; }
        setTimeout(function () {
          if (el) el.classList.add('is-out');
          setTimeout(function () {
            document.body.classList.remove('booting');
            if (el && el.parentNode) el.parentNode.removeChild(el);
          }, 360);
        }, 130);
      })();
    }, wait);
  }

  // 平台边缘会把 sharecode 从服务端请求里摘掉，只能靠浏览器地址栏判断来路
  if (/[?&]sharecode=/.test(location.search)) {
    var bf = document.getElementById('bootFrom');
    if (bf) bf.classList.add('on');
  }

  bootStep(14);

  function setToken(t) {
    AUTH.token = t || '';
    try { if (t) localStorage.setItem('xc_token', t); else localStorage.removeItem('xc_token'); } catch (e) {}
  }

  function showLogin(msg) {
    bootFinish();
    document.body.classList.add('locked');
    if (authMask) authMask.classList.add('show');
    setAuthMode('login');
    if (authErrEl) authErrEl.textContent = msg || '';
  }

  function hideLogin() {
    // 启动页到此结束：内容已经能画，遮罩可以撤了
    bootStep(96);
    bootFinish();
    document.body.classList.remove('locked');
    if (authMask) authMask.classList.remove('show');
    if (authErrEl) authErrEl.textContent = '';
  }

  // 统一请求入口：自动带登录令牌，401 时统一回到登录页
  function api(url, opts) {
    opts = opts || {};
    var h = opts.headers || {};
    if (AUTH.token) h['X-Token'] = AUTH.token;
    opts.headers = h;
    if (!opts.credentials) opts.credentials = 'same-origin';
    return fetch(url, opts).then(function (r) {
      if (r.status === 401) {
        // 后端用 detail 区分「没登录」和「过了夜里 12 点」，提示文案跟着变
        return r.clone().json().catch(function () { return null; }).then(function (d) {
          var why = (d && d.detail) || '';
          useStop();
          dayWatchStop();
          AUTH.user = null;
          setToken('');
          showLogin(why === 'day_rollover'
            ? '已过夜里 12 点，请重新登录'
            : '登录状态已失效，请重新登录');
          var err = new Error('unauthorized');
          err.unauthorized = true;
          throw err;
        });
      }
      return r;
    });
  }

  var main = document.getElementById('main');
  var messagesEl = document.getElementById('messages');
  var welcomeEl = document.getElementById('welcome');
  var input = document.getElementById('input');
  var sendBtn = document.getElementById('send');
  var statusEl = document.getElementById('status');
  var noticeEl = document.getElementById('notice');
  var editingHint = document.getElementById('editingHint');
  var sidebar = document.getElementById('sidebar');
  var sidebarMask = document.getElementById('sidebarMask');
  var sessionListEl = document.getElementById('sessionList');

  var LS_KEY = 'xiaochong_sessions_v1';
  // 对话记录按账号隔离，避免同一台设备切换账号时互相看到对方的问答
  function sessionsKey() { return LS_KEY + (AUTH.user && AUTH.user.uid ? ':' + AUTH.user.uid : ''); }
  var MAX_SESSIONS = 30;

  var history = [];
  var sessions = [];
  var currentId = null;
  var sending = false;
  var configured = false;
  var editingIdx = null;
  var rawBuffer = '';
  var currentView = 'chat';
  var pendingTask = null;   // { task_id, sessionId, question }
  var pollTimer = null;
  var PENDING_KEY = 'xiaochong_pending_task';
  function savePendingTask() { try { localStorage.setItem(PENDING_KEY, JSON.stringify(pendingTask)); } catch (e) {} }
  function loadPendingTask() { try { var s = localStorage.getItem(PENDING_KEY); return s ? JSON.parse(s) : null; } catch (e) { return null; } }
  function clearPendingTask() { pendingTask = null; try { localStorage.removeItem(PENDING_KEY); } catch (e) {} }

  // ============ 访问埋点（用于后台日活/月活/渠道统计） ============
  // 来源判定优先级：URL 参数(?from=) > 已记录的来源 > referrer/UA 推断
  function detectSource() {
    var raw = '';
    try {
      var qs = location.search.replace(/^\?/, '').split('&');
      for (var i = 0; i < qs.length; i++) {
        if (!qs[i]) continue;
        var p = qs[i].split('=');
        var k = decodeURIComponent(p[0] || '');
        if (k === 'from' || k === 'utm_source' || k === 'src') {
          raw = decodeURIComponent((p[1] || '').replace(/\+/g, ' '));
          break;
        }
      }
    } catch (e) {}
    if (raw) { return String(raw).toLowerCase().replace(/[^a-z0-9_\-]/g, '').slice(0, 20) || 'direct'; }
    try {
      var saved = localStorage.getItem('xc_src');
      if (saved) return saved;
    } catch (e) {}
    var ref = document.referrer || '';
    var ua = navigator.userAgent || '';
    if (/mp\.weixin\.qq\.com/.test(ref)) return 'mp_article';
    if (/MicroMessenger/i.test(ua)) return 'wechat';
    if (/baidu\.com|sogou\.com|so\.com|bing\.com|google\./i.test(ref)) return 'search';
    if (ref && ref.indexOf(location.host) === -1) return 'external';
    return 'direct';
  }

  function trackVisit() {
    try {
      var d = new Date();
      var day = d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
      var key = 'xc_track_day';
      var src = detectSource();
      // 首次进入时固化来源，之后同一设备沿用，避免被无关跳转改写
      try { if (!localStorage.getItem('xc_src')) localStorage.setItem('xc_src', src); } catch (e) {}
      if (localStorage.getItem(key) === day) return;
      localStorage.setItem(key, day);
      api('/api/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: DEVICE_ID, src: src })
      }).catch(function () {});
    } catch (e) {}
  }

  // ============ 会话管理 ============
  function genId() { return 's' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  function getDeviceId() {
    try {
      var k = 'xc_device_id';
      var id = localStorage.getItem(k);
      if (!id) { id = 'd' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12); localStorage.setItem(k, id); }
      return id;
    } catch (e) { return ''; }
  }
  var DEVICE_ID = getDeviceId();

  // ============ 登录 / 注册 ============
  var AUTHV = { tried: false };

  var FV = {
    phone: { box: 'gpPhone', err: 'errPhone', input: 'authPhone' },
    pwd: { box: 'gpPwd', err: 'errPwd', input: 'authPwd' },
    pwd2: { box: 'authPwd2Box', err: 'errPwd2', input: 'authPwd2' }
  };

  function av(id) {
    var el = document.getElementById(id);
    return el ? (el.value || '') : '';
  }

  function setFv(name, msg) {
    var m = FV[name];
    if (!m) return;
    var box = document.getElementById(m.box);
    var err = document.getElementById(m.err);
    if (err && err.textContent !== (msg || '')) err.textContent = msg || '';
    if (box) box.classList.toggle('is-bad', !!msg);
    var inp = document.getElementById(m.input);
    if (inp) inp.setAttribute('aria-invalid', msg ? 'true' : 'false');
  }

  function vPhone(strict) {
    var v = av('authPhone').replace(/[^\d]/g, '');
    if (!v) return strict ? '请填写手机号，用于登录和找回密码' : '';
    if (v.length < 11) return '手机号是 11 位数字，现在 ' + v.length + ' 位，还差 ' + (11 - v.length) + ' 位';
    if (v.length > 11) return '手机号是 11 位数字，现在多出 ' + (v.length - 11) + ' 位';
    if (!/^1[3-9]/.test(v)) return '手机号以 1 开头、第 2 位是 3-9，请核对前两位';
    return '';
  }

  function vPwd(strict) {
    var v = av('authPwd');
    var isNew = AUTH.mode === 'register' || AUTH.mode === 'reset';
    if (!v) return strict ? (isNew ? '请设置密码，至少 6 位' : '请填写密码') : '';
    if (v.length < 6) return '密码至少 6 位，还差 ' + (6 - v.length) + ' 位';
    if (v.length > 32) return '密码最多 32 位，请删掉 ' + (v.length - 32) + ' 位';
    return '';
  }

  function vPwd2(strict) {
    if (AUTH.mode === 'login') return '';
    var v = av('authPwd2');
    if (!v) return strict ? '再输入一次同样的密码' : '';
    if (v !== av('authPwd')) return '两次输入不一致，请对照上面那一格重填';
    return '';
  }

  // 0 = 空，1 = 很弱 …… 返回 0~1 的比例
  function pwdScore(v) {
    if (!v) return 0;
    var n = v.length;
    var kinds = 0;
    if (/[a-z]/.test(v)) kinds++;
    if (/[A-Z]/.test(v)) kinds++;
    if (/\d/.test(v)) kinds++;
    if (/[^A-Za-z0-9]/.test(v)) kinds++;
    var s = (Math.min(n, 8) / 8) * 0.5;
    if (n >= 10) s += 0.1;
    if (n >= 14) s += 0.1;
    s += (Math.min(kinds, 3) / 3) * 0.3;
    if (n < 6) s = Math.min(s, 0.28);
    if (/^\d+$/.test(v)) s = Math.min(s, 0.22);
    if (/^[a-z]+$/i.test(v)) s = Math.min(s, 0.25);
    return Math.max(0, Math.min(1, s));
  }

  function pwdLvText(sc) {
    if (sc < 0.34) return '弱';
    if (sc < 0.62) return '一般';
    if (sc < 0.86) return '强';
    return '很强';
  }

  function pwdPaint() {
    var v = av('authPwd');
    var meter = document.getElementById('pwdMeter');
    if (!meter) return;
    var bar = meter.querySelector('i');
    var lv = document.getElementById('pwdLv');
    var isNew = AUTH.mode === 'register' || AUTH.mode === 'reset';
    var sc = v ? pwdScore(v) : 0;
    // 色相走 pow 曲线：低分段老老实实红，别刚过 6 位就发绿
    var hue = Math.round(4 + 141 * Math.pow(sc, 1.45));

    meter.classList.toggle('on', isNew && !!v);
    if (bar) {
      bar.style.width = v ? Math.max(8, Math.round(sc * 100)) + '%' : '0%';
      bar.style.backgroundColor = 'hsl(' + hue + ', 62%, 46%)';
    }
    if (lv) {
      lv.textContent = (isNew && v) ? pwdLvText(sc) : '';
      lv.style.color = v ? 'hsl(' + hue + ', 62%, 52%)' : '';
    }
  }

  function bindEye(btnId, inputId) {
    var b = document.getElementById(btnId);
    var i = document.getElementById(inputId);
    if (!b || !i) return;
    b.addEventListener('click', function () {
      var show = i.type === 'password';
      i.type = show ? 'text' : 'password';
      b.classList.toggle('on', show);
      b.setAttribute('aria-pressed', show ? 'true' : 'false');
      b.setAttribute('aria-label', show ? '隐藏密码' : '显示密码');
      if (show) {
        try { i.setSelectionRange(i.value.length, i.value.length); } catch (e) {}
      }
      i.focus();
    });
  }

  function setAuthMode(mode) {
    AUTH.mode = mode;
    AUTHV.tried = false;
    var isReg = mode === 'register';
    var isReset = mode === 'reset';
    var isNew = isReg || isReset;
    var t = document.getElementById('authTitle');
    var d = document.getElementById('authDesc');
    var s = document.getElementById('authSubmit');
    var sw = document.getElementById('authSwitch');
    var fg = document.getElementById('authForgot');
    if (t) t.textContent = isReset ? '重置密码' : (isReg ? '注册账号' : '手机号登录');
    if (d) d.textContent = isReset
      ? '填注册那个手机号，直接换个新密码'
      : (isReg
        ? '不用验证码，设个密码就能用'
        : '登录一下，问过的都给你留着');
    document.getElementById('authPwd2Box').hidden = !isNew;
    if (s) s.textContent = isReset ? '重置并登录' : (isReg ? '注册并登录' : '登录');
    if (sw) sw.innerHTML = isReset ? '想起密码了？<b>返回登录</b>'
      : (isReg ? '已有账号？<b>去登录</b>' : '还没有账号？<b>立即注册</b>');
    if (fg) fg.hidden = isReset;
    var sep = document.querySelector('.auth-links-sep');
    if (sep) sep.hidden = isReset;

    var p1 = document.getElementById('authPwd');
    if (p1) p1.setAttribute('autocomplete', isNew ? 'new-password' : 'current-password');
    var lb1 = document.getElementById('lbPwd');
    if (lb1) lb1.textContent = isReset ? '新密码' : (isReg ? '设置密码' : '密码');
    var lb2 = document.getElementById('lbPwd2');
    if (lb2) lb2.textContent = isReset ? '再输一次新密码' : '确认密码';

    var helpTxt = document.getElementById('pwdHelpTxt');
    if (helpTxt) helpTxt.textContent = isNew
      ? '至少 6 位，字母加数字更保险'
      : '密码 6-32 位，区分大小写';

    // 眼睛回到「隐藏」状态，避免切换模式时明文残留在屏幕上
    [['eyePwd', 'authPwd'], ['eyePwd2', 'authPwd2']].forEach(function (pair) {
      var b = document.getElementById(pair[0]);
      var i = document.getElementById(pair[1]);
      if (b && i && i.type === 'text') {
        i.type = 'password';
        b.classList.remove('on');
        b.setAttribute('aria-pressed', 'false');
      }
    });

    setFv('phone', ''); setFv('pwd', ''); setFv('pwd2', '');
    pwdPaint();
    if (authErrEl) authErrEl.textContent = '';
  }

  function authError(msg) {
    if (authErrEl) authErrEl.textContent = msg || '';
  }

  // 后端错误尽量归到具体那一格，归不进去才放到按钮下方
  function authErrorToField(msg) {
    if (!msg) return;
    var hasPhone = /手机号/.test(msg);
    var hasPwd = /密码/.test(msg);
    if (/频繁|次数过多|稍后再试/.test(msg)) { authError(msg); return; }
    if (/手机号或密码/.test(msg)) { authError(msg); return; }
    if (hasPhone) { setFv('phone', msg); return; }
    if (hasPwd) { setFv('pwd', msg); return; }
    authError(msg);
  }

  function initAuthForm() {
    bindEye('eyePwd', 'authPwd');
    bindEye('eyePwd2', 'authPwd2');

    // 失焦才校验；已经报过错的格子，输入时实时更新，别让人一边打字一边挨骂
    var pairs = [['authPhone', 'phone', vPhone], ['authPwd', 'pwd', vPwd], ['authPwd2', 'pwd2', vPwd2]];
    pairs.forEach(function (p) {
      var el = document.getElementById(p[0]);
      if (!el) return;
      el.addEventListener('blur', function () {
        setFv(p[1], p[2](AUTHV.tried));
      });
      el.addEventListener('input', function () {
        var box = document.getElementById(FV[p[1]].box);
        if (box && box.classList.contains('is-bad')) setFv(p[1], p[2](false));
        if (p[1] === 'pwd') {
          pwdPaint();
          // 第一个密码改过之后，确认框如果已经报错，跟着重新判断
          var g2 = document.getElementById('authPwd2Box');
          if (g2 && g2.classList.contains('is-bad')) setFv('pwd2', vPwd2(false));
        }
      });
    });

    pwdPaint();
  }

  var authSubmitting = false;

  function submitAuth() {
    if (authSubmitting) return;
    AUTHV.tried = true;
    var e1 = vPhone(true), e2 = vPwd(true), e3 = vPwd2(true);
    setFv('phone', e1); setFv('pwd', e2); setFv('pwd2', e3);
    if (e1) { document.getElementById('authPhone').focus(); return; }
    if (e2) { document.getElementById('authPwd').focus(); return; }
    if (e3) { document.getElementById('authPwd2').focus(); return; }
    authError('');

    var phone = av('authPhone').replace(/[^\d]/g, '');
    var pwd = av('authPwd');
    var btn = document.getElementById('authSubmit');
    var oldText = btn.textContent;
    authSubmitting = true;
    btn.disabled = true;
    btn.textContent = '处理中…';

    var authPath = AUTH.mode === 'register' ? 'register' : (AUTH.mode === 'reset' ? 'reset' : 'login');
    fetch('/api/auth/' + authPath, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ phone: phone, password: pwd, device_id: DEVICE_ID, src: detectSource() })
    }).then(function (r) {
      return r.json().then(function (d) { return { status: r.status, d: d }; });
    }).then(function (res) {
      if (res.status !== 200 || !res.d || res.d.error) {
        authErrorToField((res.d && res.d.error) || '登录失败，请稍后重试');
        return;
      }
      AUTH.user = res.d.user;
      setToken(res.d.token || '');
      document.getElementById('authPwd').value = '';
      document.getElementById('authPwd2').value = '';
      pwdPaint();
      dayWatch(res.d.day_end);
      hideLogin();
      enterApp();
    }).catch(function () {
      authError('网络异常，请检查网络后重试');
    }).then(function () {
      authSubmitting = false;
      btn.disabled = false;
      btn.textContent = oldText;
    });
  }


  function fmtDay(ts) {
    if (!ts) return '-';
    var d = new Date(ts * 1000);
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }

  // ============ 我的 · 个人主页 ============
  function toast(msg) {
    var el = document.getElementById('xcToast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'xcToast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.classList.remove('show'); }, 1900);
  }

  var AV_COLORS = ['lamp', 'moss', 'clay', 'slate', 'plum'];  var GENDER_TXT = { male: '男', female: '女', secret: '保密' };
  var CITIES = ['广东 · 深圳', '广东 · 广州', '上海', '北京', '四川 · 成都'];

  // 省 → 城市（两级，够填「所在地」用；不追求行政区划的完整层级）
  var LOC_RAW = [
    ['北京', '北京'], ['天津', '天津'], ['上海', '上海'], ['重庆', '重庆'],
    ['河北', '石家庄 唐山 秦皇岛 邯郸 邢台 保定 张家口 承德 沧州 廊坊 衡水'],
    ['山西', '太原 大同 阳泉 长治 晋城 朔州 晋中 运城 忻州 临汾 吕梁'],
    ['内蒙古', '呼和浩特 包头 乌海 赤峰 通辽 鄂尔多斯 呼伦贝尔 巴彦淖尔 乌兰察布'],
    ['辽宁', '沈阳 大连 鞍山 抚顺 本溪 丹东 锦州 营口 阜新 辽阳 盘锦 铁岭 朝阳 葫芦岛'],
    ['吉林', '长春 吉林 四平 辽源 通化 白山 松原 白城'],
    ['黑龙江', '哈尔滨 齐齐哈尔 鸡西 鹤岗 双鸭山 大庆 伊春 佳木斯 七台河 牡丹江 黑河 绥化'],
    ['江苏', '南京 无锡 徐州 常州 苏州 南通 连云港 淮安 盐城 扬州 镇江 泰州 宿迁'],
    ['浙江', '杭州 宁波 温州 嘉兴 湖州 绍兴 金华 衢州 舟山 台州 丽水'],
    ['安徽', '合肥 芜湖 蚌埠 淮南 马鞍山 淮北 铜陵 安庆 黄山 滁州 阜阳 宿州 六安 亳州 池州 宣城'],
    ['福建', '福州 厦门 莆田 三明 泉州 漳州 南平 龙岩 宁德'],
    ['江西', '南昌 景德镇 萍乡 九江 新余 鹰潭 赣州 吉安 宜春 抚州 上饶'],
    ['山东', '济南 青岛 淄博 枣庄 东营 烟台 潍坊 济宁 泰安 威海 日照 临沂 德州 聊城 滨州 菏泽'],
    ['河南', '郑州 开封 洛阳 平顶山 安阳 鹤壁 新乡 焦作 濮阳 许昌 漯河 三门峡 南阳 商丘 信阳 周口 驻马店'],
    ['湖北', '武汉 黄石 十堰 宜昌 襄阳 鄂州 荆门 孝感 荆州 黄冈 咸宁 随州'],
    ['湖南', '长沙 株洲 湘潭 衡阳 邵阳 岳阳 常德 张家界 益阳 郴州 永州 怀化 娄底'],
    ['广东', '广州 深圳 珠海 汕头 佛山 韶关 湛江 肇庆 江门 茂名 惠州 梅州 汕尾 河源 阳江 清远 东莞 中山 潮州 揭阳 云浮'],
    ['广西', '南宁 柳州 桂林 梧州 北海 防城港 钦州 贵港 玉林 百色 贺州 河池 来宾 崇左'],
    ['海南', '海口 三亚 儋州'],
    ['四川', '成都 自贡 攀枝花 泸州 德阳 绵阳 广元 遂宁 内江 乐山 南充 眉山 宜宾 广安 达州 雅安 巴中 资阳'],
    ['贵州', '贵阳 六盘水 遵义 安顺 毕节 铜仁'],
    ['云南', '昆明 曲靖 玉溪 保山 昭通 丽江 普洱 临沧 大理 西双版纳'],
    ['西藏', '拉萨 日喀则 昌都 林芝'],
    ['陕西', '西安 铜川 宝鸡 咸阳 渭南 延安 汉中 榆林 安康 商洛'],
    ['甘肃', '兰州 嘉峪关 金昌 白银 天水 武威 张掖 平凉 酒泉 庆阳 定西 陇南'],
    ['青海', '西宁 海东'],
    ['宁夏', '银川 石嘴山 吴忠 固原 中卫'],
    ['新疆', '乌鲁木齐 克拉玛依 吐鲁番 哈密 喀什 伊宁 阿克苏 库尔勒'],
    ['中国香港', '香港'], ['中国澳门', '澳门'], ['中国台湾', '台北 高雄 台中 台南']
  ];
  var LOC_DB = LOC_RAW.map(function (p) { return [p[0], p[1].split(' ')]; });
  var LOC = { open: false, mode: 'ac', items: [], idx: -1 };
  var LOC_ALL = null;

  function locLabel(p, c) { return p === c ? c : p + ' · ' + c; }

  function locAll() {
    if (LOC_ALL) return LOC_ALL;
    var out = [];
    for (var i = 0; i < LOC_DB.length; i++) {
      var p = LOC_DB[i][0];
      for (var j = 0; j < LOC_DB[i][1].length; j++) {
        var c = LOC_DB[i][1][j];
        out.push({ p: p, c: c, label: locLabel(p, c) });
      }
    }
    LOC_ALL = out;
    return out;
  }

  function locMatch(q) {
    q = (q || '').trim().replace(/[\s·]/g, '');
    if (!q) return [];
    var all = locAll(), hit = [];
    for (var i = 0; i < all.length; i++) {
      var it = all[i];
      var city = it.c.replace(/[\s·]/g, '');
      var key = it.label.replace(/[\s·]/g, '');
      var r = -1;
      if (city.indexOf(q) === 0) r = 0;
      else if (city.indexOf(q) > 0) r = 1;
      else if (key.indexOf(q) === 0) r = 2;
      else if (key.indexOf(q) > 0) r = 3;
      if (r >= 0) hit.push({ it: it, r: r, i: i });
    }
    hit.sort(function (a, b) { return a.r - b.r || a.i - b.i; });
    return hit.slice(0, 8).map(function (x) { return x.it; });
  }

  function locHl(text, q) {
    q = (q || '').trim().replace(/[\s·]/g, '');
    if (!q) return escapeHtml(text);
    var at = text.indexOf(q);
    if (at < 0) return escapeHtml(text);
    return escapeHtml(text.slice(0, at)) + '<mark>' + escapeHtml(text.slice(at, at + q.length)) + '</mark>'
      + escapeHtml(text.slice(at + q.length));
  }

  function locRenderAc(q) {
    var box = document.getElementById('locAc');
    if (!box) return;
    var list = locMatch(q);
    LOC.items = list; LOC.idx = -1;
    if (!q) { box.innerHTML = ''; return; }
    if (!list.length) {
      box.innerHTML = '<div class="loc-none">没有找到「' + escapeHtml(q) + '」。可以只输两个字，或点右侧按钮按省份选。</div>';
      return;
    }
    box.innerHTML = list.map(function (it, i) {
      var tag = it.p !== it.c ? it.p : (it.p.indexOf('中国') === 0 ? '特别行政区' : '直辖市');
      return '<button type="button" class="loc-item" role="option" data-loc="' + escapeHtml(it.label) + '">'
        + '<b>' + locHl(it.c, q) + '</b><em>' + tag + '</em></button>';
    }).join('');
  }

  function locRenderProv(sel) {
    var box = document.getElementById('locProv');
    if (!box) return;
    box.innerHTML = LOC_DB.map(function (p) {
      return '<button type="button" data-p="' + escapeHtml(p[0]) + '"'
        + (p[0] === sel ? ' class="on"' : '') + '>' + escapeHtml(p[0]) + '</button>';
    }).join('');
  }

  function locRenderCity(pName) {
    var box = document.getElementById('locCity');
    if (!box) return;
    var p = null;
    for (var i = 0; i < LOC_DB.length; i++) if (LOC_DB[i][0] === pName) { p = LOC_DB[i]; break; }
    if (!p) { box.innerHTML = ''; return; }
    box.innerHTML = '<div class="loc-hint">' + escapeHtml(pName) + ' · 选城市</div>'
      + p[1].map(function (c) {
        return '<button type="button" data-loc="' + escapeHtml(locLabel(p[0], c)) + '">' + escapeHtml(c) + '</button>';
      }).join('');
  }

  function locPick(label) {
    var inp = document.getElementById('pfInLoc');
    if (inp) inp.value = label;
    document.querySelectorAll('#pfCity button').forEach(function (b) {
      b.classList.toggle('on', b.dataset.city === label);
    });
    locClose();
  }

  function locClose() {
    var pop = document.getElementById('locPop');
    if (pop) pop.hidden = true;
    var casc = document.getElementById('locCasc');
    if (casc) { casc.classList.remove('on'); casc.setAttribute('aria-expanded', 'false'); }
    var inp = document.getElementById('pfInLoc');
    if (inp) inp.setAttribute('aria-expanded', 'false');
    LOC.open = false;
  }

  function locOpen(mode) {
    var pop = document.getElementById('locPop');
    var ac = document.getElementById('locAc');
    var cols = document.getElementById('locCols');
    var casc = document.getElementById('locCasc');
    var inp = document.getElementById('pfInLoc');
    if (!pop || !inp) return;
    var isCasc = mode === 'casc';
    pop.hidden = false;
    ac.hidden = isCasc;
    cols.hidden = !isCasc;
    casc.classList.toggle('on', isCasc);
    casc.setAttribute('aria-expanded', isCasc ? 'true' : 'false');
    inp.setAttribute('aria-expanded', 'true');
    if (isCasc) {
      var cur = (inp.value || '').trim();
      var sel = '';
      for (var i = 0; i < LOC_DB.length; i++) {
        if (LOC_DB[i][0] === cur || LOC_DB[i][1].indexOf(cur) >= 0) { sel = LOC_DB[i][0]; break; }
      }
      if (!sel && cur) {
        var hit = locMatch(cur)[0];
        if (hit) sel = hit.p;
      }
      sel = sel || LOC_DB[0][0];
      locRenderProv(sel);
      locRenderCity(sel);
      var onProv = document.querySelector('#locProv .on');
      if (onProv && onProv.scrollIntoView) onProv.scrollIntoView({ block: 'center' });
      if (pop.scrollIntoView) pop.scrollIntoView({ block: 'nearest' });
    } else {
      locRenderAc(inp.value);
    }
    LOC.open = true;
  }

  function initialOf(name) {
    name = (name || '宠').trim();
    return name ? name.slice(0, 1) : '宠';
  }

  function paintAvatar(box, imgEl, txtEl, name, avatar, color) {
    if (!box) return;
    var hasImg = !!avatar;
    box.setAttribute('data-color', AV_COLORS.indexOf(color) >= 0 ? color : 'lamp');
    if (imgEl) {
      if (hasImg) {
        imgEl.src = avatar;
        imgEl.hidden = false;
      } else {
        imgEl.removeAttribute('src');
        imgEl.hidden = true;
      }
    }
    if (txtEl) {
      txtEl.textContent = initialOf(name);
      txtEl.hidden = hasImg;
    }
  }

  function mineNo(uid) {
    // 编号给纯数字：字母混排读起来像乱码
    var s = (uid || '').replace(/[^0-9a-fA-F]/g, '');
    if (!s) return '0000';
    var n = parseInt(s.slice(-6), 16) % 10000;
    return ('0000' + n).slice(-4);
  }

  function sinceText(ts) {
    if (!ts) return '加入于 —';
    var d = new Date(ts * 1000);
    return '加入于 ' + d.getFullYear() + '.' + ('0' + (d.getMonth() + 1)).slice(-2);
  }

  function renderMine() {
    var u = AUTH.user;
    if (!u) return;
    var name = u.nickname || '宠友';
    var nameEl = document.getElementById('mineName');
    if (nameEl) nameEl.textContent = name;

    paintAvatar(document.getElementById('mineAvatar'),
                document.getElementById('pfAvImg'),
                document.getElementById('pfAvTxt'),
                name, u.avatar, u.avatar_color);

    var no = document.getElementById('pfNo');
    if (no) no.textContent = mineNo(u.uid);
    var sIn = document.getElementById('pfSince');
    if (sIn) sIn.textContent = sinceText(u.created);

    var gEl = document.getElementById('pfGender');
    if (gEl) {
      var g = u.gender || '';
      gEl.className = 'pf-chip g-' + (GENDER_TXT[g] ? g : 'secret');
      gEl.textContent = GENDER_TXT[g] || '性别未填';
    }
    var lEl = document.getElementById('pfLoc');
    if (lEl) {
      var loc = (u.location || '').trim();
      lEl.className = 'pf-chip' + (loc ? '' : ' p-empty');
      lEl.textContent = loc || '所在地未填';
    }
    var bioEl = document.getElementById('pfBio');
    if (bioEl) {
      var bio = (u.bio || '').trim();
      bioEl.className = 'pf-bio' + (bio ? '' : ' p-empty');
      bioEl.textContent = bio || '还没写。写一句你养的是什么。';
    }

    var ph = document.getElementById('acctPhone');
    if (ph) ph.textContent = u.phone_masked || '微信授权登录';
    var cr = document.getElementById('acctCreated');
    if (cr) cr.textContent = fmtDay(u.created);
    var qn = document.getElementById('acctAsks');
    if (qn) qn.textContent = u.questions || 0;
    var qs = document.getElementById('acctAsksNum');
    if (qs) qs.textContent = (u.questions || 0) + ' 次';
    var days = document.getElementById('pfDays');
    if (days) days.textContent = u.created ? Math.max(1, Math.floor((Date.now() / 1000 - u.created) / 86400) + 1) : 1;

    // 在养档案数：懒加载一次，失败不影响主页
    var petsEl = document.getElementById('pfPets');
    if (petsEl && !renderMine._pets) {
      renderMine._pets = true;
      api('/api/pets').then(function (r) { return r.json(); }).then(function (d) {
        petsEl.textContent = ((d && d.items) || []).length;
      }).catch(function () {});
    }
  }

  // ---------- 资料编辑 ----------
  // img：本次新选的图（dataURL，保存时才上传）；photo：账号上已有的头像；usePhoto：是否继续用照片
  var PF = { img: '', photo: '', usePhoto: false, color: 'lamp', gender: 'secret', saving: false, geo: '' };

  function pfSetMsg(t) {
    var el = document.getElementById('pfMsg');
    if (el) el.textContent = t || '';
  }

  function pfPaintPreview() {
    var name = (document.getElementById('pfInName').value || '').trim();
    paintAvatar(document.getElementById('pfPrev'),
                document.getElementById('pfPrevImg'),
                document.getElementById('pfPrevTxt'),
                name || '宠', PF.img || (PF.usePhoto ? PF.photo : ''), PF.color);
    var dc = document.getElementById('pfNameCnt');
    if (dc) dc.textContent = name.length;
    var bv = document.getElementById('pfInBio').value || '';
    var bc = document.getElementById('pfBioCnt');
    if (bc) bc.textContent = bv.length;
  }

  function pfSelectColor(c) {
    PF.color = c;
    PF.img = ''; PF.usePhoto = false;   // 选底色＝不用照片
    document.querySelectorAll('#pfPresets .pf-dot').forEach(function (d) {
      d.classList.toggle('on', d.dataset.color === c);
    });
    pfPaintPreview();
  }

  function openProfile() {
    var u = AUTH.user;
    if (!u) return;
    PF.img = '';
    PF.color = AV_COLORS.indexOf(u.avatar_color) >= 0 ? u.avatar_color : 'lamp';
    PF.gender = GENDER_TXT[u.gender] ? u.gender : 'secret';

    document.getElementById('pfInName').value = u.nickname || '';
    document.getElementById('pfInBio').value = u.bio || '';
    document.getElementById('pfInLoc').value = u.location || '';

    document.querySelectorAll('#pfPresets .pf-dot').forEach(function (d) {
      d.classList.toggle('on', d.dataset.color === PF.color);
    });
    document.querySelectorAll('#pfSeg button').forEach(function (b) {
      b.classList.toggle('on', b.dataset.g === PF.gender);
    });
    // 已有头像（本地上传的或微信的）先原样显示，用户点色块才换成首字头像
    PF.img = '';
    PF.photo = u.avatar || '';
    PF.usePhoto = !!PF.photo;
    if (PF.usePhoto) {
      document.querySelectorAll('#pfPresets .pf-dot').forEach(function (d) { d.classList.remove('on'); });
    }

    var geoBox = document.getElementById('pfGeo');
    var geoTxt = document.getElementById('pfGeoCity');
    if (geoBox && geoTxt) {
      var show = PF.geo && PF.geo !== u.location;
      geoBox.classList.toggle('show', !!show);
      geoTxt.textContent = PF.geo || '';
    }
    document.querySelectorAll('#pfCity button').forEach(function (b) {
      b.classList.toggle('on', b.dataset.city === (u.location || ''));
    });

    pfSetMsg('');
    pfPaintPreview();
    document.getElementById('pfMask').classList.add('show');
    setTimeout(function () {
      var el = document.getElementById('pfInName');
      if (el) el.focus();
    }, 240);
  }

  function closeProfile() {
    document.getElementById('pfMask').classList.remove('show');
  }

  // 相册图先在本地裁成 1:1、缩到 320，再上传；别指望后端替你处理 8MB 的原图
  function pfPickImage(file) {
    if (!file) return;
    if (!/^image\//.test(file.type)) { pfSetMsg('请选一张图片'); return; }
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () {
        var s = Math.min(img.width, img.height);
        var cv = document.createElement('canvas');
        cv.width = cv.height = 320;
        var ctx = cv.getContext('2d');
        ctx.drawImage(img, (img.width - s) / 2, (img.height - s) / 2, s, s, 0, 0, 320, 320);
        PF.img = cv.toDataURL('image/jpeg', 0.86);
        PF.usePhoto = true;
        document.querySelectorAll('#pfPresets .pf-dot').forEach(function (d) { d.classList.remove('on'); });
        pfPaintPreview();
        pfSetMsg('');
      };
      img.onerror = function () { pfSetMsg('这张图读不出来，换一张试试'); };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  }

  function pfSave() {
    if (PF.saving) return;
    var name = (document.getElementById('pfInName').value || '').trim();
    if (!name) { pfSetMsg('昵称不能为空'); return; }
    var bio = (document.getElementById('pfInBio').value || '').trim();
    var loc = (document.getElementById('pfInLoc').value || '').trim();
    var btn = document.getElementById('pfSave');
    PF.saving = true;
    if (btn) { btn.disabled = true; btn.textContent = '保存中…'; }

    var body = { nickname: name, bio: bio, gender: PF.gender, location: loc,
                 avatar_color: PF.color, avatar_clear: !(PF.usePhoto || PF.img) };
    api('/api/auth/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.error) throw new Error(d.error);
      if (d && d.user) AUTH.user = d.user;
      if (!PF.img) return null;
      return api('/api/auth/avatar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: PF.img })
      }).then(function (r) { return r.json(); }).then(function (a) {
        if (a && a.error) throw new Error(a.error);
        if (a && a.user) AUTH.user = a.user;
        return null;
      });
    }).then(function () {
      renderMine();
      closeProfile();
      toast('资料已更新');
    }).catch(function (e) {
      pfSetMsg((e && e.message) || '保存失败，稍后再试');
    }).then(function () {
      PF.saving = false;
      if (btn) { btn.disabled = false; btn.textContent = '保存资料'; }
    });
  }

  function initProfile() {
    var cityBox = document.getElementById('pfCity');
    if (cityBox) {
      cityBox.innerHTML = CITIES.map(function (c) {
        return '<button type="button" data-city="' + escapeHtml(c) + '">' + escapeHtml(c.replace(' · ', ' ')) + '</button>';
      }).join('');
      cityBox.addEventListener('click', function (e) {
        var b = e.target.closest('[data-city]');
        if (b) locPick(b.dataset.city);
      });
    }

    var locIn = document.getElementById('pfInLoc');
    if (locIn) {
      locIn.addEventListener('focus', function () {
        // 空值时先不铺面板，避免键盘和面板同时弹；有内容则直接给候选
        if (!(locIn.value || '').trim()) return;
        locOpen('ac');
        locRenderAc(locIn.value);
      });
      locIn.addEventListener('input', function () {
        locOpen('ac');
        locRenderAc(locIn.value);
      });
      locIn.addEventListener('keydown', function (e) {
        if (!LOC.open) return;
        var items = LOC.items || [];
        if (!items.length) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault();
          LOC.idx += (e.key === 'ArrowDown' ? 1 : -1);
          if (LOC.idx < 0) LOC.idx = items.length - 1;
          if (LOC.idx >= items.length) LOC.idx = 0;
          var btns = document.querySelectorAll('#locAc .loc-item');
          btns.forEach(function (b, i) { b.classList.toggle('on', i === LOC.idx); });
          if (btns[LOC.idx] && btns[LOC.idx].scrollIntoView) btns[LOC.idx].scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter' && LOC.idx >= 0) {
          e.preventDefault();
          locPick(items[LOC.idx].label);
        } else if (e.key === 'Escape') {
          locClose();
        }
      });
      // 面板收起交给 document 的 click 判断：手机上 blur 先于 click，
      // 在 blur 里关会把刚点到的省份/城市一起吞掉。
    }

    var casc = document.getElementById('locCasc');
    if (casc) {
      casc.addEventListener('click', function () {
        var cols = document.getElementById('locCols');
        if (LOC.open && cols && !cols.hidden) { locClose(); return; }
        locOpen('casc');
        if (locIn) locIn.blur();   // 收起键盘，给两列腾地方
      });
    }

    var pop = document.getElementById('locPop');
    if (pop) {
      pop.addEventListener('click', function (e) {
        e.stopPropagation();   // 面板内部点击不交给下面的「点外部关闭」
        var prov = e.target.closest('#locProv [data-p]');
        if (prov) {
          var name = prov.dataset.p;
          locRenderProv(name);
          var p = null;
          for (var i = 0; i < LOC_DB.length; i++) if (LOC_DB[i][0] === name) { p = LOC_DB[i]; break; }
          if (p && p[1].length === 1) { locPick(locLabel(p[0], p[1][0])); return; }
          locRenderCity(name);
          return;
        }
        var b = e.target.closest('[data-loc]');
        if (b) locPick(b.dataset.loc);
      });
    }

    document.addEventListener('click', function (e) {
      if (!LOC.open) return;
      // 面板重绘后旧节点已脱离文档，closest 找不到祖先，别误判成「点了外面」
      if (e.target && e.target.isConnected === false) return;
      if (e.target.closest && e.target.closest('#pfLocField')) return;
      locClose();
    });

    ['mineEditBtn', 'mineEditTop'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('click', openProfile);
    });
    var cl = document.getElementById('pfClose');
    if (cl) cl.addEventListener('click', closeProfile);
    var mask = document.getElementById('pfMask');
    if (mask) mask.addEventListener('click', function (e) { if (e.target === mask) closeProfile(); });

    var pick = document.getElementById('pfPick');
    var file = document.getElementById('pfFile');
    if (pick && file) {
      pick.addEventListener('click', function () { file.click(); });
      file.addEventListener('change', function () {
        pfPickImage(file.files && file.files[0]);
        file.value = '';
      });
    }

    var presets = document.getElementById('pfPresets');
    if (presets) {
      presets.addEventListener('click', function (e) {
        var d = e.target.closest('[data-color]');
        if (d) pfSelectColor(d.dataset.color);
      });
    }

    var seg = document.getElementById('pfSeg');
    if (seg) {
      seg.addEventListener('click', function (e) {
        var b = e.target.closest('[data-g]');
        if (!b) return;
        PF.gender = b.dataset.g;
        seg.querySelectorAll('button').forEach(function (x) {
          x.classList.toggle('on', x === b);
        });
      });
    }

    var nm = document.getElementById('pfInName');
    var bio = document.getElementById('pfInBio');
    if (nm) nm.addEventListener('input', pfPaintPreview);
    if (bio) bio.addEventListener('input', pfPaintPreview);

    var save = document.getElementById('pfSave');
    if (save) save.addEventListener('click', pfSave);

    var gu = document.getElementById('pfGeoUse');
    if (gu) {
      gu.addEventListener('click', function () {
        if (!PF.geo) return;
        document.getElementById('pfInLoc').value = PF.geo;
      });
    }
  }

  function initSessions() {
    sessions = loadSessions();
    var nonEmpty = sessions.filter(function (s) { return s.messages && s.messages.length > 0; });
    if (nonEmpty.length !== sessions.length) {
      sessions = nonEmpty;
      saveSessions();
    }
    sessions.sort(function (a, b) { return (b.updatedAt || 0) - (a.updatedAt || 0); });
    if (sessions.length > 0) {
      openSession(sessions[0].id);
    } else {
      currentId = null;
      history = [];
      messagesEl.innerHTML = '';
      welcomeEl.style.display = '';
      updateWelcome();
      renderSessionList();
    }
  }

  // ============ 使用时长 ============
  // 只算「页面在前台、且最近三分钟动过」的时间。挂在后台的标签页不计，
  // 否则一个放一整天不关的窗口能把「使用时长」刷成几十小时。
  var USE = { acc: 0, lastTick: 0, lastAct: 0, timer: 0 };

  function useTouch() { USE.lastAct = Date.now(); }

  function useVis() {
    if (document.hidden) { useFlush(); return; }
    // 从后台切回来时先看有没有跨过零点：浏览器后台会把定时器压到很慢
    if (DAY.end && Date.now() >= DAY.end) { sessionExpired('已过夜里 12 点，请重新登录'); return; }
    USE.lastTick = Date.now();
    USE.lastAct = Date.now();
  }

  function useTick() {
    var now = Date.now();
    var dt = now - (USE.lastTick || now);
    USE.lastTick = now;
    if (document.hidden || now - USE.lastAct > 180000) return;
    USE.acc += Math.min(dt, 30000);
    if (USE.acc >= 30000) useFlush();
  }

  function useFlush() {
    if (USE.acc < 5000 || !AUTH.user) { USE.acc = 0; return; }
    var sec = Math.round(USE.acc / 1000);
    USE.acc = 0;
    var payload = JSON.stringify({ seconds: sec });
    // 关页面时 fetch 会被掐断，优先走 sendBeacon；它带不了自定义头，靠 cookie 认人
    if (navigator.sendBeacon) {
      try {
        if (navigator.sendBeacon('/api/usage/ping', new Blob([payload], { type: 'application/json' }))) return;
      } catch (e) {}
    }
    try {
      fetch('/api/usage/ping', {
        method: 'POST', body: payload, credentials: 'same-origin', keepalive: true,
        headers: { 'Content-Type': 'application/json', 'X-Token': AUTH.token || '' }
      });
    } catch (e) {}
  }

  function useStart() {
    if (USE.timer) return;
    USE.lastTick = Date.now();
    USE.lastAct = Date.now();
    USE.acc = 0;
    USE.timer = setInterval(useTick, 20000);
    ['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach(function (ev) {
      document.addEventListener(ev, useTouch, { passive: true });
    });
    document.addEventListener('visibilitychange', useVis);
    window.addEventListener('pagehide', useFlush);
  }

  function useStop() {
    useFlush();
    if (USE.timer) { clearInterval(USE.timer); USE.timer = 0; }
    document.removeEventListener('visibilitychange', useVis);
    window.removeEventListener('pagehide', useFlush);
  }

  // ============ 每日零点重置登录 ============
  // 登录态只保当天有效：服务端令牌里带签发日，过了夜里 12 点就认不出人。
  // 前端这边提前收摊，省得用户点了才被 401 弹回去；收摊前先把攒下的时长报掉。
  var DAY = { end: 0, timer: 0, guard: 0 };

  function dayWatchStop() {
    if (DAY.timer) { clearTimeout(DAY.timer); DAY.timer = 0; }
    if (DAY.guard) { clearInterval(DAY.guard); DAY.guard = 0; }
    DAY.end = 0;
  }

  function dayWatch(dayEnd) {
    dayWatchStop();
    if (!dayEnd) return;
    // 以服务端给的「今天 24:00」为准，不看本机时区，手机时间调过也不影响
    DAY.end = dayEnd * 1000;
    var left = DAY.end - Date.now();
    if (left <= 0) { sessionExpired('已过夜里 12 点，请重新登录'); return; }
    DAY.timer = setTimeout(function () {
      // 零点前 10 秒先报时长：过了零点这个令牌就作废了，报也报不上去
      useFlush();
      var wait = Math.max(0, DAY.end - Date.now()) + 1500;
      DAY.timer = setTimeout(function () {
        sessionExpired('已过夜里 12 点，请重新登录');
      }, wait);
    }, Math.max(0, left - 10000));
    // 兜底：标签页挂后台时定时器会被浏览器掐，回前台或每分钟核对一次
    DAY.guard = setInterval(function () {
      if (DAY.end && Date.now() >= DAY.end) sessionExpired('已过夜里 12 点，请重新登录');
    }, 60000);
  }

  function sessionExpired(msg) {
    dayWatchStop();
    if (!AUTH.user) { showLogin(msg); return; }
    useStop();
    // 顺手把服务端 cookie 也清掉：Token 已经过期，但 cookie 还赖在浏览器里，
    // 不清的话下次打开还会带着它多跑一趟 401
    try { fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); } catch (e) {}
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    sending = false;
    AUTH.user = null;
    setToken('');
    sessions = [];
    currentId = null;
    history = [];
    if (messagesEl) messagesEl.innerHTML = '';
    if (welcomeEl) welcomeEl.style.display = '';
    booted = false;
    showLogin(msg);
  }

  function enterApp() {
    renderMine();
    useStart();
    if (booted) { switchView(currentView || 'chat'); return; }
    booted = true;
    trackVisit();
    renderFAQ();
    loadCompliance();
    loadNews(renderTicker);
    initSessions();
    loadAppStatus();
    refreshServiceDot();
    resumePendingTask();
    prefetchViews();
  }

  // 首屏空下来之后悄悄把图鉴列表拉回来：点进图鉴不用再等一次请求。
  // 图片全是 loading="lazy"，隐藏容器里的缩略图不会提前下载，不占带宽。
  function prefetchViews() {
    var run = function () {
      if (!DEX.loaded) dexLoad();
    };
    if (window.requestIdleCallback) {
      requestIdleCallback(run, { timeout: 2500 });
    } else {
      setTimeout(run, 1200);
    }
  }

  function checkAuth() {
    bootStep(58);
    return fetch('/api/auth/me', {
      headers: AUTH.token ? { 'X-Token': AUTH.token } : {},
      credentials: 'same-origin'
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.logged_in) {
        AUTH.user = d.user;
        PF.geo = d.user.hint_loc || '';
        if (d.token) setToken(d.token);
        bootStep(86);
        dayWatch(d.day_end);
        hideLogin();
        enterApp();
      } else {
        AUTH.user = null;
        setToken('');
        bootStep(86);
        // 昨天登录的人今天打开，直接说明原因，别让人以为密码出了问题
        showLogin(d && d.reason === 'newday' ? '已过夜里 12 点，请重新登录'
          : (d && d.reason === 'invalid' ? '登录状态已失效，请重新登录' : ''));
      }
    }).catch(function () {
      showLogin('网络异常，请检查网络后重试');
    });
  }

  function logout() {
    useStop();
    dayWatchStop();
    try { fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); } catch (e) {}
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    sending = false;
    AUTH.user = null;
    setToken('');
    sessions = [];
    currentId = null;
    history = [];
    if (messagesEl) messagesEl.innerHTML = '';
    if (welcomeEl) welcomeEl.style.display = '';
    clearPendingTask();
    booted = false;
    showLogin('已退出登录');
  }

  function initAuth() {
    document.getElementById('authSubmit').addEventListener('click', submitAuth);
    initAuthForm();
    document.getElementById('authSwitch').addEventListener('click', function (e) {
      if (e.target && e.target.tagName === 'B') {
        setAuthMode(AUTH.mode === 'login' ? 'register' : 'login');
      }
    });
    var forgot = document.getElementById('authForgot');
    if (forgot) forgot.addEventListener('click', function () { setAuthMode('reset'); });
    ['authPhone', 'authPwd', 'authPwd2'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('keydown', function (e) { if (e.key === 'Enter') submitAuth(); });
    });
    document.getElementById('authWechat').addEventListener('click', function () {
      location.href = '/api/wx/login';
    });
    document.getElementById('btnLogout').addEventListener('click', function () {
      if (window.confirm('确定要退出登录吗？')) logout();
    });
    document.getElementById('btnChangePwd').addEventListener('click', function () {
      var f = document.getElementById('pwdForm');
      f.hidden = !f.hidden;
      if (!f.hidden) document.getElementById('pwdOld').focus();
    });
    document.getElementById('pwdSubmit').addEventListener('click', changePassword);
    // 微信登录方式由后端配置决定是否展示
    fetch('/api/auth/config').then(function (r) { return r.json(); }).then(function (c) {
      if (c && c.wechat_login) document.getElementById('authWechat').classList.add('show');
    }).catch(function () {});
  }

  function changePassword() {
    var oldPwd = document.getElementById('pwdOld').value || '';
    var newPwd = document.getElementById('pwdNew').value || '';
    var newPwd2 = document.getElementById('pwdNew2').value || '';
    if (!oldPwd || !newPwd) { alert('请填写原密码与新密码'); return; }
    if (newPwd.length < 6) { alert('新密码至少 6 位'); return; }
    if (newPwd !== newPwd2) { alert('两次输入的新密码不一致'); return; }
    api('/api/auth/password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.error) { alert(d.error); return; }
      alert('密码修改成功');
      document.getElementById('pwdOld').value = '';
      document.getElementById('pwdNew').value = '';
      document.getElementById('pwdNew2').value = '';
      document.getElementById('pwdForm').hidden = true;
    }).catch(function (e) {
      if (!e.unauthorized) alert('网络异常，请稍后重试');
    });
  }

  function loadSessions() {
    var key = sessionsKey();
    try {
      var raw = localStorage.getItem(key);
      if (!raw && AUTH.user && AUTH.user.uid) {
        // 首次登录：把登录前留在本机的对话迁移到当前账号下，避免历史丢失
        raw = localStorage.getItem(LS_KEY);
        if (raw) {
          localStorage.setItem(key, raw);
          localStorage.removeItem(LS_KEY);
        }
      }
      if (!raw) return [];
      var arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      return arr.filter(function (s) { return s && s.id && Array.isArray(s.messages); });
    } catch (e) { return []; }
  }
  function saveSessions() {
    try {
      if (sessions.length > MAX_SESSIONS) sessions = sessions.slice(0, MAX_SESSIONS);
      localStorage.setItem(sessionsKey(), JSON.stringify(sessions));
    } catch (e) {}
  }
  function findSession(id) {
    for (var i = 0; i < sessions.length; i++) if (sessions[i].id === id) return sessions[i];
    return null;
  }
  function makeTitle(messages) {
    for (var i = 0; i < messages.length; i++) {
      if (messages[i].role === 'user') {
        var t = messages[i].content.replace(/\s+/g, ' ').trim();
        if (t) return t.length > 16 ? t.slice(0, 16) + '…' : t;
      }
    }
    return '新对话';
  }
  function fmtTime(ts) {
    var d = new Date(ts);
    var now = new Date();
    var hh = ('0' + d.getHours()).slice(-2);
    var mm = ('0' + d.getMinutes()).slice(-2);
    if (d.toDateString() === now.toDateString()) return '今天 ' + hh + ':' + mm;
    return (d.getMonth() + 1) + '/' + d.getDate() + ' ' + hh + ':' + mm;
  }
  function persistSession() {
    if (!currentId) return;
    var s = findSession(currentId);
    if (!s) return;
    s.messages = history.slice();
    s.title = makeTitle(history);
    s.updatedAt = Date.now();
    sessions = sessions.filter(function (x) { return x.id !== currentId; });
    sessions.unshift(s);
    saveSessions();
    renderSessionList();
  }
  function renderSessionList() {
    sessionListEl.innerHTML = '';
    if (sessions.length === 0) {
      sessionListEl.innerHTML = '<div class="sidebar-empty">还没聊过</div>';
      return;
    }
    sessions.forEach(function (s) {
      var item = document.createElement('div');
      item.className = 'sidebar-item' + (s.id === currentId ? ' active' : '');
      item.dataset.id = s.id;
      var body = document.createElement('div');
      body.className = 'sidebar-item-main';
      var title = document.createElement('div');
      title.className = 'sidebar-item-title';
      title.textContent = s.title || '新对话';
      var time = document.createElement('div');
      time.className = 'sidebar-item-time';
      time.textContent = fmtTime(s.updatedAt || Date.now());
      body.appendChild(title);
      body.appendChild(time);
      var del = document.createElement('button');
      del.className = 'sidebar-item-del';
      del.dataset.id = s.id;
      del.setAttribute('aria-label', '删除');
      del.textContent = '×';
      item.appendChild(body);
      item.appendChild(del);
      sessionListEl.appendChild(item);
    });
  }
  function updateWelcome() {
    welcomeEl.style.display = (history.length === 0) ? '' : 'none';
  }
  function renderMessages() {
    messagesEl.innerHTML = '';
    rawBuffer = '';
    for (var i = 0; i < history.length; i++) {
      appendMessage(history[i].role, history[i].content, i, false);
    }
    scrollBottom();
  }
  function openSession(id) {
    var s = findSession(id);
    if (!s) return;
    currentId = id;
    history = s.messages.slice();
    editingIdx = null;
    rawBuffer = '';
    input.value = '';
    editingHint.classList.remove('show');
    renderMessages();
    updateWelcome();
    renderSessionList();
  }
  function switchSession(id) {
    if (id === currentId) { closeSidebar(); return; }
    openSession(id);
    closeSidebar();
  }
  function newSession() {
    // 懒创建：不立即持久化空会话，只有真正发出第一条消息时才建会话，避免刷新出现多余"新对话"
    currentId = null;
    history = [];
    editingIdx = null;
    rawBuffer = '';
    input.value = '';
    editingHint.classList.remove('show');
    messagesEl.innerHTML = '';
    updateWelcome();
    renderSessionList();
    closeSidebar();
  }
  function deleteSession(id) {
    sessions = sessions.filter(function (s) { return s.id !== id; });
    saveSessions();
    if (currentId === id) {
      if (sessions.length > 0) {
        openSession(sessions[0].id);
      } else {
        currentId = null;
        history = [];
        editingIdx = null;
        rawBuffer = '';
        input.value = '';
        editingHint.classList.remove('show');
        messagesEl.innerHTML = '';
        updateWelcome();
      }
    }
    renderSessionList();
  }
  function clearAllSessions() {
    sessions = [];
    currentId = null;
    history = [];
    editingIdx = null;
    rawBuffer = '';
    input.value = '';
    editingHint.classList.remove('show');
    messagesEl.innerHTML = '';
    updateWelcome();
    saveSessions();
    renderSessionList();
  }

  // ============ 侧边栏开关 ============
  function openSidebar() {
    renderSessionList();
    sidebar.classList.add('open');
    sidebarMask.classList.add('show');
  }
  function closeSidebar() {
    sidebar.classList.remove('open');
    sidebarMask.classList.remove('show');
  }

  // ============ 视图切换 ============
  function switchView(name) {
    // 兜底：没有任何视图应该在未登录状态下被打开
    if (!AUTH.user) { showLogin(''); return; }
    document.getElementById('view-chat').hidden = (name !== 'chat');
    document.getElementById('view-compliance').hidden = (name !== 'compliance');
    document.getElementById('view-dex').hidden = (name !== 'dex');
    document.getElementById('view-news').hidden = (name !== 'news');
    document.getElementById('view-care').hidden = (name !== 'care');
    document.getElementById('view-mine').hidden = (name !== 'mine');
    document.querySelectorAll('.tab').forEach(function (t) {
      t.classList.toggle('active', t.dataset.view === name);
    });
    currentView = name;
    if (name === 'chat') { clearAnswerBadge(); hideAnswerToast(); }
    else if (sending) { showAnswerBadge('answering'); }
    // 动态条只在问答页滚动，切走就停，不白耗电
    if (typeof startTicker === 'function') { if (name === 'chat') startTicker(); else stopTicker(); }
    if (name === 'dex') dexEnter();
    if (name === 'compliance') renderCompliance();
    if (name === 'news') renderNews();
    if (name === 'care') careRefresh();
    if (name === 'mine') renderMine();
  }

  // ============ 异宠图鉴 ============
  var DEX = { items: [], groups: [], group: '全部', q: '', loaded: false, total: 0, all: 0,
              scope: 'keep', keepN: 0, noN: 0, cur: null, seq: 0, dseq: 0 };

  function dexEnter() {
    dexShowList();
    if (!DEX.loaded) dexLoad(); else dexPaint();
  }

  function dexHeadTxt() {
    var sub = document.getElementById('dexSub');
    if (!sub) return;
    if (DEX.scope === 'no') {
      sub.textContent = (DEX.noN ? DEX.noN + ' 种不能养' : '这些不能养') + '，认出来别买';
    } else {
      sub.textContent = (DEX.keepN ? DEX.keepN + ' 种能养' : '能养的') + '，都有实拍';
    }
  }

  function dexShowList() {
    var lw = document.getElementById('dexListWrap');
    var dw = document.getElementById('dexDetailWrap');
    if (!lw || !dw) return;
    lw.hidden = false; dw.hidden = true;
    DEX.dseq++;   // 详情还没回来就返回时，别再把详情塞回来
    document.getElementById('dexBack').hidden = true;
    document.getElementById('dexTitle').textContent = '异宠图鉴';
    dexHeadTxt();
  }

  function dexLoad() {
    // 连打搜索词时，先发的请求可能后回来；只认最后一次，避免旧结果盖掉新结果
    var seq = ++DEX.seq;
    var url = '/api/dex?scope=' + DEX.scope
      + '&group=' + encodeURIComponent(DEX.group)
      + '&q=' + encodeURIComponent(DEX.q);
    api(url).then(function (r) { return r.json(); }).then(function (d) {
      if (seq !== DEX.seq) return;
      DEX.items = (d && d.items) || [];
      DEX.groups = (d && d.groups) || [];
      DEX.total = (d && d.total) || 0;
      DEX.all = (d && d.all) || 0;
      var c = (d && d.counts) || {};
      if (c.keep != null) DEX.keepN = c.keep;
      if (c.no != null) DEX.noN = c.no;
      DEX.loaded = true;
      dexPaint();
      dexHeadTxt();
    }).catch(function () {});
  }

  function dexCreditTxt(c) {
    if (!c) return '照片来自 iNaturalist 公开图库';
    var m = /\(c\)\s*(.+?)[,，]\s*some rights reserved.*?\((CC[^)]+)\)/i.exec(c);
    if (m) return '照片：' + m[1].trim() + ' · ' + m[2].toUpperCase() + '（署名 / 非商业）';
    return '照片：' + c;
  }

  function dexSizeShort(s) {
    return String(s || '').replace(/^成体\s*/, '').replace(/（.*?）/g, '').trim();
  }

  function dexPaint() {
    var sc = document.getElementById('dexScope');
    if (sc) {
      Array.prototype.forEach.call(sc.querySelectorAll('[data-scope]'), function (b) {
        b.classList.toggle('on', b.dataset.scope === DEX.scope);
      });
      var kn = document.getElementById('dexKeepN');
      var nn = document.getElementById('dexNoN');
      if (kn) kn.textContent = DEX.keepN ? DEX.keepN : '';
      if (nn) nn.textContent = DEX.noN ? DEX.noN : '';
    }

    var chips = document.getElementById('dexGroups');
    if (chips) {
      var gs = DEX.groups.length ? DEX.groups : ['全部'];
      chips.innerHTML = gs.map(function (g) {
        return '<button class="dex-chip' + (g === DEX.group ? ' on' : '') + '" data-g="'
          + escapeHtml(g) + '">' + escapeHtml(g) + '</button>';
      }).join('');
    }

    var note = document.getElementById('dexNote');
    if (note) {
      note.textContent = DEX.scope === 'no'
        ? '这里列的，要么是国家重点保护野生动物，要么在 CITES 附录里、得有专用标识。个人无证养、买卖、甚至寄个快递都算违法。写出来是让你认得出、别被人忽悠着买，不是教你怎么养。地方名录可能更严，拿不准就问当地林草或农业农村部门。'
        : '这里的温湿度是成体常规值。幼体、繁殖期、冬化期都得另调，同一窝里个体差别也不小。照片来自公开图库，只帮你认物种。标了「需凭证」的，记得跟卖家要人工繁育证明或专用标识，拿不出来源的别接。';
    }

    var box = document.getElementById('dexList');
    if (!box) return;
    if (!DEX.items.length) {
      box.innerHTML = DEX.scope === 'no'
        ? '<div class="dex-empty">这一类里没有收录禁养物种。</div>'
        : '<div class="dex-empty">没有匹配的物种。<br>换个说法试试，比如「守宫」「玉米蛇」「角蛙」。</div>';
      return;
    }

    if (DEX.scope === 'no') {
      box.innerHTML = DEX.items.map(function (it) {
        return '<button class="dex-card ban" data-k="' + escapeHtml(it.k) + '">'
          + '<div class="dex-ban-wrap"><img class="dex-ph" src="' + escapeHtml(it.thumb || it.img) + '" alt="'
          + escapeHtml(it.name) + '" loading="lazy" decoding="async"><span class="dex-ban-tag">禁止饲养</span></div>'
          + '<div class="dex-body"><div class="dex-name">' + escapeHtml(it.name) + '</div>'
          + '<div class="dex-latin">' + escapeHtml(it.latin) + '</div>'
          + '<div class="dex-tags"><span class="dex-tag">' + escapeHtml(it.group) + '</span>'
          + '<span class="dex-law">' + escapeHtml(it.short || '') + '</span></div></div></button>';
      }).join('');
      return;
    }

    box.innerHTML = DEX.items.map(function (it) {
      var lv = it.level === 1 ? '易上手' : (it.level === 2 ? '要功课' : '进阶');
      return '<button class="dex-card" data-k="' + escapeHtml(it.k) + '">'
        + '<img class="dex-ph" src="' + escapeHtml(it.thumb || it.img) + '" alt="' + escapeHtml(it.name) + '" loading="lazy" decoding="async">'
        + '<div class="dex-body"><div class="dex-name">' + escapeHtml(it.name) + '</div>'
        + '<div class="dex-latin">' + escapeHtml(it.latin) + '</div>'
        + '<div class="dex-tags"><span class="dex-tag">' + escapeHtml(dexSizeShort(it.size)) + '</span>'
        + '<span class="dex-lv l' + it.level + '">' + lv + '</span></div></div></button>';
    }).join('');
  }

  function dexOpen(k) {
    var lw = document.getElementById('dexListWrap');
    var dw = document.getElementById('dexDetailWrap');
    var el = document.getElementById('dexDetail');
    if (!dw || !el) return;
    // 连点两张卡时只渲染最后点的那张
    var seq = ++DEX.dseq;
    lw.hidden = true; dw.hidden = false;
    document.getElementById('dexBack').hidden = false;
    dw.scrollTop = 0;
    el.innerHTML = '<div class="dex-empty">读取中…</div>';
    api('/api/dex/' + encodeURIComponent(k)).then(function (r) { return r.json(); }).then(function (d) {
      if (seq !== DEX.dseq) return;
      if (!d || !d.item) { el.innerHTML = '<div class="dex-empty">没找到这个物种</div>'; return; }
      DEX.cur = d.item;
      if (d.item.keep === false) dexPaintBan(d.item); else dexPaintDetail(d.item);
    }).catch(function () {});
  }

  function dexLegalTag(it) {
    if (it.legal === 'doc') {
      return '<div class="dex-sec" style="background:rgba(138,106,31,.05)">'
        + '<h4 style="color:#8A6A1F">合规提示 · 需凭证</h4>'
        + '<p>这个物种可以养，但要能说明来源合法：向卖家索取人工繁育证明、专用标识或正规票据。'
        + '拿不出来源的个体，无论多便宜都别接。</p></div>';
    }
    return '';
  }

  // 详情大图：先显示已缓存的缩略图（点开即有画面），原图在后台加载完再无缝替换
  function dexHeroUpgrade() {
    var img = document.querySelector('#dexDetail img.dex-hero[data-full]');
    if (!img) return;
    var full = img.getAttribute('data-full');
    img.removeAttribute('data-full');
    if (!full) return;
    var pre = new Image();
    pre.onload = function () {
      if (img.isConnected) { img.src = full; img.classList.add('hi'); }
    };
    pre.src = full;
  }

  function dexPaintDetail(it) {
    var el = document.getElementById('dexDetail');
    if (!el) return;
    document.getElementById('dexTitle').textContent = it.name;
    var lvTxt = ['', '新手可养', '需要做功课', '进阶，不建议第一次养'][it.level] || '';
    document.getElementById('dexSub').textContent = it.group + ' · ' + lvTxt;
    var hum = (it.hum && it.hum[1]) ? (it.hum[0] + '–' + it.hum[1] + '%') : '看水温';
    var alias = (it.alias && it.alias.length) ? (' · 又叫 ' + it.alias.join('、')) : '';
    var credit = escapeHtml(dexCreditTxt(it.credit));

    el.innerHTML = '<img class="dex-hero" src="' + escapeHtml(it.thumb || it.img) + '" data-full="'
      + escapeHtml(it.img) + '" alt="' + escapeHtml(it.name) + '">'
      + '<div class="dex-d-head">'
      + '<div class="dex-d-name">' + escapeHtml(it.name) + '</div>'
      + '<div class="dex-d-latin">' + escapeHtml(it.latin) + '</div>'
      + '<div class="dex-d-en">' + escapeHtml(it.en) + escapeHtml(alias) + '</div></div>'
      + '<div class="dex-d-badges">'
      + '<div><b>' + it.temp[0] + '–' + it.temp[1] + '℃</b><span>温度</span></div>'
      + '<div><b>' + hum + '</b><span>湿度</span></div>'
      + '<div><b>' + escapeHtml(it.life.replace(/\s/g, '')) + '</b><span>寿命</span></div>'
      + '</div>'
      + '<div class="dex-d-badges" style="border-top:none">'
      + '<div style="flex:1.1"><b>' + escapeHtml(dexSizeShort(it.size)) + '</b><span>成体尺寸</span></div>'
      + '<div style="flex:1.4"><b>' + escapeHtml(lvTxt) + '</b><span>上手难度</span></div>'
      + '</div>'
      + '<div class="dex-sec"><h4>性格</h4><p>' + escapeHtml(it.temper) + '</p></div>'
      + '<div class="dex-sec"><h4>怎么喂</h4><p>' + escapeHtml(it.feed) + '</p></div>'
      + '<div class="dex-sec"><h4>蜕皮 / 换壳</h4><p>' + escapeHtml(it.shed) + '</p></div>'
      + '<div class="dex-sec risk"><h4>最容易踩的坑</h4><p>' + escapeHtml(it.tip) + '</p></div>'
      + (it.no ? '<div class="dex-sec"><h4>不要做</h4><p>' + escapeHtml(it.no) + '</p></div>' : '')
      + '<div class="dex-sec"><h4>常见问题</h4><ul>'
      + (it.ill || []).map(function (x) { return '<li>' + escapeHtml(x) + '</li>'; }).join('')
      + '</ul></div>'
      + dexLegalTag(it)
      + '<div class="dex-credit">' + credit + '。<br>'
      + '温湿度与喂食频率为成体常规参考，幼体、繁殖期、冬化期另调。'
      + '宠物品种（如侏儒兔、金丝熊、各类毛色品系）外观与野生个体差异较大，'
      + '照片只作物种识别参考。状态不对时，到「养护 → 拍照诊断」拍一张，或直接问兽医。</div>';
    dexHeroUpgrade();
  }

  var DEX_WARN_SVG = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    + 'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
    + '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path>'
    + '<path d="M12 9v4"></path><path d="M12 17h.01"></path></svg>';

  function dexPaintBan(it) {
    var el = document.getElementById('dexDetail');
    if (!el) return;
    document.getElementById('dexTitle').textContent = it.name;
    document.getElementById('dexSub').textContent = '不能养 · ' + (it.short || '受保护物种');
    var alias = (it.alias && it.alias.length) ? (' · 又叫 ' + it.alias.join('、')) : '';
    var credit = escapeHtml(dexCreditTxt(it.credit));
    var alt = it.instead;

    el.innerHTML = '<div class="dex-ban-wrap">'
      + '<img class="dex-hero" src="' + escapeHtml(it.thumb || it.img) + '" data-full="'
      + escapeHtml(it.img) + '" alt="' + escapeHtml(it.name) + '">'
      + '<span class="dex-ban-tag">禁止饲养</span></div>'
      + '<div class="dex-alert">' + DEX_WARN_SVG
      + '<div><b>这个不能养</b><span>' + escapeHtml(it.short || '')
      + '。个人无证持有、买卖、运输都违法，下面只讲怎么认出来和为什么不能养。</span></div></div>'
      + '<div class="dex-d-head">'
      + '<div class="dex-d-name">' + escapeHtml(it.name) + '</div>'
      + '<div class="dex-d-latin">' + escapeHtml(it.latin) + '</div>'
      + '<div class="dex-d-en">' + escapeHtml(it.en) + escapeHtml(alias) + '</div></div>'
      + '<div class="dex-sec"><h4>法律依据</h4><p>' + escapeHtml(it.law) + '</p></div>'
      + '<div class="dex-sec"><h4>为什么个人养不了</h4><p>' + escapeHtml(it.why) + '</p></div>'
      + '<div class="dex-sec risk"><h4>硬来的后果</h4><p>' + escapeHtml(it.risk) + '</p></div>'
      + (alt ? '<div class="dex-sec" style="padding-bottom:0;border-bottom:none"><h4>想养类似的，可以看</h4></div>'
        + '<button class="dex-alt" data-k="' + escapeHtml(alt.k) + '">'
        + '<img src="' + escapeHtml(alt.thumb || alt.img) + '" alt="' + escapeHtml(alt.name) + '" loading="lazy" decoding="async">'
        + '<div><b>' + escapeHtml(alt.name) + '</b><span>合法可饲养 · 点开看怎么养</span></div><i>›</i></button>' : '')
      + '<div class="dex-credit">' + credit + '。<br>'
      + '法规会调整，各地执法口径也有差异。拿不准某个物种能不能养，先问当地林业和草原局或农业农村局，'
      + '别问卖家。</div>';
    dexHeroUpgrade();
  }

  function dexBind() {
    var back = document.getElementById('dexBack');
    if (back) back.addEventListener('click', dexShowList);

    var sc = document.getElementById('dexScope');
    if (sc) {
      sc.addEventListener('click', function (e) {
        var b = e.target.closest('[data-scope]');
        if (!b || b.dataset.scope === DEX.scope) return;
        DEX.scope = b.dataset.scope;
        DEX.group = '全部';
        DEX.q = '';
        var q = document.getElementById('dexQ');
        if (q) q.value = '';
        var clr = document.getElementById('dexClear');
        if (clr) clr.classList.remove('show');
        DEX.loaded = false;
        DEX.items = [];
        document.getElementById('dexList').innerHTML = '<div class="dex-empty">读取中…</div>';
        dexPaint();
        dexLoad();
      });
    }

    var chips = document.getElementById('dexGroups');
    if (chips) {
      chips.addEventListener('click', function (e) {
        var b = e.target.closest('[data-g]');
        if (!b) return;
        DEX.group = b.dataset.g;
        DEX.loaded = false;
        dexPaint();
        dexLoad();
      });
    }

    var list = document.getElementById('dexList');
    if (list) {
      list.addEventListener('click', function (e) {
        var b = e.target.closest('[data-k]');
        if (b) dexOpen(b.dataset.k);
      });
    }

    var detail = document.getElementById('dexDetail');
    if (detail) {
      detail.addEventListener('click', function (e) {
        var b = e.target.closest('[data-k]');
        if (b) { dexOpen(b.dataset.k); }
      });
    }

    var q = document.getElementById('dexQ');
    var clr = document.getElementById('dexClear');
    if (q) {
      var timer = null;
      q.addEventListener('input', function () {
        var v = q.value.trim();
        if (clr) clr.classList.toggle('show', !!v);
        clearTimeout(timer);
        timer = setTimeout(function () {
          DEX.q = v; DEX.loaded = false; dexLoad();
        }, 280);
      });
      q.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); q.blur(); }
      });
    }
    if (clr) {
      clr.addEventListener('click', function () {
        q.value = ''; DEX.q = ''; clr.classList.remove('show');
        DEX.loaded = false; dexLoad();
      });
    }
  }

  dexBind();

  // ============ 后台问答与答完提醒 ============
  var chatBadge = document.getElementById('chatBadge');
  var answerToast = document.getElementById('answerToast');
  var answerToastText = document.getElementById('answerToastText');

  function showAnswerBadge(state) {
    if (!chatBadge) return;
    chatBadge.className = 'tab-badge show' + (state === 'answering' ? ' answering' : '');
  }
  function clearAnswerBadge() {
    if (chatBadge) chatBadge.className = 'tab-badge';
  }
  function showAnswerToast(text) {
    if (!answerToast) return;
    answerToastText.textContent = text || '答完了，点开看';
    answerToast.classList.add('show');
    clearTimeout(showAnswerToast._t);
    showAnswerToast._t = setTimeout(function () { answerToast.classList.remove('show'); }, 8000);
  }
  function hideAnswerToast() {
    if (answerToast) answerToast.classList.remove('show');
  }
  function notifyAnswerStart() {
    if (currentView !== 'chat') showAnswerBadge('answering');
  }
  function notifyAnswerDone() {
    if (currentView !== 'chat') {
      showAnswerBadge('done');
      showAnswerToast('答完了，点开看');
    }
  }
  answerToast.addEventListener('click', function () { switchView('chat'); });
  document.querySelector('.tabbar').addEventListener('click', function (e) {
    var t = e.target.closest('.tab');
    if (t) switchView(t.dataset.view);
  });

  // ============ 事件绑定 ============
  document.getElementById('histBtn').addEventListener('click', openSidebar);
  sidebarMask.addEventListener('click', closeSidebar);
  document.getElementById('newChat').addEventListener('click', newSession);
  sessionListEl.addEventListener('click', function (e) {
    var del = e.target.closest('.sidebar-item-del');
    if (del) { e.stopPropagation(); deleteSession(del.dataset.id); return; }
    var item = e.target.closest('.sidebar-item');
    if (item) switchSession(item.dataset.id);
  });

  document.getElementById('backBtn').addEventListener('click', function () {
    newSession();
    switchView('chat');
  });

  document.getElementById('clearChat').addEventListener('click', function () {
    clearAllSessions();
    switchView('chat');
  });

  document.querySelectorAll('.mine-item[data-detail]').forEach(function (item) {
    item.addEventListener('click', function () {
      var d = document.getElementById(item.dataset.detail);
      if (d) d.classList.toggle('show');
      item.classList.toggle('open');
    });
  });

  // 状态检查 + 数据背书
  function loadAppStatus() {
    api('/api/admin/status').then(function (r) { return r.json(); }).then(function (s) {
      configured = !!s.configured;
      statusEl.textContent = s.configured ? '在线' : '未配置';
      statusEl.classList.toggle('off', !s.configured);
      noticeEl.classList.toggle('show', !s.configured);
      sendBtn.disabled = !s.configured;
      // 数据背书（知识条数）；物种数统一由图鉴口径回填，这里不再覆盖
      var kc = s.knowledge_count || '--';
      var tk = document.getElementById('tKnowledge');
      var mk = document.getElementById('statKnowledge');
      if (tk) tk.textContent = kc;
      if (mk) mk.textContent = kc;
    }).catch(function (e) {
      if (e && e.unauthorized) return;
      statusEl.textContent = '离线';
      statusEl.classList.add('off');
    });
  }

  input.addEventListener('input', function () {
    sendBtn.disabled = !configured || sending || !input.value.trim();
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!sendBtn.disabled) send();
    }
  });
  sendBtn.addEventListener('click', send);

  document.getElementById('chips').addEventListener('click', function (e) {
    var chip = e.target.closest('.chip');
    if (chip) sendText(chip.dataset.q);
  });
  document.getElementById('qa-list').addEventListener('click', function (e) {
    var card = e.target.closest('.qa-card');
    if (card) sendText(card.dataset.q);
  });

  // 编辑已发送消息
  messagesEl.addEventListener('click', function (e) {
    var btn = e.target.closest('.edit-btn');
    if (!btn) return;
    var idx = parseInt(btn.dataset.idx, 10);
    if (isNaN(idx) || idx < 0 || idx >= history.length) return;
    var item = history[idx];
    if (!item || item.role !== 'user') return;
    editingIdx = idx;
    input.value = item.content;
    editingHint.classList.add('show');
    switchView('chat');
    input.focus();
  });

  // ============ 发送与流式 ============
  function send() {
    if (sending) return;
    var text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendBtn.disabled = true;
    sendText(text);
  }

  function sendText(text) {
    if (sending) return;
    if (!configured) {
      noticeEl.classList.add('show');
      return;
    }
    if (!currentId) {
      var id = genId();
      sessions.unshift({ id: id, title: '新对话', messages: [], updatedAt: Date.now() });
      currentId = id;
    }
    welcomeEl.style.display = 'none';

    if (editingIdx !== null) {
      history = history.slice(0, editingIdx);
      removeMessagesFrom(editingIdx);
      editingIdx = null;
      editingHint.classList.remove('show');
    }

    var userIdx = history.length;
    history.push({ role: 'user', content: text });
    appendMessage('user', text, userIdx);
    if (history.length > 12) {
      var cut = history.length - 12;
      history = history.slice(cut);
      removeMessagesFrom(0, cut);
    }

    var aiEl = appendMessage('ai', '', history.length, true);
    sending = true;
    persistSession();
    notifyAnswerStart();
    submitChat(text, aiEl);
  }

  function removeMessagesFrom(fromIdx, count) {
    messagesEl.querySelectorAll('.msg').forEach(function (row) {
      if (parseInt(row.dataset.idx, 10) >= fromIdx) row.remove();
    });
    if (count) {
      messagesEl.querySelectorAll('.msg').forEach(function (row) {
        row.dataset.idx = String(parseInt(row.dataset.idx, 10) - count);
      });
    }
  }

  // 提交任务 + 轮询：答案在服务端后台生成，页面退出/断网也能继续，回来即可接续
  function submitChat(text, aiEl) {
    api('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history, device_id: DEVICE_ID })
    }).then(function (resp) {
      if (resp.status === 503) {
        return resp.json().then(function (d) {
          setText(aiEl, ''); appendError(aiEl, d.message || '服务未配置', text); finishFail();
        });
      }
      if (resp.status !== 200) {
        return resp.text().then(function () {
          setText(aiEl, ''); appendError(aiEl, '服务出错（' + resp.status + '）', text); finishFail();
        });
      }
      return resp.json().then(function (d) {
        if (!d.task_id) {
          setText(aiEl, ''); appendError(aiEl, d.message || d.error || '提交失败', text); finishFail(); return;
        }
        pendingTask = { task_id: d.task_id, sessionId: currentId, question: text };
        savePendingTask();
        if (d.refs) showRefs(aiEl, d.refs);
        startPolling(aiEl);
      });
    }).catch(function (e) {
      if (e && e.unauthorized) { finishFail(); return; }
      setText(aiEl, ''); appendError(aiEl, '网络请求失败，请稍后重试', text); finishFail();
    });
  }

  function setAnswer(aiEl, text, done) {
    // 轮询会反复推同一份累积文本，内容没变就别整段重排一次 Markdown
    if (!done && aiEl._lastText === text) return;
    aiEl._lastText = text;
    var html = renderMarkdown(text || '');
    if (!done) html += '<span class="typing" style="margin-left:2px"><span></span><span></span><span></span></span>';
    aiEl.innerHTML = html;
    scrollBottom();
  }

  function startPolling(aiEl) {
    if (!pendingTask) return;
    var taskId = pendingTask.task_id;
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    var ticks = 0;
    function tick() {
      api('/api/chat/status?task_id=' + encodeURIComponent(taskId))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.found) {
            appendError(aiEl, '回答未能完成，请点下方按钮重试', pendingTask ? pendingTask.question : '');
            finishFail();
            return;
          }
          if (d.status === 'queued' || d.status === 'running') {
            if (d.answer) setAnswer(aiEl, d.answer, false);
            // 起手快一点，让用户尽早看到字出来；稳定后再放宽，减少无谓请求
            ticks += 1;
            var gap = d.answer ? 600 : (ticks < 6 ? 260 : 500);
            pollTimer = setTimeout(tick, gap);
          } else if (d.status === 'done') {
            setAnswer(aiEl, d.answer, true);
            finalize(aiEl, d.answer);
            var qtext = pendingTask ? (pendingTask.question || '') : '';
            appendFollowUps(aiEl, qtext, d.answer);
            finishDone();
          } else {
            appendError(aiEl, d.err || '回答失败，请稍后重试', pendingTask ? pendingTask.question : '');
            finishFail();
          }
        })
        .catch(function (e) {
          if (e && e.unauthorized) { finishFail(); return; }
          pollTimer = setTimeout(tick, 1500);
        });
    }
    tick();
  }

  function finishDone() {
    sending = false;
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    clearPendingTask();
    sendBtn.disabled = !configured || !input.value.trim();
    notifyAnswerDone();
  }

  function finishFail() {
    sending = false;
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    clearPendingTask();
    sendBtn.disabled = !configured || !input.value.trim();
    notifyAnswerDone();
  }

  // 参考知识来源标签
  function showRefs(bubble, refs) {
    if (!refs || !refs.length) return;
    var row = bubble.closest('.msg');
    if (!row) return;
    var old = row.querySelector('.refs-tag');
    if (old) old.remove();

    var tag = document.createElement('div');
    tag.className = 'refs-tag';
    tag.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>';
    tag.appendChild(document.createTextNode('参考了 ' + refs.length + ' 条资料'));

    var list = document.createElement('div');
    list.className = 'refs-list';
    refs.forEach(function (r) {
      var it = document.createElement('div');
      it.className = 'refs-item';
      var html = '<b>' + escapeHtml(r.species || '') + '</b> · ' + escapeHtml(r.title || '');
      // 出处：药典条目带书名、章节、页码；没出处的（常识类）不显示这一行
      if (r.book) {
        var src = [r.book];
        if (r.chapter) src.push(r.chapter);
        if (r.page) src.push('p.' + r.page);
        html += '<span class="refs-src">' + escapeHtml(src.join(' · ')) + '</span>';
      }
      it.innerHTML = html;
      list.appendChild(it);
    });

    var wrap = document.createElement('div');
    wrap.className = 'refs-wrap';
    wrap.style.width = 'calc(100% - 40px)';
    wrap.style.marginLeft = '40px';
    wrap.style.flex = '0 0 auto';
    wrap.appendChild(tag);
    wrap.appendChild(list);
    row.appendChild(wrap);

    tag.addEventListener('click', function (e) {
      e.stopPropagation();
      list.classList.toggle('show');
    });
  }

  function appendMessage(role, content, idx, isTyping) {
    var row = document.createElement('div');
    row.className = 'msg ' + role;
    row.dataset.idx = String(idx);
    if (role === 'ai') {
      var av = document.createElement('div');
      av.className = 'avatar'; av.innerHTML = '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="小宠百问"><defs><linearGradient id="lgAv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1fb46d"/><stop offset="1" stop-color="#0d7a45"/></linearGradient></defs><circle cx="32" cy="32" r="30.5" fill="url(#lgAv)" stroke="rgba(255,255,255,.5)" stroke-width="2.5"/><g fill="#fff"><rect x="15" y="17" width="26" height="22" rx="8"/><path d="M21 39 L16 46 L29 39 Z"/><ellipse cx="41" cy="46" rx="2.6" ry="3.6" transform="rotate(-20 41 46)"/><ellipse cx="47" cy="43" rx="2.6" ry="3.6"/><ellipse cx="53" cy="46" rx="2.6" ry="3.6" transform="rotate(20 53 46)"/><ellipse cx="47" cy="52" rx="5.8" ry="4.6"/></g><text x="28" y="34" font-family="-apple-system,\'PingFang SC\',\'Microsoft YaHei\',sans-serif" font-size="19" font-weight="800" fill="#0d7a45" text-anchor="middle">?</text></svg>';
      row.appendChild(av);
    }
    if (role === 'user') {
      var eb = document.createElement('button');
      eb.className = 'edit-btn'; eb.dataset.idx = String(idx); eb.setAttribute('aria-label', '编辑');
      eb.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>';
      row.appendChild(eb);
    }
    var b = document.createElement('div');
    b.className = 'bubble';
    if (isTyping) b.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    else if (role === 'user') b.textContent = content;
    else b.innerHTML = renderMarkdown(content);
    row.appendChild(b);
    messagesEl.appendChild(row);
    scrollBottom();
    return b;
  }

  function appendDelta(bubble, text) {
    rawBuffer += text;
    bubble.innerHTML = renderMarkdown(rawBuffer) + '<span class="typing" style="margin-left:2px"><span></span><span></span><span></span></span>';
    scrollBottom();
  }
  function finalize(bubble, content) {
    var c = (typeof content === 'string') ? content : rawBuffer;
    rawBuffer = '';
    bubble.innerHTML = renderMarkdown(c);
    history.push({ role: 'assistant', content: c });
    if (history.length > 12) history = history.slice(-12);
    persistSession();
  }
  function setText(bubble, html) { rawBuffer = ''; bubble.innerHTML = html; }
  function showTyping(bubble, on) {
    if (on) bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
  }
  function appendError(bubble, msg, retryText) {
    bubble.innerHTML = '<span style="color:#c0392b">' + escapeHtml(msg) + '</span>';
    if (!retryText) return;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'retry-btn';
    btn.textContent = '重新提问';
    btn.addEventListener('click', function () {
      if (sending) return;
      bubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
      sending = true;
      notifyAnswerStart();
      submitChat(retryText, bubble);
    });
    bubble.appendChild(btn);
  }
  function scrollBottom() { main.scrollTop = main.scrollHeight; }
  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  // 模型爱在开头加 🚨⚠️ 这类图标，但不少安卓机没有彩色 emoji 字体，
  // 显示出来是个空方框，比没有还难看。统一剥掉，正文照读。
  function stripEmoji(s) {
    var out;
    try {
      out = s.replace(/[\p{Extended_Pictographic}\uFE0F\u20E3]/gu, '');
    } catch (e) {
      out = s.replace(/[\u{1F000}-\u{1FAFF}]/gu, '');
    }
    return out.replace(/[ \t]{2,}/g, ' ').replace(/^[ \t]+$/gm, '');
  }

  function renderMarkdown(text) {
    if (!text) return '';
    var lines = escapeHtml(stripEmoji(text)).split('\n');
    var out = [], listType = null;
    function closeList() { if (listType) { out.push('</' + listType + '>'); listType = null; } }
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) { closeList(); continue; }
      // 分隔线：模型常用 --- 分段，之前会原样吐出三个减号
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) { closeList(); out.push('<hr>'); continue; }
      var h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        closeList();
        var lv = Math.min(5, Math.max(3, h[1].length + 2));
        out.push('<h' + lv + '>' + inline(h[2]) + '</h' + lv + '>');
        continue;
      }
      var q = line.match(/^&gt;\s*(.*)$/);
      if (q) { closeList(); out.push('<blockquote>' + inline(q[1]) + '</blockquote>'); continue; }
      var ul = line.match(/^[-*+]\s+(.*)$/);
      if (ul) {
        if (listType !== 'ul') { closeList(); out.push('<ul>'); listType = 'ul'; }
        out.push('<li>' + inline(ul[1]) + '</li>');
        continue;
      }
      // 有序列表单独成 ol，保留「第几步」的语义
      var ol = line.match(/^(\d{1,2})[.、)]\s*(.+)$/);
      if (ol) {
        if (listType !== 'ol') { closeList(); out.push('<ol>'); listType = 'ol'; }
        out.push('<li>' + inline(ol[2]) + '</li>');
        continue;
      }
      // 表格分隔行（|---|---|）跳过，数据行按等宽列渲染
      if (line.indexOf('|') >= 0 && /^\|?[\s:|-]+\|[\s:|-]*$/.test(line)) { continue; }
      if (/^\|.*\|$/.test(line)) {
        closeList();
        var cells = line.replace(/^\||\|$/g, '').split('|');
        out.push('<div class="md-tr">' + cells.map(function (c) {
          return '<span>' + inline(c.trim()) + '</span>';
        }).join('') + '</div>');
        continue;
      }
      closeList();
      out.push('<p>' + inline(line) + '</p>');
    }
    closeList();
    return out.join('');
  }
  function inline(s) {
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // 行内代码：内容已经过 escapeHtml，安全
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    // 只认 http/https 链接，挡住 javascript: 之类
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, function (m, t, u) {
      return '<a href="' + u + '" target="_blank" rel="noopener noreferrer">' + t + '</a>';
    });
    // 回答被截断时 marker 会落单，剩两个星号露在正文里很扎眼，直接去掉
    s = s.replace(/\*\*/g, '');
    return s;
  }

  // ============ 常见问题（每次打开随机更新，避开上次展示） ============
  var FAQ_POOL = [
    { q: '兔子拉稀能喂阿莫西林吗', tag: '用药' },
    { q: '兔子不吃东西肚子胀，能先喂点什么药', tag: '用药' },
    { q: '鹦鹉热用什么药，会传染给人吗', tag: '用药' },
    { q: '龟打针为什么容易烂一块', tag: '用药' },
    { q: '鸟长螨了能用伊维菌素吗', tag: '用药' },
    { q: '狗用的驱虫滴剂能给兔子用吗', tag: '用药' },
    { q: '兔子只吃兔粮不吃草，会怎么样', tag: '兔' },
    { q: '兔子拉的便便变软、粘在屁股上', tag: '兔' },
    { q: '兔子突然不吃不喝，一直趴着', tag: '兔' },
    { q: '兔子能洗澡吗', tag: '兔' },
    { q: '仓鼠半夜一直啃笼子，是病了吗', tag: '仓鼠' },
    { q: '仓鼠能两只养一个笼子吗', tag: '仓鼠' },
    { q: '仓鼠颊囊塞太满了要不要掏', tag: '仓鼠' },
    { q: '仓鼠掉毛、后背秃了一块', tag: '仓鼠' },
    { q: '龙猫屋里三十度，它会不会中暑', tag: '龙猫' },
    { q: '龙猫用水洗澡行不行', tag: '龙猫' },
    { q: '豚鼠不吃东西能撑几天', tag: '豚鼠' },
    { q: '豚鼠为什么一定要补维C', tag: '豚鼠' },
    { q: '蜜袋鼯晚上一直叫，正常吗', tag: '蜜袋鼯' },
    { q: '刺猬冬天一定要冬眠吗', tag: '刺猬' },
    { q: '雪貂身上味道很重，能去掉吗', tag: '雪貂' },
    { q: '花枝鼠要养两只才不抑郁吗', tag: '花枝鼠' },
    { q: '豹纹守宫白天三十度、晚上二十度可以吗', tag: '守宫' },
    { q: '豹纹守宫不吃东西，尾巴越来越细', tag: '守宫' },
    { q: '守宫尾巴断了还能长回来吗', tag: '守宫' },
    { q: '守宫眼睛睁不开，有一层白膜', tag: '守宫' },
    { q: '肥尾守宫和豹纹守宫差在哪', tag: '守宫' },
    { q: '玉米蛇吐食了是怎么回事', tag: '蛇' },
    { q: '蛇一直不蜕皮，眼睛发蓝好几天', tag: '蛇' },
    { q: '猪鼻蛇会装死吗', tag: '蛇' },
    { q: '王蛇适合第一次养蛇的人吗', tag: '蛇' },
    { q: '陆龟必须照UVB吗，晒窗边太阳行不行', tag: '龟' },
    { q: '巴西龟眼睛肿成一条缝', tag: '龟' },
    { q: '龟壳发软是缺钙吗', tag: '龟' },
    { q: '水龟的水多久换一次', tag: '龟' },
    { q: '鬃狮蜥不吃菜只吃虫，怎么改', tag: '蜥蜴' },
    { q: '鬃狮蜥张嘴呼吸、脖子鼓起来', tag: '蜥蜴' },
    { q: '蓝舌石龙子能上手吗', tag: '蜥蜴' },
    { q: '变色龙养在玻璃缸里可以吗', tag: '蜥蜴' },
    { q: '角蛙一动不动好几天，是死了吗', tag: '蛙' },
    { q: '角蛙能两只放一起吗', tag: '蛙' },
    { q: '箭毒蛙有毒吗，家里能养吗', tag: '蛙' },
    { q: '虎皮鹦鹉吃什么，只喂小米行不行', tag: '鹦鹉' },
    { q: '鹦鹉绝对不能吃的东西有哪些', tag: '鹦鹉' },
    { q: '鹦鹉一直炸毛、缩在角落', tag: '鹦鹉' },
    { q: '鹦鹉咬人要不要弹它嘴', tag: '鹦鹉' },
    { q: '玄凤鹦鹉晚上需要盖布吗', tag: '鹦鹉' },
    { q: '八哥多久能学会说话', tag: '鸟' },
    { q: '捕鸟蛛蜕皮的时候能碰吗', tag: '蛛' },
    { q: '捕鸟蛛不吃东西，肚子瘪了', tag: '蛛' },
    { q: '蝎子能上手吗', tag: '蝎子' },
    { q: '独角仙幼虫用不用换土', tag: '甲虫' },
    { q: '寄居蟹换壳的时候要准备什么', tag: '寄居蟹' },
    { q: '六角恐龙的水温多少合适', tag: '六角龙' },
    { q: '斗鱼能和小鱼一起养吗', tag: '斗鱼' },
    { q: '新手先养什么异宠不容易养死', tag: '通用' },
    { q: '加热垫放箱底还是贴侧面', tag: '通用' },
    { q: '冬天停电，箱子怎么保温', tag: '通用' },
    { q: '异宠生病了，附近没有异宠医院怎么办', tag: '通用' },
    { q: '哪些异宠是国家保护动物，不能买', tag: '通用' },
    { q: '卖家说不用办证，能信吗', tag: '通用' },
  ];

  var FAQ_KEY = 'xiaochong_last_faq';
  var FAQ_COUNT = 8;
  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }
  function renderFAQ() {
    var qaList = document.getElementById('qa-list');
    var lastShown = [];
    try { lastShown = JSON.parse(localStorage.getItem(FAQ_KEY) || '[]'); } catch (e) { lastShown = []; }
    var lastSet = {};
    lastShown.forEach(function (q) { lastSet[q] = true; });
    var fresh = FAQ_POOL.filter(function (it) { return !lastSet[it.q]; });
    var pool = fresh.length >= FAQ_COUNT ? fresh : FAQ_POOL;
    var picked = shuffle(pool).slice(0, FAQ_COUNT);
    var html = '';
    picked.forEach(function (it) {
      html += '<div class="qa-card" data-q="' + escapeHtml(it.q) + '"><span>' + escapeHtml(it.q) + '</span><span class="tag">' + escapeHtml(it.tag) + '</span></div>';
    });
    qaList.innerHTML = html;
    var shown = picked.map(function (it) { return it.q; });
    try { localStorage.setItem(FAQ_KEY, JSON.stringify(shown)); } catch (e) {}
  }

  // ============ 合规速查 ============
  var complianceData = null;
  var compStatus = 'all';
  var compCat = 'all';
  var compKeyword = '';

  function loadCompliance(cb) {
    if (complianceData) { cb && cb(); return; }
    api('/api/compliance').then(function (r) { return r.json(); }).then(function (d) {
      complianceData = d;
      renderComplianceStats();
      renderCompCats();
      cb && cb();
    }).catch(function () {
      complianceData = { items: [], categories: [], stats: {} };
      renderComplianceStats();
      renderCompCats();
      cb && cb();
    });
  }

  function renderComplianceStats() {
    var s = (complianceData && complianceData.stats) || {};
    document.getElementById('csCan').textContent = s['可养'] || 0;
    document.getElementById('csPermit').textContent = s['需许可'] || 0;
    document.getElementById('csBan').textContent = s['禁止'] || 0;
  }

  function renderCompCats() {
    var cats = (complianceData && complianceData.categories) || [];
    var html = '<button class="cc active" data-cat="all">全部</button>';
    cats.forEach(function (c) {
      html += '<button class="cc" data-cat="' + escapeHtml(c) + '">' + escapeHtml(c) + '</button>';
    });
    document.getElementById('compCatFilter').innerHTML = html;
  }

  function renderCompliance() {
    loadCompliance(function () {
      var items = (complianceData && complianceData.items) || [];
      var kw = compKeyword.toLowerCase();
      var list = items.filter(function (it) {
        if (compStatus !== 'all' && it.status !== compStatus) return false;
        if (compCat !== 'all' && it.category !== compCat) return false;
        if (kw) {
          var hay = it.name + ' ' + ((it.aliases || []).join(' '));
          if (hay.toLowerCase().indexOf(kw) < 0) return false;
        }
        return true;
      });
      var html = '';
      if (list.length === 0) {
        // 空结果不要变成死胡同：给出「换个词」和「直接问 AI」两条出路
        var kwTxt = compKeyword ? '「' + escapeHtml(compKeyword) + '」' : '该条件';
        html = '<div class="comp-empty">没找到' + kwTxt + '相关的物种'
          + '<div class="comp-empty-sub">试试更常见的叫法（如「陆龟」「球蟒」「玄凤」），或直接问 AI</div>'
          + '<button class="comp-ask comp-ask-empty" data-name="' + escapeHtml(compKeyword || '这个物种') + '">去问 AI 能不能养 ›</button></div>';
      } else {
        list.forEach(function (it) {
          var st = it.status;
          var stClass = st === '可养' ? 'can' : (st === '需许可' ? 'permit' : 'ban');
          var alias = (it.aliases && it.aliases.length) ? '<span class="comp-alias">' + escapeHtml(it.aliases[0]) + '</span>' : '';
          html += '<div class="comp-card">'
            + '<div class="comp-card-head"><span class="comp-name">' + escapeHtml(it.name) + alias + '</span>'
            + '<span class="comp-tags"><span class="comp-status ' + stClass + '">' + st + '</span>'
            + (it.proof ? '<span class="comp-proof">需来源证明</span>' : '') + '</span></div>'
            + '<div class="comp-brief">' + escapeHtml(it.brief || '') + '</div>'
            + '<div class="comp-detail">' + escapeHtml(it.detail || '') + '</div>'
            + '<div class="comp-basis">依据：' + escapeHtml(it.basis || '') + '</div>'
            + '<div class="comp-actions"><button class="comp-ask" data-name="' + escapeHtml(it.name) + '">'
            + (st === '禁止' ? '问它为什么不能养 ›' : (st === '需许可' ? '问要办什么证 ›' : '问怎么养 ›'))
            + '</button></div>'
            + '<div class="comp-chev">点按查看详情</div>'
            + '</div>';
        });
      }
      document.getElementById('compList').innerHTML = html;
      var proofN = list.filter(function (x) { return x.proof; }).length;
      document.getElementById('compCount').textContent = '共 ' + list.length + ' 个物种'
        + (proofN ? ' · 其中 ' + proofN + ' 种需来源证明' : '');
    });
  }

  document.getElementById('compSearch').addEventListener('input', function (e) {
    compKeyword = e.target.value.trim();
    document.getElementById('compClear').classList.toggle('show', !!compKeyword);
    renderCompliance();
  });
  document.getElementById('compClear').addEventListener('click', function () {
    document.getElementById('compSearch').value = '';
    compKeyword = '';
    document.getElementById('compClear').classList.remove('show');
    renderCompliance();
  });
  document.getElementById('compStatusFilter').addEventListener('click', function (e) {
    var b = e.target.closest('.cf');
    if (!b) return;
    compStatus = b.dataset.status;
    document.querySelectorAll('#compStatusFilter .cf').forEach(function (x) { x.classList.toggle('active', x === b); });
    renderCompliance();
  });
  document.getElementById('compCatFilter').addEventListener('click', function (e) {
    var b = e.target.closest('.cc');
    if (!b) return;
    compCat = b.dataset.cat;
    document.querySelectorAll('#compCatFilter .cc').forEach(function (x) { x.classList.toggle('active', x === b); });
    renderCompliance();
  });
  var newsData = null;
  var activeNewsIdx = 0;
  var newsKeyword = '';
  function loadNews(cb) {
    if (newsData) { cb && cb(); return; }
    api('/api/news').then(function (r) { return r.json(); }).then(function (d) {
      newsData = d;
      cb && cb();
    }).catch(function () {
      newsData = { sections: [], updated: '', version: '' };
      cb && cb();
    });
  }
  // ============ 问答页：行业动态滚动条（可按行业切换） ============
  // 日期格式不统一（2026 / 2026-07 / 2026-07-01），补齐后再比较，避免年份条目抢占最新
  function dkey(d) {
    d = String(d || '');
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
    if (/^\d{4}-\d{2}$/.test(d)) return d + '-00';
    if (/^\d{4}$/.test(d)) return d + '-00-00';
    return '0000-00-00';
  }
  var SEC_SHORT = {
    policy: '政策', market: '市场', reptile: '爬宠', bird: '鸟类',
    mammal: '哺乳', arthropod: '节肢', aquatic: '水族'
  };
  var tickerSec = 'all';
  var tickerItems = [];
  var tickerIdx = 0;
  var tickerTimer = null;
  try { tickerSec = localStorage.getItem('xc_ticker_sec') || 'all'; } catch (e) { tickerSec = 'all'; }

  function tickerPool() {
    var sections = (newsData && newsData.sections) || [];
    var out = [];
    sections.forEach(function (s) {
      if (tickerSec !== 'all' && s.id !== tickerSec) return;
      (s.items || []).forEach(function (n) {
        if (!n || !n.title) return;
        out.push({
          title: n.title, date: n.date || '', secId: s.id, secName: s.name,
          short: SEC_SHORT[s.id] || String(s.name || '').slice(0, 2)
        });
      });
    });
    out.sort(function (a, b) { return dkey(b.date).localeCompare(dkey(a.date)); });
    return out;
  }

  function tickerDate(d) {
    d = String(d || '');
    if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d.slice(5);
    if (/^\d{4}-\d{2}$/.test(d)) return d.slice(5) + ' 月';
    return d;
  }

  function tickerItemHtml(it) {
    return '<div class="nt-item" data-sec="' + escapeHtml(it.secId) + '">'
      + (tickerSec === 'all' ? '<span class="nt-tag">' + escapeHtml(it.short) + '</span>' : '')
      + '<span class="nt-title">' + escapeHtml(it.title) + '</span>'
      + '<span class="nt-date">' + escapeHtml(tickerDate(it.date)) + '</span></div>';
  }

  function renderTicker() {
    var box = document.getElementById('newsTicker');
    var track = document.getElementById('ntTrack');
    if (!box || !track) return;
    tickerItems = tickerPool();
    if (!tickerItems.length) {
      box.hidden = true;
      document.getElementById('ntPicker').hidden = true;
      stopTicker();
      return;
    }
    box.hidden = false;
    document.getElementById('ntSecName').textContent =
      tickerSec === 'all' ? '全部' : (SEC_SHORT[tickerSec] || '行业');
    // 多于一条时克隆首条，滚到末尾无缝回到开头
    var html = tickerItems.map(tickerItemHtml).join('');
    if (tickerItems.length > 1) html += tickerItemHtml(tickerItems[0]);
    track.style.transition = 'none';
    track.style.transform = 'translateY(0)';
    track.innerHTML = html;
    tickerIdx = 0;
    void track.offsetHeight;
    startTicker();
  }

  function tickerStep() {
    var track = document.getElementById('ntTrack');
    if (!track || tickerItems.length < 2) return;
    var first = track.querySelector('.nt-item');
    var h = first ? first.offsetHeight : 48;
    tickerIdx++;
    track.style.transition = 'transform .42s cubic-bezier(.4,0,.2,1)';
    track.style.transform = 'translateY(-' + (tickerIdx * h) + 'px)';
    if (tickerIdx >= tickerItems.length) {
      setTimeout(function () {
        var t = document.getElementById('ntTrack');
        if (!t) return;
        t.style.transition = 'none';
        t.style.transform = 'translateY(0)';
        tickerIdx = 0;
        void t.offsetHeight;
      }, 460);
    }
  }

  function startTicker() {
    stopTicker();
    if (document.hidden || currentView !== 'chat') return;
    if (tickerItems.length < 2) return;
    tickerTimer = setInterval(tickerStep, 4200);
  }

  function stopTicker() {
    if (tickerTimer) { clearInterval(tickerTimer); tickerTimer = null; }
  }

  // 点动态条跳到行业动态页，并直接定位到该板块
  function goNewsSection(secId) {
    var sections = (newsData && newsData.sections) || [];
    var idx = -1;
    sections.forEach(function (s, i) { if (s.id === secId) idx = i; });
    if (idx >= 0) activeNewsIdx = idx;
    newsKeyword = '';
    var inp = document.getElementById('newsSearch');
    if (inp) inp.value = '';
    var clr = document.getElementById('newsClear');
    if (clr) clr.classList.remove('show');
    switchView('news');
  }

  function renderSecChips() {
    var box = document.getElementById('ntChips');
    if (!box) return;
    var sections = (newsData && newsData.sections) || [];
    var h = '<button type="button" class="nt-chip' + (tickerSec === 'all' ? ' active' : '')
      + '" data-sec="all">全部行业</button>';
    sections.forEach(function (s) {
      h += '<button type="button" class="nt-chip' + (tickerSec === s.id ? ' active' : '')
        + '" data-sec="' + escapeHtml(s.id) + '">' + escapeHtml(s.name) + '</button>';
    });
    box.innerHTML = h;
  }

  function closePicker() {
    var p = document.getElementById('ntPicker');
    if (!p || p.hidden) return;
    p.hidden = true;
    document.getElementById('ntSec').setAttribute('aria-expanded', 'false');
    startTicker();
  }

  (function initTicker() {
    var secBtn = document.getElementById('ntSec');
    var picker = document.getElementById('ntPicker');
    var chips = document.getElementById('ntChips');
    var track = document.getElementById('ntTrack');
    var allBtn = document.getElementById('ntAll');
    if (!secBtn || !picker || !chips || !track || !allBtn) return;
    secBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (picker.hidden) {
        renderSecChips();
        picker.hidden = false;
        secBtn.setAttribute('aria-expanded', 'true');
        stopTicker();
      } else {
        closePicker();
      }
    });
    chips.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('.nt-chip') : null;
      if (!b) return;
      tickerSec = b.dataset.sec || 'all';
      try { localStorage.setItem('xc_ticker_sec', tickerSec); } catch (err) {}
      closePicker();
      renderTicker();
    });
    document.getElementById('ntAll').addEventListener('click', function (e) {
      e.stopPropagation();
      goNewsSection('all');
    });
    document.getElementById('ntTrack').addEventListener('click', function (e) {
      var it = e.target.closest ? e.target.closest('.nt-item') : null;
      if (!it) return;
      goNewsSection(it.dataset.sec);
    });
    document.addEventListener('click', function (e) {
      if (!picker.hidden && !picker.contains(e.target)) closePicker();
    });
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) stopTicker(); else startTicker();
    });
    // 每 10 分钟重取一次资讯：后台每天 06:00 更新，用户挂着页面也能等到新内容
    setInterval(function () {
      if (document.hidden) return;
      newsData = null;
      loadNews(renderTicker);
    }, 10 * 60 * 1000);
  })();

  // 只有 http/https 才渲染外链，避免脏数据带出 javascript: 之类
  function safeUrl(u) {
    u = String(u || '').trim();
    return /^https?:\/\//i.test(u) ? u : '';
  }
  // 每条资讯都能一键接着问 AI：把标题带进输入框，用户补一句就能问
  function newsLinkRow(n) {
    var u = safeUrl(n && n.url);
    var h = '<div class="news-acts">';
    if (u) {
      h += '<a href="' + escapeHtml(u) + '" target="_blank" rel="noopener noreferrer">原文 ›</a>';
    }
    h += '<button type="button" class="news-ask" data-title="' + escapeHtml((n && n.title) || '') + '">'
      + '问问 AI ›</button></div>';
    return h;
  }

  function renderNews() {
    loadNews(function () {
      var sections = (newsData && newsData.sections) || [];
      var updated = (newsData && newsData.updated) || '';
      var el = document.getElementById('newsUpdated');
      if (el) el.textContent = updated ? '更新于 ' + updated : '';

      if (sections.length === 0) {
        document.getElementById('newsTabs').innerHTML = '';
        document.getElementById('newsList').innerHTML = '<div class="comp-empty">暂无行业动态</div>';
        return;
      }

      // 搜索模式：跨板块检索，直接给出命中条目
      if (newsKeyword) {
        var kw = newsKeyword.toLowerCase();
        var hits = [];
        sections.forEach(function (s) {
          (s.items || []).forEach(function (n) {
            var hay = (n.title || '') + ' ' + (n.summary || '') + ' ' + (n.source || '');
            if (hay.toLowerCase().indexOf(kw) >= 0) {
              hits.push({ n: n, sec: s.name });
            }
          });
        });
        document.getElementById('newsTabs').innerHTML = '';
        if (!hits.length) {
          document.getElementById('newsList').innerHTML =
            '<div class="comp-empty">没有找到「' + escapeHtml(newsKeyword) + '」相关的行业动态<br>'
            + '<span class="comp-empty-sub">换个关键词试试，或清空搜索查看全部板块</span></div>';
          return;
        }
        var h = '<div class="news-section-head"><div class="news-section-name">搜索结果</div>'
              + '<div class="news-section-desc">共 ' + hits.length + ' 条，来自全部板块</div></div>';
        hits.forEach(function (x) {
          var n = x.n;
          h += '<div class="news-item">'
            + '<div class="news-item-top">'
            + '<span class="news-date">' + escapeHtml(n.date) + '</span>'
            + '<span class="news-src">' + escapeHtml(x.sec) + '</span></div>'
            + '<div class="news-item-title">' + escapeHtml(n.title) + '</div>'
            + '<div class="news-item-summary">' + escapeHtml(n.summary) + '</div>'
            + newsLinkRow(n)
            + '</div>';
        });
        document.getElementById('newsList').innerHTML = h;
        return;
      }

      if (activeNewsIdx < 0 || activeNewsIdx >= sections.length) activeNewsIdx = 0;

      var tabsHtml = '';
      sections.forEach(function (s, i) {
        // 不再渲染 emoji：部分安卓/无彩色字体环境会显示成方框，统一用文字标签
        tabsHtml += '<button class="news-tab' + (i === activeNewsIdx ? ' active' : '') + '" data-idx="' + i + '">'
          + '<span class="nt-num">' + ('0' + (i + 1)).slice(-2) + '</span>'
          + escapeHtml(s.name) + '</button>';
      });
      document.getElementById('newsTabs').innerHTML = tabsHtml;
      renderNewsSection(sections[activeNewsIdx]);
    });
  }

  function renderNewsSection(section) {
    var items = (section && section.items) || [];
    var html = '';
    if (section && section.desc) {
      html += '<div class="news-section-head">'
        + '<div class="news-section-name">' + escapeHtml(section.name) + '</div>'
        + '<div class="news-section-desc">' + escapeHtml(section.desc) + '</div></div>';
    }
    if (items.length === 0) {
      html += '<div class="comp-empty">该板块暂无资讯</div>';
    } else {
      items.forEach(function (n) {
        html += '<div class="news-item">'
          + '<div class="news-item-top">'
          + '<span class="news-date">' + escapeHtml(n.date) + '</span>'
          + '<span class="news-src">' + escapeHtml(n.source || '') + '</span></div>'
          + '<div class="news-item-title">' + escapeHtml(n.title) + '</div>'
          + '<div class="news-item-summary">' + escapeHtml(n.summary) + '</div>'
          + newsLinkRow(n)
          + '</div>';
      });
    }
    document.getElementById('newsList').innerHTML = html;
  }

  document.getElementById('newsSearch').addEventListener('input', function (e) {
    newsKeyword = e.target.value.trim();
    document.getElementById('newsClear').classList.toggle('show', !!newsKeyword);
    renderNews();
  });
  document.getElementById('newsClear').addEventListener('click', function () {
    document.getElementById('newsSearch').value = '';
    newsKeyword = '';
    document.getElementById('newsClear').classList.remove('show');
    renderNews();
  });

  document.getElementById('newsTabs').addEventListener('click', function (e) {
    var b = e.target.closest('.news-tab');
    if (!b) return;
    activeNewsIdx = parseInt(b.dataset.idx, 10) || 0;
    renderNews();
  });

  function askSpecies(name) {
    switchView('chat');
    sendText(name + '怎么养？');
  }

  // 从资讯跳到提问：预填标题，用户补一句即可发送（少打字 = 更快触达）
  document.getElementById('newsList').addEventListener('click', function (e) {
    var b = e.target.closest('.news-ask');
    if (!b) return;
    var title = b.dataset.title || '';
    if (!title) return;
    switchView('chat');
    input.value = '关于「' + title + '」，';
    try {
      input.focus();
      var n = input.value.length;
      input.setSelectionRange(n, n);
    } catch (err) {}
    sendBtn.disabled = !configured || !input.value.trim();
    scrollBottom();
  });

  document.getElementById('compList').addEventListener('click', function (e) {
    var ask = e.target.closest('.comp-ask');
    if (ask) { e.stopPropagation(); askSpecies(ask.dataset.name); return; }
    var card = e.target.closest('.comp-card');
    if (card) card.classList.toggle('open');
  });

  // ============ 退出后回来：接续未答完的问题 ============
  function resumePendingTask() {
    var p = loadPendingTask();
    if (!p || !p.task_id) return;
    var s = p.sessionId ? findSession(p.sessionId) : null;
    if (!s) { clearPendingTask(); return; }
    if (currentId !== p.sessionId) openSession(p.sessionId);
    var last = history[history.length - 1];
    if (last && last.role === 'assistant') { clearPendingTask(); return; }
    pendingTask = p;
    sending = true;
    var aiEl = appendMessage('ai', '', history.length, true);
    sendBtn.disabled = true;
    startPolling(aiEl);
  }

  // ============ 分享（带来源参数，便于后台区分渠道） ============
  function buildShareUrl(from) {
    var base = location.origin + '/';
    var params = [];
    var m = location.search.match(/[?&]sharecode=([^&]+)/);
    if (m) params.push('sharecode=' + m[1]);
    params.push('from=' + from);
    return base + '?' + params.join('&');
  }

  function isWeChat() {
    return /micromessenger/i.test(navigator.userAgent);
  }

  // 复制文本：优先 Clipboard API，失败回退 execCommand（兼容微信内置浏览器）
  function copyText(text, cb) {
    var finished = false;
    function done(ok) {
      if (finished) return;
      finished = true;
      if (cb) cb(ok);
    }
    function fallback() {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;outline:0;box-shadow:none;background:transparent;opacity:0;';
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        ta.setSelectionRange(0, text.length);
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        done(ok);
      } catch (e) {
        done(false);
      }
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(true); }).catch(fallback);
    } else {
      fallback();
    }
  }

  var SHARE_URL = '';

  function openSharePanel() {
    var mask = document.getElementById('shareMask');
    if (!mask) return;
    var wx = isWeChat();
    SHARE_URL = buildShareUrl('share');
    document.getElementById('shareLink').textContent = SHARE_URL;
    document.getElementById('shareSub').textContent = wx
      ? '按下面两步操作，即可发送给微信好友'
      : '复制链接后，打开微信粘贴发送给好友';
    document.getElementById('shareSteps').innerHTML = wx
      ? '<div class="share-step"><i>1</i><div>点击右上角的 <b>···</b> 按钮</div></div>'
        + '<div class="share-step"><i>2</i><div>选择 <b>发送给朋友</b>，也可以选「分享到朋友圈」</div></div>'
      : '<div class="share-step"><i>1</i><div>点击下方 <b>复制链接</b></div></div>'
        + '<div class="share-step"><i>2</i><div>打开微信，粘贴到聊天窗口发送</div></div>';
    var btn = document.getElementById('shareCopy');
    btn.textContent = '复制链接';
    btn.classList.remove('done');
    mask.classList.add('show');
    mask.classList.toggle('wechat', wx);
  }

  function closeSharePanel() {
    var m = document.getElementById('shareMask');
    if (m) m.classList.remove('show');
  }

  function initShare() {
    var btn = document.getElementById('shareApp');
    if (btn) {
      btn.addEventListener('click', function () {
        // 微信内置浏览器不支持系统分享 API，也不允许脚本直接拉起分享面板，
        // 可靠做法是引导用户点右上角菜单；其余环境优先调起系统分享。
        if (!isWeChat() && navigator.share) {
          navigator.share({
            title: '小宠百问 · 异宠饲养问答助手',
            text: '养异宠有疑问？推荐你用「小宠百问」，兔子仓鼠龙猫、守宫蜥蜴龟、鹦鹉、蜘蛛蝎子、水族都能问：',
            url: buildShareUrl('share')
          }).catch(function () { openSharePanel(); });
          return;
        }
        openSharePanel();
      });
    }

    var mask = document.getElementById('shareMask');
    if (!mask) return;
    document.getElementById('shareClose').addEventListener('click', closeSharePanel);
    mask.addEventListener('click', function (e) {
      if (e.target === mask) closeSharePanel();
    });
    document.getElementById('shareCopy').addEventListener('click', function () {
      var t = this;
      copyText(SHARE_URL || buildShareUrl('share'), function (ok) {
        if (!ok) { t.textContent = '请长按链接复制'; return; }
        t.textContent = '已复制 ✓';
        t.classList.add('done');
        setTimeout(function () {
          t.textContent = '复制链接';
          t.classList.remove('done');
        }, 2200);
      });
    });
  }

  // 分享图需带 sharecode 才能通过平台鉴权，缺失时用当前地址补齐
  function fixShareImage() {
    var m = location.search.match(/[?&]sharecode=([^&]+)/);
    if (!m) return;
    var src = location.origin + '/static/share.png?sharecode=' + m[1];
    var og = document.querySelector('meta[property="og:image"]');
    if (og) og.setAttribute('content', src);
    var img = document.querySelector('img[alt="小宠百问"]');
    if (img && img.src.indexOf('sharecode') < 0) img.src = src;
  }

  // ============ 客服面板 ============
  // 常见问题固定不变（不随机、不轮换），便于用户和客服口径一致
  var SVC_FAQ = [
    { q: '忘记密码 / 换手机号了怎么办？',
      a: '账号以「手机号 + 密码」登录。忘记密码可在下方「提交反馈」选择「其他问题」，写明注册手机号与大致注册时间，我们核实后为你重置。为保护隐私，我们不会在对话中索要密码。' },
    { q: '关掉页面，正在回答的问题会中断吗？',
      a: '不会。问题提交后由服务端继续生成答案，切到微信、锁屏或跳到其它板块都不影响；重新打开「小宠百问」会自动接续，答完还会提醒你查看。' },
    { q: '怎样提问才能答得更准？',
      a: '说清四件事，答案会准很多：什么动物、多大；箱里多少度、用什么垫材和灯；喂什么、多久喂一次；现在哪里不对、多久了。答完还能点下面的「继续问」接着问。' },
    { q: '回答能当作兽医诊断吗？',
      a: '不能。我们提供的是饲养管理与常见问题参考，不替代执业兽医。出现拒食超过 2 天、呼吸困难、持续腹泻、外伤出血、抽搐、脱肛脱垂等情况，请尽快联系有异宠诊疗经验的医院。' },
    { q: '合规速查的结果能作为法律依据吗？',
      a: '仅作快速参考。结果依据《国家重点保护野生动物名录》《重点管理外来入侵物种名录》、CITES 附录及「三有」名录整理；实际能否饲养还取决于合法来源（人工繁育证明、检疫、专用标识）与地方规定，请以当地林业、农业农村主管部门及官方最新名录为准。' },
    { q: '支持哪些物种？冷门物种能问吗？',
      a: '覆盖小型哺乳（兔、仓鼠、龙猫、豚鼠、蜜袋鼯、刺猬、雪貂、花枝鼠等）、爬宠（守宫、蛇、龟、蜥蜴、蛙、变色龙）、鸟类（鹦鹉、文鸟、八哥）、节肢（蜘蛛、蝎子、螳螂、甲虫）、水生（观赏虾、金鱼、锦鲤、蝾螈、六角恐龙）及寄居蟹等。冷门物种也可以直接问，我们会区分「已知」与「不确定」。' },
    { q: '行业动态多久更新一次？',
      a: '系统每天 06:00 自动抓取并合并资讯到 7 大板块（政策法规、市场大盘、爬宠、鸟类、小型哺乳、节肢·两栖、水生·水族），运营也会手动补充重要政策与市场信息。' },
    { q: '换设备后对话记录还在吗？',
      a: '在。用同一手机号登录即可，历史对话跟随账号保存在服务端，不依赖本机缓存。' },
    { q: '发现回答有错，怎么反馈？',
      a: '在下方「提交反馈」选择「内容纠错」，把出错的原话和正确说法一起发给我们。内容类反馈会优先处理，修正后知识库会同步更新。' },
    { q: '可以在公众号里直接用吗？',
      a: '可以。分享链接到微信，好友点开即可登录使用，无需下载 App；页面已适配手机屏幕与微信内置浏览器。' }
  ];

  var SVC = { type: 'bug', info: { support: '', support_hours: '' } };

  function openServicePanel() {
    var mask = document.getElementById('svcMask');
    if (!mask) return;
    mask.classList.add('show');
    document.body.style.overflow = 'hidden';
    loadMyFeedback(false);
  }
  function closeServicePanel() {
    var m = document.getElementById('svcMask');
    if (m) m.classList.remove('show');
    document.body.style.overflow = '';
  }

  // ============ 我的反馈（含客服回复） ============
  function renderMyFeedback(d, scroll) {
    var box = document.getElementById('myFbList');
    if (!box) return;
    var items = (d && d.items) || [];
    var badge = document.getElementById('myFbNew');
    if (badge) badge.style.display = (d && d.unread) ? 'inline-block' : 'none';
    var dot = document.getElementById('svcDot');
    if (dot) dot.hidden = !(d && d.unread);

    if (!items.length) {
      box.innerHTML = '<div class="my-fb-empty">还没有提交过反馈<br>有问题可以在上面直接告诉我们</div>';
      return;
    }
    var h = '';
    items.forEach(function (it) {
      var isNew = !!it.is_new;
      h += '<div class="my-fb-item' + (isNew ? ' is-new' : '') + '">'
        + '<div class="my-fb-top"><span class="my-fb-type">' + escapeHtml(it.type_name)
        + (isNew ? ' · 新回复' : '') + '</span>'
        + '<span class="my-fb-date">' + escapeHtml(it.date) + '</span></div>'
        + '<div class="my-fb-content">' + escapeHtml(it.content) + '</div>';
      if (it.reply) {
        h += '<div class="my-fb-reply"><b>客服回复' + (it.reply_time ? ' · ' + escapeHtml(it.reply_time) : '')
          + '</b>' + escapeHtml(it.reply) + '</div>';
      } else {
        h += '<div class="my-fb-wait">已收到，处理中</div>';
      }
      h += '</div>';
    });
    box.innerHTML = h;
    if (scroll) {
      try { box.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (e) {}
    }
    // 停留 1.5 秒再标记已读，让用户先看到「新回复」标记
    if (d && d.unread) {
      setTimeout(function () {
        api('/api/feedback/read', { method: 'POST' }).catch(function () {});
        if (badge) badge.style.display = 'none';
        if (dot) dot.hidden = true;
      }, 1500);
    }
  }

  function loadMyFeedback(scroll) {
    api('/api/feedback/mine').then(function (r) { return r.json(); })
      .then(function (d) { renderMyFeedback(d, scroll); })
      .catch(function () {});
  }

  function refreshServiceDot() {
    api('/api/feedback/mine').then(function (r) { return r.json(); }).then(function (d) {
      var dot = document.getElementById('svcDot');
      if (dot) dot.hidden = !(d && d.unread);
    }).catch(function () {});
  }

  function initService() {
    var mask = document.getElementById('svcMask');
    if (!mask) return;

    // 固定 FAQ 列表（手风琴，一次只展开一条，减少滚动）
    var list = document.getElementById('svcList');
    SVC_FAQ.forEach(function (it) {
      var box = document.createElement('div');
      box.className = 'svc-item';
      var q = document.createElement('div');
      q.className = 'svc-q';
      q.innerHTML = '<span class="qt">' + escapeHtml(it.q) + '</span><span class="ar">\u203a</span>';
      var a = document.createElement('div');
      a.className = 'svc-a';
      a.textContent = it.a;
      box.appendChild(q);
      box.appendChild(a);
      list.appendChild(box);
      q.addEventListener('click', function () {
        var wasOpen = box.classList.contains('open');
        Array.prototype.forEach.call(list.children, function (c) {
          c.classList.remove('open');
          var qq = c.querySelector('.svc-q');
          if (qq) qq.classList.remove('open');
        });
        if (!wasOpen) { box.classList.add('open'); q.classList.add('open'); }
      });
    });

    document.getElementById('openService').addEventListener('click', openServicePanel);
    document.getElementById('svcClose').addEventListener('click', closeServicePanel);
    mask.addEventListener('click', function (e) {
      if (e.target === mask) closeServicePanel();
    });

    // 反馈类型
    var types = document.getElementById('svcTypes');
    types.addEventListener('click', function (e) {
      var b = e.target.closest('.svc-type');
      if (!b) return;
      Array.prototype.forEach.call(types.querySelectorAll('.svc-type'), function (x) {
        x.classList.remove('active');
      });
      b.classList.add('active');
      SVC.type = b.dataset.type;
    });

    document.getElementById('svcSubmit').addEventListener('click', submitService);
    document.getElementById('svcAsk').addEventListener('click', function () {
      closeServicePanel();
      switchView('chat');
      setTimeout(function () { try { input.focus(); } catch (err) {} }, 260);
    });

    // 客服联系方式（后台「系统配置」可填，留空则不展示）
    fetch('/api/health').then(function (r) { return r.json(); }).then(function (d) {
      SVC.info.support = (d && d.support) || '';
      SVC.info.support_hours = (d && d.support_hours) || '';
      renderServiceContact();
    }).catch(function () {});
  }

  function renderServiceContact() {
    var box = document.getElementById('svcContactBox');
    if (!box) return;
    var sup = String(SVC.info.support || '').trim();
    var parts = [];
    if (sup) {
      // 纯号码渲染成可点击拨号，减少「看到号码还要手动复制」这一层损耗
      if (/^[\d\-\s+]{7,20}$/.test(sup)) {
        parts.push('客服电话：<a href="tel:' + escapeHtml(sup.replace(/[\s\-]/g, '')) + '">'
          + escapeHtml(sup) + '</a>');
      } else {
        parts.push('客服联系方式：<b>' + escapeHtml(sup) + '</b>');
      }
    }
    if (SVC.info.support_hours) parts.push('响应时间：' + escapeHtml(SVC.info.support_hours));
    if (!parts.length) { box.classList.remove('show'); return; }
    box.innerHTML = parts.join('<br>');
    box.classList.add('show');
  }

  function submitService() {
    var ta = document.getElementById('svcText');
    var btn = document.getElementById('svcSubmit');
    var content = (ta.value || '').trim();
    if (content.length < 4) {
      ta.focus();
      ta.style.borderColor = '#e5484d';
      setTimeout(function () { ta.style.borderColor = ''; }, 1400);
      return;
    }
    btn.disabled = true;
    btn.textContent = '提交中…';
    api('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: SVC.type,
        content: content,
        contact: (document.getElementById('svcContact').value || '').trim()
      })
    }).then(function (r) {
      return r.json().then(function (d) { return { status: r.status, d: d }; });
    }).then(function (res) {
      btn.disabled = false;
      if (res.status !== 200) {
        btn.textContent = '提交反馈';
        ta.style.borderColor = '#e5484d';
        setTimeout(function () { ta.style.borderColor = ''; }, 1600);
        if (res.d && res.d.error) alert(res.d.error);
        return;
      }
      btn.textContent = '已提交 ✓';
      btn.style.background = '#0d7a45';
      ta.value = '';
      document.getElementById('svcContact').value = '';
      setTimeout(function () {
        btn.textContent = '提交反馈';
        btn.style.background = '';
        loadMyFeedback(true);
      }, 900);
    }).catch(function (e) {
      btn.disabled = false;
      btn.textContent = '提交反馈';
      if (e && e.unauthorized) { closeServicePanel(); return; }
      alert('网络异常，请稍后重试');
    });
  }

  // ============ 追问建议（让用户少打字、更快问到点上） ============
  var FOLLOW_MAP = [
    { k: ['守宫', '豹纹', '睫角', '瘤尾'], q: ['箱子白天黑夜各多少度', '它不吃东西，先查哪几样', '蜕皮卡住一半怎么办'] },
    { k: ['角蛙', '蛙', '蝾螈', '六角', '娃娃鱼'], q: ['水温多少度合适', '一直不动是正常的吗', '多久喂一次、喂多少'] },
    { k: ['蛇', '蟒', '玉米蛇', '球蟒', '王蛇', '猪鼻'], q: ['多久喂一次算正常', '吐食了要不要先停喂', '蜕皮不完整是湿度不够吗'] },
    { k: ['龟', '陆龟', '水龟', '草龟', '巴西龟'], q: ['晒背灯一天开多久', '不吃东西是温度低了吗', '水多久换一次'] },
    { k: ['蜥蜴', '鬃狮', '蓝舌', '变色龙'], q: ['灯和钙粉怎么配', '晒点要多少度', '突然不吃了要紧吗'] },
    { k: ['兔', '兔子'], q: ['一天该喂多少草', '软便了怎么调', '要不要打疫苗'] },
    { k: ['仓鼠', '金丝熊', '侏儒'], q: ['笼子多大才够', '湿尾怎么急救', '两只能不能合笼'] },
    { k: ['龙猫', '毛丝鼠'], q: ['三十度会不会中暑', '洗澡砂怎么选', '磨牙要准备什么'] },
    { k: ['豚鼠', '荷兰猪'], q: ['维C 要怎么补', '笼子怎么布置', '掉毛正常吗'] },
    { k: ['蜜袋鼯', '蜜袋'], q: ['能不能单养', '食谱怎么配', '自残怎么办'] },
    { k: ['刺猬', '雪貂', '花枝鼠', '松鼠', '沙鼠'], q: ['冬天怎么保温', '身上的味道能减轻吗', '养几只合适'] },
    { k: ['鹦鹉', '玄凤', '虎皮', '牡丹', '文鸟', '八哥'], q: ['掉羽是什么原因', '要补哪些营养', '咬人怎么纠正'] },
    { k: ['蜘蛛', '捕鸟蛛', '蝎子', '螳螂', '甲虫', '蜈蚣'], q: ['湿度怎么控', '拒食正常吗', '要不要加热垫'] },
    { k: ['虾', '水晶虾'], q: ['水质参数怎么调', '能放什么水草', '脱壳失败怎么办'] },
    { k: ['金鱼', '锦鲤', '鱼缸'], q: ['养水要几天', '身上长白点怎么办', '多久换一次水'] },
    { k: ['寄居蟹', '蜗牛', '马陆'], q: ['换壳要准备什么', '湿度要多高', '能和其他宠物一起养吗'] },
  ];
  var FOLLOW_DEFAULT = ['它不太对劲时先看什么', '多久喂一次、喂多少', '要不要现在就去医院'];

  function suggestFollowUps(question, answer) {
    var hay = ((question || '') + ' ' + (answer || '').slice(0, 300)).toLowerCase();
    var out = [];
    for (var i = 0; i < FOLLOW_MAP.length && out.length < 3; i++) {
      var hit = FOLLOW_MAP[i].k.some(function (k) {
        return hay.indexOf(String(k).toLowerCase()) >= 0;
      });
      if (!hit) continue;
      FOLLOW_MAP[i].q.forEach(function (q) {
        if (out.length < 3 && out.indexOf(q) < 0) out.push(q);
      });
    }
    if (out.length < 3) {
      FOLLOW_DEFAULT.forEach(function (q) {
        if (out.length < 3 && out.indexOf(q) < 0) out.push(q);
      });
    }
    return out.slice(0, 3);
  }

  function appendFollowUps(bubble, question, answer) {
    var row = bubble && bubble.closest ? bubble.closest('.msg') : null;
    if (!row) return;
    var old = row.querySelector('.follow-wrap');
    if (old) old.remove();
    var qs = suggestFollowUps(question, answer);
    if (!qs.length) return;

    var wrap = document.createElement('div');
    wrap.className = 'follow-wrap';

    var lab = document.createElement('div');
    lab.className = 'follow-label';
    lab.textContent = '继续问';
    wrap.appendChild(lab);

    var chips = document.createElement('div');
    chips.className = 'follow-chips';
    qs.forEach(function (t) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'follow-chip';
      b.textContent = t;
      b.addEventListener('click', function () {
        if (sending) return;
        sendText(t);
      });
      chips.appendChild(b);
    });
    wrap.appendChild(chips);

    var acts = document.createElement('div');
    acts.className = 'follow-acts';
    var cp = document.createElement('button');
    cp.type = 'button';
    cp.className = 'follow-act';
    cp.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"></rect><path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg><span>复制答案</span>';
    cp.addEventListener('click', function () {
      copyText(answer || row.querySelector('.bubble').innerText, function (ok) {
        cp.querySelector('span').textContent = ok ? '已复制 ✓' : '复制失败';
        setTimeout(function () { cp.querySelector('span').textContent = '复制答案'; }, 1800);
      });
    });
    acts.appendChild(cp);
    wrap.appendChild(acts);
    row.appendChild(wrap);
    scrollBottom();
  }

  // ============ 养护：异宠档案 / 温湿度 / 症状分级 / 急救 / 就医 ============
  var CARE = {
    pane: 'home', pets: [], logs: [], petlogs: [], logSummary: {}, weights: {}, petId: '', loaded: false,
    triSpecies: '', triPart: '全部', triPicked: [], rendered: {}, lastEv: {}
  };

  // 养护模块使用埋点：只上报行为，不上报宠物资料内容
  function careEvent(kind, extra) {
    var body = { kind: kind };
    if (extra) { for (var k in extra) body[k] = extra[k]; }
    try {
      api('/api/care/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      }).catch(function () {});
    } catch (e) {}
  }

  // 同一面板 15 秒内重复进入只记一次，避免来回点把数据刷花
  function careEventOnce(kind, extra) {
    var now = Date.now();
    if (CARE.lastEv[kind] && now - CARE.lastEv[kind] < 15000) return;
    CARE.lastEv[kind] = now;
    careEvent(kind, extra);
  }

  // 物种 → 参考温湿度区间（成体常规饲养；幼体、繁殖期、蜕皮期需另调）
  var CARE_ENV = [
    { k: ['睫角', '冠尾'], n: '睫角守宫', t: [22, 26], h: [60, 80], emoji: '🦎' },
    { k: ['守宫', '豹纹', '肥尾', '瘤尾'], n: '守宫', t: [28, 32], h: [40, 60], emoji: '🦎' },
    { k: ['变色龙'], n: '变色龙', t: [24, 28], h: [50, 70], emoji: '🦎' },
    { k: ['鬃狮', '蜥蜴', '蓝舌', '石龙子'], n: '蜥蜴', t: [30, 35], h: [40, 50], emoji: '🦎' },
    { k: ['蛙', '角蛙', '树蛙'], n: '蛙类', t: [24, 28], h: [70, 85], emoji: '🐸' },
    { k: ['蛇', '玉米蛇', '球蟒', '王蛇', '猪鼻'], n: '蛇类', t: [28, 32], h: [50, 70], emoji: '🐍' },
    { k: ['龟', '陆龟', '水龟', '草龟', '巴西'], n: '龟类', t: [25, 30], h: [60, 80], emoji: '🐢' },
    { k: ['六角', '蝾螈'], n: '两栖', t: [16, 22], h: [60, 80], emoji: '🦎' },
    { k: ['龙猫'], n: '龙猫', t: [18, 22], h: [40, 55], emoji: '🐭' },
    { k: ['兔'], n: '兔子', t: [18, 25], h: [40, 60], emoji: '🐰' },
    { k: ['豚鼠', '荷兰猪'], n: '豚鼠', t: [18, 24], h: [40, 60], emoji: '🐹' },
    { k: ['仓鼠', '金丝熊', '侏儒'], n: '仓鼠', t: [20, 24], h: [40, 60], emoji: '🐹' },
    { k: ['蜜袋鼯'], n: '蜜袋鼯', t: [24, 28], h: [50, 60], emoji: '🐿️' },
    { k: ['刺猬'], n: '刺猬', t: [24, 28], h: [40, 60], emoji: '🦔' },
    { k: ['雪貂'], n: '雪貂', t: [18, 24], h: [40, 60], emoji: '🦡' },
    { k: ['松鼠', '花枝', '沙鼠', '大鼠', '老鼠'], n: '小型啮齿', t: [20, 26], h: [40, 60], emoji: '🐭' },
    { k: ['鹦鹉', '玄凤', '虎皮', '牡丹'], n: '鹦鹉', t: [20, 28], h: [40, 60], emoji: '🦜' },
    { k: ['文鸟', '八哥', '鸟'], n: '鸟类', t: [20, 28], h: [40, 60], emoji: '🐦' },
    { k: ['蜘蛛', '捕鸟蛛'], n: '蜘蛛', t: [25, 30], h: [60, 75], emoji: '🕷️' },
    { k: ['蝎子'], n: '蝎子', t: [26, 32], h: [50, 70], emoji: '🦂' },
    { k: ['螳螂', '甲虫', '锹', '兜虫'], n: '昆虫', t: [24, 28], h: [60, 80], emoji: '🪲' },
    { k: ['虾', '鱼', '锦鲤', '金鱼'], n: '水族', t: [22, 26], h: [0, 0], emoji: '🐟' }
  ];

  var CARE_SP_CHIPS = ['豹纹守宫', '睫角守宫', '玉米蛇', '球蟒', '鬃狮蜥', '中华草龟',
    '垂耳兔', '金丝熊', '龙猫', '玄凤鹦鹉', '蜜袋鼯', '捕鸟蛛'];

  function careEnvOf(species) {
    var s = species || '';
    for (var i = 0; i < CARE_ENV.length; i++) {
      for (var j = 0; j < CARE_ENV[i].k.length; j++) {
        if (s.indexOf(CARE_ENV[i].k[j]) >= 0) return CARE_ENV[i];
      }
    }
    return { n: '通用参考', t: [20, 28], h: [40, 70], emoji: '🐾' };
  }

  function careTime(ts) {
    var d = new Date((ts || 0) * 1000);
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    return (d.getMonth() + 1) + '/' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }

  function careAge(birthday) {
    if (!birthday) return '';
    var b = new Date(birthday.replace(/-/g, '/'));
    if (isNaN(b.getTime())) return '';
    var now = new Date();
    var m = (now.getFullYear() - b.getFullYear()) * 12 + (now.getMonth() - b.getMonth());
    if (m < 0) return '';
    if (m < 12) return m + ' 个月';
    var y = Math.floor(m / 12), mm = m % 12;
    return y + ' 岁' + (mm ? mm + ' 个月' : '');
  }

  function careToast(msg) {
    var el = document.getElementById('careToast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'careToast';
      el.className = 'answer-toast';
      el.innerHTML = '<span></span>';
      document.body.appendChild(el);
    }
    el.querySelector('span').textContent = msg;
    el.classList.add('show');
    clearTimeout(careToast._t);
    careToast._t = setTimeout(function () { el.classList.remove('show'); }, 2200);
  }

  var CARE_TITLES = {
    home: ['养护', '记录与判断'],
    pets: ['异宠档案', '一只一份，带照片和记录'],
    pet: ['档案', '照片 · 生命线'],
    env: ['温湿度记录', '对比适宜区间'],
    triage: ['症状分级', '先判断轻重缓急'],
    diag: ['拍照诊断', '拍清楚，看图出清单'],
    firstaid: ['急救指引', '稳住情况，争取时间'],
    vet: ['就医提示', '出发前该准备什么'],
    vetnear: ['附近医院', '按定位找，点一下导航']
  };

  function careShowPane(name) {
    CARE.pane = name;
    ['home', 'pets', 'pet', 'env', 'triage', 'diag', 'firstaid', 'vet', 'vetnear'].forEach(function (p) {
      var el = document.getElementById('pane-' + p);
      if (el) el.hidden = (p !== name);
    });
    var t = CARE_TITLES[name] || CARE_TITLES.home;
    document.getElementById('careTitle').textContent = t[0];
    document.getElementById('careSub').textContent = t[1];
    document.getElementById('careBack').hidden = (name === 'home');
    document.getElementById('careMain').scrollTop = 0;
    if (name === 'home') careRenderToday();
    if (name === 'pets') careRenderPets();
    if (name === 'pet') careRenderPetHome();
    if (name === 'env') careInitEnv();
    if (name === 'triage') careRenderTriage();
    if (name === 'diag') { careInitDiag(); if (!CARE.loaded) careLoadPets(careInitDiag); careLoadDiagHist(); }
    if (name === 'firstaid') { careRenderAid(); careEventOnce('aid', {}); }
    if (name === 'vet') { careRenderVet(); careEventOnce('vet', {}); }
    if (name === 'vetnear') careInitVetNear();
  }

  function careRefresh() {
    careLoadPets(function () {
      careLoadPetlogs(function () { careRenderLogBrief(); });
      if (CARE.pane === 'pets') careRenderPets();
      if (CARE.pane === 'env') careInitEnv();
    });
  }

  // ---------- 饲养日志：喂食 / 蜕皮 / 排便 / 用药 / 观察追踪 ----------
  var LOG_TYPES = [
    { k: 'feed', n: '喂食', short: '喂食' },
    { k: 'shed', n: '蜕皮', short: '蜕皮' },
    { k: 'poop', n: '排便', short: '排便' },
    { k: 'med', n: '用药', short: '用药' }
  ];
  function logTypeName(k) {
    var hit = '';
    LOG_TYPES.forEach(function (t) { if (t.k === k) hit = t.n; });
    if (k === 'watch') hit = '观察';
    if (k === 'weight') hit = '称重';
    return hit || k;
  }

  function careLoadPetlogs(cb) {
    api('/api/petlogs?limit=80').then(function (r) { return r.json(); }).then(function (d) {
      CARE.petlogs = (d && d.items) || [];
      CARE.logSummary = (d && d.summary) || {};
      CARE.weights = (d && d.weights) || {};
      // 今日卡要用 logSummary 算「多久没喂」，日志回来了得重画一次
      if (document.getElementById('careToday') && CARE.pane === 'home') careRenderToday();
      if (cb) cb();
    }).catch(function () { if (cb) cb(); });
  }

  function careDaysAgo(ts) {
    if (!ts) return '';
    var d = Math.floor((Date.now() / 1000 - ts) / 86400);
    if (d <= 0) return '今天';
    if (d === 1) return '1 天';
    return d + ' 天';
  }

  function careQuickLog(petId, type, btn) {
    if (btn) { btn.disabled = true; }
    api('/api/petlogs', {
      method: 'POST',
      body: JSON.stringify({ type: type, pet_id: petId })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) {
        careToast('已记下：' + logTypeName(type));
        if (btn) { btn.classList.add('done'); btn.textContent = '✓'; }
        careLoadPetlogs(function () {
          careRenderLogBrief();
          if (CARE.pane === 'pets') careRenderPets();
        });
      } else {
        careToast((d && d.error) || '记录失败');
        if (btn) btn.disabled = false;
      }
    }).catch(function () {
      careToast('网络异常，请重试');
      if (btn) btn.disabled = false;
    });
  }

  // 养护首页：观察追踪 + 最近记录
  function careRenderLogBrief() {
    var bar = document.getElementById('trackBar');
    var box = document.getElementById('logBrief');
    if (!bar || !box) return;

    // 未到期的观察项
    var now = Math.floor(Date.now() / 1000);
    var watch = null;
    CARE.petlogs.forEach(function (it) {
      if (it.type !== 'watch') return;
      if ((it.until || 0) > now && (!watch || (it.until || 0) > (watch.until || 0))) watch = it;
    });
    if (watch) {
      var left = Math.max(0, Math.round(((watch.until || 0) - now) / 3600));
      var p = carePetById(watch.pet_id);
      bar.hidden = false;
      bar.className = 'track-bar' + (watch.level >= 3 ? ' red' : '');
      bar.innerHTML = '<b>观察中</b><i>' + escapeHtml((p ? p.name + ' · ' : '') + (watch.symptoms || watch.note || '异常表现'))
        + '</i><span>剩 ' + left + ' 小时</span>';
    } else {
      bar.hidden = true;
    }

    var rows = CARE.petlogs.filter(function (it) { return it.type !== 'watch'; }).slice(0, 4);
    if (!rows.length) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = '<div class="lb-hd">RECENT · 最近记录</div>' + rows.map(function (it) {
      var p = carePetById(it.pet_id);
      return '<div class="lb-row"><span class="lb-type">' + escapeHtml(logTypeName(it.type)) + '</span>'
        + '<span class="lb-name">' + escapeHtml((p ? p.name : '未指定') + (it.note ? ' · ' + it.note : '')) + '</span>'
        + '<span class="lb-when">' + escapeHtml(careDaysAgo(it.ts)) + '</span></div>';
    }).join('');
  }

  // ---------- 宠物档案 ----------
  function careLoadPets(cb) {
    api('/api/pets').then(function (r) { return r.json(); }).then(function (d) {
      CARE.pets = (d && d.items) || [];
      CARE.loaded = true;
      careUpdateHome();
      if (cb) cb();
    }).catch(function () { if (cb) cb(); });
  }

  var CARE_TODAY = { pid: '', at: 0, log: null, count: 0, petIdx: 0, diag: null, diagAt: 0 };

  // 把「适宜区间」画成一把看得见的尺子


  // ---------- 环境现场判定（温湿度红绿灯） ----------
  var CARE_ADVICE = {
    temp_low: ['检查加热灯、温控器是否正常工作', '加保温垫，临时封住通风口（留透气孔）', '不要用热水袋直接接触箱底，容易烫伤'],
    temp_high: ['调低加热灯功率或温控上限', '移到阴凉处、加强通风，避免阳光直射', '换更大的水盆，帮助降温'],
    hum_low: ['每天喷水 1～2 次，或加大水盆面积', '换保湿性更好的垫材（椰土、苔藓）', '放一个湿躲避，帮助蜕皮'],
    hum_high: ['加强通风，箱盖不要完全封死', '换干爽垫材，减少喷水频率', '检查水盆有没有打翻']
  };
  var CARE_RISK = {
    temp_low: '长时间低温会让消化停滞、免疫力下降，变温动物尤其危险',
    temp_high: '高温会快速脱水、热应激，几小时内就可能危及生命',
    hum_low: '湿度过低会导致蜕皮不全、呼吸道不适',
    hum_high: '湿度过高容易滋生真菌、引发皮肤和呼吸道感染'
  };

  function careEnvJudge(species, t, h) {
    var env = careEnvOf(species);
    var tlo = env.t[0], thi = env.t[1], hlo = env.h[0], hhi = env.h[1];
    var water = hhi <= 0;           // 水族只看温度
    var items = [];
    if (t < tlo) items.push({ k: 'temp_low', dev: Math.round((tlo - t) * 10) / 10 });
    else if (t > thi) items.push({ k: 'temp_high', dev: Math.round((t - thi) * 10) / 10 });
    if (!water) {
      if (h < hlo) items.push({ k: 'hum_low', dev: Math.round(hlo - h) });
      else if (h > hhi) items.push({ k: 'hum_high', dev: Math.round(h - hhi) });
    }
    // 温度和湿度的量纲不一样，不能套同一个阈值：
    // 差 2℃ 已经会影响变温动物的消化，差 2% 湿度几乎无感。分开判，再取更严重的那个。
    var T_SOFT = 2, H_SOFT = 10;
    var level = 0, worst = null, worstScore = 0;
    items.forEach(function (it) {
      var soft = it.k.indexOf('temp') === 0 ? T_SOFT : H_SOFT;
      var score = it.dev / soft;
      if (score > worstScore) { worstScore = score; worst = it; }
      var lv = it.dev <= soft ? 1 : 2;
      if (lv > level) level = lv;
    });
    return { level: level, items: items, env: env, water: water, worst: worst };
  }

  function careJudgeSpecies() {
    var sel = document.getElementById('envPet');
    var pid = sel && sel.value;
    var p = null;
    CARE.pets.forEach(function (x) { if (x.id === pid) p = x; });
    if (!p && CARE.pets.length) p = CARE.pets[0];
    return p;
  }

  function careJudgePaint() {
    var tEl = document.getElementById('jTemp');
    var hEl = document.getElementById('jHum');
    var out = document.getElementById('judgeOut');
    if (!tEl || !hEl || !out) return;
    var p = careJudgeSpecies();
    var species = p ? p.species : '';
    var env = careEnvOf(species);
    var t = parseFloat(tEl.value), h = parseFloat(hEl.value);
    var water = env.h <= 0;

    document.getElementById('jvTemp').textContent = t.toFixed(1);
    document.getElementById('jvHum').textContent = Math.round(h);
    document.getElementById('jTempRange').textContent =
      '适宜 ' + env.t[0] + '–' + env.t[1] + '℃';
    document.getElementById('jHumRange').textContent = water
      ? '水生环境不判湿度'
      : '适宜 ' + env.h[0] + '–' + env.h[1] + '%';
    document.getElementById('judgeSp').textContent =
      (p ? p.name + ' · ' + (env.n || species) : (env.n || '通用参考'));

    var r = careEnvJudge(species, t, h);
    var lvTxt = ['达标', '轻微偏差', '需要马上处理'][r.level];
    var msg;
    if (r.level === 0) {
      msg = '温度和湿度都在' + (env.n || '该物种') + '的适宜区间内，保持现状就行。';
    } else {
      msg = r.items.map(function (it) {
        var name = it.k.indexOf('temp') === 0 ? '温度' : '湿度';
        var dir = it.k.indexOf('low') > 0 ? '偏低' : '偏高';
        var unit = it.k.indexOf('temp') === 0 ? '℃' : '%';
        return name + dir + ' ' + it.dev + unit;
      }).join('，') + '。';
      if (r.level === 2) msg += CARE_RISK[(r.worst || r.items[0]).k] + '。';
    }

    var advice = '';
    if (r.level > 0) {
      var seen = {};
      var list = [];
      r.items.forEach(function (it) {
        (CARE_ADVICE[it.k] || []).forEach(function (a) {
          if (!seen[a]) { seen[a] = 1; list.push(a); }
        });
      });
      advice = '<div class="jo-advice">' + list.slice(0, 4).map(function (a) {
        return '<div><i>·</i><span>' + escapeHtml(a) + '</span></div>';
      }).join('') + '</div>';
    }

    out.className = 'judge-out jo' + r.level;
    out.innerHTML = '<div class="jo-bar"><span class="jo-dot"></span>'
      + '<span class="jo-lv">' + lvTxt + '</span>'
      + (r.worst ? '<span class="jo-deg">偏差 ' + r.worst.dev
          + (r.worst.k.indexOf('temp') === 0 ? '℃' : '%') + '</span>' : '') + '</div>'
      + '<div class="jo-msg">' + escapeHtml(msg) + '</div>' + advice;
  }

  function careJudgeInit() {
    var tEl = document.getElementById('jTemp');
    var hEl = document.getElementById('jHum');
    if (!tEl || !hEl || tEl.dataset.done) return;
    var p = careJudgeSpecies();
    var env = careEnvOf(p ? p.species : '');
    // 初始值取适宜区间中点，用户拖起来更有参照
    var tMid = env.t[0] && env.t[1] ? (env.t[0] + env.t[1]) / 2 : 26;
    var hMid = env.h[1] > 0 ? (env.h[0] + env.h[1]) / 2 : 55;
    if (CARE.logs && CARE.logs.length && CARE.logs[0].temp) {
      tMid = CARE.logs[0].temp;
      hMid = CARE.logs[0].hum;
    }
    tEl.value = Math.round(tMid * 2) / 2;
    hEl.value = Math.round(hMid);
    tEl.addEventListener('input', careJudgePaint);
    hEl.addEventListener('input', careJudgePaint);
    tEl.dataset.done = '1';
    careJudgePaint();
  }

  function careScaleBar(val, range, unit) {
    if (val === null || val === undefined || isNaN(val)) return '';
    if (!range || !range[1]) return '';
    var lo = range[0], hi = range[1];
    var pad = Math.max((hi - lo) * 1.2, 1);
    var dMin = lo - pad, dMax = hi + pad, span = dMax - dMin;
    var pos = Math.max(0, Math.min(1, (val - dMin) / span)) * 100;
    var left = (lo - dMin) / span * 100;
    var width = (hi - lo) / span * 100;
    var ok = val >= lo && val <= hi;
    return '<div class="scale">'
      + '<div class="scale-track">'
      + '<div class="scale-range" style="left:' + left.toFixed(1) + '%;width:' + width.toFixed(1) + '%"></div>'
      + '<div class="scale-dot' + (ok ? ' ok' : '') + '" style="left:' + pos.toFixed(1) + '%"></div>'
      + '</div>'
      + '<div class="scale-labels"><span>' + Math.round(dMin) + unit + '</span>'
      + '<span>适宜 ' + lo + '–' + hi + '</span>'
      + '<span>' + Math.round(dMax) + unit + '</span></div>'
      + '</div>';
  }

  // 各物种的饲养节奏参考（成体常规值）。只用来判断「该不该提醒」，
  // 不是硬标准——幼体、季节、个体差异都很大，所以区间放宽，只在明显超期时出声。
  var CARE_BASE = {
    '睫角守宫': { feed: [1, 2], shed: [28, 45] },
    '守宫': { feed: [3, 7], shed: [21, 35] },
    '变色龙': { feed: [1, 3], shed: [30, 60] },
    '蜥蜴': { feed: [1, 3], shed: [30, 60] },
    '蛙类': { feed: [2, 7], shed: [30, 60] },
    '蛇类': { feed: [7, 14], shed: [30, 60] },
    '龟类': { feed: [1, 2], shed: [0, 0] },
    '两栖': { feed: [1, 2], shed: [0, 0] },
    '龙猫': { feed: [1, 1], shed: [0, 0] },
    '兔子': { feed: [1, 1], shed: [60, 120] },
    '豚鼠': { feed: [1, 1], shed: [0, 0] },
    '仓鼠': { feed: [1, 2], shed: [0, 0] },
    '蜜袋鼯': { feed: [1, 1], shed: [0, 0] },
    '刺猬': { feed: [1, 1], shed: [90, 150] },
    '雪貂': { feed: [1, 1], shed: [60, 120] },
    '小型啮齿': { feed: [1, 1], shed: [0, 0] },
    '鹦鹉': { feed: [1, 1], shed: [60, 120] },
    '鸟类': { feed: [1, 1], shed: [60, 120] },
    '蜘蛛': { feed: [5, 14], shed: [30, 90] },
    '蝎子': { feed: [5, 14], shed: [60, 120] },
    '昆虫': { feed: [2, 5], shed: [20, 60] },
    '水族': { feed: [1, 1], shed: [0, 0] },
    '通用参考': { feed: [2, 7], shed: [30, 60] }
  };

  function careBaseOf(species) {
    return CARE_BASE[careEnvOf(species).n] || CARE_BASE['通用参考'];
  }

  function careDayNum(ts) {
    if (!ts) return -1;
    return Math.floor((Date.now() / 1000 - ts) / 86400);
  }

  // 治疗周期通常 3–6 周，一次诊断值三次回访：3 天、7 天、14 天各一次
  function careFuWindow(dd) {
    if (dd >= 3 && dd < 7) return 1;
    if (dd >= 7 && dd < 14) return 2;
    if (dd >= 14 && dd < 21) return 3;
    return 0;
  }

  // 回访标记：点过「去拍照」就不再反复提示
  var CARE_FU_KEY = 'xc_care_fu';
  function careFuDone(id) {
    try {
      var o = JSON.parse(localStorage.getItem(CARE_FU_KEY) || '{}');
      return !!o[id];
    } catch (e) { return false; }
  }
  function careFuMark(id) {
    try {
      var o = JSON.parse(localStorage.getItem(CARE_FU_KEY) || '{}');
      o[id] = 1;
      var ks = Object.keys(o);
      if (ks.length > 60) { ks.slice(0, ks.length - 60).forEach(function (k) { delete o[k]; }); }
      localStorage.setItem(CARE_FU_KEY, JSON.stringify(o));
    } catch (e) {}
  }

  function careTodayClick(e) {
    var sw = e.target.closest('[data-sw]');
    if (sw) {
      var n = Math.max(1, CARE.pets.length);
      CARE_TODAY.petIdx = ((CARE_TODAY.petIdx || 0) + 1) % n;
      CARE_TODAY.log = null;
      CARE_TODAY.pid = '';
      careRenderToday();
      return;
    }
    var fu = e.target.closest('[data-fu]');
    if (fu) {
      careFuMark(fu.dataset.fu);
      careShowPane('diag');
      return;
    }
    var b = e.target.closest('[data-act]');
    if (!b) return;
    var pane = b.dataset.act;
    careShowPane(pane);
    var p = CARE.pets[CARE_TODAY.petIdx || 0];
    if (pane === 'pets' && p) {
      setTimeout(function () {
        var card = document.querySelector('.pet-card[data-pid="' + p.id + '"]');
        if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 60);
    }
  }

  function careRenderToday() {
    var box = document.getElementById('careToday');
    if (!box) return;
    var envTail = document.getElementById('careEnvTail');

    if (!box.dataset.bound) {
      box.dataset.bound = '1';
      box.addEventListener('click', careTodayClick);
    }

    if (!CARE.pets.length) {
      box.innerHTML = '<div class="today-top"><span class="who">还没建档</span><span class="st">空着</span></div>'
        + '<div class="td-adv"><div class="td-adv-body">建一份档案，之后每天打开就知道该喂了没、'
        + '箱里湿度够不够。</div>'
        + '<button class="td-act" data-act="pets">建一份</button></div>';
      if (envTail) envTail.textContent = '';
      return;
    }

    var idx = CARE_TODAY.petIdx || 0;
    if (idx >= CARE.pets.length) idx = 0;
    var p = CARE.pets[idx];
    var env = careEnvOf(p.species);
    var base = careBaseOf(p.species);
    var sum = (CARE.logSummary && CARE.logSummary[p.id]) || {};

    if (!(CARE_TODAY.pid === p.id && Date.now() - CARE_TODAY.at < 30000)) {
      CARE_TODAY.pid = p.id;
      CARE_TODAY.at = Date.now();
      api('/api/care/logs?pet_id=' + encodeURIComponent(p.id)).then(function (r) { return r.json(); }).then(function (d) {
        if (CARE_TODAY.pid !== p.id) return;
        var items = (d && d.items) || [];
        CARE_TODAY.log = items[0] || null;
        CARE_TODAY.count = items.length;
        if (document.getElementById('careToday')) careRenderToday();
      }).catch(function () {});
    }
    var log = CARE_TODAY.pid === p.id ? CARE_TODAY.log : null;

    // 诊断回访：只拉一次，10 分钟内不重复
    if (!CARE_TODAY.diagAt || Date.now() - CARE_TODAY.diagAt > 600000) {
      CARE_TODAY.diagAt = Date.now();
      api('/api/diagnoses?limit=6').then(function (r) { return r.json(); }).then(function (d) {
        CARE_TODAY.diag = ((d && d.items) || [])[0] || null;
        if (document.getElementById('careToday')) careRenderToday();
      }).catch(function () {});
    }

    // ---- 三行状态 ----
    function row(k, v, tag, cls) {
      return '<div class="td-row"><span class="td-k">' + k + '</span>'
        + '<span class="td-v">' + v + '</span>'
        + (tag ? '<span class="td-tag' + (cls || '') + '">' + tag + '</span>' : '')
        + '</div>';
    }

    var rows = '';
    var feedD = careDayNum(sum.feed);
    if (feedD < 0) {
      rows += row('喂食', '<i>还没有记录</i>', '记一次');
    } else {
      var fTxt = feedD <= 0 ? '今天' : feedD + ' 天前';
      if (feedD > base.feed[1]) rows += row('喂食', fTxt, '该喂了', ' due');
      else if (feedD >= base.feed[0]) rows += row('喂食', fTxt, '正常', ' ok');
      else rows += row('喂食', fTxt, '刚喂过');
    }

    if (base.shed[1] > 0) {
      var shedD = careDayNum(sum.shed);
      if (shedD < 0) rows += row('蜕皮', '<i>还没有记录</i>', '记一次');
      else if (shedD > base.shed[1]) rows += row('蜕皮', shedD + ' 天前', '留意', ' due');
      else rows += row('蜕皮', shedD + ' 天前', '正常', ' ok');
    }

    var envTxt = '<i>还没有记录</i>', envTag = '记一条', envCls = '';
    var jr = null;
    if (log) {
      var t = Number(log.temp), h = Number(log.hum);
      envTxt = t.toFixed(1) + '<i>℃</i>' + (env.h[1] > 0 ? ' / ' + Math.round(h) + '<i>%</i>' : '');
      jr = careEnvJudge(p.species, t, h);
      if (jr.level === 2) { envTag = '马上处理'; envCls = ' due'; }
      else if (jr.level === 1) { envTag = '略偏'; }
      else { envTag = '区间内'; envCls = ' ok'; }
    }
    rows += row('环境', envTxt, envTag, envCls);

    // ---- 今天做一件事 ----
    var hd = '', body = '', act = '', actPane = '';
    var hasTrack = (CARE.petlogs || []).filter(function (it) {
      return it.type === 'watch' && it.until && it.until > Date.now() / 1000
        && (!it.pet_id || it.pet_id === p.id);
    })[0];

    if (jr && jr.level === 2) {
      var w = jr.worst || jr.items[0];
      var isT = w.k.indexOf('temp') === 0;
      hd = '先处理环境';
      body = '箱内' + (isT ? '温度' : '湿度') + '偏离了' + (p.species || env.n) + '的适宜区间 '
        + (isT ? env.t[0] + '–' + env.t[1] + '℃' : env.h[0] + '–' + env.h[1] + '%')
        + '，' + (CARE_ADVICE[w.k] || [])[0] + '。';
      act = '记一条新读数'; actPane = 'env';
    } else if (hasTrack) {
      hd = '观察期进行中';
      body = '「' + escapeHtml(hasTrack.symptoms || hasTrack.note || '观察') + '」还在追踪，'
        + Math.max(0, Math.ceil((hasTrack.until - Date.now() / 1000) / 3600)) + ' 小时后到期。'
        + '期间精神、进食、排便有变化就再拍一张。';
      act = '再拍一张'; actPane = 'diag';
    } else if (feedD > base.feed[1]) {
      hd = '该喂了';
      body = '上次喂食是 ' + feedD + ' 天前，' + (p.species || env.n || '这类') + '常规间隔 '
        + base.feed[0] + '–' + base.feed[1] + ' 天。喂完记一笔，下次就不会算错。';
      act = '记一次喂食'; actPane = 'pets';
    } else if (base.shed[1] > 0 && careDayNum(sum.shed) > 0 && careDayNum(sum.shed) >= base.shed[1] - 5 && careDayNum(sum.shed) < 99) {
      hd = '可能要蜕皮了';
      body = '离上次蜕皮 ' + careDayNum(sum.shed) + ' 天了，把湿度往上带一点、放个湿躲避，'
        + '蜕不干净时别硬撕。';
      act = '看看蜕皮不顺'; actPane = 'triage';
    } else if (!sum.feed && !sum.shed) {
      hd = '从第一条记录开始';
      body = '喂食、蜕皮、称重，各记一次。三天后这张卡就知道你的' + (p.species || '宠物') + '什么节奏。';
      act = '记一次喂食'; actPane = 'pets';
    } else {
      hd = '今天没什么要做的';
      body = '喂食、蜕皮、环境都在正常范围。想更稳一点，隔两周称一次重，曲线比感觉准。';
      act = '去档案里称重'; actPane = 'pets';
    }

    // ---- 诊断回访条 ----
    var call = '';
    var dg = CARE_TODAY.diag;
    if (dg) {
      var dd = careDayNum(dg.ts);
      var win = careFuWindow(dd);
      var fkey = dg.id + '#' + win;
      if (win && !careFuDone(fkey)) {
        var fuTxt = win === 1
          ? '3 天前诊断过「<b>' + escapeHtml(dg.title || '症状') + '</b>」，拍张新的看有没有好转'
          : (win === 2
            ? '一周前诊断过「<b>' + escapeHtml(dg.title || '症状') + '</b>」，对比一下恢复得怎么样'
            : '两周前诊断过「<b>' + escapeHtml(dg.title || '症状') + '</b>」，现在什么情况了');
        call = '<div class="td-call">'
          + '<div class="td-call-tx">' + fuTxt + '</div>'
          + '<button class="td-call-go" data-fu="' + escapeHtml(fkey) + '">去拍照 ›</button>'
          + '</div>';
      }
    }

    var days = posterDays(p);
    var now = new Date();
    var wk = '日一二三四五六'.charAt(now.getDay());

    var h = '<div class="td-head"><span class="td-date">'
      + (now.getMonth() + 1) + ' 月 ' + now.getDate() + ' 日 · 周' + wk + '</span>'
      + '<span class="td-day">' + (days > 0 ? '到家 ' + days + ' 天' : '今天建档') + '</span></div>'
      + '<div class="today-top"><span class="who">' + carePhotoTag(p, 'td-av') + '<b>' + escapeHtml(p.name) + '</b> · '
      + escapeHtml(p.species || '未填物种') + '</span>'
      + (CARE.pets.length > 1
          ? '<span class="st" data-sw="1" style="cursor:pointer">' + (idx + 1) + '/' + CARE.pets.length + ' 切换</span>'
          : '<span class="st">' + (CARE.pets.length ? '仅一只' : '') + '</span>')
      + '</div>'
      + '<div class="td-rows">' + rows + '</div>'
      + '<div class="td-adv"><div class="td-adv-hd">' + hd + '</div>'
      + '<div class="td-adv-body">' + body + '</div>'
      + (act ? '<button class="td-act" data-act="' + actPane + '">' + act + '</button>' : '')
      + '</div>'
      + call;

    box.innerHTML = h;
    if (envTail) envTail.textContent = (CARE_TODAY.count ? '共 ' + CARE_TODAY.count + ' 条' : '');

  }


  function careUpdateHome() {
    var el = document.getElementById('petCountDesc');
    var n = CARE.pets.length;
    if (el) {
      el.textContent = n
        ? ('建了 ' + n + ' 份，点进去看或者接着加')
        : '给每只单独记：什么时候来的、现在多重、吃什么';
    }
    var tail = document.getElementById('carePetTail');
    if (tail) tail.textContent = n ? (n + ' 只') : '';
    careRenderToday();
  }

  // ---------- 体重曲线：档案里改一次体重就长一个点 ----------
  function careWeightsOf(pid) {
    var arr = CARE.weights[pid];
    return (arr && arr.length) ? arr : [];
  }

  // 档案卡右上角的迷你折线，只给趋势不给刻度
  function careSpark(arr) {
    if (!arr || arr.length < 2) return '';
    var W = 54, H = 18, pad = 2;
    var vs = arr.map(function (p) { return p.v; });
    var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs);
    var span = (mx - mn) || 1;
    var pts = arr.map(function (p, i) {
      var x = pad + (W - pad * 2) * (i / (arr.length - 1));
      var y = H - pad - (H - pad * 2) * ((p.v - mn) / span);
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    var last = pts[pts.length - 1].split(',');
    var up = arr[arr.length - 1].v >= arr[0].v;
    var color = up ? '#B4572F' : '#2B5871';
    return '<svg width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">'
      + '<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + color + '" stroke-width="1.2" stroke-linejoin="round"/>'
      + '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="1.6" fill="' + color + '"/></svg>';
  }

  // 档案卡上的体重行：当前值 + 与上一个点的差值 + 迷你曲线
  function careWeightLine(p) {
    var arr = careWeightsOf(p.id);
    var cur = arr.length ? arr[arr.length - 1].v : (parseFloat(p.weight) || 0);
    if (!cur) return '';
    var h = '<div class="pet-wt">体重 <b>' + (Math.round(cur * 10) / 10) + '</b> g';
    if (arr.length >= 2) {
      var diff = Math.round((cur - arr[arr.length - 2].v) * 10) / 10;
      if (diff > 0) h += '<span class="wt-up">↑ ' + diff + '</span>';
      else if (diff < 0) h += '<span class="wt-down">↓ ' + Math.abs(diff) + '</span>';
      else h += '<span>持平</span>';
    }
    if (arr.length >= 2) h += '<span class="wt-spark">' + careSpark(arr) + '</span>';
    return h + '</div>';
  }

  // 表单里的完整曲线 + 快捷记体重
  function careWeightBox(pid) {
    var arr = careWeightsOf(pid);
    var body;
    if (!arr.length) {
      body = '<div class="wt-empty">还没有体重记录。填上面的体重保存一次，就长出第一个点；之后隔几周记一次，能看出长没长、掉没掉。</div>';
    } else if (arr.length === 1) {
      body = '<div class="wt-empty">已记 1 次：' + arr[0].v + ' g（' + careDateTxt(arr[0].ts) + '）。再记一次就能连成曲线。</div>';
    } else {
      body = careWeightChart(arr);
    }
    return '<div class="wt-box"><h5>WEIGHT · 体重曲线（克）</h5>' + body
      + '<div class="wt-input"><input id="wtVal" type="number" step="0.1" inputmode="decimal" placeholder="今天的体重，如 68.5" maxlength="8">'
      + '<button type="button" id="wtAdd">记一笔</button></div></div>';
  }

  function careDateTxt(ts) {
    var d = new Date((ts || 0) * 1000);
    return (d.getMonth() + 1) + '/' + d.getDate();
  }

  function careWeightChart(arr) {
    var W = 300, H = 86, pl = 6, pr = 30, pt = 8, pb = 16;
    var vs = arr.map(function (p) { return p.v; });
    var mn = Math.min.apply(null, vs), mx = Math.max.apply(null, vs);
    if (mx === mn) { mx = mn + 1; mn = Math.max(0, mn - 1); }
    var pad = (mx - mn) * 0.12;
    mn = Math.max(0, mn - pad); mx = mx + pad;
    var span = mx - mn;
    var x = function (i) { return pl + (W - pl - pr) * (i / (arr.length - 1)); };
    var y = function (v) { return pt + (H - pt - pb) * (1 - (v - mn) / span); };
    var pts = arr.map(function (p, i) { return x(i).toFixed(1) + ',' + y(p.v).toFixed(1); });
    var area = 'M' + x(0).toFixed(1) + ',' + (H - pb) + ' L' + pts.join(' L')
      + ' L' + x(arr.length - 1).toFixed(1) + ',' + (H - pb) + ' Z';
    var last = arr[arr.length - 1];
    var h = '<svg class="wt-chart" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">'
      + '<line x1="' + pl + '" y1="' + (H - pb) + '" x2="' + (W - pr) + '" y2="' + (H - pb) + '" stroke="#EAE4D6" stroke-width="1"/>'
      + '<path d="' + area + '" fill="#E7EFE6" opacity=".7"/>'
      + '<polyline points="' + pts.join(' ') + '" fill="none" stroke="#1E4634" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>'
      + arr.map(function (p, i) {
          var isLast = i === arr.length - 1;
          return '<circle cx="' + x(i).toFixed(1) + '" cy="' + y(p.v).toFixed(1) + '" r="' + (isLast ? 2.6 : 1.6) + '" fill="' + (isLast ? '#B4572F' : '#1E4634') + '"/>';
        }).join('')
      + '<text x="' + (W - pr + 4) + '" y="' + (y(last.v) + 3.2).toFixed(1) + '" font-size="9" fill="#4A554C" font-family="ui-monospace,Menlo,monospace">' + last.v + '</text>'
      + '<text x="' + pl + '" y="' + (H - 4) + '" font-size="8" fill="#8A9088" font-family="ui-monospace,Menlo,monospace">' + careDateTxt(arr[0].ts) + '</text>'
      + '<text x="' + (W - pr) + '" y="' + (H - 4) + '" font-size="8" fill="#8A9088" text-anchor="end" font-family="ui-monospace,Menlo,monospace">' + careDateTxt(last.ts) + '</text>'
      + '</svg>';
    // 变化摘要
    var d0 = arr[0].v, dn = last.v;
    var delta = Math.round((dn - d0) * 10) / 10;
    var span2 = Math.round((last.ts - arr[0].ts) / 86400);
    var txt = delta > 0 ? ('涨 ' + delta + ' g') : (delta < 0 ? ('掉 ' + Math.abs(delta) + ' g') : '持平');
    h += '<div class="pet-wt" style="margin-top:6px">共 ' + arr.length + ' 次 · ' + (span2 > 0 ? span2 + ' 天' : '当天')
      + ' · <b>' + txt + '</b></div>';
    return h;
  }

  function careAddWeight(pid) {
    var inp = document.getElementById('wtVal');
    if (!inp) return;
    var v = parseFloat(inp.value);
    if (!(v > 0)) { careToast('请填写体重数字'); return; }
    var btn = document.getElementById('wtAdd');
    if (btn) btn.disabled = true;
    api('/api/petlogs', {
      method: 'POST',
      body: JSON.stringify({ type: 'weight', pet_id: pid, value: v })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) {
        careToast('已记下 ' + v + ' g');
        careLoadPetlogs(function () {
          var box = document.querySelector('#careSheet .wt-box');
          if (box) {
            var nb = document.createElement('div');
            nb.innerHTML = careWeightBox(pid);
            box.replaceWith(nb.firstChild);
            careBindWeightBox(pid);
          }
          careRenderPets();
          careRenderLogBrief();
        });
      } else {
        careToast((d && d.error) || '记录失败');
        if (btn) btn.disabled = false;
      }
    }).catch(function () {
      careToast('网络异常，请重试');
      if (btn) btn.disabled = false;
    });
  }

  function careBindWeightBox(pid) {
    var btn = document.getElementById('wtAdd');
    if (btn) btn.addEventListener('click', function () { careAddWeight(pid); });
    var inp = document.getElementById('wtVal');
    if (inp) inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') careAddWeight(pid); });
  }

  // ---------- 单只档案主页：照片 + 生命线 ----------
  var PET_HOME = { pid: '', items: [], total: 0, at: 0 };

  function carePhotoTag(p, cls) {
    if (p && typeof p.photo === 'string' && p.photo.indexOf('data:image/') === 0) {
      return '<img class="' + cls + '" src="' + p.photo + '" alt="' + escapeHtml(p.name || '') + '">';
    }
    return '';
  }

  function careRenderPetHome() {
    var hero = document.getElementById('petHero');
    var list = document.getElementById('tlList');
    var cnt = document.getElementById('tlCount');
    if (!hero || !list) return;

    var p = carePetById(CARE.petId) || CARE.pets[0];
    if (!p) {
      hero.innerHTML = '<div class="tl-empty">还没有档案。先建一份，这里会从第一天开始记。</div>';
      list.innerHTML = '';
      if (cnt) cnt.textContent = '';
      return;
    }
    CARE.petId = p.id;
    var days = posterDays(p);
    var av = carePhotoTag(p, '') || escapeHtml((p.name || '宠').slice(0, 1));
    var meta = [p.species, p.sex, careAge(p.birthday)].filter(Boolean).join(' · ');

    hero.innerHTML = '<div class="pet-hero">'
      + '<div class="pet-hero-ph">' + av + '</div>'
      + '<div class="pet-hero-main">'
      + '<div class="pet-hero-name">' + escapeHtml(p.name) + '</div>'
      + '<div class="pet-hero-meta">' + escapeHtml(meta || '未填物种')
      + (days > 0 ? '<br>到家 ' + days + ' 天' : '') + '</div>'
      + '</div></div>'
      + '<div class="pet-acts">'
      + '<button data-pa="edit">编辑档案</button>'
      + '<button data-pa="poster">生成海报</button>'
      + '<button data-pa="back">档案列表</button>'
      + '</div>';

    hero.onclick = function (e) {
      var b = e.target.closest('[data-pa]');
      if (!b) return;
      var a = b.dataset.pa;
      if (a === 'edit') careOpenPetForm(p.id);
      else if (a === 'poster') careOpenPoster(p.id);
      else if (a === 'back') careShowPane('pets');
    };

    // 数据 30 秒内不重复拉
    if (PET_HOME.pid === p.id && Date.now() - PET_HOME.at < 30000) {
      carePaintTimeline();
      return;
    }
    list.innerHTML = '<div class="tl-empty">正在读记录…</div>';
    api('/api/pets/timeline?limit=150&pet_id=' + encodeURIComponent(p.id))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (CARE.pane !== 'pet' || CARE.petId !== p.id) return;
        PET_HOME.items = (d && d.items) || [];
        PET_HOME.total = (d && d.total) || 0;
        PET_HOME.pid = p.id;
        PET_HOME.at = Date.now();
        carePaintTimeline();
      })
      .catch(function () {
        list.innerHTML = '<div class="tl-empty">记录没读出来，下拉重试。</div>';
      });
  }

  function carePaintTimeline() {
    var list = document.getElementById('tlList');
    var cnt = document.getElementById('tlCount');
    if (!list) return;
    var items = PET_HOME.items || [];
    if (cnt) cnt.textContent = items.length ? ('共 ' + PET_HOME.total + ' 条') : '';
    if (!items.length) {
      list.innerHTML = '<div class="tl-empty">这条线还是空的。<br>'
        + '喂一次、蜕一次皮、称一次重，都会落在这里，时间越久越有用。</div>';
      return;
    }
    var html = items.map(function (it) {
      var cls = it.kind === 'diag' ? ' diag' : '';
      var thumb = (it.thumb && it.thumb.indexOf('data:image/') === 0)
        ? '<img class="tl-thumb" src="' + it.thumb + '" alt="">' : '';
      var d = careDayNum(it.ts);
      var when = d <= 0 ? '今天' : (d === 1 ? '昨天' : (d < 30 ? d + ' 天前' : careTime(it.ts).split(' ')[0]));
      var sub = it.sub || '';
      return '<div class="tl-item' + cls + '">' + thumb
        + '<div class="tl-main"><div class="tl-title">' + escapeHtml(it.title || '') + '</div>'
        + (sub ? '<div class="tl-sub">' + escapeHtml(sub) + '</div>' : '')
        + '</div><div class="tl-when">' + escapeHtml(when) + '</div></div>';
    }).join('');
    list.innerHTML = html;
  }

  function careOpenPetHome(pid) {
    CARE.petId = pid || '';
    PET_HOME.pid = '';
    careShowPane('pet');
  }

  function careRenderPets() {
    var box = document.getElementById('petList');
    if (!box) return;
    if (!CARE.pets.length) {
      box.innerHTML = '<div class="pet-empty"><b>还没有档案</b>建一份，把物种、生日、体重记下来<br>以后看病、换粮、调温都有依据</div>';
      return;
    }
    var h = '';
    CARE.pets.forEach(function (p) {
      var env = careEnvOf(p.species);
      var meta = [p.species, p.sex, careAge(p.birthday)].filter(Boolean).join(' · ');
      h += '<div class="pet-card" data-pid="' + escapeHtml(p.id) + '">'
        + '<div class="pet-av">' + (carePhotoTag(p, '') || escapeHtml((p.name || '宠').slice(0, 1))) + '</div>'
        + '<div class="pet-main">'
        + '<div class="pet-name">' + escapeHtml(p.name) + '</div>'
        + '<div class="pet-meta">' + escapeHtml(meta || '未填物种') + '</div>'
        + careWeightLine(p)
        + '<div class="pet-last">参考 ' + env.t[0] + '～' + env.t[1] + '℃'
        + (env.h[1] ? ' · 湿度 ' + env.h[0] + '～' + env.h[1] + '%' : '') + '</div>'
        + '<div class="pet-log">'
        + '<span class="pet-log-txt">' + careFeedLine(p.id) + '</span>'
        + '<span class="pet-log-btns">'
        + LOG_TYPES.slice(0, 3).map(function (t) {
            return '<button type="button" data-log="' + t.k + '">' + t.short + '</button>';
          }).join('')
        + '</span></div>'
        + '</div><span class="care-arrow">›</span></div>';
    });
    box.innerHTML = h;
    box.querySelectorAll('.pet-card').forEach(function (card) {
      card.addEventListener('click', function () { careOpenPetHome(card.dataset.pid); });
      card.querySelectorAll('button[data-log]').forEach(function (b) {
        b.addEventListener('click', function (e) {
          e.stopPropagation();
          careQuickLog(card.dataset.pid, b.dataset.log, b);
        });
      });
    });
  }

  function careAgoTxt(label, ts) {
    var d = careDaysAgo(ts);
    return d === '今天' ? '今天' + label : label + ' ' + d + '前';
  }

  function careFeedLine(pid) {
    var row = CARE.logSummary[pid] || {};
    var feed = row.feed || 0;
    var shed = row.shed || 0;
    if (!feed && !shed) return '还没记过，点右边打卡';
    var bits = [];
    if (feed) bits.push(careAgoTxt('喂食', feed));
    if (shed) bits.push(careAgoTxt('蜕皮', shed));
    return bits.join(' · ');
  }

  // 档案照：居中裁正方形，压到手机上看得清的尺寸
  function careSquarePhoto(file, size, cb) {
    if (!file || !/^image\//.test(file.type || '')) { careToast('请选择一张照片'); return; }
    if (file.size > 12 * 1024 * 1024) { careToast('照片太大，换一张小一点的'); return; }
    var fr = new FileReader();
    fr.onload = function () {
      var img = new Image();
      img.onload = function () {
        var w = img.naturalWidth || img.width;
        var h = img.naturalHeight || img.height;
        var s = Math.min(w, h);
        var cv = document.createElement('canvas');
        cv.width = cv.height = size;
        var x = cv.getContext('2d');
        x.fillStyle = '#fff';
        x.fillRect(0, 0, size, size);
        x.drawImage(img, (w - s) / 2, (h - s) / 2, s, s, 0, 0, size, size);
        cb(cv.toDataURL('image/jpeg', 0.82));
      };
      img.onerror = function () { careToast('这张图读不出来，换一张试试'); };
      img.src = fr.result;
    };
    fr.readAsDataURL(file);
  }

  function careOpenPetForm(pid) {
    var p = null;
    if (pid) {
      CARE.pets.forEach(function (x) { if (x.id === pid) p = x; });
      if (!p) return;
    }
    var sheet = document.getElementById('careSheet');
    var mask = document.getElementById('careSheetMask');
    var chips = CARE_SP_CHIPS.map(function (s) {
      return '<button type="button" class="sp-chip" data-sp="' + escapeHtml(s) + '">' + escapeHtml(s) + '</button>';
    }).join('');
    sheet.innerHTML = '<div class="sheet-head"><h3>' + (p ? '编辑档案' : '新建档案') + '</h3>'
      + '<button class="sheet-x" id="pfX" aria-label="关闭">×</button></div>'
      + '<div class="ph-row">'
      + '<div class="ph-box" id="pfPhBox">' + (p && p.photo ? '<img src="' + p.photo + '" alt="">' : '暂无<br>照片') + '</div>'
      + '<div class="ph-btns">'
      + '<button type="button" id="pfPhCam">拍照</button>'
      + '<button type="button" id="pfPhPick">从相册选</button>'
      + (p && p.photo ? '<button type="button" id="pfPhDel">删掉照片</button>' : '')
      + '<div class="ph-tip">会自动裁成方形</div>'
      + '</div></div>'
      + '<input type="file" id="pfPhInCam" accept="image/*" capture="environment" hidden>'
      + '<input type="file" id="pfPhInFile" accept="image/*" hidden>'
      + '<div class="form-row"><label>名字</label><input id="pfName" maxlength="20" placeholder="如：豆豆" value="' + escapeHtml(p ? p.name : '') + '"></div>'
      + '<div class="form-row"><label>物种</label><input id="pfSpecies" maxlength="30" placeholder="如：豹纹守宫" value="' + escapeHtml(p ? p.species : '') + '">'
      + '<div class="sp-chips">' + chips + '</div>'
      + '<div class="ph-tip" style="margin-top:7px"><a href="#" id="pfDex" style="color:var(--clay);text-decoration:none">不确定是什么物种？去图鉴查 →</a></div></div>'
      + '<div class="form-2col">'
      + '  <div class="form-row"><label>性别</label><select id="pfSex">'
      + '    <option value="">未知</option><option value="公"' + (p && p.sex === '公' ? ' selected' : '') + '>公</option>'
      + '    <option value="母"' + (p && p.sex === '母' ? ' selected' : '') + '>母</option></select></div>'
      + '  <div class="form-row"><label>体重（g）</label><input id="pfWeight" type="number" step="0.1" inputmode="decimal" placeholder="65" value="' + escapeHtml(p && p.weight ? p.weight : '') + '"></div>'
      + '</div>'
      + '<div class="form-2col">'
      + '  <div class="form-row"><label>生日</label><input id="pfBirthday" type="date" value="' + escapeHtml(p && p.birthday ? p.birthday : '') + '"></div>'
      + '  <div class="form-row"><label>入手日期</label><input id="pfAdopted" type="date" value="' + escapeHtml(p && p.adopted ? p.adopted : '') + '"></div>'
      + '</div>'
      + '<div class="form-row"><label>备注</label><textarea id="pfNote" rows="2" maxlength="200" placeholder="性格、笼箱尺寸、特别要注意的事">' + escapeHtml(p && p.note ? p.note : '') + '</textarea></div>'
      + (p ? careWeightBox(p.id) : '')
      + '<div class="form-err" id="pfErr"></div>'
      + '<button class="btn-main" id="pfSave">保存</button>'
      + (p ? '<button class="btn-line" id="pfPoster" style="margin-top:8px">生成这张档案的海报</button>' : '')
      + (p ? '<button class="btn-line" id="pfDel" style="margin-top:8px;color:#e5484d;border-color:#f6d3d1">删除这份档案</button>' : '');
    mask.classList.add('show');

    // undefined = 不改；'' = 删掉；data URI = 换成新的
    var PET_PHOTO = { v: undefined };
    (function bindPhoto() {
      var inCam = document.getElementById('pfPhInCam');
      var inFile = document.getElementById('pfPhInFile');
      var box = document.getElementById('pfPhBox');
      function take(file) {
        careSquarePhoto(file, 640, function (uri) {
          PET_PHOTO.v = uri;
          if (box) box.innerHTML = '<img src="' + uri + '" alt="">';
        });
      }
      var cam = document.getElementById('pfPhCam');
      var pick = document.getElementById('pfPhPick');
      if (cam) cam.addEventListener('click', function () { inCam.click(); });
      if (pick) pick.addEventListener('click', function () { inFile.click(); });
      [inCam, inFile].forEach(function (inp) {
        if (!inp) return;
        inp.addEventListener('change', function () {
          if (inp.files && inp.files[0]) take(inp.files[0]);
          inp.value = '';
        });
      });
      var dexLink = document.getElementById('pfDex');
      if (dexLink) dexLink.addEventListener('click', function (e) {
        e.preventDefault();
        careCloseSheet();
        switchView('dex');
      });
      var del = document.getElementById('pfPhDel');
      if (del) del.addEventListener('click', function () {
        PET_PHOTO.v = '';
        if (box) box.innerHTML = '暂无<br>照片';
        del.style.display = 'none';
      });
    })();

    if (p) careBindWeightBox(p.id);

    document.getElementById('pfX').addEventListener('click', careCloseSheet);
    sheet.querySelectorAll('.sp-chip').forEach(function (c) {
      c.addEventListener('click', function () {
        document.getElementById('pfSpecies').value = c.dataset.sp;
        sheet.querySelectorAll('.sp-chip').forEach(function (x) { x.classList.remove('on'); });
        c.classList.add('on');
      });
    });
    document.getElementById('pfSave').addEventListener('click', function () {
      var body = {
        photo: PET_PHOTO.v,
        name: document.getElementById('pfName').value.trim(),
        species: document.getElementById('pfSpecies').value.trim(),
        sex: document.getElementById('pfSex').value,
        birthday: document.getElementById('pfBirthday').value,
        adopted: document.getElementById('pfAdopted').value,
        weight: document.getElementById('pfWeight').value.trim(),
        note: document.getElementById('pfNote').value.trim()
      };
      var err = document.getElementById('pfErr');
      if (body.photo === undefined) delete body.photo;
      if (!body.name) { err.textContent = '请填写名字'; return; }
      if (!body.species) { err.textContent = '请填写物种'; return; }
      err.textContent = '';
      if (p) body.id = p.id;
      var btn = document.getElementById('pfSave');
      btn.disabled = true;
      btn.textContent = '保存中…';
      api('/api/pets', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (d.error) { err.textContent = d.error; btn.disabled = false; btn.textContent = '保存'; return; }
        careCloseSheet();
        careLoadPets(function () {
          careLoadPetlogs(function () {
            careRenderPets();
            careRenderLogBrief();
            if (CARE.pane === 'pet') { PET_HOME.pid = ''; careRenderPetHome(); }
          });
          careToast(p ? '已更新档案' : '档案已建好');
        });
      }).catch(function () {
        err.textContent = '网络异常，请重试';
        btn.disabled = false; btn.textContent = '保存';
      });
    });
    var pfPoster = document.getElementById('pfPoster');
    if (pfPoster) pfPoster.addEventListener('click', function () {
      careCloseSheet();
      careOpenPoster(p.id);
    });
    var del = document.getElementById('pfDel');
    if (del) {
      del.addEventListener('click', function () {
        if (!confirm('删除「' + p.name + '」的档案？这只宠物的温湿度记录和饲养日志也会一起删除，无法恢复。')) return;
        api('/api/pets/delete', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: p.id })
        }).then(function (r) { return r.json(); }).then(function (d) {
          if (d.error) { careToast(d.error); return; }
          careCloseSheet();
          careLoadPets(function () { careRenderPets(); careToast('档案已删除'); });
        }).catch(function () { careToast('网络异常，请重试'); });
      });
    }
  }

  function careCloseSheet() {
    var mask = document.getElementById('careSheetMask');
    if (mask) mask.classList.remove('show');
  }

  // ---------- 温湿度 ----------
  function careInitEnv() {
    var sel = document.getElementById('envPet');
    if (!sel) return;
    if (!CARE.loaded) { careLoadPets(function () { careInitEnv(); }); return; }
    var cur = CARE.petId;
    if (!cur && CARE.pets.length) cur = CARE.pets[0].id;
    CARE.petId = cur;
    var h = '<option value="">不指定宠物</option>';
    CARE.pets.forEach(function (p) {
      h += '<option value="' + escapeHtml(p.id) + '"' + (p.id === cur ? ' selected' : '') + '>'
        + escapeHtml(p.name + '（' + p.species + '）') + '</option>';
    });
    sel.innerHTML = h;
    if (!CARE.pets.some(function (p) { return p.id === cur; })) {
      CARE.petId = '';
      sel.value = '';
    }
    careLoadLogs(CARE.petId);
    careJudgeInit();
  }

  function carePetById(id) {
    var hit = null;
    CARE.pets.forEach(function (p) { if (p.id === id) hit = p; });
    return hit;
  }

  function careLoadLogs(pid) {
    CARE.petId = pid || '';
    api('/api/care/logs?pet_id=' + encodeURIComponent(CARE.petId)).then(function (r) {
      return r.json();
    }).then(function (d) {
      CARE.logs = (d && d.items) || [];
      careRenderEnv();
    }).catch(function () { careRenderEnv(); });
  }

  function careEnvRange() {
    if (!CARE.petId) return null;
    var p = carePetById(CARE.petId);
    if (!p) return null;
    return careEnvOf(p.species);
  }

  function careRenderEnv() {
    var env = careEnvRange();
    var latestBox = document.getElementById('envLatest');
    var logBox = document.getElementById('envLogs');
    var trendBox = document.getElementById('envTrend');
    if (!latestBox) return;

    var trendBoxWrap = document.getElementById('envTrendBox');
    if (!CARE.logs.length) {
      latestBox.innerHTML = '<div class="env-top"><b>还没有记录</b><span>固定时段测一次</span></div>'
        + '<div class="today-empty">数据要连续才有可比性，建议每天同一时段（如开灯后 1 小时）记录。</div>';
      logBox.innerHTML = '<div class="today-empty">暂无记录</div>';
      trendBox.innerHTML = '';
      if (trendBoxWrap) trendBoxWrap.hidden = true;
      return;
    }
    if (trendBoxWrap) trendBoxWrap.hidden = false;

    var last = CARE.logs[0];
    var tState = 'none', tTxt = '选择宠物后可对比区间';
    if (env) {
      if (last.temp < env.t[0]) { tState = 'lo'; tTxt = '低于参考 ' + env.t[0] + '～' + env.t[1] + '℃，注意加温'; }
      else if (last.temp > env.t[1]) { tState = 'hi'; tTxt = '高于参考 ' + env.t[0] + '～' + env.t[1] + '℃，注意降温通风'; }
      else { tState = 'ok'; tTxt = '在参考区间内'; }
    }

    var hState = 'none', hTxt = '';
    if (env && env.h[1]) {
      if (last.hum < env.h[0]) { hState = 'lo'; hTxt = '湿度偏低，注意加湿'; }
      else if (last.hum > env.h[1]) { hState = 'hi'; hTxt = '湿度偏高，注意通风'; }
      else { hState = 'ok'; hTxt = '湿度适宜'; }
    }

    var petName = CARE.petId ? ((carePetById(CARE.petId) || {}).name || '已选宠物') : '未指定宠物';
    var hHtml = '<div class="env-top"><b>' + escapeHtml(petName) + '</b>'
      + '<span>记录于 ' + careTime(last.ts) + '</span></div>'
      + '<div class="env-nums">'
      + '<div><div><span class="env-val">' + last.temp.toFixed(1) + '</span><span class="env-unit">℃</span></div><div class="env-lbl">温度</div></div>'
      + '<div><div><span class="env-val">' + Math.round(last.hum) + '</span><span class="env-unit">%</span></div><div class="env-lbl">湿度</div></div>'
      + '</div>'
      + '<div style="margin:2px 0 10px">'
      + '<span class="env-state ' + tState + '" style="margin-left:12px">' + escapeHtml(tTxt) + '</span>'
      + (hTxt ? '<span class="env-state ' + hState + '" style="margin-left:10px">' + escapeHtml(hTxt) + '</span>' : '')
      + '</div>'
      + careScaleBar(last.temp, env ? env.t : null, '℃');
    latestBox.innerHTML = hHtml;

    var lh = '';
    CARE.logs.slice(0, 30).forEach(function (l) {
      var st = '';
      if (env) st = l.temp < env.t[0] ? 'lo' : (l.temp > env.t[1] ? 'hi' : '');
      lh += '<div class="log-row">'
        + '<span class="log-time">' + careTime(l.ts) + '</span>'
        + '<span class="log-val" style="width:58px">' + l.temp.toFixed(1) + '℃</span>'
        + '<span class="log-val" style="width:44px;color:' + (st === 'hi' ? '#c2571a' : st === 'lo' ? '#2563eb' : 'inherit') + '">'
        + Math.round(l.hum) + '%</span>'
        + '<span class="log-note">' + escapeHtml(l.note || '') + '</span>'
        + '<button class="log-del" data-lid="' + escapeHtml(l.id) + '" aria-label="删除">×</button>'
        + '</div>';
    });
    logBox.innerHTML = lh;
    logBox.querySelectorAll('.log-del').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!confirm('删除这条记录？')) return;
        api('/api/care/logs/delete', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: b.dataset.lid })
        }).then(function (r) { return r.json(); }).then(function (d) {
          if (d.error) { careToast(d.error); return; }
          careLoadLogs(CARE.petId);
        }).catch(function () { careToast('网络异常，请重试'); });
      });
    });

    // 趋势：最近 14 条，按时间正序
    var arr = CARE.logs.slice(0, 14).reverse();
    var tmin = Math.min.apply(null, arr.map(function (x) { return x.temp; }));
    var tmax = Math.max.apply(null, arr.map(function (x) { return x.temp; }));
    var span = Math.max(1, tmax - tmin);
    trendBox.innerHTML = arr.map(function (x, i) {
      var pct = 14 + ((x.temp - tmin) / span) * 82;
      var cls = env && x.temp > env.t[1] ? 'hi' : (env && x.temp < env.t[0] ? 'lo' : '');
      var showVal = arr.length <= 8 || i === arr.length - 1;
      return '<div class="tcol' + (i === arr.length - 1 ? ' big' : '') + '" title="'
        + escapeHtml(careTime(x.ts) + ' ' + x.temp.toFixed(1) + '℃') + '">'
        + (showVal ? '<span class="tval">' + x.temp.toFixed(0) + '</span>' : '<span class="tval"></span>')
        + '<i class="' + cls + '" style="height:' + pct.toFixed(0) + '%"></i></div>';
    }).join('');
  }

  function careSaveEnv() {
    var tEl = document.getElementById('envTemp');
    var hEl = document.getElementById('envHum');
    var nEl = document.getElementById('envNote');
    var t = tEl.value.trim(), h = hEl.value.trim();
    if (!t || !h) { careToast('温度和湿度都要填'); return; }
    if (isNaN(parseFloat(t)) || isNaN(parseFloat(h))) { careToast('请填数字'); return; }
    var btn = document.getElementById('envSave');
    btn.disabled = true; btn.textContent = '保存中…';
    api('/api/care/logs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pet_id: CARE.petId, temp: t, hum: h, note: nEl.value.trim() })
    }).then(function (r) { return r.json(); }).then(function (d) {
      btn.disabled = false; btn.textContent = '保存这次记录';
      if (d.error) { careToast(d.error); return; }
      tEl.value = ''; hEl.value = ''; nEl.value = '';
      careToast('已记录');
      careLoadLogs(CARE.petId);
    }).catch(function () {
      btn.disabled = false; btn.textContent = '保存这次记录';
      careToast('网络异常，请重试');
    });
  }


  // ---------- 症状分级 ----------
  // 症状按部位归类；sev：3 急诊 / 2 尽快就医 / 1 可观察 / 0 正常生理现象
  var CARE_SYMS = [
    // —— 红灯：急诊 ——
    { id: 'breath', n: '呼吸困难 / 张口呼吸', sev: 3, part: '呼吸' },
    { id: 'seizure', n: '抽搐、突然倒地', sev: 3, part: '行为' },
    { id: 'bleed', n: '出血止不住', sev: 3, part: '外伤' },
    { id: 'palsy', n: '无法站立 / 后肢瘫痪', sev: 3, part: '行为' },
    { id: 'cold', n: '身体冰凉、反应迟钝', sev: 3, part: '全身' },
    { id: 'poison', n: '误食有毒物 / 异物', sev: 3, part: '消化道' },
    { id: 'dystocia', n: '难产 / 卡蛋超过 2 小时', sev: 3, part: '生殖' },
    { id: 'dehydrate', n: '严重脱水（皮肤回弹慢）', sev: 3, part: '全身' },
    { id: 'bloat', n: '腹部急剧胀大', sev: 3, part: '消化道' },
    // —— 黄灯：尽快就医 / 居家干预 ——
    { id: 'not_eat', n: '拒食', sev: 2, part: '消化道',
      steps: ['核对热区温度是否达标（守宫 30～32℃、兔 18～25℃），低温会直接停食',
              '回想最近是否换粮、换环境、刚到家或正在蜕皮',
              '把食物放在它平时活动的位置，人走开 2 小时再看动没动',
              '记录体重：连续两次下降超过 5% 就要就医'] },
    { id: 'diarrhea', n: '持续腹泻 / 水样便', sev: 2, part: '消化道',
      steps: ['先停掉蔬菜水果等含水高的食物，只给干草 / 常规粮',
              '保证饮水，防止脱水；兔、豚鼠可补电解质',
              '清理并拍照记录粪便形态，方便给医生看',
              '24 小时内没有成形趋势就就医'] },
    { id: 'vomit', n: '反复呕吐', sev: 2, part: '消化道',
      steps: ['停食 4～6 小时让肠胃休息，但不要停水',
              '检查是否误食毛发、垫材、异物',
              '呕吐超过 3 次或伴随精神萎靡，直接就医'] },
    { id: 'discharge', n: '眼鼻分泌物增多', sev: 2, part: '呼吸',
      steps: ['用生理盐水棉签轻轻清理，别硬抠',
              '检查垫材粉尘、通风与温度波动',
              '分泌物呈黄绿色或伴随打喷嚏，需要就医排查呼吸道感染'] },
    { id: 'noise', n: '呼吸有杂音 / 喘', sev: 2, part: '呼吸',
      steps: ['保持安静、适宜温度，减少抓握',
              '检查是否刚运动、过热或应激',
              '安静状态下仍有杂音，按呼吸道问题就医'] },
    { id: 'swell', n: '局部肿胀 / 包块', sev: 2, part: '皮肤',
      steps: ['拍照记录位置与大小，每天同一角度对比',
              '不要挤压、穿刺或自行上药',
              '短期变大、破溃或影响活动，尽快就医'] },
    { id: 'shed', n: '蜕皮不全超过 48 小时', sev: 2, part: '皮肤',
      steps: ['提高湿度到 70～80%，放湿躲避',
              '脚趾、尾尖残留的旧皮可用温水浸泡 10 分钟后用棉签轻推',
              '不要硬撕；多处残留或勒住脚趾要就医'] },
    { id: 'weight', n: '体重短期明显下降', sev: 2, part: '全身',
      steps: ['固定同一时间、同一秤称重，隔天一次',
              '核对进食量与温度，排查寄生虫',
              '两周内下降超过 10%，尽快就医'] },
    { id: 'wound', n: '外伤（出血已止）', sev: 2, part: '外伤',
      steps: ['生理盐水冲洗，碘伏消毒创面',
              '保持干燥清洁，避免垫材粘在伤口上',
              '伤口深、面积大或两天没有结痂，就医处理'] },
    { id: 'lethargy', n: '长时间不动 / 缩在角落', sev: 2, part: '行为',
      steps: ['先测温度：低温是嗜睡最常见的原因',
              '检查是否有脱水、外伤、被同类欺负',
              '调整温度后 12 小时仍无改善，就医'] },
    { id: 'mouth', n: '口腔、喙或牙齿异常', sev: 2, part: '口腔',
      steps: ['检查是否有口炎、牙过长、喙变形',
              '兔、豚鼠牙过长会流口水、拒食，需要磨牙',
              '不要自行剪牙，找异宠医生处理'] },
    // —— 可观察（黄灯轻）——
    { id: 'soft', n: '单次软便', sev: 1, part: '消化道' },
    { id: 'scratch', n: '轻微抓伤 / 擦伤', sev: 1, part: '外伤' },
    { id: 'fur', n: '换毛期掉毛增多', sev: 1, part: '皮肤' },
    { id: 'sneeze', n: '偶发打喷嚏（无分泌物）', sev: 1, part: '呼吸' },
    { id: 'appetite', n: '食欲略降但精神正常', sev: 1, part: '消化道' },
    // —— 绿灯：正常生理现象 ——
    { id: 'n_shed', n: '蜕皮前皮肤发白、眼睛发蒙', sev: 0, part: '皮肤',
      why: '守宫、蛇在蜕皮前 2～3 天，旧皮与新生皮分离，看起来会发白、发灰，眼睛像蒙了一层膜。这是正常的蜕皮前兆，不是生病。',
      steps: ['把湿度提到 60～80%，放一个湿躲避', '不要上手，也不要用手去撕旧皮', '蜕皮完成后检查脚趾、尾尖有没有残留旧皮'] },
    { id: 'n_sperm', n: '公守宫尾部两侧有白色小囊', sev: 0, part: '生殖',
      why: '成年公守宫泄殖腔两侧的白色膨大是储精囊（半阴茎），性成熟后都会出现，属于正常解剖结构，不是肿瘤或脓肿。',
      steps: ['确认是两侧对称、质地柔软', '不要挤压', '若单侧红肿、破溃或流出脓液，才需要就医'] },
    { id: 'n_molt', n: '换羽 / 换毛，笼底毛屑变多', sev: 0, part: '皮肤',
      why: '鸟类换羽、哺乳类换毛都有周期性，期间毛屑增多、局部秃一小块很常见，通常 1～3 周自行恢复。',
      steps: ['增加蛋白质与维生素供给（鸟可给蛋黄、换羽粮）', '勤清理笼底毛屑，避免误食', '观察是否有秃斑扩大、皮肤发红破溃'] },
    { id: 'n_season', n: '降温后食欲下降、活动变少', sev: 0, part: '消化道',
      why: '变温动物在气温下降时会自然降低代谢，进食减少、活动变慢是适应行为；部分物种冬季还会进入浅冬眠状态。',
      steps: ['确认饲养箱温度仍在该物种适宜区间', '不要强行加温或强行喂食', '体重没有持续下降就无需干预'] },
    { id: 'n_bask', n: '龟晒背时张嘴、四肢摊开', sev: 0, part: '行为',
      why: '龟在灯下晒背时会伸展四肢、微微张嘴，这是调节体温和吸收 UVB 的正常姿势，不是呼吸困难。',
      steps: ['确认晒点温度 30～35℃、有 UVB 灯', '提供躲避，让它能自己选择冷热区', '若离水也持续张嘴喘、鼻孔有泡沫，才按肺炎处理'] },
    { id: 'n_female', n: '母守宫发情期拒食', sev: 0, part: '生殖',
      why: '性成熟的母守宫在繁殖季会周期性拒食，腹部可见卵泡轮廓，体重不一定下降，属于正常生理现象。',
      steps: ['补充钙粉与维生素，准备产卵盒（湿润蛭石）', '不要强行填喂', '超过 3 周完全不吃或体重明显下降，再就医'] },
    { id: 'n_pouch', n: '仓鼠颊囊塞得鼓鼓的', sev: 0, part: '口腔',
      why: '仓鼠用颊囊搬运和储存食物，塞满时两侧鼓起是正常行为，不代表长了肿块。',
      steps: ['不要用手去挤颊囊', '减少一次给食量，避免塞太多变质', '若颊囊一直不空、有异味或脱出，需要就医'] },
    { id: 'n_cecotrope', n: '兔子吃自己的软便', sev: 0, part: '消化道',
      why: '兔子每天会排出盲肠便（软便），并直接吃掉以回收维生素 B 和蛋白质，这是正常的消化过程。',
      steps: ['不要阻止它吃', '保证足够的干草摄入', '若软便量大、粘在笼底没被吃掉，才提示饮食或肠胃问题'] }
  ];
  var CARE_PARTS = ['全部', '口腔', '皮肤', '消化道', '呼吸', '行为', '外伤', '生殖', '全身'];
  var CARE_TRI_SP = ['小型哺乳', '爬宠', '鸟类', '节肢', '水族'];

  function careSymById(id) {
    var hit = null;
    CARE_SYMS.forEach(function (s) { if (s.id === id) hit = s; });
    return hit;
  }

  function careRenderTriage() {
    var spBox = document.getElementById('triSpecies');
    if (spBox && !spBox.dataset.done) {
      if (!CARE.triSpecies) CARE.triSpecies = CARE_TRI_SP[0];
      spBox.innerHTML = CARE_TRI_SP.map(function (s) {
        return '<button type="button" class="sym-chip' + (s === CARE.triSpecies ? ' on' : '')
          + '" data-sp="' + s + '">' + s + '</button>';
      }).join('');
      spBox.querySelectorAll('.sym-chip').forEach(function (c) {
        c.addEventListener('click', function () {
          CARE.triSpecies = c.dataset.sp;
          spBox.querySelectorAll('.sym-chip').forEach(function (x) { x.classList.remove('on'); });
          c.classList.add('on');
        });
      });
      spBox.dataset.done = '1';
    }

    // 部位筛选：先收窄范围，症状列表才不会一次铺 33 项
    var partBox = document.getElementById('triPart');
    if (partBox && !partBox.dataset.done) {
      if (!CARE.triPart) CARE.triPart = '全部';
      partBox.innerHTML = CARE_PARTS.map(function (p) {
        return '<button type="button" class="sym-chip part-chip' + (p === CARE.triPart ? ' on' : '')
          + '" data-part="' + p + '">' + p + '</button>';
      }).join('');
      partBox.querySelectorAll('.sym-chip').forEach(function (c) {
        c.addEventListener('click', function () {
          CARE.triPart = c.dataset.part;
          partBox.querySelectorAll('.sym-chip').forEach(function (x) { x.classList.remove('on'); });
          c.classList.add('on');
          // 换部位等于重新选，旧的选择（已经不在列表里）继续参与判定会误导
          CARE.triPicked = [];
          careRenderSymList();
        });
      });
      partBox.dataset.done = '1';
    }

    careRenderSymList();
  }

  function careRenderSymList() {
    var box = document.getElementById('triSyms');
    if (!box) return;
    var part = CARE.triPart || '全部';
    var list = CARE_SYMS.filter(function (s) { return part === '全部' || s.part === part; });
    var groups = [
      { t: '急诊表现（勾选任意一项即按急诊处理）', sev: 3 },
      { t: '需要尽快就医（24 小时内）', sev: 2 },
      { t: '可以先观察（24～48 小时）', sev: 1 },
      { t: '正常生理现象（不是生病）', sev: 0 }
    ];
    var html = '';
    groups.forEach(function (g) {
      var items = list.filter(function (s) { return s.sev === g.sev; });
      if (!items.length) return;
      html += '<div class="sym-group"><div class="sym-title">' + g.t + '</div><div class="sym-chips">'
        + items.map(function (s) {
          var on = CARE.triPicked.indexOf(s.id) >= 0;
          return '<button type="button" class="sym-chip sev' + s.sev + (on ? ' on' : '')
            + '" data-sid="' + s.id + '">' + s.n + '</button>';
        }).join('') + '</div></div>';
    });
    if (!html) html = '<div class="sym-group"><div class="sym-title">该部位暂无对应表现，换个部位看看</div></div>';
    box.innerHTML = html;
    box.querySelectorAll('.sym-chip').forEach(function (c) {
      c.addEventListener('click', function () {
        c.classList.toggle('on');
        var id = c.dataset.sid;
        var i = CARE.triPicked.indexOf(id);
        if (i >= 0) CARE.triPicked.splice(i, 1); else CARE.triPicked.push(id);
      });
    });
  }

  function careRunTriage() {
    if (!CARE.triPicked.length) { careToast('先勾选至少一个表现'); return; }
    var top = null;
    var picked = [];
    CARE.triPicked.forEach(function (id) {
      var s = careSymById(id);
      if (!s) return;
      picked.push(s);
      if (!top || s.sev > top.sev) top = s;
    });
    var lv = top.sev;
    // 只要有一项不是「正常现象」，就按最重的那项判
    var names = picked.filter(function (x) { return x.sev > 0; }).map(function (x) { return x.n; });
    if (!names.length) names = picked.map(function (x) { return x.n; });
    var spTxt = CARE.triSpecies || '宠物';
    var askQ = '我家' + spTxt + '最近出现' + names.join('、') + '，应该怎么处理？需要注意什么？';

    if (lv === 0) {
      careRenderGreen(top, picked, askQ);
    } else {
      careRenderWarn(lv, top, picked, names, spTxt, askQ);
    }
    careEvent('triage', { level: lv, species: CARE.triSpecies, symptoms: names });
  }

  // 绿灯：选的都是正常生理现象
  function careRenderGreen(top, picked, askQ) {
    var rows = picked.map(function (x) {
      return '<div class="result-h">' + escapeHtml(x.n) + '</div>'
        + '<div class="result-why">' + escapeHtml(x.why || '属于该物种的正常生理现象。') + '</div>'
        + (x.steps ? '<div class="result-li-wrap">' + x.steps.map(function (t, i) {
            return '<div class="result-step"><i>' + (i + 1) + '</i><span>' + escapeHtml(t) + '</span></div>';
          }).join('') + '</div>' : '');
    }).join('');

    var html = '<div class="result lv0">'
      + '<div class="result-bar"><span class="result-lv">Ⅲ</span>'
      + '<span class="result-title">正常现象，不用紧张</span>'
      + '<span class="result-win">无需处理</span></div>'
      + '<div class="result-body">'
      + '<div class="result-why">你选的这些属于正常的生理过程，不是生病。按下面几件事做就行。</div>'
      + rows
      + '<div class="result-acts">'
      + '<button class="solid" data-ask="' + escapeHtml(askQ) + '">还有疑问，问 AI</button>'
      + '<button data-go="pets">记到档案里</button>'
      + '</div></div></div>';

    var res = document.getElementById('triResult');
    res.innerHTML = html;
    careBindResult(res);
    res.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // 黄灯 / 红灯
  function careRenderWarn(lv, top, picked, names, spTxt, askQ) {
    var M = {
      3: { num: 'Ⅰ', title: '立即就医（急诊）', win: '现在' },
      2: { num: 'Ⅱ', title: '居家干预，24 小时内就医', win: '24 小时' },
      1: { num: 'Ⅱ', title: '先居家观察', win: '24–48 小时' }
    }[lv];

    var why = lv === 3
      ? '你勾选的「' + escapeHtml(top.n) + '」属于急症表现。异宠体型小、代偿能力弱，恶化常以小时计算，不要在家观察过夜。'
      : (lv === 2
        ? '「' + escapeHtml(top.n) + '」不是立刻致命的表现，但需要干预并观察变化，不建议拖过 24 小时。'
        : '你勾选的表现偏轻微。先按下面做，同时把饲养环境调回适宜区间，多数情况会自行恢复。');

    var steps;
    if (lv === 3) {
      // 急诊先做保命的三件事，不做环境排查
      steps = ['清理口鼻分泌物，检查口腔有无异物，保持呼吸道通畅',
               '维持适宜温度，减少搬动和抓握，避免应激加重',
               '立刻联系异宠医生，说清症状、出现时间和最近的进食排泄情况'];
    } else if (top.steps && top.steps.length) {
      steps = top.steps;
    } else {
      steps = ['核对温度、湿度是否偏离适宜区间，灯具、垫材最近有没有更换',
               '记录进食、饮水、排泄的时间与形态，拍照片留存',
               '每 12 小时看一次精神和食欲'];
    }

    var noList = lv === 3
      ? ['不要强行灌食灌水', '不要自行喂人用药', '不要用洗澡、暴晒、冰敷「急救」']
      : ['不要自行喂人用药', '不要在这时换粮、换环境', lv === 3 ? '' : '不要拖过 24 小时'].filter(Boolean);

    var stepsHtml = steps.map(function (t, i) {
      return '<div class="result-step"><i>' + (i + 1) + '</i><span>' + escapeHtml(t) + '</span></div>';
    }).join('');

    // 食草小宠的拒食红线，单独提示
    var extra = '';
    if (lv < 3 && CARE.triPicked.indexOf('not_eat') >= 0 && CARE.triSpecies === '小型哺乳') {
      extra = '<div class="result-h">还要注意</div><div class="result-li">兔、豚鼠、龙猫这类食草小宠，拒食超过 12 小时即属急症（易发生胃肠停滞），不要拖到 24 小时。</div>';
    }

    // 客服联系人也常填微信号/邮箱，只有真能拨的号码才给 tel: 按钮，否则点了必然失败
    var supTxt = String((SVC && SVC.info && SVC.info.support) || '').trim();
    var phoneHit = supTxt.match(/1[3-9]\d{9}|0\d{2,3}-?\d{7,8}/);
    var telBtn = phoneHit
      ? '<a class="solid" href="tel:' + phoneHit[0] + '">一键拨打 ' + phoneHit[0] + '</a>'
      : '<button class="solid" data-go="vet">看就医准备清单</button>';
    var acts = lv === 3
      ? '<div class="result-acts">'
        + telBtn
        + '<button data-go="vet">就医准备清单</button>'
        + '<button data-go="firstaid">急救步骤</button>'
        + '<button data-ask="' + escapeHtml(askQ) + '">问 AI</button></div>'
      : '<div class="result-acts">'
        + '<button class="solid" data-track="' + escapeHtml(names.join('、')) + '" data-level="' + lv + '">加入 48 小时追踪</button>'
        + '<button data-go="pets">记到档案里</button>'
        + '<button data-go="vet">就医准备清单</button>'
        + '<button data-ask="' + escapeHtml(askQ) + '">问 AI</button></div>';

    var html = '<div class="result lv' + lv + '">'
      + '<div class="result-bar"><span class="result-lv">' + M.num + '</span>'
      + '<span class="result-title">' + M.title + '</span>'
      + '<span class="result-win">' + M.win + '</span></div>'
      + '<div class="result-body">'
      + '<div class="result-why">' + why + '</div>'
      + '<div class="result-h">' + (lv === 3 ? '现在做' : '按下面做') + '</div>'
      + stepsHtml
      + '<div class="result-h">不要做</div>'
      + noList.map(function (x) { return '<div class="result-li">' + escapeHtml(x) + '</div>'; }).join('')
      + extra
      + (lv === 3 ? '' : '<div class="result-h">出现这些立刻升级为急诊</div><div class="result-li">呼吸困难、张口呼吸、抽搐、无法站立、出血不止、体温明显过低</div>')
      + acts
      + '</div></div>';

    var res = document.getElementById('triResult');
    res.innerHTML = html;
    careBindResult(res);
    res.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function careBindResult(res) {
    res.querySelectorAll('button[data-go]').forEach(function (b) {
      b.addEventListener('click', function () { careShowPane(b.dataset.go); });
    });
    var ask = res.querySelector('button[data-ask]');
    if (ask) {
      ask.addEventListener('click', function () {
        switchView('chat');
        setTimeout(function () { sendText(ask.dataset.ask); }, 80);
      });
    }
    var tr = res.querySelector('button[data-track]');
    if (tr) {
      tr.addEventListener('click', function () {
        careAddTrack(tr.dataset.track || '', parseInt(tr.dataset.level || '2', 10), tr);
      });
    }
  }

  // 黄灯结果 → 写一条 48 小时观察记录
  function careAddTrack(symptoms, level, btn) {
    var petId = '';
    var sel = document.getElementById('envPet');
    if (sel && sel.value) petId = sel.value;
    if (!petId && CARE.pets && CARE.pets.length) petId = CARE.pets[0].id;
    if (btn) { btn.disabled = true; btn.textContent = '正在加入…'; }
    api('/api/petlogs', {
      method: 'POST',
      body: JSON.stringify({
        type: 'watch', pet_id: petId, level: level,
        symptoms: symptoms, hours: 48,
        note: symptoms.slice(0, 40)
      })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d && d.ok) {
        careToast('已加入追踪，48 小时内可在养护首页看到');
        if (btn) { btn.textContent = '已加入追踪'; }
        careLoadPetlogs(function () { careRenderLogBrief(); });
      } else {
        careToast((d && d.error) || '加入失败，请重试');
        if (btn) { btn.disabled = false; btn.textContent = '加入 48 小时追踪'; }
      }
    }).catch(function () {
      careToast('网络异常，请重试');
      if (btn) { btn.disabled = false; btn.textContent = '加入 48 小时追踪'; }
    });
  }

  // ---------- 急救指引 ----------
  var CARE_AID = [
    {
      n: '中暑 / 热应激',
      steps: [
        '立刻移到阴凉通风处，室温控制在 22～25℃，避开空调直吹',
        '用常温水打湿毛巾，擦拭腹部、四肢内侧、耳部帮助散热',
        '清醒时少量多次给水或宠物电解质水；意识不清不要灌',
        '一边降温一边联系医院，途中保持通风'
      ],
      no: '不要用冰水浸泡或冰袋直接贴皮肤：血管骤然收缩反而散不出热，小型动物还容易应激休克。',
      to: '体温超过 40℃、张口呼吸、流涎、站不稳或抽搐，立即送医。'
    },
    {
      n: '外伤 / 出血',
      steps: [
        '用干净纱布或棉片持续按压伤口 3～5 分钟，中途不要反复揭开查看',
        '止血后用生理盐水冲洗，碘伏消毒伤口周围（不要倒进伤口深处）',
        '伤口较深或污染严重，用无菌纱布覆盖后直接去医院处理',
        '限制活动，放在安静、昏暗、温度适宜的盒子里'
      ],
      no: '不要用酒精、碘酒直接冲伤口；不要撒面粉、烟灰、云南白药粉，异物会妨碍清创。',
      to: '出血呈喷射状或按压 5 分钟仍不止、伤口见骨、肢体变形，立即送医。'
    },
    {
      n: '骨折 / 脱臼 / 坠落',
      steps: [
        '不要试图复位，也不要拉直肢体',
        '用硬纸板、冰棍棒加纱布做简易固定，范围超过骨折上下两个关节',
        '放入小而暗的运输盒，垫软材，减少移动',
        '尽快送医拍片，途中避免颠簸'
      ],
      no: '不要按摩、热敷或强行让宠物走动「试试看」，可能造成二次损伤。',
      to: '所有疑似骨折都应就医；出现休克表现（牙龈发白、四肢冰凉）立即急诊。'
    },
    {
      n: '误食 / 中毒',
      steps: [
        '立刻移开可疑食物或物品，保留包装、残渣、呕吐物样本',
        '记录误食时间、大概数量、可能的成分',
        '联系医院说明吃了什么，按医生指示处理',
        '保持环境安静，观察有无流涎、呕吐、抽搐'
      ],
      no: '不要自行催吐：兔、豚鼠、鸟类等无法安全催吐，误吸会致命；也不要用牛奶、油「稀释」。',
      to: '误食杀虫剂、老鼠药、巧克力、木糖醇、人类药物、百合等，一律立即就医，不要等症状。'
    },
    {
      n: '脱水',
      steps: [
        '判断：轻捏背部皮肤，松手后回弹慢；眼窝凹陷、口腔黏膜发黏，提示脱水',
        '清醒时少量多次给口服补液盐（宠物专用），每次几毫升',
        '移到温度适宜、安静的环境，避免继续失水（如腹泻、暴晒）',
        '幼体、老年个体脱水进展快，尽早就医'
      ],
      no: '不要一次灌大量水，容易呛入气管；不要用运动饮料、糖水代替补液盐。',
      to: '精神萎靡、皮肤回弹超过 2 秒、无尿、站不稳，需要医生皮下或静脉补液。'
    },
    {
      n: '难产 / 卡蛋',
      steps: [
        '提供阴暗、安静、温度湿度适宜的产房，减少打扰',
        '爬宠卡蛋可短时提高湿度并放置湿润垫材，帮助产出',
        '记录开始用力的时间与进展，不要反复上手检查',
        '尽快联系有异宠经验的医生，必要时补钙或手术'
      ],
      no: '不要硬拉、不要挤压腹部、不要自行注射催产素，可能造成子宫破裂或蛋破裂。',
      to: '用力超过 2～4 小时无进展、阴道或泄殖腔出血、精神急剧变差，立即急诊。'
    },
    {
      n: '烫伤 / 烧伤',
      steps: [
        '小面积烫伤立即用流动常温水冲 10～15 分钟',
        '用无菌纱布轻轻覆盖，不要包扎过紧',
        '移到干净、温度适宜的环境，防止抓挠感染',
        '尽快就医评估深度，必要时止痛与抗感染'
      ],
      no: '不要涂牙膏、酱油、食用油、紫药水；不要弄破水泡；不要用冰块直接敷。',
      to: '面积超过一元硬币、皮肤发白或焦黑、宠物明显疼痛挣扎，立即送医。'
    },
    {
      n: '休克 / 抽搐',
      steps: [
        '保持环境安静昏暗，移开硬物和尖锐物，防止撞伤',
        '不要按住抽搐的肢体，让它自然停止，记录开始时间和持续时长',
        '抽搐停止后侧卧，保持气道通畅，清理口鼻分泌物',
        '立即联系医院，途中注意保温'
      ],
      no: '不要往嘴里塞任何东西（包括手指、勺子），不要掐人中，不要喂水喂药。',
      to: '抽搐超过 2 分钟、短时间内反复发作、停止后意识不恢复，属于急症，立即送医。'
    }
  ];

  function careRenderAid() {
    var box = document.getElementById('aidList');
    if (!box || box.dataset.done) return;
    box.innerHTML = CARE_AID.map(function (a, i) {
      return '<div class="aid-item" data-i="' + i + '">'
        + '<div class="aid-head"><div class="aid-ic">'
        + '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path></svg>'
        + '</div><div class="aid-name">' + a.n + '</div><span class="aid-caret">›</span></div>'
        + '<div class="aid-body">'
        + a.steps.map(function (s, k) {
          return '<div class="aid-step"><i>' + (k + 1) + '</i><span>' + s + '</span></div>';
        }).join('')
        + '<div class="aid-no">不要做：' + a.no + '</div>'
        + '<div class="aid-to">送医指征：' + a.to + '</div>'
        + '</div></div>';
    }).join('');
    box.querySelectorAll('.aid-head').forEach(function (h) {
      h.addEventListener('click', function () {
        var item = h.parentNode;
        item.classList.toggle('open');
        if (item.classList.contains('open')) careEvent('aid', { item: (item.querySelector('.aid-name') || {}).textContent || '' });
      });
    });
    box.dataset.done = '1';
  }

  // ---------- 就医提示 ----------
  var CARE_VET_LIST = [
    '症状视频：发作时拍 10～30 秒，比口头描述有用',
    '粪便、呕吐物照片；有条件装袋带来',
    '饲养参数：温度、湿度、灯具、垫材、笼箱尺寸',
    '最近 3 天的喂食与排泄记录',
    '体重变化（近 1～2 个月，有记录更好）',
    '用药史：药名、剂量、用了几天（含网购药和保健品）',
    '宠物本身：透气运输盒 + 保温措施',
    '医院电话确认过：接诊异宠、当天有医生'
  ];
  var VET_KEY = 'xiaochong_vet_check_v1';
  var VET_CITY_KEY = 'xiaochong_vet_city_v1';
  var VET_MINE_KEY = 'xiaochong_vet_mine_v1';

  function vetGet(key, dft) {
    try { return JSON.parse(localStorage.getItem(key) || dft); } catch (e) { return JSON.parse(dft); }
  }
  function vetSet(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {}
  }

  // 城市 + 关键词 → 地图搜索页。不内置医院名单：异宠医院变动快，写死会误导，
  // 直接跳地图让用户看最新的地址、电话、营业状态。
  function careRenderVetLinks() {
    var box = document.getElementById('vetLinks');
    var inp = document.getElementById('vetCity');
    if (!box || !inp) return;
    var city = (inp.value || '').trim().slice(0, 12);
    if (!city) {
      box.innerHTML = '<div class="vm-empty">填上城市，生成三个搜索入口：两个地图 + 爬宠/小哺乳专用关键词。</div>';
      return;
    }
    var enc = encodeURIComponent;
    var kwMain = city + ' 异宠医院';
    var items = [
      ['百度地图', '异宠医院', 'https://map.baidu.com/search/' + enc(kwMain)],
      ['高德地图', '异宠医院', 'https://uri.amap.com/search?keyword=' + enc(kwMain) + '&city=' + enc(city)],
      ['百度地图', '爬宠医生', 'https://map.baidu.com/search/' + enc(city + ' 爬宠医生')],
      ['百度地图', '兔子 鹦鹉 医院', 'https://map.baidu.com/search/' + enc(city + ' 兔子 鹦鹉 医院')]
    ];
    box.innerHTML = items.map(function (it) {
      return '<a href="' + it[2] + '" target="_blank" rel="noopener noreferrer">' + it[0]
        + '<b>' + escapeHtml(it[1]) + '</b></a>';
    }).join('');
  }

  function careRenderVetMine() {
    var box = document.getElementById('vetMine');
    if (!box) return;
    var list = vetGet(VET_MINE_KEY, '[]');
    if (!Array.isArray(list) || !list.length) {
      box.innerHTML = '<div class="vm-empty">还没有记录。看过靠谱的医院，存下名称和电话，下次急诊不用现找。</div>';
      return;
    }
    box.innerHTML = list.map(function (it, i) {
      var tel = (it.t || '').replace(/[^\d+]/g, '');
      return '<div class="vm-row"><span class="vm-name">' + escapeHtml(it.n || '未命名')
        + (it.t ? '<span style="color:var(--ink-3);font-family:var(--mono);font-size:10px"> · ' + escapeHtml(it.t) + '</span>' : '')
        + '</span>'
        + (tel ? '<a href="tel:' + escapeHtml(tel) + '">拨号</a>' : '')
        + '<button type="button" data-del="' + i + '" aria-label="删除">×</button></div>';
    }).join('');
    box.querySelectorAll('button[data-del]').forEach(function (b) {
      b.addEventListener('click', function () {
        var arr = vetGet(VET_MINE_KEY, '[]');
        arr.splice(Number(b.dataset.del), 1);
        vetSet(VET_MINE_KEY, arr);
        careRenderVetMine();
      });
    });
  }

  function careRenderVet() {
    var box = document.getElementById('vetChecklist');
    if (!box) return;
    var saved = vetGet(VET_KEY, '[]');
    if (!Array.isArray(saved)) saved = [];
    box.innerHTML = CARE_VET_LIST.map(function (t, i) {
      var on = saved.indexOf(i) >= 0;
      return '<label class="check-item' + (on ? ' done' : '') + '">'
        + '<input type="checkbox" data-i="' + i + '"' + (on ? ' checked' : '') + '>'
        + '<span>' + t + '</span></label>';
    }).join('');
    box.querySelectorAll('input[type=checkbox]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        var arr = [];
        box.querySelectorAll('input[type=checkbox]').forEach(function (x) {
          if (x.checked) arr.push(Number(x.dataset.i));
        });
        vetSet(VET_KEY, arr);
        cb.closest('.check-item').classList.toggle('done', cb.checked);
      });
    });

    // 城市：记住上次填的，下次打开直接出链接
    var city = document.getElementById('vetCity');
    if (city && !city.value) {
      var saved2 = '';
      try { saved2 = localStorage.getItem(VET_CITY_KEY) || ''; } catch (e) {}
      city.value = saved2;
    }
    careRenderVetLinks();
    careRenderVetMine();
  }

  // ---------- 附近医院（定位 → 高德周边 → 导航） ----------
  var VN = { lat: 0, lng: 0, radius: 5000, items: [], at: 0, loading: false, ready: false,
             isArea: false, areaName: '', areaPath: '', areaUp: '', areaCode: '',
             userLat: 0, userLng: 0, region: 'cn' };

  // 浏览器定位给的是 WGS-84，高德吃 GCJ-02。不转的话整条街都错位几百米，
  // 「附近 2 公里」会变成隔壁区。这个偏移算法是公开的国测局加偏算法。
  var _PI = Math.PI, _AA = 6378245.0, _EE = 0.00669342162296594323;

  function _vnTlat(x, y) {
    var r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
    r += (20 * Math.sin(6 * x * _PI) + 20 * Math.sin(2 * x * _PI)) * 2 / 3;
    r += (20 * Math.sin(y * _PI) + 40 * Math.sin(y / 3 * _PI)) * 2 / 3;
    r += (160 * Math.sin(y / 12 * _PI) + 320 * Math.sin(y * _PI / 30)) * 2 / 3;
    return r;
  }

  function _vnTlng(x, y) {
    var r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
    r += (20 * Math.sin(6 * x * _PI) + 20 * Math.sin(2 * x * _PI)) * 2 / 3;
    r += (20 * Math.sin(x * _PI) + 40 * Math.sin(x / 3 * _PI)) * 2 / 3;
    r += (150 * Math.sin(x / 12 * _PI) + 300 * Math.sin(x / 30 * _PI)) * 2 / 3;
    return r;
  }

  function wgs2gcj(lat, lng) {
    if (lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271) {
      return { lat: lat, lng: lng };   // 境外不加偏
    }
    var dLat = _vnTlat(lng - 105, lat - 35);
    var dLng = _vnTlng(lng - 105, lat - 35);
    var radLat = lat / 180 * _PI;
    var magic = Math.sin(radLat);
    magic = 1 - _EE * magic * magic;
    var sq = Math.sqrt(magic);
    dLat = (dLat * 180) / ((_AA * (1 - _EE)) / (magic * sq) * _PI);
    dLng = (dLng * 180) / (_AA / sq * Math.cos(radLat) * _PI);
    return { lat: lat + dLat, lng: lng + dLng };
  }

  // 高德能直接吃 GCJ-02，百度要 BD-09。不转的话百度那边会偏几百米，
  // 「附近」搜出来的是隔壁街道。
  function gcj2bd(lat, lng) {
    var z = Math.sqrt(lng * lng + lat * lat) + 0.00002 * Math.sin(lat * _PI);
    var theta = Math.atan2(lat, lng) + 0.000003 * Math.cos(lng * _PI);
    return { lat: z * Math.sin(theta) + 0.006, lng: z * Math.cos(theta) + 0.0065 };
  }

  function vnDist(m) {
    if (!m && m !== 0) return '';
    if (m < 1000) return Math.round(m) + ' m';
    return (m / 1000).toFixed(m < 9500 ? 1 : 0) + ' km';
  }

  // 高德导航：to 里是「经度,纬度,名称」，coordinate=gaode 声明这组已是火星坐标
  function vnNavUrl(it) {
    return 'https://uri.amap.com/navigation?to=' + it.lng.toFixed(6) + ',' + it.lat.toFixed(6)
      + ',' + encodeURIComponent(it.name) + '&mode=car&policy=1&src=xiaochong&coordinate=gaode&callnative=1';
  }

  function vnMapUrl(it) {
    return 'https://uri.amap.com/marker?position=' + it.lng.toFixed(6) + ',' + it.lat.toFixed(6)
      + '&name=' + encodeURIComponent(it.name) + '&src=xiaochong&coordinate=gaode&callnative=1';
  }

  function vnState(title, sub, act) {
    var box = document.getElementById('vnList');
    if (!box) return;
    box.innerHTML = '<div class="vn-state"><b>' + title + '</b><span>' + (sub || '') + '</span>'
      + (act ? '<button type="button" id="vnActBtn">' + act[0] + '</button>' : '') + '</div>';
    if (act) {
      var b = document.getElementById('vnActBtn');
      if (b) b.addEventListener('click', act[1]);
    }
  }

  // 兜底出口：不管有没有 Key、有没有定位，都能把用户送到地图里去搜
  function vnFallbackLinks() {
    var box = document.getElementById('vnLinks');
    var wrap = document.getElementById('vnFallback');
    if (!box || !wrap) return;
    var enc = encodeURIComponent;
    // 有定位就把中心点和半径一起带上，地图打开就是「我周围这一圈」；
    // 没定位只能给关键词，地图会按 IP 或默认城市猜一个位置。
    // 选了区县就按整个区县来：一个区动辄几百平方公里，5 公里只够贴中心那一块
    var rad = VN.isArea ? 20000 : VN.radius;
    var amapLoc = VN.lat
      ? '&center=' + VN.lng.toFixed(6) + ',' + VN.lat.toFixed(6) + '&radius=' + rad : '';
    var bd = VN.lat ? gcj2bd(VN.lat, VN.lng) : null;
    var bdLoc = bd
      ? '&location=' + bd.lat.toFixed(6) + ',' + bd.lng.toFixed(6) + '&radius=' + rad : '';
    // 百度用 place/search：老的 map.baidu.com/search/关键词 在手机上会被重定向到
    // 地图首页，关键词直接丢掉，等于把人扔在原地。
    var bdUrl = 'https://api.map.baidu.com/place/search?query=' + enc('宠物医院')
      + bdLoc + '&output=html&src=webapp.xiaochong';
    var items;
    if (VN.region !== 'cn') {
      // 高德在港澳台几乎没有动物医院数据，硬跳过去是一片空白。
      // Google 在那边的 POI 才全，繁体关键词命中率也高。
      var at = VN.lat ? '/@' + VN.lat.toFixed(6) + ',' + VN.lng.toFixed(6) + ',14z' : '';
      items = [
        ['Google 地图', '附近的動物醫院',
         'https://www.google.com/maps/search/' + enc('動物醫院') + at],
        ['Google 地图', '特殊寵物 / exotic',
         'https://www.google.com/maps/search/' + enc('exotic pet vet') + at]
      ];
    } else {
      items = [
        ['高德地图', '附近宠物医院',
         'https://uri.amap.com/search?keyword=' + enc('宠物医院') + amapLoc + '&callnative=1'],
        ['百度地图', '附近宠物医院', bdUrl],
        ['高德地图', '异宠 / 爬宠医生',
         'https://uri.amap.com/search?keyword=' + enc('异宠医院') + amapLoc + '&callnative=1']
      ];
    }
    box.innerHTML = items.map(function (it) {
      return '<a href="' + it[2] + '" target="_blank" rel="noopener noreferrer">' + it[0]
        + '<b>' + escapeHtml(it[1]) + '</b></a>';
    }).join('');
    wrap.hidden = false;
    var h4 = wrap.querySelector('h4');
    if (h4) h4.textContent = VN.isArea ? '在这片地图里找' : '手机上直接找';
    var foot = document.getElementById('vnFoot');
    if (foot) {
      foot.textContent = VN.region !== 'cn'
        ? '地图数据来自 Google 地图，营业状态与是否接诊特殊宠物请以电话确认为准'
        : '地图数据来自高德 / 百度，营业状态与是否接诊异宠请以电话确认为准';
    }
  }

  function vnLocText(main, sub) {
    var a = document.getElementById('vnLoc');
    var b = document.getElementById('vnLocSub');
    if (a) a.textContent = main;
    if (b) b.textContent = sub || '';
  }

  function vnLocate() {
    VN.isArea = false; VN.areaName = ''; VN.areaPath = ''; VN.areaUp = '';
    var h4 = document.querySelector('#vnFallback h4');
    if (h4) h4.textContent = '手机上直接找';
    VN.areaCode = ''; VN.region = 'cn';
    var rc = document.getElementById('vnRadius');
    if (rc) rc.hidden = false;
    var rb = document.getElementById('vnRelocate');
    if (rb) rb.textContent = '定位';
    vnLocText('正在获取位置…', '第一次用要允许定位权限');
    if (!navigator.geolocation) {
      vnLocText('这台设备不支持定位', '可以直接在手机地图里找');
      vnState('定位用不了', '浏览器没提供定位能力，用下面的地图入口找吧。', null);
      vnFallbackLinks();
      return;
    }
    vnState(VN.ready ? '正在找附近…' : '正在定位…',
      VN.ready ? '按你现在的位置搜，最多 20 公里' : '拿到位置后，下面直接跳地图', null);
    navigator.geolocation.getCurrentPosition(function (pos) {
      var c = wgs2gcj(pos.coords.latitude, pos.coords.longitude);
      VN.lat = c.lat; VN.lng = c.lng; VN.at = Date.now();
      VN.userLat = c.lat; VN.userLng = c.lng;
      var acc = pos.coords.accuracy ? ' · 误差约 ' + Math.round(pos.coords.accuracy) + ' 米' : '';
      if (VN.ready) {
        vnLocText('已定位', '按距离从近到远' + acc);
        vnLoad();
      } else {
        vnLocText('已定位',
          Math.round(VN.radius / 1000) + ' 公里内 · 跳过去的地图会从这个位置开始搜' + acc);
        vnNoKey();
      }
    }, function (err) {
      var msg = '定位失败';
      if (err && err.code === 1) msg = '定位权限被拒绝了';
      else if (err && err.code === 2) msg = '暂时拿不到位置';
      else if (err && err.code === 3) msg = '定位超时了';
      vnLocText(msg, '可以在手机设置里允许定位，或直接用地图找');
      vnState(msg, '检查一下手机的定位权限；不方便开定位的话，下面的地图入口也能用。',
        ['再试一次', function () { vnLocate(); }]);
      vnFallbackLinks();
    }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 120000 });
  }

  // 两点直线距离（公里），只在选地区时用来判断「用你的位置算距离合不合适」
  function vnKm(a1, b1, a2, b2) {
    var R = 6371, d1 = (a2 - a1) * Math.PI / 180, d2 = (b2 - b1) * Math.PI / 180;
    var h = Math.sin(d1 / 2) * Math.sin(d1 / 2)
      + Math.cos(a1 * Math.PI / 180) * Math.cos(a2 * Math.PI / 180)
      * Math.sin(d2 / 2) * Math.sin(d2 / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function vnLoad() {
    if (!VN.lat || !VN.lng) { vnLocate(); return; }
    VN.loading = true;
    var url;
    if (VN.isArea) {
      // 距离的原点：人在这个区县周边就用他自己的位置，隔着几百公里查老家
      // 就按区中心算，不然「距你 1200 公里」毫无意义。
      var b = VN.lat, c = VN.lng;
      if (VN.userLat && vnKm(VN.userLat, VN.userLng, VN.lat, VN.lng) < 50) {
        b = VN.userLat; c = VN.userLng;
      }
      vnState('正在查' + VN.areaName + '…', '把这一片登记过的动物医院都拉出来', null);
      url = '/api/vet/area?adcode=' + VN.areaCode + '&lat=' + b.toFixed(6) + '&lng=' + c.toFixed(6);
    } else {
      vnState('正在找附近…', '这一片最多 30 家，按距离排', null);
      url = '/api/vet/nearby?lat=' + VN.lat.toFixed(6) + '&lng=' + VN.lng.toFixed(6)
        + '&radius=' + VN.radius;
    }
    api(url)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        VN.loading = false;
        if (!d || !d.ok) {
          if (d && d.need_key) return vnNoKey();
          return vnErr((d && d.error) || '没搜到，稍后再试');
        }
        VN.items = d.items || [];
        vnRender();
      })
      .catch(function (e) {
        VN.loading = false;
        if (e && e.unauthorized) return;
        vnErr('网络异常，稍后再试');
      });
  }

  function vnNoKey() {
    // 没配高德 Key 时，列表位不放任何说明文字，
    // 直接把下面的「手机上直接找」顶到定位行下面，页面上不出现「去后台填 Key」这类话
    var box = document.getElementById('vnList');
    if (box) box.innerHTML = '';
    vnFallbackLinks();
  }

  function vnErr(msg) {
    vnState('没搜到', msg + '。换个范围再试，或者直接用地图找。',
      ['重试', function () { vnLoad(); }]);
    vnFallbackLinks();
  }

  function vnRender() {
    var box = document.getElementById('vnList');
    if (!box) return;
    if (!VN.items.length) {
      vnState('这附近没搜到医院', '把范围放大到 10 公里或 20 公里再试；也可以直接用下面的地图入口。',
        ['放大到 10 公里', function () { vnRadiusTo(10000); }]);
      vnFallbackLinks();
      return;
    }
    if (VN.isArea) vnLocText(VN.areaName, VN.items.length + ' 家 · ' + VN.areaUp);
    else vnLocText('已定位', Math.round(VN.radius / 1000) + ' 公里内 '
      + VN.items.length + ' 家 · 按距离从近到远');
    // 分两拨：名字里带「异宠 / 爬宠 / 兔」的单独一栏放在上面。
    // 直接按距离排的话，几十家猫狗医院会把唯一一家异宠挤到第 15 屏。
    var ordered = VN.items.slice().sort(function (a, b) {
      return (a.dist || 0) - (b.dist || 0);
    });
    var ex = ordered.filter(function (x) { return x.exotic; });
    var ot = ordered.filter(function (x) { return !x.exotic; });
    function card(it) {
      var raw = (it.tel || '').split(' / ')[0].trim();
      var tel = raw.replace(/[^\d+\-]/g, '');
      var addr = (it.area ? it.area + ' ' : '') + (it.addr || '');
      return '<div class="vn-card">'
        + '<div class="vn-hd"><span class="vn-name">' + escapeHtml(it.name)
        + (it.exotic ? '<span class="vn-exotic">可能接异宠</span>' : '') + '</span>'
        + '<span class="vn-dist">' + vnDist(it.dist) + '</span></div>'
        + (addr ? '<div class="vn-addr">' + escapeHtml(addr) + '</div>' : '')
        + (it.open ? '<div class="vn-meta">' + escapeHtml(it.open) + '</div>' : '')
        + '<div class="vn-acts">'
        + '<a class="primary" href="' + vnNavUrl(it) + '" target="_blank" rel="noopener noreferrer">导航过去</a>'
        + (tel ? '<a href="tel:' + escapeHtml(tel) + '">打 ' + escapeHtml(tel) + '</a>'
               : '<a href="' + vnMapUrl(it) + '" target="_blank" rel="noopener noreferrer">地图上看</a>')
        + '</div></div>';
    }
    var html = '';
    if (ex.length) {
      html += '<div class="vn-group">可能接异宠 · ' + ex.length + ' 家</div>' + ex.map(card).join('');
    }
    if (ot.length) {
      html += '<div class="vn-group">' + (ex.length ? '其他动物医院' : '附近的动物医院')
        + ' · ' + ot.length + ' 家</div>' + ot.map(card).join('');
    }
    box.innerHTML = '<div class="vn-list">' + html + '</div>';
    // 有结果就把兜底入口收起来：列表里每条都有「导航 / 电话」，再摆一遍只是占屏
    var fb = document.getElementById('vnFallback');
    if (fb) fb.hidden = true;
  }

  function vnRadiusTo(r) {
    VN.radius = r;
    var rc = document.getElementById('vnRadius');
    if (rc) {
      rc.querySelectorAll('button[data-r]').forEach(function (x) {
        x.classList.toggle('on', Number(x.dataset.r) === r);
      });
    }
    if (!VN.lat) { vnLocate(); return; }
    if (!VN.ready) {
      vnLocText('已定位', Math.round(VN.radius / 1000) + ' 公里内 · 跳过去的地图会从这个位置开始搜');
      vnNoKey();
      return;
    }
    vnLoad();
  }

  function careInitVetNear() {
    // 手动选了地区：就留在这个地区，别再弹定位把人拽回去
    if (VN.isArea) {
      if (VN.items.length && Date.now() - VN.at < 300000) { vnRender(); return; }
      vnLocText(VN.areaName, VN.areaUp);
      if (VN.region !== 'cn') { vnOverseas(); return; }
      if (VN.ready) vnLoad(); else vnNoKey();
      return;
    }
    // 5 分钟内回到这一页不重复定位：一是省得每次都弹权限，二是不白烧地图配额
    if (VN.items.length && Date.now() - VN.at < 300000) { vnRender(); return; }
    if (VN.lat && Date.now() - VN.at < 300000) {
      if (VN.ready) vnLoad(); else vnNoKey();
      return;
    }
    // 先问一句地图服务配好没，只影响「页面内要不要出列表」，
    // 不影响定位——没定位的话，跳过去的地图也不知道「附近」是哪儿。
    api('/api/vet/ready').then(function (r) { return r.json(); }).then(function (d) {
      VN.ready = !!(d && d.ready);
      vnLocate();
    }).catch(function () { VN.ready = false; vnLocate(); });
  }

  // ---------- 全国省市县（换个地方找） ----------
  // 数据是阿里云 DataV 的行政区划，省 / 市 / 区县三级带中心点，
  // 一共 2896 个可选地点，含港澳台的区和堂区、台湾 22 个县市。
  var REG = { tree: null, path: [], loading: null };
  var REG_CACHE = 'xc_regions_v1';

  function regBuild(areas) {
    var map = {}, roots = [];
    areas.forEach(function (a) {
      map[a[0]] = { c: a[0], n: a[1], x: a[2], y: a[3], p: a[4], k: a[5], kids: [] };
    });
    areas.forEach(function (a) {
      var nd = map[a[0]];
      if (!nd) return;
      if (a[4] && map[a[4]]) map[a[4]].kids.push(nd);
      else roots.push(nd);
    });
    return { map: map, roots: roots };
  }

  // 143KB 的一个文件，存本地一份，第二次进页面直接读，不再打接口
  function regLoad() {
    if (REG.tree) return Promise.resolve(REG.tree);
    if (REG.loading) return REG.loading;
    try {
      var raw = localStorage.getItem(REG_CACHE);
      if (raw) {
        var d = JSON.parse(raw);
        if (d && d.areas && d.areas.length > 2000) {
          REG.tree = regBuild(d.areas);
          return Promise.resolve(REG.tree);
        }
      }
    } catch (e) { /* 存不下就当没缓存，不影响用 */ }
    REG.loading = api('/api/vet/regions')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        REG.tree = regBuild((d && d.areas) || []);
        try {
          localStorage.setItem(REG_CACHE, JSON.stringify({ v: d && d.v, areas: d.areas }));
        } catch (e) { /* 隐私模式或配额满了，忽略 */ }
        REG.loading = null;
        return REG.tree;
      })
      .catch(function (e) { REG.loading = null; throw e; });
    return REG.loading;
  }

  function vnSheetRender() {
    var grid = document.getElementById('vnGrid');
    var crumb = document.getElementById('vnCrumb');
    var title = document.getElementById('vnSheetTitle');
    if (!grid) return;

    var parts = ['<i data-back="-1">全国</i>'];
    REG.path.forEach(function (n, i) {
      parts.push('<span>›</span><i data-back="' + i + '">' + escapeHtml(n.n) + '</i>');
    });
    if (crumb) crumb.innerHTML = parts.join('');

    var t = REG.tree;
    if (!t) {
      grid.innerHTML = '<div class="vn-grid-empty">正在加载全国地区…</div>';
      if (title) title.textContent = '选择地区';
      return;
    }
    var list = REG.path.length ? REG.path[REG.path.length - 1].kids : t.roots;
    if (title) {
      title.textContent = REG.path.length === 0 ? '选省份'
        : (REG.path.length === 1 ? '选城市 / 区' : '选区县');
    }
    if (!list.length) {
      grid.innerHTML = '<div class="vn-grid-empty">这里没有下级了，点上面的名字直接查</div>';
      return;
    }
    grid.innerHTML = list.map(function (n) {
      var sub = n.kids.length ? (n.kids.length + ' 个下级') : '';
      return '<button type="button" data-c="' + n.c + '">'
        + '<span class="n">' + escapeHtml(n.n) + '</span>'
        + (sub ? '<span class="c">' + sub + '</span>' : '') + '</button>';
    }).join('');
  }

  function vnOpenSheet() {
    var sh = document.getElementById('vnSheet');
    if (!sh) return;
    sh.hidden = false;
    document.body.classList.add('vn-no-scroll');
    REG.path = [];
    vnSheetRender();
    if (!REG.tree) {
      regLoad().then(function () { vnSheetRender(); }).catch(function () {
        var g = document.getElementById('vnGrid');
        if (g) g.innerHTML = '<div class="vn-grid-empty">地区列表没加载出来，检查一下网络</div>';
      });
    }
  }

  function vnCloseSheet() {
    var sh = document.getElementById('vnSheet');
    if (sh) sh.hidden = true;
    document.body.classList.remove('vn-no-scroll');
  }

  function vnSheetPick(code) {
    if (!REG.tree) return;
    var nd = REG.tree.map[code];
    if (!nd) return;
    if (nd.kids.length) { REG.path.push(nd); vnSheetRender(); return; }
    vnApplyArea(nd, REG.path.concat([nd]));
  }

  function vnApplyArea(node, trail) {
    var names = trail.map(function (n) { return n.n; });
    VN.isArea = true;
    VN.areaName = node.n;
    VN.areaPath = names.join(' · ');
    VN.areaUp = names.slice(0, -1).join(' · ');
    VN.areaCode = node.c;
    VN.lat = Number(node.y);
    VN.lng = Number(node.x);
    VN.at = Date.now();
    VN.items = [];
    var pre = String(node.c).slice(0, 2);
    VN.region = pre === '71' ? 'tw' : pre === '81' ? 'hk' : pre === '82' ? 'mo' : 'cn';
    vnCloseSheet();
    // 按行政区查，不需要半径档位了，留着只会让人以为还有没搜到的
    var rc = document.getElementById('vnRadius');
    if (rc) rc.hidden = true;
    var rb = document.getElementById('vnRelocate');
    if (rb) rb.textContent = '我附近';
    vnLocText(node.n, VN.areaUp);
    if (VN.region !== 'cn') { vnOverseas(); return; }
    if (VN.ready) vnLoad(); else vnNoKey();
  }

  // 港澳台：高德那边没什么数据，直接给 Google 的入口，别让人对着空列表发呆
  function vnOverseas() {
    vnState('这一片要用 Google 地图',
      '港澳台的地图数据我们不从高德取，点下面的按钮打开 Google 地图，'
      + '「動物醫院」一搜就出来了。', null);
    vnFallbackLinks();
  }

  // ---------- 事件绑定 ----------
  function initCare() {
    document.querySelectorAll('.care-card[data-pane]').forEach(function (c) {
      c.addEventListener('click', function () { careShowPane(c.dataset.pane); });
    });
    var back = document.getElementById('careBack');
    if (back) back.addEventListener('click', function () { careShowPane('home'); });
    // 附近医院：重新定位 / 切换搜索半径
    var reloc = document.getElementById('vnRelocate');
    if (reloc) reloc.addEventListener('click', function () { vnLocate(); });
    var pick = document.getElementById('vnPickArea');
    if (pick) pick.addEventListener('click', vnOpenSheet);
    var shClose = document.getElementById('vnSheetClose');
    if (shClose) shClose.addEventListener('click', vnCloseSheet);
    var shMask = document.getElementById('vnSheetMask');
    if (shMask) shMask.addEventListener('click', vnCloseSheet);
    var grid = document.getElementById('vnGrid');
    if (grid) grid.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button[data-c]') : null;
      if (b) vnSheetPick(b.dataset.c);
    });
    var crumb = document.getElementById('vnCrumb');
    if (crumb) crumb.addEventListener('click', function (e) {
      var i = e.target.closest ? e.target.closest('i[data-back]') : null;
      if (!i) return;
      var d = Number(i.dataset.back);
      REG.path = d < 0 ? [] : REG.path.slice(0, d + 1);
      vnSheetRender();
    });
    var rbox = document.getElementById('vnRadius');
    if (rbox) rbox.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('button[data-r]') : null;
      if (!b) return;
      vnRadiusTo(Number(b.dataset.r));
    });
    // 首页底部「去看医生」：急诊时不用翻菜单
    var goVet = document.getElementById('goVet');
    if (goVet) goVet.addEventListener('click', function () {
      switchView('care');
      careShowPane('vetnear');
    });
    // 今日卡内部的跳转由 careRenderToday 自己接管（切换宠物 / 建议动作 / 诊断回访），
    // 这里不要再绑全局跳转，否则点「切换」会连带跳到温湿度。
    var add = document.getElementById('petAdd');
    if (add) add.addEventListener('click', function () { careOpenPetForm(''); });
    var sel = document.getElementById('envPet');
    if (sel) sel.addEventListener('change', function () {
      CARE.petId = sel.value;
      var jt = document.getElementById('jTemp');
      if (jt) jt.dataset.done = '';
      careJudgeInit();
      careLoadLogs(sel.value);
    });
    var save = document.getElementById('envSave');
    if (save) save.addEventListener('click', careSaveEnv);
    var run = document.getElementById('triRun');
    if (run) run.addEventListener('click', careRunTriage);
    var vetGo = document.getElementById('vetGo');
    if (vetGo) vetGo.addEventListener('click', function () {
      var c = (document.getElementById('vetCity').value || '').trim();
      if (!c) { careToast('先填你在的城市'); return; }
      try { localStorage.setItem(VET_CITY_KEY, c); } catch (e) {}
      careRenderVetLinks();
    });
    var vetCity = document.getElementById('vetCity');
    if (vetCity) vetCity.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); if (vetGo) vetGo.click(); }
    });
    var vmAdd = document.getElementById('vmAdd');
    if (vmAdd) vmAdd.addEventListener('click', function () {
      var n = (document.getElementById('vmName').value || '').trim();
      var t = (document.getElementById('vmTel').value || '').trim();
      if (!n) { careToast('填一下医院名称'); return; }
      var arr = vetGet(VET_MINE_KEY, '[]');
      if (!Array.isArray(arr)) arr = [];
      arr.unshift({ n: n.slice(0, 24), t: t.slice(0, 20) });
      vetSet(VET_MINE_KEY, arr.slice(0, 20));
      document.getElementById('vmName').value = '';
      document.getElementById('vmTel').value = '';
      careRenderVetMine();
      careToast('已存下');
    });
    var mask = document.getElementById('careSheetMask');
    if (mask) mask.addEventListener('click', function (e) { if (e.target === mask) careCloseSheet(); });
    var mp = document.getElementById('makePoster');
    if (mp) mp.addEventListener('click', function () { careOpenPoster(''); });
    careBindPoster();
  }

  // ============ 分享海报（模块 D） ============
  var POSTER_W = 750, POSTER_H = 1180;

  // 「养了多久」按入手日期算，没填就按建档时间，不能用生日
  function posterDays(p) {
    var s = (p && p.adopted) || '';
    var t = s ? new Date(String(s).replace(/-/g, '/')).getTime() : 0;
    if (!t || isNaN(t)) t = ((p && p.created) || 0) * 1000;
    if (!t) return 0;
    var d = Math.floor((Date.now() - t) / 86400000);
    return d > 0 ? d : 0;
  }

  function posterRoundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  function posterDraw(p, qrImg) {
    var c = document.createElement('canvas');
    c.width = POSTER_W; c.height = POSTER_H;
    var x = c.getContext('2d');
    var SERIF = '"Noto Serif SC", "Songti SC", "SimSun", serif';
    var SANS = '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif';
    var MONO = 'ui-monospace, Menlo, Consolas, monospace';

    x.fillStyle = '#F4EFE4';
    x.fillRect(0, 0, POSTER_W, POSTER_H);
    x.strokeStyle = '#DCD5C4';
    x.lineWidth = 2;
    x.strokeRect(28, 28, POSTER_W - 56, POSTER_H - 56);

    // 页眉
    x.fillStyle = '#1E4634';
    x.font = '600 46px ' + SERIF;
    x.textAlign = 'left';
    x.fillText('小宠百问', 68, 132);
    x.fillStyle = '#8A9088';
    x.font = '400 15px ' + MONO;
    x.fillText('异 宠 饲 养 手 册', 70, 166);
    x.textAlign = 'right';
    x.font = '400 13px ' + MONO;
    var dt = new Date();
    x.fillText(dt.getFullYear() + '.' + (dt.getMonth() + 1) + '.' + dt.getDate(), POSTER_W - 68, 132);
    x.textAlign = 'left';
    x.strokeStyle = '#DCD5C4';
    x.lineWidth = 1;
    x.beginPath(); x.moveTo(68, 198); x.lineTo(POSTER_W - 68, 198); x.stroke();

    // 宠物卡
    x.fillStyle = '#FFFDF7';
    posterRoundRect(x, 68, 232, POSTER_W - 136, 412, 3);
    x.fill();
    x.strokeStyle = '#E0D9C7';
    x.stroke();

    if (p) {
      x.fillStyle = '#E7EFE6';
      x.beginPath(); x.arc(150, 328, 56, 0, Math.PI * 2); x.fill();
      x.fillStyle = '#1E4634';
      x.font = '600 42px ' + SERIF;
      x.textAlign = 'center';
      x.fillText((p.name || '宠').slice(0, 1), 150, 344);
      x.textAlign = 'left';

      x.fillStyle = '#1E2B23';
      x.font = '600 38px ' + SERIF;
      x.fillText((p.name || '').slice(0, 10), 232, 318);
      x.fillStyle = '#8A9088';
      x.font = '400 18px ' + SANS;
      var meta = [p.species, p.sex, careAge(p.birthday)].filter(Boolean).join(' · ');
      x.fillText(meta.slice(0, 26), 232, 356);
    } else {
      x.fillStyle = '#1E2B23';
      x.font = '600 34px ' + SERIF;
      x.fillText('一只异宠，一份档案', 108, 340);
      x.fillStyle = '#8A9088';
      x.font = '400 18px ' + SANS;
      x.fillText('物种、生日、体重、喂食与蜕皮，都记在手机上', 108, 378);
    }

    // 三个数据格
    var weights = p ? careWeightsOf(p.id) : [];
    var curW = weights.length ? weights[weights.length - 1].v : (p ? parseFloat(p.weight) || 0 : 0);
    var feedTs = p ? ((CARE.logSummary[p.id] || {}).feed || 0) : 0;
    var pd = p ? posterDays(p) : 0;
    var cells = [
      // 没有档案时出通用版，第一格说「覆盖」而不是「养了」，否则"养了 30+ 个物种"读着别扭
      p ? ['养了', pd ? pd + '' : '今天', pd ? '天' : '建档']
        : ['覆盖', '30+', '个物种'],
      ['体重', curW ? String(Math.round(curW * 10) / 10) : '—', '克'],
      ['喂食', feedTs ? careDaysAgo(feedTs).replace(' 天', '') : '—', feedTs ? '天前' : '还没记']
    ];
    var cw = (POSTER_W - 136) / 3;
    cells.forEach(function (cell, i) {
      var cx = 68 + cw * i;
      if (i) {
        x.strokeStyle = '#EAE4D6';
        x.beginPath(); x.moveTo(cx, 418); x.lineTo(cx, 512); x.stroke();
      }
      x.fillStyle = '#8A9088';
      x.font = '400 14px ' + MONO;
      x.fillText(cell[0], cx + 34, 448);
      x.fillStyle = '#1E4634';
      x.font = '600 40px ' + MONO;
      x.fillText(cell[1], cx + 32, 500);
      var w1 = x.measureText(cell[1]).width;
      x.fillStyle = '#8A9088';
      x.font = '400 15px ' + SANS;
      x.fillText(cell[2], cx + 32 + w1 + 6, 500);
    });

    // 记录摘要
    x.strokeStyle = '#EAE4D6';
    x.beginPath(); x.moveTo(96, 538); x.lineTo(POSTER_W - 96, 538); x.stroke();
    x.fillStyle = '#4A554C';
    x.font = '400 19px ' + SANS;
    var line2 = '还没开始记，从今天记第一笔';
    if (p) {
      var bits = [];
      if (feedTs) bits.push('喂食 ' + careDaysAgo(feedTs) + '前');
      var shedTs = (CARE.logSummary[p.id] || {}).shed || 0;
      if (shedTs) bits.push('蜕皮 ' + careDaysAgo(shedTs) + '前');
      if (bits.length) line2 = '最近记录 · ' + bits.join(' · ');
    }
    x.fillText(line2.slice(0, 30), 104, 590);

    // 主文案
    x.fillStyle = '#1E2B23';
    x.font = '600 30px ' + SERIF;
    x.fillText('吃多少、长多少、什么时候蜕皮', 68, 736);
    x.fillText('记下来，看病换粮都有据可查', 68, 784);

    // 二维码
    var qy = 850, qs = 240;
    x.fillStyle = '#FFFFFF';
    x.fillRect(68, qy, qs, qs);
    x.strokeStyle = '#DCD5C4';
    x.strokeRect(68, qy, qs, qs);
    if (qrImg && qrImg.width) {
      x.drawImage(qrImg, 82, qy + 14, qs - 28, qs - 28);
    } else {
      x.fillStyle = '#8A9088';
      x.font = '400 15px ' + SANS;
      x.textAlign = 'center';
      x.fillText('二维码生成中', 68 + qs / 2, qy + qs / 2);
      x.textAlign = 'left';
    }

    x.fillStyle = '#1E4634';
    x.font = '600 32px ' + SERIF;
    x.fillText('扫码打开', 350, qy + 78);
    x.fillStyle = '#4A554C';
    x.font = '400 19px ' + SANS;
    x.fillText('异宠能不能养 · 生病怎么处理', 350, qy + 124);
    x.fillText('急救分诊 · 温湿度 · 就医清单', 350, qy + 158);
    x.strokeStyle = '#1E4634';
    x.lineWidth = 2;
    x.beginPath(); x.moveTo(350, qy + 186); x.lineTo(430, qy + 186); x.stroke();

    // 页脚
    x.fillStyle = '#8A9088';
    x.font = '400 14px ' + SANS;
    x.textAlign = 'center';
    x.fillText('东莞市栖联科技有限公司 · 内容仅供饲养参考', POSTER_W / 2, 1140);
    x.textAlign = 'left';
    return c;
  }

  function careOpenPoster(petId) {
    if (!CARE.loaded) {
      careLoadPets(function () { careOpenPoster(petId); });
      return;
    }
    var p = null;
    if (petId) { CARE.pets.forEach(function (x) { if (x.id === petId) p = x; }); }
    if (!p) p = CARE.pets[0] || null;
    var mask = document.getElementById('posterMask');
    var img = document.getElementById('posterImg');
    var tip = document.getElementById('posterTip');
    if (!mask || !img) return;

    var qr = new Image();
    var url = posterUrl();
    var done = false;
    var render = function () {
      if (done) return;
      done = true;
      var canvas = posterDraw(p, qr.width ? qr : null);
      var data;
      try { data = canvas.toDataURL('image/png'); }
      catch (e) { data = canvas.toDataURL(); }
      img.src = data;
      img.dataset.file = '小宠百问-' + (p ? p.name : '养护') + '海报.png';
      mask.classList.add('show');
      if (tip) tip.textContent = isWechat() ? '长按图片保存到相册，再发朋友圈' : '长按图片保存，或点下面按钮下载';
    };
    qr.onload = render;
    qr.onerror = render;
    qr.src = '/api/qr?size=240&text=' + encodeURIComponent(url);
    setTimeout(render, 2500);  // 二维码慢或失败也要出图
  }

  function isWechat() {
    return /MicroMessenger/i.test(navigator.userAgent || '');
  }

  // 海报二维码的落地地址：一定要带 sharecode，否则平台鉴权会挡掉
  function posterUrl() {
    var sc = '';
    var m = (location.search || '').match(/[?&]sharecode=([^&]+)/);
    if (m) sc = m[1];
    if (!sc) {
      var mt = document.querySelector('meta[name="xc-sharecode"]');
      sc = (mt && mt.getAttribute('content')) || '';
      if (sc.indexOf('__') === 0) sc = '';
    }
    return location.origin + '/' + (sc ? '?sharecode=' + encodeURIComponent(sc) : '');
  }

  // ============ 拍照诊断 ============
  var DIAG = { dataUrl: '', busy: false, bound: false, hist: [], last: null, curId: '' };

  var DIAG_TIPS = ['不吃东西', '拉稀/软便', '眼睛睁不开', '皮肤有白点', '蜕皮不顺', '呼吸有声音', '站不稳', '有伤口'];

  var DIAG_LV = {
    0: { badge: '观察', title: '先在家观察', win: '48 小时' },
    1: { badge: '就医', title: '24 小时内就医', win: '24 小时' },
    2: { badge: '急诊', title: '尽快就医', win: '现在' }
  };

  function careInitDiag() {
    var sel = document.getElementById('diagPet');
    if (sel) {
      var cur = sel.value;
      var opts = ['<option value="">不指定（只按照片判断）</option>'];
      (CARE.pets || []).forEach(function (p) {
        opts.push('<option value="' + escapeHtml(p.id) + '">'
          + escapeHtml(p.name || '未命名') + (p.species ? ' · ' + escapeHtml(p.species) : '')
          + '</option>');
      });
      sel.innerHTML = opts.join('');
      if (cur) sel.value = cur;
    }
    var tips = document.getElementById('diagTips');
    if (tips && !tips.dataset.init) {
      tips.innerHTML = DIAG_TIPS.map(function (t) {
        return '<button type="button" class="sym-chip" data-tip="' + escapeHtml(t) + '">' + escapeHtml(t) + '</button>';
      }).join('');
      tips.dataset.init = '1';
    }
    if (DIAG.bound) return;
    DIAG.bound = true;

    if (tips) {
      tips.addEventListener('click', function (e) {
        var b = e.target.closest('[data-tip]');
        if (!b) return;
        var ta = document.getElementById('diagNote');
        if (!ta) return;
        var t = b.dataset.tip;
        var v = (ta.value || '').trim();
        if (v.indexOf(t) >= 0) { b.classList.add('on'); return; }
        ta.value = v ? v + (/[，。、]$/.test(v) ? '' : '，') + t : t;
        b.classList.add('on');
      });
    }

    // 两个入口分开：带 capture 的会直接调相机、不弹选择器，所以不能共用一个 input
    var input = document.getElementById('diagFile');   // 相册 / 文件
    var camIn = document.getElementById('diagCam');    // 相机
    function bindPick(el) {
      if (!el) return;
      el.addEventListener('change', function () {
        var f = el.files && el.files[0];
        el.value = '';                                  // 清掉，同一张图也能再选一次
        careDiagPick(f);
      });
    }
    bindPick(input);
    bindPick(camIn);

    var shot = document.getElementById('diagShot');
    var camBtn = document.getElementById('diagCamBtn');
    var albumBtn = document.getElementById('diagAlbumBtn');
    // 点空白处走相册（多数是选已有照片），两个按钮各管各的，别让冒泡重复触发
    if (shot && input) shot.addEventListener('click', function () { input.click(); });
    if (camBtn && camIn) camBtn.addEventListener('click', function (e) { e.stopPropagation(); camIn.click(); });
    if (albumBtn && input) albumBtn.addEventListener('click', function (e) { e.stopPropagation(); input.click(); });
    var retake = document.getElementById('diagRetake');
    if (retake && input) retake.addEventListener('click', function () { input.click(); });
    var run = document.getElementById('diagRun');
    if (run) run.addEventListener('click', careDiagRun);
  }

  // 本地先压一遍：微信里拍的原图常有 3–8 MB，压到长边 1180 再传，省流量也省等待
  function careDiagPick(file) {
    if (!file) return;
    if (!/^image\//.test(file.type || '')) { careDiagErr('请选择一张照片'); return; }
    careDiagErr('');
    var fr = new FileReader();
    fr.onload = function () {
      var img = new Image();
      img.onload = function () {
        var max = 1180;
        var w = img.naturalWidth || img.width;
        var h = img.naturalHeight || img.height;
        var s = Math.min(1, max / Math.max(w, h));
        var cv = document.createElement('canvas');
        cv.width = Math.max(1, Math.round(w * s));
        cv.height = Math.max(1, Math.round(h * s));
        var x = cv.getContext('2d');
        x.fillStyle = '#fff';
        x.fillRect(0, 0, cv.width, cv.height);
        x.drawImage(img, 0, 0, cv.width, cv.height);
        DIAG.dataUrl = cv.toDataURL('image/jpeg', 0.82);

        var prev = document.getElementById('diagPrev');
        var pimg = document.getElementById('diagImg');
        if (pimg) pimg.src = DIAG.dataUrl;
        if (prev) prev.hidden = false;
        var nm = document.getElementById('diagFileName');
        if (nm) nm.textContent = '已就绪 · ' + cv.width + '×' + cv.height + ' · ' + Math.round(DIAG.dataUrl.length * 0.75 / 1024) + 'KB';
        var shotZone = document.getElementById('diagShot');
        if (shotZone) shotZone.hidden = true;
        var run = document.getElementById('diagRun');
        if (run) run.disabled = false;
      };
      img.onerror = function () { careDiagErr('这张图读不出来，换一张试试'); };
      img.src = fr.result;
    };
    fr.onerror = function () { careDiagErr('读取照片失败，请重试'); };
    fr.readAsDataURL(file);
  }

  function careDiagErr(msg) {
    var el = document.getElementById('diagErr');
    if (el) el.textContent = msg || '';
  }

  function careDiagRun() {
    if (DIAG.busy) return;
    if (!DIAG.dataUrl) { careDiagErr('先拍一张照片'); return; }
    var btn = document.getElementById('diagRun');
    var box = document.getElementById('diagResult');
    var sel = document.getElementById('diagPet');
    var note = document.getElementById('diagNote');
    var petId = sel ? sel.value : '';
    var sp = '';
    (CARE.pets || []).forEach(function (p) { if (p.id === petId) sp = p.species || ''; });

    DIAG.busy = true;
    if (btn) { btn.disabled = true; btn.textContent = '正在看图…'; }
    careDiagErr('');
    if (box) {
      box.innerHTML = '<div class="diag-wait"><h4>正在看这张照片</h4>'
        + '<div class="diag-bar"><i></i></div>'
        + '<p>先确认画面里能看到什么，再对照物种的常见表现。通常 10–20 秒，先别离开这一页。</p></div>';
      box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    api('/api/diagnose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: DIAG.dataUrl, pet_id: petId, species: sp, note: (note && note.value || '').trim() })
    }).then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, d: d || {} }; });
    }).then(function (res) {
      DIAG.busy = false;
      if (btn) { btn.disabled = false; btn.textContent = '重新诊断'; }
      if (!res.ok || !res.d.result) {
        var msg = res.d.message || res.d.error || '诊断失败，请重试';
        if (box) {
          box.innerHTML = '<div class="diag-wait"><h4>这次没看成</h4><p>' + escapeHtml(msg) + '</p></div>';
        }
        return;
      }
      DIAG.last = res.d;
      careDiagRender(res.d.result, {
        id: res.d.id, pet_name: (sel && sel.selectedIndex > 0 ? sel.options[sel.selectedIndex].text.split(' · ')[0] : ''),
        species: sp, ts: Math.floor(Date.now() / 1000)
      });
      careLoadDiagHist();
    }).catch(function () {
      DIAG.busy = false;
      if (btn) { btn.disabled = false; btn.textContent = '重新诊断'; }
      if (box) box.innerHTML = '<div class="diag-wait"><h4>网络断了</h4><p>照片没传上去，检查一下网络再试。</p></div>';
    });
  }

  function careDiagRender(r, meta) {
    meta = meta || {};
    var box = document.getElementById('diagResult');
    if (!box) return;
    DIAG.curId = meta.id || '';
    var M = DIAG_LV[r.level] || DIAG_LV[0];
    var cls = r.level === 2 ? 3 : r.level;

    var causes = (r.causes || []).map(function (c) {
      var od = c.odds === '高' ? 'hi' : (c.odds === '中' ? 'mid' : '');
      return '<div class="diag-cause"><span class="odds ' + od + '">' + escapeHtml(c.odds) + '</span>'
        + '<div class="cbody"><div class="cname">' + escapeHtml(c.name) + '</div>'
        + (c.why ? '<div class="cwhy">' + escapeHtml(c.why) + '</div>' : '') + '</div></div>';
    }).join('');

    var steps = (r.now || []).map(function (t, i) {
      return '<div class="result-step"><i>' + (i + 1) + '</i><span>' + escapeHtml(t) + '</span></div>';
    }).join('');

    var see = (r.see || []).map(function (t) {
      return '<div class="result-li">' + escapeHtml(t) + '</div>';
    }).join('');

    var avoid = (r.avoid || []).map(function (t) {
      return '<div class="result-li">' + escapeHtml(t) + '</div>';
    }).join('');

    var vet = (r.vet || []).map(function (t) {
      return '<div class="result-li">' + escapeHtml(t) + '</div>';
    }).join('');

    var need = (r.need || []).map(function (t) {
      return '<div class="result-li">' + escapeHtml(t) + '</div>';
    }).join('');

    var html = '<div class="result lv' + cls + '">'
      + '<div class="result-bar"><span class="result-lv">' + M.badge + '</span>'
      + '<span class="result-title">' + escapeHtml(r.title || M.title) + '</span>'
      + '<span class="result-win">' + M.win + '</span></div>'
      + '<div class="result-body">'
      + '<div class="result-why">' + escapeHtml(r.summary || '') + '</div>'
      + (see ? '<div class="result-h">照片里看到</div>' + see : '')
      + (causes ? '<div class="result-h">可能的原因</div>' + causes : '')
      + (steps ? '<div class="result-h">现在做</div>' + steps : '')
      + (avoid ? '<div class="result-h">不要做</div>' + avoid : '')
      + (vet ? '<div class="result-h">出现这些立刻就医</div>' + vet : '')
      + (need ? '<div class="result-h">还想让你补充</div>' + need : '')
      + '<div class="result-acts diag-acts">'
      + '<button class="solid" data-dact="save">保存这张清单</button>'
      + '<button data-dact="copy">复制文字</button>'
      + (r.level < 2 ? '<button data-dact="track">加入 48 小时追踪</button>' : '<button data-go="vet">就医准备清单</button>')
      + '<button data-dact="again">再拍一张</button>'
      + '</div>'
      + '<div class="diag-disc">这份判断依据照片中可见的部分得出，看不清的地方已列为「还想让你补充」。它不能替代执业兽医的检查，用药请遵医嘱。</div>'
      + '</div></div>';

    box.innerHTML = html;
    box.querySelector('.result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    var acts = box.querySelector('.result-acts');
    if (acts) {
      acts.addEventListener('click', function (e) {
        var b = e.target.closest('[data-dact]');
        if (!b) return;
        var act = b.dataset.dact;
        if (act === 'save') careDiagPoster(r, meta);
        if (act === 'copy') careDiagCopy(r, meta);
        if (act === 'track') careAddTrack(r.title || 'AI 诊断', r.level === 1 ? 2 : 1, b);
        if (act === 'again') careDiagReset();
      });
    }
    box.querySelectorAll('button[data-go]').forEach(function (b) {
      b.addEventListener('click', function () { careShowPane(b.dataset.go); });
    });
  }

  function careDiagReset() {
    DIAG.dataUrl = '';
    var prev = document.getElementById('diagPrev');
    if (prev) prev.hidden = true;
    var zone = document.getElementById('diagShot');
    if (zone) zone.hidden = false;
    var run = document.getElementById('diagRun');
    if (run) { run.disabled = true; run.textContent = '开始诊断'; }
    var note = document.getElementById('diagNote');
    if (note) note.value = '';
    var tips = document.getElementById('diagTips');
    if (tips) tips.querySelectorAll('.sym-chip.on').forEach(function (c) { c.classList.remove('on'); });
    careDiagErr('');
    var box = document.getElementById('diagResult');
    if (box) box.innerHTML = '';
    document.getElementById('careMain').scrollTop = 0;
  }

  function careLoadDiagHist(cb) {
    api('/api/diagnoses?limit=10').then(function (r) { return r.json(); }).then(function (d) {
      DIAG.hist = (d && d.items) || [];
      careRenderDiagHist();
      if (cb) cb();
    }).catch(function () { if (cb) cb(); });
  }

  function careRenderDiagHist() {
    var box = document.getElementById('diagHist');
    if (!box) return;
    if (!DIAG.hist.length) {
      box.innerHTML = '<div class="diag-empty">还没有诊断记录。拍一张，结论会留在这里，复诊时给医生看。</div>';
      return;
    }
    box.innerHTML = DIAG.hist.map(function (it) {
      var lv = it.level || 0;
      var d = new Date((it.ts || 0) * 1000);
      var when = (d.getMonth() + 1) + '/' + d.getDate() + ' ' + ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
      var thumb = it.thumb
        ? '<img class="diag-thumb" src="' + it.thumb + '" alt="">'
        : '<div class="diag-thumb empty">无图</div>';
      return '<div class="diag-item" data-id="' + escapeHtml(it.id) + '">'
        + thumb
        + '<div class="diag-it-body"><div class="diag-it-title">' + escapeHtml(it.title || '诊断记录') + '</div>'
        + '<div class="diag-it-sub">' + when + (it.pet_name ? ' · ' + escapeHtml(it.pet_name) : '') + '</div></div>'
        + '<span class="diag-it-lv lv' + lv + '">' + (DIAG_LV[lv] || DIAG_LV[0]).badge + '</span>'
        + '<button type="button" class="diag-it-del" data-del="' + escapeHtml(it.id) + '" aria-label="删除这条记录">×</button>'
        + '</div>';
    }).join('');

    // 拍废的记录得能自己删掉，不然只能等系统按 30 条上限淘汰
    box.querySelectorAll('.diag-it-del').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = btn.dataset.del;
        if (!confirm('删掉这条诊断记录？清单和缩略图都会一起清掉。')) return;
        api('/api/diagnoses/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id })
        }).then(function (r) { return r.json(); }).then(function (d) {
          if (d && d.error) { careToast(d.error); return; }
          DIAG.hist = DIAG.hist.filter(function (x) { return x.id !== id; });
          if (DIAG.curId === id) {
            DIAG.curId = '';
            DIAG.last = null;
            var rb = document.getElementById('diagResult');
            if (rb) rb.innerHTML = '';
          }
          careRenderDiagHist();
          careToast('已删除');
        }).catch(function () { careToast('网络异常，稍后再试'); });
      });
    });

    box.querySelectorAll('.diag-item').forEach(function (el) {
      el.addEventListener('click', function () {
        var it = null;
        DIAG.hist.forEach(function (x) { if (x.id === el.dataset.id) it = x; });
        if (!it || !it.detail) return;
        careDiagRender(it.detail, { id: it.id, pet_name: it.pet_name, species: it.species, ts: it.ts });
        document.getElementById('careMain').scrollTop = 0;
      });
    });
  }

  function careDiagText(r, meta) {
    var M = DIAG_LV[r.level] || DIAG_LV[0];
    var L = [];
    L.push('【' + (meta.pet_name || r.species_guess || '宠物') + '】' + (r.title || M.title));
    L.push('分级：' + M.title + '（' + M.win + '）');
    if (r.summary) L.push(r.summary);
    if (r.see && r.see.length) L.push('\n■ 照片里看到\n- ' + r.see.join('\n- '));
    if (r.causes && r.causes.length) {
      L.push('\n■ 可能的原因\n' + r.causes.map(function (c) {
        return '- ' + c.name + '（可能性 ' + c.odds + '）' + (c.why ? '：' + c.why : '');
      }).join('\n'));
    }
    if (r.now && r.now.length) L.push('\n■ 现在做\n' + r.now.map(function (t, i) { return (i + 1) + '. ' + t; }).join('\n'));
    if (r.avoid && r.avoid.length) L.push('\n■ 不要做\n- ' + r.avoid.join('\n- '));
    if (r.vet && r.vet.length) L.push('\n■ 出现这些立刻就医\n- ' + r.vet.join('\n- '));
    if (r.need && r.need.length) L.push('\n■ 还想让你补充\n- ' + r.need.join('\n- '));
    L.push('\n—— 小宠百问 · AI 初步判断，不能替代执业兽医检查');
    return L.join('\n');
  }

  function careDiagCopy(r, meta) {
    var txt = careDiagText(r, meta);
    var done = function () { careToast('清单已复制，可粘贴到备忘录'); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done).catch(function () { careDiagCopyFallback(txt); });
    } else {
      careDiagCopyFallback(txt);
    }
  }

  function careDiagCopyFallback(txt) {
    var ta = document.createElement('textarea');
    ta.value = txt;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); careToast('清单已复制'); }
    catch (e) { careToast('复制失败，请长按选择文字'); }
    ta.remove();
  }

  // 把清单画成一张长图：微信里长按保存，浏览器直接下载
  function careDiagPoster(r, meta) {
    meta = meta || {};
    var mask = document.getElementById('posterMask');
    var img = document.getElementById('posterImg');
    var tip = document.getElementById('posterTip');
    if (!mask || !img) return;
    var qr = new Image();
    var done = false;
    var render = function () {
      if (done) return;
      done = true;
      var cv = careDiagDraw(r, meta, qr.width ? qr : null);
      var data;
      try { data = cv.toDataURL('image/png'); } catch (e) { data = cv.toDataURL(); }
      img.src = data;
      img.dataset.file = '小宠百问-诊断清单-' + (meta.pet_name || '宠物') + '.png';
      mask.classList.add('show');
      if (tip) tip.textContent = isWechat() ? '长按图片保存到相册，复诊时给医生看' : '长按图片保存，或点下面按钮下载';
    };
    qr.onload = render;
    qr.onerror = render;
    qr.src = '/api/qr?size=200&text=' + encodeURIComponent(posterUrl());
    setTimeout(render, 2200);
  }

  function careDiagDraw(r, meta, qr) {
    var W = 750, PAD = 56, CW = W - PAD * 2;
    var SANS = '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,sans-serif';
    var SERIF = '"Songti SC","Noto Serif CJK SC","SimSun",serif';
    var MONO = 'ui-monospace,Menlo,Consolas,monospace';
    var INK = '#232B24', INK2 = '#4A534B', INK3 = '#8A8F87', RULE = '#DCD5C4';
    var lv = r.level || 0;
    var M = DIAG_LV[lv] || DIAG_LV[0];
    var barBg = lv === 2 ? '#F2E0D4' : (lv === 1 ? '#F2E8D2' : '#E2EAE2');
    var barFg = lv === 2 ? '#8E3F1E' : (lv === 1 ? '#6E4A12' : '#1E4634');

    var blocks = [];
    if (r.see && r.see.length) {
      blocks.push({ t: 'h', s: '照片里看到' });
      r.see.forEach(function (t) { blocks.push({ t: 'li', s: t }); });
    }
    if (r.causes && r.causes.length) {
      blocks.push({ t: 'h', s: '可能的原因' });
      r.causes.forEach(function (c) { blocks.push({ t: 'cause', s: c.name, odds: c.odds, why: c.why || '' }); });
    }
    if (r.now && r.now.length) {
      blocks.push({ t: 'h', s: '现在做' });
      r.now.forEach(function (t, i) { blocks.push({ t: 'n', s: t, i: i + 1 }); });
    }
    if (r.avoid && r.avoid.length) {
      blocks.push({ t: 'h', s: '不要做' });
      r.avoid.forEach(function (t) { blocks.push({ t: 'li', s: t }); });
    }
    if (r.vet && r.vet.length) {
      blocks.push({ t: 'h', s: '出现这些立刻就医' });
      r.vet.forEach(function (t) { blocks.push({ t: 'li', s: t }); });
    }
    if (r.need && r.need.length) {
      blocks.push({ t: 'h', s: '还想让你补充' });
      r.need.forEach(function (t) { blocks.push({ t: 'li', s: t }); });
    }

    var cv = document.createElement('canvas');
    var x = cv.getContext('2d');

    function wrap(text, maxW) {
      var out = [], line = '';
      var arr = String(text == null ? '' : text).split('');
      for (var i = 0; i < arr.length; i++) {
        var ch = arr[i];
        if (line && x.measureText(line + ch).width > maxW) { out.push(line); line = ch; }
        else line += ch;
      }
      if (line) out.push(line);
      return out.length ? out : [''];
    }

    function paint(y, draw) {
      blocks.forEach(function (b) {
        if (b.t === 'h') {
          y += 34;
          x.font = '600 20px ' + MONO;
          if (draw) {
            x.fillStyle = INK3;
            x.fillText(b.s, PAD, y);
            var w = x.measureText(b.s).width;
            x.strokeStyle = RULE;
            x.lineWidth = 1;
            x.beginPath();
            x.moveTo(PAD + w + 14, y - 6);
            x.lineTo(W - PAD, y - 6);
            x.stroke();
          }
          y += 40;
        } else if (b.t === 'li') {
          x.font = '26px ' + SANS;
          wrap(b.s, CW - 26).forEach(function (ln, k) {
            if (draw) {
              x.fillStyle = INK2;
              x.fillText(ln, PAD + 26, y);
              if (k === 0) { x.fillStyle = '#B9B2A0'; x.fillRect(PAD + 10, y - 9, 7, 2); }
            }
            y += 38;
          });
          y += 8;
        } else if (b.t === 'n') {
          x.font = '26px ' + SANS;
          wrap(b.s, CW - 54).forEach(function (ln, k) {
            if (draw) {
              x.fillStyle = INK2;
              x.fillText(ln, PAD + 54, y);
              if (k === 0) {
                x.strokeStyle = '#CFC7B4';
                x.lineWidth = 1;
                x.strokeRect(PAD + 6, y - 22, 26, 26);
                x.fillStyle = '#7A817A';
                x.font = '16px ' + MONO;
                x.fillText(String(b.i), PAD + 14, y - 4);
              }
              x.font = '26px ' + SANS;
            }
            y += 38;
          });
          y += 8;
        } else if (b.t === 'cause') {
          x.font = '600 26px ' + SANS;
          wrap(b.s, CW - 72).forEach(function (ln, k) {
            if (draw) {
              x.fillStyle = INK;
              x.fillText(ln, PAD + 72, y);
              if (k === 0) {
                x.fillStyle = b.odds === '高' ? '#F6E6DC' : (b.odds === '中' ? '#F7F1E1' : '#FFFFFF');
                x.fillRect(PAD + 8, y - 22, 46, 26);
                x.strokeStyle = b.odds === '高' ? '#B4572F' : (b.odds === '中' ? '#C9A96A' : RULE);
                x.strokeRect(PAD + 8, y - 22, 46, 26);
                x.fillStyle = b.odds === '高' ? '#8E3F1E' : (b.odds === '中' ? '#6E4A12' : INK3);
                x.font = '16px ' + MONO;
                x.fillText(b.odds, PAD + 25, y - 3);
              }
              x.font = '600 26px ' + SANS;
            }
            y += 36;
          });
          if (b.why) {
            x.font = '21px ' + SANS;
            wrap(b.why, CW - 72).forEach(function (ln) {
              if (draw) { x.fillStyle = INK3; x.fillText(ln, PAD + 72, y); }
              y += 32;
            });
          }
          y += 12;
        }
      });
      return y;
    }

    x.font = '25px ' + SANS;
    var sumLines = r.summary ? wrap(r.summary, CW) : [];
    var sumY = 342;
    var startY = sumY + sumLines.length * 40 + 10;
    var endY = paint(startY, false);
    var H = endY + (qr ? 250 : 200);

    cv.width = W;
    cv.height = H;

    x.fillStyle = '#FBF7EC';
    x.fillRect(0, 0, W, H);
    x.strokeStyle = '#D8D0BE';
    x.lineWidth = 2;
    x.strokeRect(24, 24, W - 48, H - 48);

    var dt = new Date((meta.ts || Math.floor(Date.now() / 1000)) * 1000);
    var ds = dt.getFullYear() + '.' + (dt.getMonth() + 1) + '.' + dt.getDate();

    x.font = '19px ' + MONO;
    x.fillStyle = INK3;
    x.fillText('看诊清单 / 小宠百问', PAD, 88);
    x.textAlign = 'right';
    x.fillText(ds, W - PAD, 88);
    x.textAlign = 'left';

    x.font = '600 46px ' + SERIF;
    x.fillStyle = '#1F2A22';
    x.fillText(meta.pet_name || r.species_guess || '宠物', PAD, 150);

    x.font = '21px ' + SANS;
    x.fillStyle = '#7A817A';
    var sub = [];
    if (r.species_guess) sub.push(r.species_guess);
    sub.push('AI 看图判断');
    x.fillText(sub.join(' · '), PAD, 186);

    x.strokeStyle = RULE;
    x.lineWidth = 1;
    x.beginPath();
    x.moveTo(PAD, 212);
    x.lineTo(W - PAD, 212);
    x.stroke();

    x.fillStyle = barBg;
    x.fillRect(PAD, 238, CW, 62);
    x.fillStyle = barFg;
    x.font = '600 28px ' + SERIF;
    x.fillText(M.title, PAD + 20, 278);
    x.font = '19px ' + MONO;
    x.textAlign = 'right';
    x.fillText(M.win, W - PAD - 20, 276);
    x.textAlign = 'left';

    x.font = '25px ' + SANS;
    x.fillStyle = INK2;
    sumLines.forEach(function (ln, i) { x.fillText(ln, PAD, sumY + i * 40); });

    var yEnd = paint(startY, true);

    var fy = yEnd + 44;
    x.strokeStyle = RULE;
    x.lineWidth = 1;
    x.beginPath();
    x.moveTo(PAD, fy - 22);
    x.lineTo(W - PAD, fy - 22);
    x.stroke();

    if (qr) {
      x.drawImage(qr, PAD, fy, 118, 118);
      x.font = '22px ' + SANS;
      x.fillStyle = INK2;
      x.fillText('扫码打开小宠百问', PAD + 136, fy + 48);
      x.font = '19px ' + SANS;
      x.fillStyle = INK3;
      x.fillText('400+ 条异宠饲养问答，随时查', PAD + 136, fy + 80);
    } else {
      x.font = '22px ' + SANS;
      x.fillStyle = INK2;
      x.fillText('小宠百问 · 异宠饲养问答助手', PAD, fy + 40);
    }

    x.font = '17px ' + SANS;
    x.fillStyle = '#9A9F96';
    wrap('AI 依据照片可见内容给出的初步判断，不能替代执业兽医检查，用药请遵医嘱。', CW)
      .forEach(function (ln, k) { x.fillText(ln, PAD, fy + 158 + k * 26); });

    return cv;
  }

  function careBindPoster() {
    var mask = document.getElementById('posterMask');
    var img = document.getElementById('posterImg');
    var save = document.getElementById('posterSave');
    var close = document.getElementById('posterClose');
    if (close) close.addEventListener('click', function () { mask.classList.remove('show'); });
    if (mask) mask.addEventListener('click', function (e) { if (e.target === mask) mask.classList.remove('show'); });
    if (save) save.addEventListener('click', function () {
      if (!img || !img.src) return;
      if (isWechat()) { careToast('微信里请长按图片保存'); return; }
      var a = document.createElement('a');
      a.href = img.src;
      a.download = img.dataset.file || '小宠百问-海报.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  }

  // ============ 版本号（前台版本，独立于后台管理系统） ============
  function loadAppVersion() {
    fetch('/api/health').then(function (r) { return r.json(); }).then(function (d) {
      if (!d || !d.app_version) return;
      var v = 'v' + d.app_version;
      var el = document.getElementById('appVer');
      if (el) el.textContent = v;
      var foot = document.getElementById('appFoot');
      if (foot) foot.innerHTML = '东莞市栖联科技有限公司<br>小宠百问 ' + v + ' · 内容仅供饲养参考';
      // 图鉴数量跟后端走，增删物种时「关于」「首页」「我的」不会和实际对不上
      var kp = document.getElementById('aboutKeep');
      var kn = document.getElementById('aboutNo');
      if (kp && d.dex_keep) kp.textContent = d.dex_keep;
      if (kn && d.dex_no) kn.textContent = d.dex_no;
      // 首页与我的页的「可养物种」统一取图鉴可养数，避免和「可以养 92」两个口径
      if (d.dex_keep) {
        var ts = document.getElementById('tSpecies');
        var ms = document.getElementById('statSpecies');
        if (ts) ts.textContent = d.dex_keep;
        if (ms) ms.textContent = d.dex_keep;
      }
    }).catch(function () {});
  }

  // ============ 初始化 ============
  // 首页那行「此刻」：让它显示真实时间，深夜打开时会有一点被接住的感觉
  function paintClock() {
    var el = document.getElementById('heroClock');
    if (!el) return;
    var d = new Date();
    el.textContent = ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }
  paintClock();
  setInterval(paintClock, 30000);

  // 微信从聊天窗口回到页面时往往复用旧 WebView，不会重新发请求，
  // 结果就是「后台已经发了新版，用户这边还是老界面」。
  // 回到前台时对一次版本号，不一致才浮一条提示，不打扰正常使用。
  (function watchVersion() {
    var tag = document.querySelector('script[src*="app.js"]');
    var mine = tag ? (tag.src.match(/[?&]v=([^&]+)/) || [])[1] : '';
    if (!mine) return;
    var checking = false;
    function showBar() {
      if (document.getElementById('verBar')) return;
      var el = document.createElement('div');
      el.id = 'verBar';
      el.className = 'ver-bar';
      el.innerHTML = '<span>已更新到新版本</span><b>刷新</b>';
      el.addEventListener('click', function () { location.reload(); });
      document.body.appendChild(el);
    }
    document.addEventListener('visibilitychange', function () {
      if (checking || document.visibilityState !== 'visible') return;
      checking = true;
      fetch('/api/health', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (d) { if (d && d.app_version && d.app_version !== mine) showBar(); })
        .catch(function () {})
        .then(function () { checking = false; });
    });
  })();

  fixShareImage();
  loadAppVersion();
  initProfile();
  initShare();
  initService();
  initCare();
  initAuth();
  bootStep(30);
  // 兜底：接口挂住也不能一直卡在加载页
  setTimeout(bootFinish, 6000);
  // 先校验登录态，登录成功后再加载问答/合规/资讯数据
  checkAuth();
})();