from __future__ import annotations

import csv
import json
import re
import tkinter as tk
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse


SOURCE_FILE = Path(__file__).resolve().parent / 'fmhy' / 'single-page.md'
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
BULLET_RE = re.compile(r'^\s*\*\s+(.*)$')
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
HTML_TAG_RE = re.compile(r'<[^>]+>')
ZERO_WIDTH_RE = re.compile(r'[\u200b-\u200f\u2060\ufeff]')
SYMBOL_PREFIX_RE = re.compile(r'^[^\w\u4e00-\u9fff\[\(*`]+')


@dataclass
class FMHYRecord:
    line_no: int
    level1_title: str
    level2_title: str
    deeper_titles: list[str]
    deeper_path: str
    heading_path: str
    content_title: str
    url: str
    description: str
    marker: str
    entry_kind: str
    extra_links: list[str]
    raw_text: str


def normalize_text(text: str) -> str:
    text = text.replace('\r', '')
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    text = HTML_TAG_RE.sub(' ', text)
    text = LINK_RE.sub(lambda match: match.group(1), text)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'[*_~]', '', text)
    text = ZERO_WIDTH_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' -\t')


def strip_prefix_symbols(text: str) -> str:
    return SYMBOL_PREFIX_RE.sub('', text).strip()


def clean_heading(text: str) -> str:
    return strip_prefix_symbols(normalize_text(text))


def update_heading_stack(stack: list[tuple[int, str]], level: int, title: str) -> list[tuple[int, str]]:
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))
    return stack


def extract_links(text: str) -> list[tuple[str, str]]:
    return [(normalize_text(label), url.strip()) for label, url in LINK_RE.findall(text)]


def split_marker(text: str) -> tuple[str, str]:
    match = re.match(r'^([^\w\u4e00-\u9fff\[\(*`]+)\s*(.*)$', text)
    if not match:
        return '', text.strip()
    return match.group(1).strip(), match.group(2).strip()


def is_internal_fmhy_url(url: str) -> bool:
    if not url:
        return False
    host = (urlparse(url).netloc or '').lower()
    if 'reddit.com' in host and 'freemediaheckyeah' in url.lower():
        return True
    if host == 'fmhy.net' and '#' in url:
        return True
    return False


def split_content(plain: str, links: list[tuple[str, str]]) -> tuple[str, str, str]:
    title = ''
    description = ''
    entry_kind = 'resource'

    if plain.lower().startswith('note'):
        entry_kind = 'note'
        if ' - ' in plain:
            title, description = plain.split(' - ', 1)
        else:
            title = plain
    elif ' - ' in plain:
        title, description = plain.split(' - ', 1)
    elif links:
        title = links[0][0]
        description = plain.removeprefix(title).strip(' -')
    else:
        title = plain

    return strip_prefix_symbols(title), strip_prefix_symbols(description), entry_kind


def build_record(line_no: int, titles: list[str], raw_text: str) -> FMHYRecord:
    marker, content = split_marker(raw_text)
    links = extract_links(content)
    plain = normalize_text(content)
    content_title, description, entry_kind = split_content(plain, links)
    if '↪' in marker:
        entry_kind = 'cross_reference'

    level1_title = titles[0] if titles else ''
    level2_title = titles[1] if len(titles) > 1 else ''
    deeper_titles = titles[2:] if len(titles) > 2 else []

    return FMHYRecord(
        line_no=line_no,
        level1_title=level1_title,
        level2_title=level2_title,
        deeper_titles=deeper_titles,
        deeper_path=' > '.join(deeper_titles),
        heading_path=' > '.join(titles),
        content_title=content_title,
        url=links[0][1] if links else '',
        description=description,
        marker=marker,
        entry_kind=entry_kind,
        extra_links=[link for _, link in links[1:]],
        raw_text=raw_text,
    )


def parse_fmhy(path: Path) -> list[FMHYRecord]:
    records: list[FMHYRecord] = []
    heading_stack: list[tuple[int, str]] = []

    for line_no, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
        heading_match = HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = clean_heading(heading_match.group(2))
            if title:
                update_heading_stack(heading_stack, level, title)
            continue

        bullet_match = BULLET_RE.match(line)
        if not bullet_match or not heading_stack:
            continue

        raw_text = bullet_match.group(1).strip()
        if not raw_text or raw_text == '***':
            continue

        titles = [title for _, title in heading_stack]
        records.append(build_record(line_no, titles, raw_text))

    return records


