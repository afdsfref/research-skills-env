# 科研技能包（PubMed 检索 · 文献综述 · 课题设计）

一套在 **Windows + DeepSeek Harness（DSH）** 上跑通的科研技能备份，含：
检索 PubMed 与其他文献库、生成并校验 BibTeX、系统综述工作流、研究设计审查、
从队列数据库找课题、撰写伦理方案、投稿期刊匹配。

> 这些技能是第三方作品，版权归原作者；来源与许可逐项列在 [LICENSES.md](LICENSES.md)。
> 本仓库把它们打成一个可直接恢复的备份，另外附上环境适配脚本与排障记录。

## 内容

```
skills/
├── pubmed-paper-finder/     PubMed 主题多模块检索 + 排序候选清单
├── paper-lookup/            11 个文献库检索、全文、引文图
├── nature-academic-search/  多源检索、引文核对、MeSH、他引审计（含 MCP server）
├── literature-review/       系统综述工作流、引文格式、文档产出
├── citation-management/     BibTeX 生成与校验
├── search-lit/              检索 + API 验证后生成 BibTeX
├── design-study/            研究设计审查（分析单位、泄漏、对照、验证）
├── find-cohort-gap/         从队列数据库找可做的课题
├── write-protocol/          伦理/IRB 方案撰写
└── find-journal/            投稿期刊匹配与拒稿回退

install.ps1              一键安装 + 本机适配
RESEARCH-SKILLS-ENV.md   环境搭建与排障记录
LICENSES.md              技能来源与许可
```

## 安装

技能目录就是 DSH 的加载路径，直接复制即可：

```powershell
git clone https://github.com/afdsfref/research-skills-env.git
cd research-skills-env
.\install.ps1
```

脚本会做四件事：

1. 复制 10 个技能到 `%USERPROFILE%\.dsh\skills\`
2. 检查 `python3`，缺失时在 Python 目录旁创建垫片
3. 安装 Python 依赖（`mcp<2`、`pybliometrics`、`lxml`、`requests`、`toml`）
4. 把 `academic-search` MCP server 写进 DSH 的 `cordis.patch.yml`（原文件会备份）

只装部分技能：

```powershell
.\install.ps1 -Skills design-study,search-lit,citation-management
```

不想动 MCP 配置或依赖：

```powershell
.\install.ps1 -SkipMCP -SkipRequirements
```

**改完 MCP 配置需要重启 DSH。** 新复制的技能在下次会话生效。

## 最关键的三个坑

装不上或者装上跑不动，八成是这三个：

1. **`python3` 是商店占位符** —— 执行返回 9009，技能里写的 `python3 xxx.py` 全部失败。
2. **`mcp` 必须 `<2`** —— 2.x 把 `FastMCP` 改名为 `MCPServer`，
   `nature-academic-search` 的 server 会直接 `ModuleNotFoundError`。另外 `pybliometrics` 是硬依赖。
3. **`search-lit` 的 E-utilities 工具原本只有 bash 版** —— 无 bash 的 Windows 上跑不了，
   本仓库带了一份等价的 `pubmed_eutils.py`。

其余（pip 索引挂起、GitHub 下载超时、GBK 控制台编码、`literature-review` 的 JSON 形状、
PDF 需要 LaTeX）都在 [RESEARCH-SKILLS-ENV.md](RESEARCH-SKILLS-ENV.md) 里。

## 快速自检

```powershell
python3 --version                                  # 应有版本号，不是 9009
python "$env:USERPROFILE\.dsh\skills\pubmed-paper-finder\scripts\pubmed_paper_finder.py" "your topic"
python -c "from mcp.server.fastmcp import FastMCP; print('ok')"    # nature-academic-search 用
pandoc --version                                   # 可选，用于 docx/html 导出
```

## 适用场景说明

`design-study`、`find-cohort-gap` 等来自 medsci-skills，提示词面向影像与临床 AI 场景。
用在孟德尔随机化、回顾性队列这类非影像研究上时，需要自己挑适用的检查项——
分析单位、泄漏、参照标准、验证策略这几条是通用的，影像特有的部分可以跳过。
