"""Pure shell-line filtering for the validators' existing manual balance check.

This is a heredoc scanner, not a replacement for Bash syntax validation. Body
and terminator lines become blank lines; original shell lines and line numbers
are retained. Pending heredocs are consumed in declaration order. Ambiguous or
unterminated delimiters fail closed rather than hiding the remaining script.
"""


class ShellScanError(ValueError):
    pass


def _delimiter(line, start):
    i = start
    while i < len(line) and line[i] in ' \t':
        i += 1
    word, quote, quoted, started = [], None, False, False
    while i < len(line):
        ch = line[i]
        if ch in '\r\n':
            break
        if quote:
            if ch == quote:
                quote = None
            elif ch == '\\' and quote == '"' and i + 1 < len(line) and line[i+1] in '$`"\\':
                i += 1
                word.append(line[i])
            else:
                word.append(ch)
        elif ch in ' \t;|&()<>' or (ch == '#' and not started):
            break
        elif ch in "'\"":
            quote, quoted, started = ch, True, True
        elif ch == '\\':
            i += 1
            if i >= len(line) or line[i] in '\r\n':
                raise ShellScanError('unsupported continued heredoc delimiter')
            word.append(line[i])
            quoted, started = True, True
        else:
            word.append(ch)
            started = True
        i += 1
    if quote or not started:
        raise ShellScanError('missing or malformed heredoc delimiter')
    return ''.join(word), quoted, i


def shell_visible_text(script):
    """Return text excluding heredoc bodies, or raise ShellScanError.

Supports plain/quoted/escaped words, <<- tab stripping, multiple pending
heredocs and continued command lines. Quoted literals, comments, here-strings
and arithmetic shifts do not introduce heredocs. No I/O or execution occurs.
"""
    output, pending = [], []
    quote, arithmetic, reading = None, 0, False
    body_prefix = ''
    for line in script.splitlines(keepends=True):
        if reading:
            delimiter, strip_tabs, quoted = pending[0]
            text = line[:-1] if line.endswith('\n') else line
            if strip_tabs:
                text = text.lstrip('\t')
            text = body_prefix + text
            body_prefix = ''
            # Unquoted heredocs remove backslash-newline before delimiter checks.
            trailing = len(text) - len(text.rstrip('\\'))
            if not quoted and line.endswith('\n') and trailing % 2:
                body_prefix = text[:-1]
            elif text == delimiter:
                pending.pop(0)
                reading = bool(pending)
            output.append('\n' if line.endswith('\n') else '')
            continue

        output.append(line)
        i, continued = 0, False
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == quote:
                    quote = None
                elif ch == '\\' and quote != "'" and i + 1 < len(line):
                    continued = line[i+1] == '\n'
                    i += 1
            elif ch == '#' and (i == 0 or line[i-1].isspace() or line[i-1] in ';|&()<>'):
                break
            elif ch in "'\"`":
                quote = ch
            elif ch == '\\' and i + 1 < len(line):
                continued = line[i+1] == '\n'
                i += 1
            elif line.startswith('((', i):
                arithmetic += 2
                i += 1
            elif arithmetic:
                if ch == '(':
                    arithmetic += 1
                elif ch == ')':
                    arithmetic -= 1
            elif line.startswith('<<<', i):
                i += 2
            elif line.startswith('<<', i):
                i += 2
                strip_tabs = i < len(line) and line[i] == '-'
                if strip_tabs:
                    i += 1
                delimiter, quoted, i = _delimiter(line, i)
                pending.append((delimiter, strip_tabs, quoted))
                continue
            i += 1
        if pending and not continued and quote is None and not arithmetic:
            reading = True
    if pending:
        raise ShellScanError('unterminated heredoc: ' + repr(pending[0][0]))
    return ''.join(output)
