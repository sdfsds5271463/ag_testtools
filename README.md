# `_test/github_pages/` —— AgGithubPages：AG 工具的分享型顯示層

把 AG 工具產生的結論，變成一條**可以直接丟給平台商客人**的網址。

```
線上   https://sdfsds5271463.github.io/ag_testtools/
本機   http://127.0.0.1:9527/AgGithubPages/      （開發用鏡像）
```

> **本目錄是顯示層，不是知識本體。** 注單怎麼判、每個欄位在講什麼
> → 看 [`../elk_find/README.md`](../elk_find/README.md)（工具本體的權威說明）。
> 這裡只講「網址怎麼產、頁面怎麼運作、改之前要知道什麼」。

---

## 這個專案最特別的三件事

1. **它不從本機執行**，而是從 GitHub Pages 執行（純靜態、零後端）。
2. **它有自己的 git**，不走最外層 `C:\allen\ag` 的版控 ——
   remote 是 `git@github.com:sdfsds5271463/ag_testtools.git`。
3. **它被授權可以主動 commit + push**（`初始說明.txt` §專案底層 3）——
   因為只有推上去才測得到真實的 GitHub Pages 行為。實測 push 後 **40~50 秒**生效。

---

## 怎麼用（目前只支援 `tracewager`）

```bash
cd ../elk_find
python tracewager.py <wagerId> <env> --share-url remote      # ⭐ 產一條線上網址
python tracewager.py <wagerId> <env> --share-url local       # 產本機鏡像網址（開發用）
python tracewager.py <wagerId> <env> --share-url remote 2>/dev/null | tail -1   # 只取網址
python tracewager.py <wagerId> <env> --share-json            # 只要承載 JSON，不要網址
```

| 參數 | 作用 |
|---|---|
| `--share-url remote\|local` | 輸出網址（隱含 `--share-json`） |
| `--share-secrets` | 憑證改**原文**（預設遮成 `頭4****尾4(len=N)`） |
| `--share-budget N` | 承載字元上限（預設 16000）。調小 ⇒ 網址變短，省略項會列在頁尾 |
| `--share-packets N` | 「我方 ↔ 平台商」最多收幾組交互（預設 4，**失敗的優先**） |

> 🔴 **既有輸出零影響**：沒帶 `--share-*` 時 `tracewager.py` 一個字都不變
> （實測帶與不帶 `--share-json`，文字段 24,394 bytes 逐位元組相同）。

---

## 承載怎麼走：hash fragment

```
https://sdfsds5271463.github.io/ag_testtools/#z1.<base64url(gzip(json))>
```

走 **`#` 而不是 `?`**，四個理由（前兩個是硬需求）：

1. 🔴 **fragment 不會送到伺服器** —— 本工具的輸出**必然含憑證**
   （`tracewager.py` 檔頭：2026-08-14 Allen 指示一律原文）。用 `?` 會把正式環境的
   api-key／token 送進 GitHub 的存取日誌與 CDN；用 `#` 則完全不會，
   瀏覽器也會把它從 `Referer` 剝掉。
2. 不吃伺服器的 URL 長度限制（Apache/nginx 的 request line 約 8 KB）。
3. base64url 字母表只有 `A-Za-z0-9_-`，**沒有 `&`**
   ⇒ 繞開「工單系統把 `&` 轉成 `&amp;`」那一族陷阱（`tracelaunch` 花了大量程式碼在偵測它）。
4. GitHub Pages 是純靜態，本來就沒有 server-side routing。

`z1.` 是**編碼版本**（不是內容版本）⇒ 頁面能秒判「這不是我認得的格式 → 403」。

> ⚠️ **`#` 擋掉的是「伺服器看得到」，不是「別人看得到」。**
> 拿到連結的人都看得到內容 —— 轉傳前請自己判斷收件對象。

---

## 頁面刻意「笨」

**頁面不含任何 AG 業務詞彙**（Allen 2026-10-01 裁決 3）。它只認 6 種通用區塊型別：

| 型別 | 用途 |
|---|---|
| `banner` | 有顏色的提示框 |
| `kv` | 鍵值對清單 |
| `table` | 表格 |
| `list` | 條列 |
| `exchange` | request/response 卡片（本頁最核心的型別） |
| `code` | 原文區塊 |

所有標題、標籤、說明文字**都來自網址裡的承載**。三個好處：

- 公開 repo 零業務資訊
- 工具新增欄位時**頁面一行都不用改**
- 多支 AG 工具共用同一個渲染器

