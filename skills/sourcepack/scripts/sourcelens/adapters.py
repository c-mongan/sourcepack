"""Normalize saved producer outputs; preserve raw bytes in the calling store."""
from html import unescape
from html.parser import HTMLParser
import json
import io
import math
import re

from .contracts import ContractError

URL = re.compile(r'https?://[^\s<>"\x27]+')
TIMING = re.compile(r'^((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+((?:\d{2,}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$')


def timestamp(value: str) -> int:
    parts = value.replace(',', '.').split(':')
    h, m, s = (0, int(parts[0]), float(parts[1])) if len(parts) == 2 else (int(parts[0]), int(parts[1]), float(parts[2]))
    if not (0 <= m < 60 and 0 <= s < 60):
        raise ContractError('Invalid subtitle timestamp')
    return round((h * 3600 + m * 60 + s) * 1000)


def chunks(text: str, kind: str = 'text', method: str = 'utf8', max_spans: int = 2000) -> list[dict]:
    spans = []
    offset = 0
    for line_no, line in enumerate(io.StringIO(text), 1):
        for start in range(0, len(line), 1200):
            part = line[start:start + 1200]
            if part.strip():
                if len(spans) >= max_spans:
                    raise ContractError('Evidence span budget exceeded during parsing')
                spans.append({'kind': kind, 'text': part, 'method': method,
                              'locator': {'start_line': line_no, 'end_line': line_no,
                                          'start_char': offset + start, 'end_char': offset + start + len(part)}})
        offset += len(line)
    return spans


def subtitles(text: str, max_spans: int = 2000) -> list[dict]:
    spans = []
    last_start = -1
    blocks = re.finditer(r'(?s)(?:^|\n\s*\n)(.*?)(?=\n\s*\n|$)', text.replace('\r\n', '\n').strip())
    for index, block_match in enumerate(blocks):
        block = block_match.group(1)
        lines = block.splitlines()
        if not lines or lines[0].startswith(('WEBVTT', 'NOTE', 'STYLE', 'REGION')):
            continue
        timing_indices = [i for i, line in enumerate(lines) if '-->' in line]
        if not timing_indices:
            raise ContractError('Unrecognized subtitle block')
        i = timing_indices[0]
        match = TIMING.fullmatch(lines[i].strip())
        if not match:
            raise ContractError('Malformed subtitle timing')
        start, end = map(timestamp, match.groups())
        if end <= start or start < last_start:
            raise ContractError('Invalid subtitle interval or order')
        last_start = start
        value = '\n'.join(lines[i + 1:])
        if not value.strip():
            raise ContractError('Empty subtitle cue')
        if len(value) > 1200:
            raise ContractError('Subtitle cue exceeds bounded span size')
        if len(spans) >= max_spans:
            raise ContractError('Evidence span budget exceeded during subtitle parsing')
        spans.append({'kind': 'transcript', 'text': value, 'method': 'subtitle-verbatim',
                      'locator': {'segment_id': str(index), 'start_ms': start, 'end_ms': end}})
    if not spans:
        raise ContractError('No subtitle cues found')
    return spans


class Page(HTMLParser):
    def __init__(self, limit=2000):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.hidden = 0
        self.limit = limit
        self.active_anchors = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        for key, value in attrs:
            if key in ('href', 'src') and value:
                if len(self.links) >= self.limit:
                    raise ContractError('HTML reference budget exceeded')
                self.links.append({'target': value, 'span_index': None,
                                   'locator': {'html_line': self.getpos()[0], 'html_column': self.getpos()[1]}, 'method': 'literal-html-attribute'})
                if tag == 'a' and key == 'href':
                    self.active_anchors.append(len(self.links) - 1)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.active_anchors.clear()
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            if len(self.parts) >= self.limit:
                raise ContractError('HTML block budget exceeded')
            self.parts.append(data.strip())
            for index in self.active_anchors:
                self.links[index].setdefault('part_index', len(self.parts) - 1)


def literal_references(text, spans, limit):
    """Inventory before chunking; a cross-span target retains its full text locator."""
    refs = []
    for match in URL.finditer(text):
        if len(refs) >= limit:
            raise ContractError('Reference budget exceeded')
        span_index = next((i for i, s in enumerate(spans)
                           if s['locator'].get('start_char', -1) <= match.start() < s['locator'].get('end_char', -1)), 0)
        target = unescape(match.group().rstrip('.,;!?)\u005d'))
        refs.append({'target': target, 'span_index': span_index,
                     'locator': {'start_char': match.start(), 'end_char': match.start() + len(match.group().rstrip('.,;!?)\u005d')),
                                 'text_version': 'adapter-input-text'}, 'method': 'literal-url'})
    return refs


