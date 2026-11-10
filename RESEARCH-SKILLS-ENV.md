# 科研技能环境说明（DSH）

本文件记录在 DSH 里安装科研技能后，为让它们真正跑起来所做的本机改动。改动只涉及
本机环境与技能目录，未修改任何技能的检索逻辑。

## 已安装技能

位于 `C:\Users\Administrator\.dsh\skills\`：

| 技能 | 用途 | 依赖 |
|---|---|---|
| `pubmed-paper-finder` | PubMed 主题多模块检索 + 排序候选清单 | 纯标准库 |
| `paper-lookup` | 11 个文献库检索、全文、引文 | 纯标准库 |
| `nature-academic-search` | 多源检索、引文核对、MeSH、他引审计 | MCP server（已接）+ 独立脚本 |
| `literature-review` | 系统综述工作流、引文格式、文档产出 | 需把检索 JSON 转成数组后处理 |
| `citation-management` | BibTeX 生成与校验 | 标准库 + requests |
| `search-lit` | 文献检索 + API 验证 BibTeX 生成 | 已补 Windows 版 E-utilities 工具 |
| `design-study` | 研究设计审查（分析单位、泄漏、对照、验证） | 纯标准库 |
| `find-cohort-gap` | 从队列数据库里找可做的课题方向 | 纯标准库 |
| `write-protocol` | 伦理/IRB 研究方案撰写 | 纯标准库 |
| `find-journal` | 投稿期刊匹配与拒稿回退 | 纯标准库 |

## 本机改动

1. **`python3` 可用**
   - 现象：`python3` 原来指向 Windows 商店占位符，执行返回 9009。
   - 处理：在 `C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe` 旁复制出 `python3.exe`。
   - 结论：`python` 与 `python3` 都可用，技能文档里的命令可直接照抄。

2. **`search-lit` 的 E-utilities 工具换成 Python 版**
   - 新增 `references/pubmed_eutils.py`（命令、输出与 `pubmed_eutils.sh` 完全一致）。
   - 原因：本机没有 bash，`.sh` 无法执行。
   - 已验证：`search | parse_pubmed.py esearch`、`fetch | parse_pubmed.py bibtex` 均可用。

3. **`nature-academic-search` 的 MCP server 已接入 DSH**
   - 依赖：`mcp==1.30.0`（v1，server 用的是 FastMCP；mcp 2.x 已改名为 MCPServer）、
     `pybliometrics`、`lxml`、`requests`、`toml`。
   - 配置：`~\.dsh\profiles\desktop\cordis.patch.yml` 中新增 `mcp-academic-search` 条目，
     备份在同目录 `cordis.patch.yml.bak-before-mcp`。
   - 工具名形如 `mcp__academic-search__search_papers`，共 16 个工具。
   - 需要重启 DSH 才会加载。

4. **pandoc**
   - `C:\Users\Administrator\AppData\Local\Pandoc\pandoc.exe`（3.13，10 月 26 日已装）。
   - 另外放了副本到 `C:\Users\Administrator\.local\bin\pandoc.exe`，并把该目录加入用户 PATH，
     因为旧进程的 PATH 不含 `Local\Pandoc`。
   - **本机没有任何 LaTeX 引擎**（xelatex / pdflatex / tectonic 都没有），所以
     `literature-review` 的 `generate_pdf.py` 会报 `'xelatex' not found`。
   - 可用的替代：`pandoc x.md -o x.docx`、`pandoc x.md -o x.html --standalone`，均已验证。
   - 若确实要 PDF，二选一：装 `tectonic`（体积小，单文件），或装 MiKTeX / TeX Live。

## 网络注意事项（本机实测）

- `pip install` 直接连 PyPI **会挂起**（索引请求被重置），但
  `https://pypi.tuna.tsinghua.edu.cn/simple/` 的包文件可直连。
  需要装 Python 包时，先取镜像上的 wheel 再用 `pip install --no-index --find-links <目录>`。
- GitHub release 直连下载会超时，`https://scoop.201704.xyz/` 与
  `https://gh-proxy.com/` 两个前缀可用（前者更快）。
- 控制台代码页是 GBK：Python 报错信息里出现非 ASCII 字符会变成
  `UnicodeEncodeError`，命令行尽量设置 `PYTHONIOENCODING=utf-8`。

## 常用命令

```powershell
# PubMed 检索 + 排序候选清单（在目标目录下执行）
python C:\Users\Administrator\.dsh\skills\pubmed-paper-finder\scripts\pubmed_paper_finder.py "your english topic"
python C:\Users\Administrator\.dsh\skills\pubmed-paper-finder\scripts\pubmed_paper_finder.py "your topic" --max-per-query 5 --show 10

# BibTeX 生成（PubMed）
python C:\Users\Administrator\.dsh\skills\citation-management\scripts\search_pubmed.py --query "topic" --limit 20 --format bibtex -o refs.bib

# BibTeX 校验
python C:\Users\Administrator\.dsh\skills\citation-management\scripts\validate_citations.py refs.bib

# search-lit：检索 -> PMID -> BibTeX
$S = "C:\Users\Administrator\.dsh\skills\search-lit\references"
python "$S\pubmed_eutils.py" search "topic query" 20 | python "$S\parse_pubmed.py" esearch
python "$S\pubmed_eutils.py" fetch "12345678,23456789" | python "$S\parse_pubmed.py" bibtex

# 研究设计：DAG 调整集
python C:\Users\Administrator\.dsh\skills\design-study\scripts\adjustment_set_helper.py --dag dag.json --exposure X --outcome Y

# 队列找课题
python C:\Users\Administrator\.dsh\skills\find-cohort-gap\scripts\build_cohort_profile.py --codebook codebook.csv --context "your domain"

# Markdown -> Word / HTML
pandoc review.md -o review.docx
pandoc review.md -o review.html --standalone
```

## 已知限制

- `literature-review` 的 `search_databases.py` 只接受 **结果数组**，不接受
  `{"results": [...]}` 包装；先用
  `json.dump(d["results"], open("arr.json","w"))` 转换。
- `literature-review` 的 PDF 依赖 LaTeX，本机没有（见上）。
- `nature-academic-search` 的 `OPENALEX_API_KEY` 为空时 OpenAlex 会 429；
  在 `mcp-server/config.toml` 填 `[pubmed] email` 与 OpenAlex key 可缓解。
- 技能目录里的 `python3` 字样仍保留在 `paper-lookup` 等文档中；本机 `python3` 已可用，
  所以不影响执行。
