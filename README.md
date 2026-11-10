# 科研技能环境搭建记事

在 Windows + DeepSeek Harness 上安装并跑通一批文献检索与课题设计技能（Agent Skills）的踩坑记录。

涵盖：`pubmed-paper-finder`、`paper-lookup`、`nature-academic-search`、`literature-review`、
`citation-management`、`search-lit`、`design-study`、`find-cohort-gap`、`write-protocol`、`find-journal`。

主要内容：

- **四个必踩的坑**：`python3` 是商店占位符；`search-lit` 的 E-utilities 工具只有 bash 版；
  MCP SDK 2.x 不兼容 FastMCP 代码（必须 `mcp<2`，且需 `pybliometrics`）；pip 索引挂起、
  GitHub 下载超时、GBK 控制台编码。
- **两处文档与行为不符**：`literature-review` 的结果处理脚本只吃纯数组、没有 `--help`；
  PDF 导出需要 LaTeX（或改用 pandoc 直出 docx/html）。
- **可直接复制的命令**：检索、BibTeX 生成与校验、DAG 调整集筛查、Markdown 转 Word/HTML。
- **验证清单与已知限制**：怎么确认"装上不等于跑得动"。

详见 [RESEARCH-SKILLS-ENV.md](RESEARCH-SKILLS-ENV.md)。

> 说明：文档里的路径用 `<SKILLS>` 占位，按自己的技能根目录替换即可。
> 技能本身来自各自的原始仓库，本仓库只记录环境适配方法，不重新分发技能文件。
