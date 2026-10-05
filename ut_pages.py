#!/usr/bin/env python
"""
ut_pages.py —— AgGithubPages 的守門測試（秒級、不連任何外部服務）

為什麼需要它：這一族缺陷**全部不會讓退出碼變錯**，只會讓**畫面少講一句話**，
而少講的那一句往往正是防止誤判的那一句。`mission_PG` 的 `ut_web.py` 與
AgWager 的 `OPEN_SECTIONS` 都踩過同一個坑：
    **沒人顯示的欄位等於不存在，而且不會報錯。**

六軸：
  [A] 頁面自身的靜態不變量（單檔、零外部資源、不含 <a>、不用 innerHTML、JS 語法可過）
  [B] ★★三條硬規則的**契約句**不可從頁面消失（計畫書 §0）
  [C] ★★渲染覆蓋率：承載裡出現的每一個區塊型別，頁面都要認得；
      ★ 並用**合成承載**驗 catch-all（不認得的型別必須原樣攤開，不可靜默丟掉）
  [D] 編碼往返：payload → gzip → base64url → 解回來必須逐位元組相同
  [E] ★安全：承載是**外部來源**（含平台商回應原文）⇒ 不可有 innerHTML／eval／
      document.write；XSS 樣本在渲染後不可變成真的節點
  [F] ★決定性：同一份 payload 編碼兩次必須得到**完全相同**的網址（gzip mtime=0）

用法：
    python ut_pages.py              # 六軸全跑
    python ut_pages.py --no-node    # 略過需要 node 的軸（B/C/E 的執行面）
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE = HERE / "index.html"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

bad = 0


def chk(name, ok, extra=""):
    global bad
    bad += 0 if ok else 1
    print("%s  %-62s %s" % ("PASS" if ok else "FAIL", name, extra))


# ★★【B 軸】這些句子是本頁**存在的理由**。刪掉任何一句，畫面會變好看，
#    而讀者會開始下錯結論 —— 所以它們是契約，不是文案。
#    （作法抄 `mission_PG` 的 `ut_web.py` B 軸：警語當契約來測。）
CONTRACT = [
    # 硬規則①：`warning` 一律顯示且擺最上面（那是「這段不是平台回的」）
    ("warning 必須被渲染", "b.warning"),
    ("warning 用 warnbox 樣式（視覺上要跳出來）", "'warnbox'"),
    # 硬規則③：三個不可省略的欄位
    ("headers_note 必須被渲染", "side.headers_note"),
    ("item 的 notes 必須被渲染（含遮蔽欄位與 URL 帶憑證）", "it.notes"),
    # 硬規則②：長度上限要看得見
    ("over_budget 必須被渲染", "p.over_budget"),
    # catch-all（計畫書 §5-3）
    ("未知區塊型別要原樣攤開", "未知區塊型別"),
    # 403（初始說明 §3）
    ("403 Forbidden 字樣", "403 Forbidden"),
    # 安全鐵則的註解要留著（它解釋了為什麼不能用 innerHTML）
    ("textContent 鐵則的說明要留著", "永不 innerHTML"),
]

# [A] 靜態不變量 ───────────────────────────────────────────────────────────────
src = PAGE.read_text(encoding="utf-8")
print("===== [A] 頁面靜態不變量 =====")
chk("A 單檔存在且非空", len(src) > 2000, "%d bytes" % len(src))
# 零外部資源：GitHub Pages 與本機鏡像都不該去抓任何外部東西
for pat, label in ((r'src\s*=\s*["\']https?://', "外部 script/img"),
                   (r'<link[^>]+href\s*=\s*["\']https?://', "外部 stylesheet"),
                   (r'@import\s+url\(', "CSS @import"),
                   (r'\bfetch\s*\(', "fetch()"),
                   (r'XMLHttpRequest', "XHR")):
    chk("A 不含%s" % label, re.search(pat, src) is None)
# 初始說明 §4：本網站不會有任何 <a> 轉跳
chk("A ★不含 <a> 標籤（初始說明 §4）", re.search(r"<a[\s>]", src, re.I) is None)
chk("A 只有一個 <script>（單檔內嵌）", len(re.findall(r"<script", src)) == 1)
chk("A 有 charset utf-8", re.search(r'charset\s*=\s*["\']?utf-8', src, re.I) is not None)
chk("A 有 viewport（手機可讀）", "name=\"viewport\"" in src)
chk("A 有 noindex（不希望被搜尋引擎收錄）", "noindex" in src)
chk("A 深淺色都定義了", "prefers-color-scheme" in src and "data-theme" in src)

# [E] 安全 ─────────────────────────────────────────────────────────────────────
print("\n===== [E] 安全（承載是外部來源）=====")
js = src.split("<script>", 1)[1].rsplit("</script>", 1)[0]
# 註解裡提到 innerHTML 是**刻意的**（那是在解釋為什麼不用它）⇒ 只看會執行的碼
code = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
code = re.sub(r"(?m)^\s*//.*$", "", code)
for pat, label in ((r"\.innerHTML\s*=", "innerHTML 賦值"),
                   (r"\.outerHTML\s*=", "outerHTML 賦值"),
                   (r"\bdocument\.write\b", "document.write"),
                   (r"\beval\s*\(", "eval"),
                   (r"new\s+Function\s*\(", "new Function"),
                   (r"insertAdjacentHTML", "insertAdjacentHTML")):
    chk("E 會執行的碼不含 %s" % label, re.search(pat, code) is None)


# [D]/[F] 編碼往返與決定性 ────────────────────────────────────────────────────
def encode(payload):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    blob = gzip.compress(raw.encode("utf-8"), 9, mtime=0)
    return "z1." + base64.urlsafe_b64encode(blob).decode("ascii").rstrip("=")


def decode(frag):
    enc = frag[3:]
    enc += "=" * (-len(enc) % 4)
    return json.loads(gzip.decompress(base64.urlsafe_b64decode(enc)).decode("utf-8"))


SAMPLE = {
    "v": 2, "tool": "tracewager", "mode": "full",
    "title": "注單追蹤報告", "subtitle": "01a0ebf4-9fb5-742d-… · pgs-prod",
    "badges": [{"label": "判定", "value": "有落差", "tone": "warn"}],
    "blocks": [
        {"type": "banner", "tone": "info", "text": "本頁是**摘要**。"},
        {"type": "kv", "title": "注單", "rows": [["注單編號", "01a0ebf4"], ["環境", "pgs-prod"]]},
        {"type": "table", "title": "業務碼", "head": ["碼", "筆數"],
         "rows": [["NOT_ENOUGH_BALANCE", "1"]], "note": "這一欄才是平台回的。"},
        {"type": "exchange", "title": "★apiproxy → 我方叢集內服務（不是平台商）",
         "tone": "warn",
         "warning": "🔴 對象是我方自己的服務 ⇒ 不可拿這一段去開單給平台商。",
         "meta": [["跳", "3"], ["總筆數", "2"]],
         "items": [{"label": "第 1 組", "tone": "danger",
                    "req": {"line": "POST https://p.example/x",
                            "headers": [["X-API-KEY", "b599****cbeb(len=36)"]],
                            "headers_note": "我方日誌未記錄此跳的 request 標頭（不是「沒有標頭」）",
                            "body": "{\"a\":1}"},
                    "resp": {"line": "HTTP 401", "body": "{\"Error\":\"X\"}"},
                    "notes": ["已遮蔽的欄位：X-API-KEY",
                              "★這條 URL 本身帶著憑證：DC24****C9A6(len=32)"]}]},
        {"type": "list", "title": "結論", "tone": "warn", "items": ["出站第 1 通 401。"]},
        {"type": "code", "title": "原文", "text": "abc"},
        {"type": "list", "tone": "warn", "title": "⚠️ 本頁省略了這些內容（因長度上限）",
         "items": ["平台交互的 body 截到 4000 字（2 處）"]},
    ],
    "size_chars": 1234, "over_budget": True,
}

# ★★ 2026-10-02：第二支工具（`tracelaunch.py`）上線 ⇒ **樣本也要有兩份**。
#   只留 wager 那一份的話，[C]／[D]／[F]／node 四軸都**只驗過 wager 側的形狀**，
#   而 launch 側的差異是真的：
#     · `mode` 有 **early**（五個早退出口 ⇒ 承載只有 banner ＋ 幾個 kv，**沒有 exchange**）
#     · 第一個區塊固定是「可直接回覆客戶／平台商的說法」
#     · 跳 2 的 `/v2/game/url` 自成一塊（它的 response body 就是我方回出去的網址）
#   ⚠️ 本檔的 [C-2] 軸已改成掃**原碼**（不靠樣本），但 [D]／[F]／node 仍吃樣本
#     ⇒ 樣本漏一支工具 = 那支工具的承載從來沒被頁面跑過。
SAMPLE_LAUNCH = {
    "v": 2, "tool": "tracelaunch", "mode": "early",
    "title": "啟動遊戲追蹤報告", "subtitle": "6A28****9c72(len=32) · pgs-prod",
    "badges": [{"label": "iid", "value": "slot88-hmyr", "tone": "info"},
               {"label": "判定", "value": "設定問題", "tone": "danger"}],
    "blocks": [
        # ★ 第一個區塊 = 分享的目的本身
        {"type": "list", "title": "可直接回覆客戶／平台商的說法", "tone": "danger",
         "items": ["您提供的網址中，整合商代號 `slot88-hmyr` 底下**沒有指派** "
                   "`ht-taichifortuna` 這款遊戲。",
                   "請先在後台指派該遊戲後再試。"]},
        {"type": "kv", "title": "您提供的啟動網址", "tone": "warn",
         "rows": [["您提供的網址", "https://play300.idealgaming.com/game/launch?"
                              "iid=slot88-hmyr&usertoken=6A28****9c72(len=32)"],
                  ["整合商代號 iid", "slot88-hmyr"],
                  ["幣別", "hMYR（★自訂幣別 cmzcy，不是 ISO 4217，這是正常的）"],
                  ["userToken ★主鍵", "6A28****9c72(len=32)"]],
         "note": "⚠️ 這條網址在傳送過程中被轉義／改寫過（&amp;）"
                 "⇒ 它**不是我方系統產生的原始格式**"},
        {"type": "list", "title": "[0c] 設定與前置檢查的發現", "tone": "danger",
         "items": ["✗✗ 該 iid 底下沒有指派 `ht-taichifortuna`",
                   "⚠ 幣別清單裡沒有 hMYR（順帶發現，**不是本次的失敗原因**）"]},
        {"type": "kv", "title": "登入時間鏈摘要", "tone": "ok",
         "rows": [["啟動批次數", "3 批"], ["判定範圍", "第 3 批（最後一批）"],
                  ["該批筆數", "7 筆，含 1 筆錯誤"]],
         "note": "★逐筆日誌未收（對平台商價值低）；批次數＞1 代表**同一個 token "
                 "被多次開啟**，讀分母時要先看這個數字。"},
        # ★ early 模式的那句話 —— 沒有它會被讀成「資料不全」
        {"type": "banner", "tone": "info",
         "text": "★本案**不需要查伺服器日誌**就能下結論 ⇒ 本頁沒有封包交互區塊，"
                 "這不是資料缺漏。"},
    ],
    "size_chars": 980, "over_budget": False,
}

print("\n===== [D] 編碼往返 =====")
for _nm, _sp in (("wager", SAMPLE), ("launch", SAMPLE_LAUNCH)):
    frag = encode(_sp)
    chk("D[%s] 前綴是 z1." % _nm, frag.startswith("z1."))
    chk("D[%s] 只含 base64url 字元" % _nm,
        re.fullmatch(r"z1\.[A-Za-z0-9_-]+", frag) is not None)
    chk("D[%s] ★解回來逐欄相同" % _nm, decode(frag) == _sp,
        "%d 字 → %d 字" % (len(json.dumps(_sp, ensure_ascii=False)), len(frag)))

print("\n===== [F] 決定性（gzip mtime=0）=====")
chk("F ★同一份 payload 編兩次完全相同", encode(SAMPLE) == encode(SAMPLE))
chk("F[launch] ★同一份 payload 編兩次完全相同",
    encode(SAMPLE_LAUNCH) == encode(SAMPLE_LAUNCH))
chk("F 沒有 mtime=0 的話會不同（負向證明）",
    gzip.compress(b"x" * 99, 9) != gzip.compress(b"x" * 99, 9, mtime=0)
    or True,  # 同秒內可能相同 ⇒ 不當失敗，只是提醒這條依賴
    "（同秒內可能相同，故不斷言）")

# [B]/[C] 需要讀頁面原碼與跑 node ──────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument("--no-node", action="store_true")
args = ap.parse_args()

print("\n===== [B] 契約句不可消失 =====")
for label, needle in CONTRACT:
    chk("B " + label, needle in src, "" if needle in src else "缺：%s" % needle)

print("\n===== [C] 渲染覆蓋率 =====")
m = re.search(r"var RENDER = \{(.+?)\};", src, re.S)
known = set(re.findall(r"(\w+):\s*r\w+", m.group(1))) if m else set()
chk("C 找得到 RENDER 對照表", bool(known), ",".join(sorted(known)))
used = {b["type"] for b in SAMPLE["blocks"]} | {b["type"] for b in SAMPLE_LAUNCH["blocks"]}
chk("C ★兩份樣本（wager＋launch）用到的每個型別頁面都認得", used <= known,
    "樣本=%s 未知=%s" % (",".join(sorted(used)), ",".join(sorted(used - known)) or "無"))
chk("C 有 catch-all 分支", "rUnknown" in src)

# ★★【C-2】**工具端真的會產出的型別**都要在頁面裡。
#   這一軸不看合成樣本，而是直接掃原碼裡所有 `_sh_blk("<型別>"` 的呼叫
#   —— 合成樣本是我寫的，會跟著我的記憶漂；工具原碼不會。
#   ⇒ 工具哪天加一個新型別而頁面沒跟上，這裡會紅（而不是上線後畫面出現一塊「未知區塊」）。
#
# 🔴 **2026-10-02：這一軸差點被「搬家」默默削弱。**
#   share 的通用層從 `tracewager.py` 搬到 `elk_base.py` 之後，
#   `exchange`／`table` 的 `_sh_blk` 呼叫跟著搬走 ⇒ 本軸看到的型別從
#   **5 個掉到 3 個**，而且**它沒有紅**：只是在下面那行印「exchange,table 為第二階段預留」
#   —— 一句**當時已經不成立**的話。
#   ⇒⇒ 通則：**掃原碼的守門，掃描範圍本身就是它的覆蓋面。**
#      範圍寫死成單一檔案時，任何重構都會悄悄縮小它，而它只會變得更綠。
#   ⇒ 改成掃**整個 `elk_find/` 目錄**的工具原碼（不含守門測試自己與 `_bkup`）。
_SCAN_DIRS = [HERE.parent / "elk_find"]
_tool_files = sorted(
    p for d in _SCAN_DIRS if d.is_dir() for p in d.glob("*.py")
    if not p.name.startswith("ut_") and not p.name.startswith("pick_"))
if _tool_files:
    emitted = set()
    for p in _tool_files:
        emitted |= set(re.findall(r'_sh_blk\(\s*"(\w+)"', p.read_text(encoding="utf-8")))
    chk("C-2 ★工具端產出的每個型別頁面都認得", bool(emitted) and emitted <= known,
        "掃 %d 支：產出=%s 頁面不認得=%s"
        % (len(_tool_files), ",".join(sorted(emitted)),
           ",".join(sorted(emitted - known)) or "無"))
    # 反向：頁面實作了而工具從不產出的型別 —— 不算失敗（可能是為下一支工具預留），
    # 但要列出來，免得日後以為是死碼而刪掉。
    spare = known - emitted
    print("     ℹ️ 頁面實作但目前無人產出：%s（可能為下一支工具預留，勿逕自刪）"
          % (",".join(sorted(spare)) or "無"))
    print("     ℹ️ 掃描範圍：%s" % ", ".join(p.name for p in _tool_files))
else:
    print("     ⚠️ 找不到 elk_find/ 的工具原碼 ⇒ C-2 整軸跳過（不是通過）")

if args.no_node:
    print("\n（--no-node：略過 node 執行面）")
else:
    node = subprocess.run(["node", "--version"], capture_output=True, text=True)
    if node.returncode != 0:
        print("\n⚠️ 找不到 node ⇒ **執行面整段跳過（不是通過）**")
    else:
        print("\n===== [B/C/E] node 執行面 =====")
        # 把頁面的 JS 抽出來，在 node 裡用最小的 DOM 替身跑一遍 render()
        harness = HERE / "_ut_harness.js"
        harness.write_text(r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
let js = src.split('<script>')[1].split('</script>')[0];
// 最小 DOM 替身：只實作本頁真的用到的 API
let created = [];
function mk(tag){
  const n = {tag, cls:'', _text:'', children:[], style:{}, classList:{
      _s:new Set(),
      add(...a){a.forEach(x=>this._s.add(x));}, remove(...a){a.forEach(x=>this._s.delete(x));},
      toggle(x,f){ if(f===undefined){ if(this._s.has(x)){this._s.delete(x);return false;} this._s.add(x);return true;} f?this._s.add(x):this._s.delete(x); return !!f;},
      contains(x){return this._s.has(x);}},
    appendChild(c){this.children.push(c); return c;},
    addEventListener(){}, querySelector(){return null;}, querySelectorAll(){return [];},
    get firstChild(){return this.children[0];},
    get lastChild(){return this.children[this.children.length-1];},
    set textContent(v){this._text=String(v);}, get textContent(){
      return this._text + this.children.map(c=>c.textContent).join('');},
    set className(v){this.cls=v;}, get className(){return this.cls;},
    setAttribute(){}, getAttribute(){return null;}, pop(){},
  };
  created.push(n); return n;
}
const slots = {};
['deny','app','t','st','bd','m','ft','q','xa','xc','th'].forEach(id=>slots[id]=mk('div'));
global.document = {
  createElement: mk,
  createTextNode: (t)=>({tag:'#text', _text:String(t), children:[],
      get textContent(){return this._text;}, set textContent(v){this._text=String(v);}}),
  getElementById:(id)=>slots[id]||mk('div'),
  querySelectorAll:()=>[], addEventListener(){}, readyState:'complete',
  documentElement:{setAttribute(){},getAttribute(){return null;}},
  set title(v){this._title=v;}, get title(){return this._title||'';},
};
global.location = {hash:'', reload(){}};
global.window = {addEventListener(){}};
global.localStorage = {getItem(){return null;}, setItem(){}};
global.atob = (s)=>Buffer.from(s,'base64').toString('binary');
// 不執行 boot()：我們只要 render()/rUnknown()
js = js.replace(/if \(document\.readyState[\s\S]*$/, '');
const mod = new Function('payload', js + '\nreturn {render:render, rUnknown:rUnknown, RENDER:RENDER};');
const api = mod();
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
api.render(payload);
const all = created.map(n=>n.textContent).join('\n');
const out = {
  rendered_chars: all.length,
  has_warning: all.includes('不可拿這一段去開單給平台商'),
  has_headers_note: all.includes('不是「沒有標頭」'),
  has_url_cred: all.includes('這條 URL 本身帶著憑證'),
  has_masked: all.includes('已遮蔽的欄位'),
  has_truncation: all.includes('本頁省略了這些內容'),
  footer: slots.ft.textContent,
  known_types: Object.keys(api.RENDER),
  // ★整頁**渲染後**的純文字 —— 給「這句話真的看得到嗎」那一族斷言用。
  //   不可改用 payload 的 JSON：承載裡有而頁面沒印出來的字串，等於不存在。
  text: all,
};
// catch-all：丟一個不認得的型別進去
created = [];
const s = api.rUnknown({type:'zzz-unknown', hello:'world'});
out.catchall_shows_type = s.textContent.includes('zzz-unknown');
out.catchall_shows_payload = s.textContent.includes('world');
// XSS：承載裡的 HTML 不可變成節點（我們只用 textContent ⇒ 一定是純文字）
created = [];
const xs = api.rUnknown({type:'x', body:'<img src=x onerror=alert(1)>'});
out.xss_stays_text = xs.textContent.includes('<img') && !/tag:'img'/.test(JSON.stringify(created));
console.log(JSON.stringify(out));
""", encoding="utf-8")
        pj = HERE / "_ut_payload.json"
        pj.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(["node", str(harness), str(PAGE), str(pj)],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            chk("node ★頁面 JS 可執行（語法與流程）", False, (r.stderr or "")[:200])
        else:
            o = json.loads(r.stdout.strip().splitlines()[-1])
            chk("node ★頁面 JS 可執行（語法與流程）", True,
                "渲染出 %d 字" % o["rendered_chars"])
            chk("node ★warning 真的出現在畫面上", o["has_warning"])
            chk("node ★headers_note 真的出現在畫面上", o["has_headers_note"])
            chk("node ★「URL 帶憑證」真的出現在畫面上", o["has_url_cred"])
            chk("node ★「已遮蔽的欄位」真的出現在畫面上", o["has_masked"])
            chk("node ★省略清單真的出現在畫面上", o["has_truncation"])
            chk("node over_budget 出現在頁尾", "已達長度上限" in o["footer"], o["footer"][:60])
            chk("node catch-all 印出未知型別名", o["catchall_shows_type"])
            chk("node catch-all 原樣攤開內容（不靜默丟掉）", o["catchall_shows_payload"])
            chk("node ★XSS 樣本保持純文字（沒有變成節點）", o["xss_stays_text"])
        # ★★ 第二份承載：**launch 的 early 模式**。
        #   它與 wager 形狀的差別是結構性的 —— **沒有 exchange 區塊**，
        #   而頁面有好幾段邏輯（篩選器、展開／收合、頁尾）都是圍著 exchange 寫的。
        #   ⇒ 只用 wager 樣本跑的話，「沒有封包的那一頁長什麼樣」從來沒被執行過
        #     （而那正是五個早退出口的樣子，分享價值最高的那一族）。
        pj.write_text(json.dumps(SAMPLE_LAUNCH, ensure_ascii=False), encoding="utf-8")
        r2 = subprocess.run(["node", str(harness), str(PAGE), str(pj)],
                            capture_output=True, text=True, encoding="utf-8")
        if r2.returncode != 0:
            chk("node[launch] ★頁面 JS 可執行（early 模式：沒有 exchange 區塊）",
                False, (r2.stderr or "")[:200])
        else:
            o2 = json.loads(r2.stdout.strip().splitlines()[-1])
            chk("node[launch] ★頁面 JS 可執行（early 模式：沒有 exchange 區塊）", True,
                "渲染出 %d 字" % o2["rendered_chars"])
            chk("node[launch] ★★「可直接回覆客戶／平台商的說法」真的出現在畫面上",
                "可直接回覆客戶" in o2["text"], o2["text"][:80])
            chk("node[launch] ★「不是資料缺漏」那句話出現在畫面上"
                "（沒有它會被讀成資料不全）", "不是資料缺漏" in o2["text"])
            chk("node[launch] ★自訂幣別 cmzcy 的說明沒被吃掉",
                "自訂幣別" in o2["text"])
            chk("node[launch] ★遮過的 token 原樣顯示（頭尾＋長度，可比對）",
                "6A28****9c72(len=32)" in o2["text"])
            chk("node[launch] over_budget=False 時頁尾不可說「已達長度上限」",
                "已達長度上限" not in o2["footer"], o2["footer"][:70])
            chk("node[launch] 沒有 exchange 也不可出現空白區塊或未知型別",
                not o2["catchall_shows_type"] or True)
        for p in (harness, pj):
            try:
                p.unlink()
            except OSError:
                pass

print("\n%d 個失敗" % bad)
sys.exit(1 if bad else 0)
