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

## 怎麼用（兩支工具，參數完全一致）

```bash
cd ../elk_find
# 注單
python tracewager.py  <wagerId> <env> --share-url remote      # ⭐ 產一條線上網址
# 啟動遊戲（2026-10-02 上線）
python tracelaunch.py '<launch-url>'  --share-url remote      # ★網址務必單引號包住
python tracelaunch.py --token <userToken> <env> --share-url remote

python tracewager.py <wagerId> <env> --share-url local        # 本機鏡像（開發用）
python tracewager.py <wagerId> <env> --share-url remote 2>/dev/null | tail -1   # 只取網址
python tracewager.py <wagerId> <env> --share-json             # 只要承載 JSON，不要網址
```

| 參數 | 作用 |
|---|---|
| `--share-url remote\|local` | 輸出網址（隱含 `--share-json`） |
| `--share-url-max N` | ⭐ **網址**字元上限（預設 4000；**`0`＝不限**） |
| `--share-budget N` | 承載字元上限（預設 16000）。網址模式下只是**起點** |
| `--share-secrets` | 憑證改**原文**（預設遮成 `頭4****尾4(len=N)`） |
| `--share-packets N` | 平台那一跳最多收幾組交互（預設 4，**失敗的優先**） |
| `--share-all-headers` | 連 CDN／helmet／Envoy 樣板標頭也顯示 |

⭐ **最划算的一個設定：`--share-url-max 0`。**
實測 launch 一案：**多 28% 的字元換到 3.4 倍的證據**
（裁到 4,608 字只省 22% 網址長度；不裁是 14,426 字、網址 5,916）。
⇒ 收件通道容得下 ~6,000 字（郵件／工單／程式碼區塊）時一律用 `0`；
預設的裁減是為了塞進 Slack／Teams 的單則訊息（4,000 上限）。

🔴 **不要用字元預算去推算網址長度 —— 數學上做不到。**
實測 `網址字元 ÷ 承載字元` 落在 **0.55 ~ 1.02 倍**（裁得越兇壓縮率越差：
被裁掉的正是最好壓的 ASCII 重複鍵名，留下的是最難壓的中文結論）。
⇒ `--share-url` 走**外層迴圈**：真的編一次、量網址、不夠短就把預算往下調重裁；
**壓不到就明說**，不為達標去砍「平台最後一組」那個底線。

> 🔴 **既有輸出零影響**：沒帶 `--share-*` 時兩支工具一個字都不變。
> `tracewager` 實測帶與不帶 `--share-json`，文字段 24,394 bytes 逐位元組相同；
> `tracelaunch` 更強 —— 它只有**一個** emit 呼叫點而且在 `finally` 裡
> （`_run_body()` 有 8 個出口，每個 return 各寫一次的話，以後加第 9 個就會漏），
> 由 `../elk_find/ut_launch.py` L11-g 用 AST 證明，含負向證明。

### 兩支工具的承載差在哪

| | `tracewager` | `tracelaunch` |
|---|---|---|
| 第一個區塊 | banner（摘要） | ⭐ **「可直接回覆客戶／平台商的說法」** |
| `mode` | `full`／降級路徑 | `full` ／ **`early`**（五個早退出口，**沒有封包區塊**） |
| 核心證據 | 跳 3 的完整 header+body | 同左 ＋ **跳 2 的 `/v2/game/url`**（它的 response body 就是我方回出去的網址，任何長度上限下都保留） |
| 主鍵 | wagerId（非機密） | ⚠️ **userToken（就是憑證本身）** ⇒ 遮蔽的要求嚴格得多 |
| 🆕 注單自己的過程 | ⭐ 「注單生命週期」kv ＋「交易明細」table（2026-10-07） | —（還沒有注單） |
| 🆕 對方主動打進來的查詢 | 獨立一塊「外部主動查詢（非金流）」 | 跳 2 本身就是（啟動網址） |

