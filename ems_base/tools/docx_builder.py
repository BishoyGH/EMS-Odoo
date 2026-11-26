"""Minimal .docx writer (no third-party dependency).

Blocks are tuples:
  ('title', text) ('h1', text) ('h2', text) ('p', text) ('bold', text) ('bullet', text)
  ('table', [[cell, ...], ...])   first row is rendered as header
  ('break',)                      page break
"""
import io
import zipfile
from xml.sax.saxutils import escape

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles %s>
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="44"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:spacing w:before="160" w:after="60"/></w:pPr><w:rPr><w:b/><w:color w:val="2E5597"/><w:sz w:val="26"/></w:rPr></w:style>
</w:styles>""" % NS


def _run(text, bold=False):
    props = '<w:rPr><w:b/></w:rPr>' if bold else ''
    parts = str(text if text is not None else '').split('\n')
    inner = '<w:br/>'.join('<w:t xml:space="preserve">%s</w:t>' % escape(p) for p in parts)
    return '<w:r>%s%s</w:r>' % (props, inner)


def _para(text, style=None, bold=False, bullet=False):
    ppr = ''
    if style:
        ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % style
    elif bullet:
        ppr = '<w:pPr><w:ind w:left="360" w:hanging="260"/></w:pPr>'
        text = '• ' + str(text)
    return '<w:p>%s%s</w:p>' % (ppr, _run(text, bold))


def _table(rows):
    out = ['<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>']
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        out.append('<w:%s w:val="single" w:sz="4" w:color="A6A6A6"/>' % side)
    out.append('</w:tblBorders></w:tblPr>')
    for idx, row in enumerate(rows):
        out.append('<w:tr>')
        for cell in row:
            shade = '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="DCE6F2"/></w:tcPr>' if idx == 0 else ''
            out.append('<w:tc>%s%s</w:tc>' % (shade, _para(cell, bold=(idx == 0))))
        out.append('</w:tr>')
    out.append('</w:tbl><w:p/>')
    return ''.join(out)


def build_docx(blocks):
    body = []
    for block in blocks:
        kind = block[0]
        if kind == 'title':
            body.append(_para(block[1], style='Title'))
        elif kind == 'h1':
            body.append(_para(block[1], style='Heading1'))
        elif kind == 'h2':
            body.append(_para(block[1], style='Heading2'))
        elif kind == 'p':
            body.append(_para(block[1]))
        elif kind == 'bold':
            body.append(_para(block[1], bold=True))
        elif kind == 'bullet':
            body.append(_para(block[1], bullet=True))
        elif kind == 'table':
            body.append(_table(block[1]))
        elif kind == 'break':
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document %s><w:body>%s'
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
                '</w:body></w:document>') % (NS, ''.join(body))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', CONTENT_TYPES)
        zf.writestr('_rels/.rels', RELS)
        zf.writestr('word/_rels/document.xml.rels', DOC_RELS)
        zf.writestr('word/styles.xml', STYLES)
        zf.writestr('word/document.xml', document)
    return buf.getvalue()