def parse(raw: bytes, suffix: str, input_format: str | None = None, max_spans: int = 2000) -> tuple[list[dict], list[dict], list[dict]]:
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ContractError('Input is not UTF-8; use an extraction adapter') from exc
    references, gaps = [], []
    reference_text = text
    if input_format == 'summarize':
        try:
            data = json.loads(text)
            extracted = data['extracted']
            if not isinstance(extracted, dict):
                raise TypeError()
        except (ValueError, TypeError, KeyError) as exc:
            raise ContractError('Expected saved Summarize JSON with an extracted object') from exc
        segments = extracted.get('transcriptSegments')
        if segments:
            if not isinstance(segments, list):
                raise ContractError('Invalid transcript segments')
            spans = []
            previous = -1
            for i, seg in enumerate(segments):
                if i >= max_spans:
                    raise ContractError('Imported segment budget exceeded')
                if not isinstance(seg, dict):
                    raise ContractError('Invalid transcript segment')
                start, end, value = seg.get('startMs'), seg.get('endMs'), seg.get('text')
                valid_time = lambda n: type(n) in (int, float) and 0 <= n <= 10 ** 12 and math.isfinite(n)
                if not valid_time(start) or start < 0 or start < previous or (end is not None and (not valid_time(end) or end <= start)):
                    raise ContractError('Invalid imported timing')
                if not isinstance(value, str) or not value.strip() or len(value) > 1200:
                    raise ContractError('Invalid imported segment text')
                previous = start
                spans.append({'kind': 'transcript', 'text': value, 'method': 'summarize-json-import',
                              'locator': {'segment_id': str(i), 'start_ms': start, 'end_ms': end}})
                if end is None:
                    gaps.append({'kind': 'timing', 'reason': f'Imported segment {i} has no end time; none invented'})
        else:
            content = extracted.get('content')
            if not isinstance(content, str) or not content.strip():
                raise ContractError('No extracted content or timed transcript')
            spans = chunks(content, method='summarize-json-import', max_spans=max_spans)
            reference_text = content
        gaps.append({'kind': 'upstream', 'reason': 'Saved extraction output imported; original remote bytes and upstream execution not verified'})
        if extracted.get('slides') or data.get('slides'):
            gaps.append({'kind': 'visual', 'reason': 'Slide metadata is not imported image evidence'})
    elif suffix in ('.srt', '.vtt'):
        spans = subtitles(text, max_spans)
    elif suffix in ('.html', '.htm'):
        page = Page(max_spans)
        page.feed(text)
        reference_text = '\n'.join(page.parts)
        spans = chunks(reference_text, 'web', 'html-text-derived', max_spans)
        references = page.links
        part_offsets, position = [], 0
        for part in page.parts:
            part_offsets.append(position)
            position += len(part) + 1
        for ref in references:
            part_index = ref.pop('part_index', None)
            if part_index is not None:
                ref['span_index'] = next((i for i, s in enumerate(spans)
                                          if s['locator']['start_char'] <= part_offsets[part_index]
                                          < s['locator']['end_char']), None)
        for span in spans:
            span['locator']['text_version'] = 'derived-html-text-v1'
    elif suffix in ('.txt', '.md', '.rst', '.csv', '.json', '.py', '.ts', '.js', '.yaml', '.yml'):
        spans = chunks(text, max_spans=max_spans)
    else:
        raise ContractError('Unsupported format; supply text/subtitles/HTML/video or --input-format summarize')
    if not spans:
        gaps.append({'kind': 'empty', 'reason': 'No readable text extracted'})
    if spans and spans[0]['kind'] == 'transcript':
        for n, span in enumerate(spans):
            for match in URL.finditer(span['text']):
                if len(references) >= max_spans:
                    raise ContractError('Reference budget exceeded')
                references.append({'target': unescape(match.group().rstrip('.,;!?)\u005d')),
                                   'span_index': n, 'locator': {'start_char_in_span': match.start(), 'end_char_in_span': match.end()},
                                   'method': 'literal-url'})
    else:
        references.extend(literal_references(reference_text, spans, max_spans - len(references)))
    return spans, references, gaps