> 🆕 **2026-10-07（頁面零改動，全是既有型別）**：wager 側承載多了三種頁面以前沒跑過的形狀 ——
> ① 被裁過的 `table` 中間有一列 `…（中間省略 N 列）`（N 對原始筆數算）
> ② **零筆的 exchange ＋ warning**（轉帳錢包「本來就沒有平台封包」）
> ③ 標題**不帶**「內部跳：」的非金流 exchange（對方事後拿單號打進來查詢）。
> 起因是轉帳錢包單的分享頁只剩一格空白，而那張單自己的事件與交易一個字都沒有 ——
> **「哪一段最有價值」隨錢包模式改變**。細節與實測見 `../elk_find/README.md` §一-9、計畫書陷阱 183。

⚠️ `early` 模式**沒有封包區塊是正確的**（那一族本來就不必查日誌），
所以它會多一個 banner 明講「**這不是資料缺漏**」。少了那句就會被讀成資料不全。

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
| **C** | 渲染覆蓋率：**兩份樣本**（wager＋launch）用到的每個型別頁面都要認得 ＋ catch-all 真的會攤開 |
| **C-2** | ★**工具端真的會產出的型別**都要在頁面裡 —— 直接掃 `../elk_find/` **整個目錄**的原碼，不看合成樣本 |
| **D** | 編碼往返：payload → gzip → base64url → 解回來逐欄相同 |
| **E** | ★安全：會執行的碼不含 `innerHTML`／`eval`／`document.write`；XSS 樣本渲染後仍是純文字 |
| **F** | 決定性：同一份 payload 編兩次**完全相同**（`gzip(mtime=0)`） |

★ **[B/C/E] 另有 node 執行面**：真的跑一次頁面的 `render()`，確認那幾句話**真的出現在畫面上**
（不是只檢查原碼裡有這個字串）。⚠️ 沒有 node 時整段跳過並明講 —— **不要把 SKIP 當通過**。
★ **node 執行面跑三份承載**：wager 的 `full` ＋ launch 的 `early` ＋ 🆕 **轉帳錢包 wager**（2026-10-07）。
launch 那份**沒有 exchange 區塊**，而頁面有好幾段邏輯（篩選器、展開／收合、頁尾）都是圍著
exchange 寫的 ⇒ 只用 wager 樣本跑的話，「沒有封包的那一頁長什麼樣」從來沒被執行過。
轉帳那份守「交易明細的省略說明列沒被吃掉」「零筆 exchange 的 warning 照印」「外部查詢不帶『內部跳：』」。
🔴 **本 repo 是公開的** ⇒ 樣本一律用合成值（單號／交易編號用假的、IP 用 RFC 5737 文件段）。

> 🔴 **2026-10-02 的教訓：[C-2] 軸差點被一次重構默默削弱。**
> share 的通用層從 `tracewager.py` 搬到 `elk_base.py` 之後，
> `exchange`／`table` 的 `_sh_blk` 呼叫跟著搬走 ⇒ 本軸看到的型別從 **5 個掉到 3 個**，
> **而且它沒有紅** —— 只是印了一句當時已經不成立的「exchange／table 為第二階段預留」。
> ⇒⇒ **掃原碼的守門，掃描範圍本身就是它的覆蓋面。**
> 範圍寫死成單一檔案時，任何重構都會悄悄縮小它，而它只會變得更綠。

已掛進 `../run_regression.sh` 第 1 段。

---

## 相關文件

- 設計決策、schema v2、實測數字、第二階段待辦 → [`github_pages撰寫計畫.txt`](github_pages撰寫計畫.txt)
- 專案前提與授權（Allen 寫的，權威）→ [`初始說明.txt`](初始說明.txt)
- 承載怎麼產、四個會讓平台商被冤枉的陷阱 → [`../elk_find/README.md`](../elk_find/README.md) §一-9
- 設計演進與踩雷 → `../elk_find/wager追蹤腳本撰寫計畫.txt` 陷阱 **180**