★ **不認得的區塊型別一律 catch-all 原樣攤開**，絕不靜默丟掉 ——
`mission_PG` 與 AgWager 都踩過「沒人顯示的欄位等於不存在，而且不會報錯」。

---

## 🔴 改這支之前必看的三條

**1. 一律 `textContent` 建 DOM，永不 `innerHTML`。**
承載裡有**平台商回應的原文** —— 那是外部來源的字串。用 `innerHTML` 等於把第三方回應
當 HTML 執行（XSS）。連 `**粗體**` 都是用 DOM 切出 `<strong>`。
`ut_pages.py` 的 [E] 軸會掃「會執行的碼」裡有沒有 `innerHTML`／`eval`／`document.write`。

**2. 參數缺漏／壞掉／解不開，一律 `403 Forbidden`，不給提示**（`初始說明.txt` §3）。
⚠️ 代價很具體：**最常見的真實故障是「網址被聊天工具截斷」，而它跟「沒帶參數」在畫面上一模一樣。**
⇒ 所以診斷刻意放在**產生端** —— `tracewager.py` 產網址時會在 stderr 印
「對方若看到 403，九成是網址被截斷」。頁面只寫 `console.warn`，不上畫面。

**3. 單檔、零外部資源。** JS 與 CSS 全部 inline ——
這樣就沒有「GitHub CDN 把舊 JS 快取住」的問題（`初始說明.txt` §4），
也不需要版本號或動態檔名。GitHub Pages 對 HTML 是 `max-age=600`，10 分鐘可接受。

---

## 本機鏡像

`C:\xampp\htdocs\allenweb\AgGithubPages\index.php` 用 **`readfile()`** 原樣輸出本目錄的
`index.html`，**不經 PHP 解析**。

> 🔴 **為什麼不是 `include`**：`include` 會讓 PHP 解析內容，任何 `<?` 序列
> （JS 的字串、正則、註解都可能出現）會被當成 PHP 開始標籤**吃掉**。
> 而 GitHub Pages 是純靜態、原樣吐出 ⇒ 同一份檔案在本機與遠端會**吐出不同的位元組**，
> 於是 bug 只在遠端出現、本機永遠測不到。
> ✅ 已實測：遠端下載的位元組與本地 `index.html` **逐位元組相同**。

不需要新 port（9527 是既有的 XAMPP Apache，同一支已掛 AgWager／mission_PG／AgGrafana）。

---

## 回歸測試

```bash
python ut_pages.py              # 六軸（秒級，不連任何外部服務）
python ut_pages.py --no-node    # 略過需要 node 的執行面
```

| 軸 | 守什麼 |
|---|---|
| **A** | 靜態不變量：單檔／零外部資源／**不含 `<a>`**／只有一個 `<script>`／深淺色都定義 |
| **B** | ★**契約句不可從頁面消失** —— `warning`／`headers_note`／`notes`／`over_budget`／catch-all／403。刪掉任何一句，畫面會變好看，而讀者會開始下錯結論 |
| **C** | 渲染覆蓋率：承載用到的每個型別頁面都要認得 ＋ catch-all 真的會攤開 |
| **D** | 編碼往返：payload → gzip → base64url → 解回來逐欄相同 |
| **E** | ★安全：會執行的碼不含 `innerHTML`／`eval`／`document.write`；XSS 樣本渲染後仍是純文字 |
| **F** | 決定性：同一份 payload 編兩次**完全相同**（`gzip(mtime=0)`） |

★ **[B/C/E] 另有 node 執行面**：真的跑一次頁面的 `render()`，確認那幾句話**真的出現在畫面上**
（不是只檢查原碼裡有這個字串）。⚠️ 沒有 node 時整段跳過並明講 —— **不要把 SKIP 當通過**。

已掛進 `../run_regression.sh` 第 1 段。

---

## 相關文件

- 設計決策、schema v2、實測數字、第二階段待辦 → [`github_pages撰寫計畫.txt`](github_pages撰寫計畫.txt)
- 專案前提與授權（Allen 寫的，權威）→ [`初始說明.txt`](初始說明.txt)
- 承載怎麼產、四個會讓平台商被冤枉的陷阱 → [`../elk_find/README.md`](../elk_find/README.md) §一-9
- 設計演進與踩雷 → `../elk_find/wager追蹤腳本撰寫計畫.txt` 陷阱 **180**
