# 科研技能环境搭建记事（Windows / DeepSeek Harness）

在一台网络受限的 Windows 机器上，把一批文献检索与课题设计技能装进 DSH 并跑通的过程记录。
适用的技能来源：本地 `.codex\skills` 里的 5 个 + 上游 `Aperivue/medsci-skills` v6.3.0 的 5 个。

装了哪些技能、为什么这么装，以及踩到的坑，都在下面。命令里的 `<SKILLS>` 指你的技能根目录，
例如 `%USERPROFILE%\.dsh\skills`。

---

## 一、装了哪些

| 技能 | 用途 | 依赖 |
|---|---|---|
| `pubmed-paper-finder` | PubMed 主题多模块检索 + 排序候选清单 | 纯标准库 |
| `paper-lookup` | 11 个文献库检索、全文、引文图 | 纯标准库 |
| `nature-academic-search` | 多源检索、引文核对、MeSH、他引审计 | MCP server + 独立脚本 |
| `literature-review` | 系统综述工作流、引文格式、文档产出 | 需转换检索 JSON 形状 |
| `citation-management` | BibTeX 生成与校验 | 标准库 + requests |
| `search-lit` | 检索 + API 验证后生成 BibTeX | 需补 Windows 版 E-utilities |
| `design-study` | 研究设计审查（分析单位、泄漏、对照、验证） | 纯标准库 |
| `find-cohort-gap` | 从队列数据库找可做的课题 | 纯标准库 |
| `write-protocol` | 伦理/IRB 方案撰写 | 纯标准库 |
| `find-journal` | 投稿期刊匹配与拒稿回退 | 纯标准库 |

前 6 个来自本地 `.codex\skills`，后 4 个来自 `medsci-skills` v6.3.0 的 `skills/` 目录。

---

## 二、四个必须处理的坑

### 1. `python3` 是商店占位符

Windows 上 `python3` 常指向 `WindowsApps\python3.exe`，执行直接返回 9009。
技能文档里大量写着 `python3 xxx.py`，照抄必失败。

修法（不需要管理员权限）：

```powershell
$py = "$env:LOCALAPPDATA\Programs\Python\Python313"
Copy-Item "$py\python.exe" "$py\python3.exe"
```

或者把用户 PATH 里的 `WindowsApps` 排到 Python 目录之后。

### 2. `search-lit` 的 E-utilities 工具是 bash 脚本

上游给的 `references/pubmed_eutils.sh` 在无 bash 的 Windows 上跑不了。
写了等价的 `pubmed_eutils.py`：命令一致（`search` / `fetch` / `fetch_json` / `related` / `cite_lookup`），
输出与 `parse_pubmed.py` 的 `esearch` / `esummary` / `efetch` / `bibtex` 模式对接。

注意 `parse_pubmed.py` 不认 `--help`，只认模式名：

```powershell
$S = "<SKILLS>\search-lit\references"
python "$S\pubmed_eutils.py" search "topic query" 20 | python "$S\parse_pubmed.py" esearch
python "$S\pubmed_eutils.py" fetch "12345678,23456789" | python "$S\parse_pubmed.py" bibtex
```

### 3. MCP 版本陷阱：`mcp` 2.x 不兼容 FastMCP 代码

`nature-academic-search` 的 server 用 `from mcp.server import FastMCP`。
`mcp` 2.x 已把它改名为 `MCPServer`（`mcp.server.mcpserver`），装上 2.x 后报：

```
ModuleNotFoundError: No module named 'mcp.server.fastmcp'. This is mcp 2.x, where FastMCP was renamed to MCPServer
```

必须固定 **`mcp<2`**（实测 `1.30.0` 可用）。另外 `pybliometrics` 是硬依赖——
`sources/scopus.py` 在导入期就 require 它，缺了整个 server 起不来。

DSH 侧配置（`~/.dsh/profiles/<profile>/cordis.patch.yml`）：

```yaml
- id: mcp-academic-search
  name: "@deepseek-ai/dsh-mcp-client"
  config:
    serverName: academic-search
    transport: stdio
    command: <python.exe 绝对路径>
    args:
      - <SKILLS>\nature-academic-search\mcp-server\academic_search_server.py
    cwd: <SKILLS>\nature-academic-search\mcp-server
    env:
      PYTHONIOENCODING: utf-8
    toolCallTimeoutMs: 120000
```

改完要**重启 DSH**；工具名形如 `mcp__academic-search__search_papers`，共 16 个。

### 4. 网络：pip 索引挂起、GitHub 下载超时

本机实测：

- `pip install <pkg>` **会静默挂起**（索引请求被重置），但包文件本身能下。
  可用路径：从镜像取 wheel → `pip install --no-index --find-links <目录>`。
