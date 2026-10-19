# AICAP 2027 论文

本目录采用 IEEE 官方 `IEEEtran` 会议双栏格式，目标会议为 **Aviation Innovation Conference for Asia Pacific (AICAP) 2027**。

## 投稿要求

根据会议公开征稿说明（核对日期：2026-10-16）：

- 使用 IEEE 双栏会议论文格式。
- 全文最多 **8 页**，包括参考文献、附录及其他补充内容。
- 提交 PDF，文件大小不超过 **6 MB**。
- 通过 EasyChair 投稿。
- 公开说明未明确是否匿名；投稿前核对系统中的最新要求。

投稿截止：2026-10-30；录用通知：2026-12-01；最终稿截止：2026-12-15。公开页面未明确截止时区。

会议官网：https://event.ntu.edu.sg/AICAP-2027

征稿与格式要求：https://easychair.org/cfp/AICAP-2027

IEEE 官方模板入口：https://www.ieee.org/conferences/publishing/templates

## 文件结构

```text
paper/
  main.tex                       论文总入口
  .latexmkrc                     本地编译配置，输出到 build/
  build/                         本地编译产物，不提交
  IEEEtran.cls                   IEEE 官方文档类
  IEEEtran.bst                   IEEE 官方参考文献样式
  macros.tex                     项目符号与草稿提示
  references.bib                 BibTeX 文献库
  sections/
    abstract.tex                 摘要
    introduction.tex             引言
    related_work.tex             已写好的 Related Work
    problem_formulation.tex      问题定义
    method.tex                   方法
    experiments.tex              实验
    discussion.tex               讨论与局限
    conclusion.tex               结论
    appendix.tex                 附录
  figures/                       图片
  tables/                        表格
```

子章节由 `main.tex` 的 `\input` 命令组织，不单独编译。Related Work 正文已保留，引用采用 IEEE 数字编号。其他章节仍有明确标注的写作占位内容，不代表已完成实验。

当前研究主线是基于航迹 embedding 点云关联维数的历史场景复杂度量化与验证。不要将尚未实现或评价的预测、控制功能写成已有结果。

## 编译

在 `paper/` 目录执行：

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

项目的 `.latexmkrc` 固定使用 pdfLaTeX，并将 PDF 与辅助文件写入 `build/`。输出为 `build/main.pdf`，不要把编译产物放回源码根目录。

清理辅助文件（保留 PDF）：

```bash
latexmk -c main.tex
```

Overleaf 请选择 `main.tex` 为主文件，编译器使用 pdfLaTeX。也可在 Codex 中打开 `paper/`，使用内置编译和 PDF 预览。

`main.tex` 使用 `\documentclass[conference]{IEEEtran}`，参考文献采用 `\bibliographystyle{IEEEtran}`。正文引用写作 `\cite{key}`；在句中提及作者时，写作 `Lim et al.~\cite{key}`。

文档类按默认 US Letter 纸张、10 pt 正文及标准双栏排版；当前会议说明未另外指定纸张尺寸。若主办方后续发布专用模板，以最新要求为准。不要修改字号、页边距或行距来压缩篇幅。附录也保持双栏并计入页数限制。

`macros.tex` 中的 `\showdraftnotesfalse` 可隐藏草稿提示；正式投稿前应完成或移除所有占位文字，并确认作者与单位。

## 样式文件与维护

`IEEEtran.cls` 和 `IEEEtran.bst` 为 TeX Live 提供的 IEEEtran 1.8b 原版文件，未作修改，随项目保留以便本地及 Overleaf 编译。其版本与发布信息见 https://ctan.org/pkg/ieeetran 。

参考文献条目的作者、题名和发表信息保存在 `references.bib`。两篇尚未核实正式发表信息的老师提供稿件如实标为 manuscript，待获得正式记录后更新。

`build/` 内的编译产物以及根目录误生成的 `main.pdf` 已在 `.gitignore` 中排除。`figures/` 中用于论文的 PDF 图片允许提交，不能与生成的论文 PDF 一并忽略。模型、数据处理与训练代码位于本目录之外；论文排版变更不涉及这些代码。

## 当前草稿状态与维护约定

- 本目录是论文草稿，摘要、实验、讨论和结论等章节仍有 `\draftnote` 占位提示。编译成功不代表论文已经完成。
- 本次整理不改正文、参考文献内容、作者占位或实验结论；不把历史会议材料自动写入当前论文。
- 当前合成扰动实验以 [evaluation 报告](../evaluation/reports/evaluation-pilot.md) 为依据；Estimator 的实现说明见 [方法文档](../doc/trajectory-embedding-point-cloud-complexity.md)。论文中的方法和结论需在写作时逐项与证据核对。
- `figures/` 存放实际被论文引用的图片；`tables/` 存放可通过 `\input` 引用的表格源码。现在两个目录为空，保留 `.gitkeep` 作为预定结构。
- 保留本地 `IEEEtran.cls` 和 `IEEEtran.bst`，不要把第三方模板当作冗余源码删除或手工改版。
- 上面的投稿信息保留原核对日期 2026-10-16；本次仅整理文件，未重新核验会议要求。