def clean_records(
    records: list[FMHYRecord],
    *,
    drop_notes: bool,
    drop_cross_refs: bool,
    drop_internal_links: bool,
    drop_empty_urls: bool,
    dedupe: bool,
) -> list[FMHYRecord]:
    cleaned: list[FMHYRecord] = []
    seen: set[tuple[str, str, str, str]] = set()

    for record in records:
        if drop_notes and record.entry_kind == 'note':
            continue
        if drop_cross_refs and record.entry_kind == 'cross_reference':
            continue
        if drop_internal_links and is_internal_fmhy_url(record.url):
            continue
        if drop_empty_urls and not record.url:
            continue

        key = (
            record.level1_title.casefold(),
            record.level2_title.casefold(),
            record.content_title.casefold(),
            record.url.casefold(),
        )
        if dedupe and key in seen:
            continue
        seen.add(key)
        cleaned.append(record)

    return cleaned


def records_to_markdown(records: list[FMHYRecord]) -> str:
    lines = ['# FMHY Cleaned Export', '']
    current_level1 = ''
    current_level2 = None

    for record in records:
        if record.level1_title != current_level1:
            current_level1 = record.level1_title
            current_level2 = None
            lines.append(f'## {current_level1}')
            lines.append('')
        level2_label = record.level2_title or '未分二级标题'
        if level2_label != current_level2:
            current_level2 = level2_label
            lines.append(f'### {level2_label}')
            lines.append('')
        prefix = f'[{record.content_title}]({record.url})' if record.url else record.content_title
        tail_parts = [part for part in [record.deeper_path, record.description] if part]
        lines.append(f"- {prefix}" + (f" - {' | '.join(tail_parts)}" if tail_parts else ''))
    return '\n'.join(lines).strip() + '\n'


class FMHYCleanerApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title('FMHY 一二级标题清洗器')
        self.root.geometry('1460x900')

        self.source_var = tk.StringVar(value=str(SOURCE_FILE))
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value='等待加载')
        self.summary_var = tk.StringVar(value='尚未解析文件')

        self.drop_notes_var = tk.BooleanVar(value=False)
        self.drop_cross_refs_var = tk.BooleanVar(value=False)
        self.drop_internal_links_var = tk.BooleanVar(value=False)
        self.drop_empty_urls_var = tk.BooleanVar(value=False)
        self.dedupe_var = tk.BooleanVar(value=True)

        self.raw_records: list[FMHYRecord] = []
        self.cleaned_records: list[FMHYRecord] = []
        self.visible_records: list[FMHYRecord] = []

        self._build_layout()
        self.root.after(50, self.load_and_clean)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        controls = ttk.Frame(self.root, padding=12)
        controls.grid(row=0, column=0, sticky='ew')
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text='源文件').grid(row=0, column=0, sticky='w')
        ttk.Entry(controls, textvariable=self.source_var).grid(row=0, column=1, sticky='ew', padx=(8, 8))
        ttk.Button(controls, text='选择文件', command=self.choose_file).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(controls, text='重新解析', command=self.load_and_clean).grid(row=0, column=3)

        options = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        options.grid(row=1, column=0, sticky='ew')
        options.columnconfigure(1, weight=1)

        ttk.Checkbutton(options, text='过滤 Note', variable=self.drop_notes_var, command=self.apply_filters).grid(row=0, column=0, sticky='w')
        ttk.Checkbutton(options, text='过滤站内跳转', variable=self.drop_cross_refs_var, command=self.apply_filters).grid(row=0, column=1, sticky='w', padx=(12, 0))
        ttk.Checkbutton(options, text='过滤 Reddit/FMHY 内链', variable=self.drop_internal_links_var, command=self.apply_filters).grid(row=0, column=2, sticky='w', padx=(12, 0))
        ttk.Checkbutton(options, text='过滤无链接条目', variable=self.drop_empty_urls_var, command=self.apply_filters).grid(row=0, column=3, sticky='w', padx=(12, 0))
        ttk.Checkbutton(options, text='按一二级标题+内容+链接去重', variable=self.dedupe_var, command=self.apply_filters).grid(row=0, column=4, sticky='w', padx=(12, 0))

        ttk.Label(options, text='搜索').grid(row=1, column=0, sticky='w', pady=(10, 0))
        search_entry = ttk.Entry(options, textvariable=self.search_var)
        search_entry.grid(row=1, column=1, sticky='ew', pady=(10, 0), padx=(8, 8))
        search_entry.bind('<KeyRelease>', lambda _event: self.refresh_tree())

        ttk.Button(options, text='导出 JSON', command=self.export_json).grid(row=1, column=2, pady=(10, 0), padx=(8, 0))
        ttk.Button(options, text='导出 CSV', command=self.export_csv).grid(row=1, column=3, pady=(10, 0), padx=(8, 0))
        ttk.Button(options, text='导出 Markdown', command=self.export_markdown).grid(row=1, column=4, pady=(10, 0), padx=(8, 0))

        body = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        body.grid(row=2, column=0, sticky='nsew', padx=12, pady=(0, 12))

        top = ttk.Frame(body)
        top.columnconfigure(0, weight=1)
        top.rowconfigure(1, weight=1)
        body.add(top, weight=3)

        ttk.Label(top, textvariable=self.summary_var).grid(row=0, column=0, sticky='w', pady=(0, 8))

        columns = ('level1', 'level2', 'deeper', 'title', 'url', 'kind', 'description')
        self.tree = ttk.Treeview(top, columns=columns, show='headings', height=20)
        config = {
            'level1': ('一级标题', 180),
            'level2': ('二级标题', 220),
            'deeper': ('更深标题', 220),
            'title': ('内容标题', 220),
            'url': ('主链接', 260),
            'kind': ('类型', 90),
            'description': ('描述', 360),
        }
        for key, (label, width) in config.items():
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor='w')
        self.tree.grid(row=1, column=0, sticky='nsew')
        self.tree.bind('<<TreeviewSelect>>', self.show_details)

        tree_scroll = ttk.Scrollbar(top, orient='vertical', command=self.tree.yview)
        tree_scroll.grid(row=1, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=tree_scroll.set)

        bottom = ttk.Notebook(body)
        body.add(bottom, weight=2)

        detail_frame = ttk.Frame(bottom, padding=8)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(0, weight=1)
        self.detail_text = tk.Text(detail_frame, wrap='word')
        self.detail_text.grid(row=0, column=0, sticky='nsew')
        detail_scroll = ttk.Scrollbar(detail_frame, orient='vertical', command=self.detail_text.yview)
        detail_scroll.grid(row=0, column=1, sticky='ns')
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        bottom.add(detail_frame, text='条目详情')

        summary_frame = ttk.Frame(bottom, padding=8)
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)
        self.summary_text = tk.Text(summary_frame, wrap='word')
        self.summary_text.grid(row=0, column=0, sticky='nsew')
        summary_scroll = ttk.Scrollbar(summary_frame, orient='vertical', command=self.summary_text.yview)
        summary_scroll.grid(row=0, column=1, sticky='ns')
        self.summary_text.configure(yscrollcommand=summary_scroll.set)
        bottom.add(summary_frame, text='统计汇总')

        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w', padding=(10, 6))
        status_bar.grid(row=3, column=0, sticky='ew')

    def choose_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title='选择 FMHY Markdown 文件',
            initialdir=str(SOURCE_FILE.parent),
            filetypes=[('Markdown', '*.md'), ('All files', '*.*')],
        )
        if file_path:
            self.source_var.set(file_path)
            self.load_and_clean()

    def load_and_clean(self) -> None:
        path = Path(self.source_var.get()).expanduser()
        if not path.exists():
            messagebox.showerror('文件不存在', f'找不到文件：\n{path}')
            return
        self.status_var.set('正在解析 FMHY 一级/二级标题关系...')
        self.root.update_idletasks()
        try:
            self.raw_records = parse_fmhy(path)
        except Exception as exc:
            messagebox.showerror('解析失败', str(exc))
            self.status_var.set('解析失败')
            return
        self.apply_filters()

    def apply_filters(self) -> None:
        self.cleaned_records = clean_records(
            self.raw_records,
            drop_notes=self.drop_notes_var.get(),
            drop_cross_refs=self.drop_cross_refs_var.get(),
            drop_internal_links=self.drop_internal_links_var.get(),
            drop_empty_urls=self.drop_empty_urls_var.get(),
            dedupe=self.dedupe_var.get(),
        )
        self.refresh_tree()

    def refresh_tree(self) -> None:
        keyword = self.search_var.get().strip().casefold()
        if keyword:
            self.visible_records = [
                record
                for record in self.cleaned_records
                if keyword in record.level1_title.casefold()
                or keyword in record.level2_title.casefold()
                or keyword in record.deeper_path.casefold()
                or keyword in record.content_title.casefold()
                or keyword in record.description.casefold()
                or keyword in record.url.casefold()
            ]
        else:
            self.visible_records = list(self.cleaned_records)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, record in enumerate(self.visible_records):
            self.tree.insert(
                '',
                'end',
                iid=str(index),
                values=(
                    record.level1_title,
                    record.level2_title,
                    record.deeper_path,
                    record.content_title,
                    record.url,
                    record.entry_kind,
                    record.description,
                ),
            )

        self.summary_var.set(
            f'原始 {len(self.raw_records)} 条，清洗后 {len(self.cleaned_records)} 条，当前显示 {len(self.visible_records)} 条'
        )
        self.status_var.set('解析完成')
        self.update_summary_text()

    def update_summary_text(self) -> None:
        primary_counts = Counter(record.level1_title for record in self.cleaned_records)
        secondary_counts = Counter(
            f"{record.level1_title} / {record.level2_title or '未分二级标题'}" for record in self.cleaned_records
        )
        lines = ['一级标题统计']
        lines.extend(f'- {title}: {count}' for title, count in primary_counts.most_common(25))
        lines.append('')
        lines.append('一级 / 二级标题统计')
        lines.extend(f'- {title}: {count}' for title, count in secondary_counts.most_common(40))
        self.summary_text.delete('1.0', tk.END)
        self.summary_text.insert('1.0', '\n'.join(lines))

    def show_details(self, _event: object | None = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        record = self.visible_records[int(selection[0])]
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert('1.0', json.dumps(asdict(record), ensure_ascii=False, indent=2))

    def _default_output_name(self, suffix: str) -> tuple[str, str]:
        source_path = Path(self.source_var.get())
        return str(source_path.parent), f'{source_path.stem}.hierarchy{suffix}'

    def export_json(self) -> None:
        if not self.cleaned_records:
            messagebox.showwarning('无数据', '当前没有可导出的记录。')
            return
        initial_dir, initial_name = self._default_output_name('.json')
        file_path = filedialog.asksaveasfilename(
            title='导出 JSON',
            defaultextension='.json',
            initialdir=initial_dir,
            initialfile=initial_name,
            filetypes=[('JSON', '*.json'), ('All files', '*.*')],
        )
        if not file_path:
            return
        Path(file_path).write_text(
            json.dumps([asdict(record) for record in self.cleaned_records], ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        self.status_var.set(f'已导出 JSON：{file_path}')

    def export_csv(self) -> None:
        if not self.cleaned_records:
            messagebox.showwarning('无数据', '当前没有可导出的记录。')
            return
        initial_dir, initial_name = self._default_output_name('.csv')
        file_path = filedialog.asksaveasfilename(
            title='导出 CSV',
            defaultextension='.csv',
            initialdir=initial_dir,
            initialfile=initial_name,
            filetypes=[('CSV', '*.csv'), ('All files', '*.*')],
        )
        if not file_path:
            return
        with Path(file_path).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    'line_no',
                    'level1_title',
                    'level2_title',
                    'deeper_path',
                    'heading_path',
                    'content_title',
                    'url',
                    'description',
                    'marker',
                    'entry_kind',
                    'extra_links',
                    'raw_text',
                ],
            )
            writer.writeheader()
            for record in self.cleaned_records:
                writer.writerow(
                    {
                        'line_no': record.line_no,
                        'level1_title': record.level1_title,
                        'level2_title': record.level2_title,
                        'deeper_path': record.deeper_path,
                        'heading_path': record.heading_path,
                        'content_title': record.content_title,
                        'url': record.url,
                        'description': record.description,
                        'marker': record.marker,
                        'entry_kind': record.entry_kind,
                        'extra_links': ' | '.join(record.extra_links),
                        'raw_text': record.raw_text,
                    }
                )
        self.status_var.set(f'已导出 CSV：{file_path}')

    def export_markdown(self) -> None:
        if not self.cleaned_records:
            messagebox.showwarning('无数据', '当前没有可导出的记录。')
            return
        initial_dir, initial_name = self._default_output_name('.md')
        file_path = filedialog.asksaveasfilename(
            title='导出 Markdown',
            defaultextension='.md',
            initialdir=initial_dir,
            initialfile=initial_name,
            filetypes=[('Markdown', '*.md'), ('All files', '*.*')],
        )
        if not file_path:
            return
        Path(file_path).write_text(records_to_markdown(self.cleaned_records), encoding='utf-8')
        self.status_var.set(f'已导出 Markdown：{file_path}')

    def run(self) -> None:
        self.root.mainloop()


if __name__ == '__main__':
    FMHYCleanerApp().run()