- GitHub release 直连超时。可用的加速前缀：`https://scoop.201704.xyz/`（较快）、
  `https://gh-proxy.com/`。用法是前缀 + 完整的 `https://github.com/...` 地址。
- 控制台代码页是 GBK：Python 报错信息里有非 ASCII 字符就会变成 `UnicodeEncodeError`，
  命令行建议设 `PYTHONIOENCODING=utf-8`。

---

## 三、两处技能文档与实际行为的差异

### `literature-review` 只吃纯数组

`search_databases.py` 接受的是**结果数组**，不接受 `{"results": [...]}` 包装，
否则 `generate_summary` 会对字符串调 `.get()` 而崩：

```python
import json
d = json.load(open("raw.json", encoding="utf-8"))
json.dump(d["results"], open("arr.json", "w", encoding="utf-8"), ensure_ascii=False)
```

然后：

```powershell
python <SKILLS>\literature-review\scripts\search_databases.py arr.json --format markdown --output out.md
```

另外它是手写 argv 解析，没有 `--help`；参数是 `--format` / `--output` / `--rank` /
`--year-start` / `--year-end` / `--deduplicate` / `--summary`。

### PDF 导出需要 LaTeX

`generate_pdf.py` 默认调 `xelatex`。装了 pandoc 但没有 LaTeX 引擎时会报
`'xelatex' not found`。两个办法：

- 装 `tectonic`（单文件、体积小）或 MiKTeX / TeX Live；
- 或者不走 PDF：`pandoc x.md -o x.docx`、`pandoc x.md -o x.html --standalone` 都可直接用。

---

## 四、常用命令

```powershell
# PubMed 检索 + 排序候选清单（在目标目录下执行，会写出 pubmed_results.md）
python <SKILLS>\pubmed-paper-finder\scripts\pubmed_paper_finder.py "your english topic"
python <SKILLS>\pubmed-paper-finder\scripts\pubmed_paper_finder.py "topic" --max-per-query 5 --show 10

# BibTeX 生成与校验
python <SKILLS>\citation-management\scripts\search_pubmed.py --query "topic" --limit 20 --format bibtex -o refs.bib
python <SKILLS>\citation-management\scripts\validate_citations.py refs.bib

# search-lit：检索 -> PMID -> BibTeX
$S = "<SKILLS>\search-lit\references"
python "$S\pubmed_eutils.py" search "topic query" 20 | python "$S\parse_pubmed.py" esearch

# 研究设计：DAG 调整集筛查（JSON 不能带 BOM）
python <SKILLS>\design-study\scripts\adjustment_set_helper.py --dag dag.json --exposure X --outcome Y

# 队列找课题
python <SKILLS>\find-cohort-gap\scripts\build_cohort_profile.py --codebook codebook.csv --context "domain"

# Markdown -> Word / HTML
pandoc review.md -o review.docx
pandoc review.md -o review.html --standalone
```

`adjustment_set_helper.py` 读 JSON 时不吃 BOM：用 PowerShell `Set-Content -Encoding utf8`
写出来的文件（带 BOM）会报 `Unexpected UTF-8 BOM`，改用 Python 写或 `-Encoding utf8NoBOM`。

---

## 五、验证清单

装完至少跑这几条，确认不是"装上了但跑不动"：

| 检查 | 期望 |
|---|---|
| `python3 --version` | 打印版本，不是退出码 9009 |
| `pubmed_paper_finder.py "some topic"` | 输出 `pubmed_results.md` |
| `search_pubmed.py --query "x" --limit 3 --format json -o r.json` | 写出文件 |
| `pubmed_eutils.py search "x" 5 \| parse_pubmed.py esearch` | 打印 PMID 列表 |
| `academic_search_server.py` 启动后 MCP `list_tools` | 16 个工具 |
| `academic_search.py "x" --limit 2 --compact` | 打印条目 |
| `pandoc --version` | 3.x |

---

## 六、已知限制

- `nature-academic-search` 未配 `OPENALEX_API_KEY` 时 OpenAlex 返回 429；
  在 `mcp-server/config.toml` 填 `[pubmed] email` 并申请免费 key 可缓解。
  `academic_search.py` 的 `--mailto` 参数对 OpenAlex 也有帮助。
- Semantic Scholar 免费额度很紧，匿名请求经常 429，属于上游限制，不是配置问题。
- `design-study` 等 medsci 技能提示词是英文、面向影像与临床 AI 场景，
  用在 MR / 队列研究上要自己挑适用的检查项（分析单位、泄漏、参照标准、验证策略这几条通用）。
