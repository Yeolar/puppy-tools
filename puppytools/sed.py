#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2014, Yeolar <yeolar@gmail.com>
#

import argparse
import os
import re
import sys
import tempfile
import textwrap

try:
    import curses
except ImportError:
    curses = None


PROG_NAME = 'pp-sed'


def _stderr_supports_color():
    color = False
    if curses and hasattr(sys.stderr, 'isatty') and sys.stderr.isatty():
        try:
            curses.setupterm()
            if curses.tigetnum("colors") > 0:
                color = True
        except Exception:
            pass
    return color


class ColorFormatter(object):

    def __init__(self):
        if _stderr_supports_color():
            fg_color = (curses.tigetstr('setaf') or
                        curses.tigetstr('setf') or '')
            self._colors = {
                'r': curses.tparm(fg_color, 1), # Red
                'g': curses.tparm(fg_color, 2), # Green
                'y': curses.tparm(fg_color, 3), # Yellow
                'b': curses.tparm(fg_color, 4), # Blue
            }
            self._bold = curses.tigetstr('bold')
            self._normal = curses.tigetstr('sgr0')
        else:
            self._colors = {}
            self._bold = ''
            self._normal = ''

    def format(self, message, color, bold=False):
        return (self._colors.get(color, self._normal) +
                (self._bold if bold else '') +
                message + self._normal)


class ColorWriter(object):

    def __init__(self, formatter):
        self.formatter = formatter

    def write(self, message, fname=None, lineno=None):
        if lineno:
            lineno = self.formatter.format(str(lineno), 'g')
            if fname:
                fname = self.formatter.format(fname, 'y')
                print '%s:%s:%s' % (fname, lineno, message)
            else:
                print '%s:%s' % (lineno, message)
        else:
            print message


color_formatter = ColorFormatter()
color_writer = ColorWriter(color_formatter)


class ReplacePattern(object):

    FLAG_MAP = { 'i': re.I, 's': re.S, 'u': re.U, }

    def __init__(self, fr, to, flags=0):
        self.fr = fr
        self.to = to
        self.count = 0 if 'g' in flags else 1   # 0 means all
        self.flags = self.bit_flags(flags)
        self.frpattern = re.compile(self.fr, self.flags)
        self.topattern = re.compile(self.to)
        if self.frpattern.groups > 1:
            raise ValueError('Pattern group count > 1')

    def __str__(self):
        return '(%s, %s)' % (self.fr, self.to)

    def bit_flags(self, flags):
        bits = 0
        for c in flags:
            if c == 'g':
                continue
            bits |= self.FLAG_MAP[c]
        return bits

    @classmethod
    def parse(cls, s):
        if not s or len(s) < 3:
            raise ValueError('Pattern format error, %s' % s)

        splited = []
        split = s[0]
        p = s[1:]
        k = 0
        while True:
            i = p.find(split, k)
            if i == -1:
                break
            if i > 0 and p[i-1] == '\\':
                k = i + 1
                continue
            splited.append(p[:i])
            p = p[i+1:]
            k = 0
        splited.append(p)

        if len(splited) != 3:
            raise ValueError('Pattern format error, %s' % s)

        return cls(*splited)


def extend_directories(paths):
    all_files = []
    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for name in files:
                    all_files.append(os.path.join(root, name))
        else:
            all_files.append(path)
    return all_files


def prepare_patterns(pattern, pattern_file):
    patterns = []
    if pattern:
        patterns.append(ReplacePattern.parse(pattern))
    if pattern_file:
        for line in pattern_file:
            patterns.append(ReplacePattern.parse(line.strip()))
    return patterns


def replace_line(s, patterns, verbose=False, fname=None, lineno=None):
    def red_message(m):
        if len(m.groups()) > 0:
            return (m.string[m.start():m.start(1)] +
                    color_formatter.format(m.group(1), 'r', bold=True) +
                    m.string[m.end(1):m.end()])
        else:
            return color_formatter.format(m.group(0), 'r', bold=True)
    def green_message(m):
        return color_formatter.format(m.group(0), 'g', bold=True)

    if verbose:
        verbose_line1 = s
        verbose_line2 = s
    for p in patterns:
        def repl(m):
            if len(m.groups()) > 0:
                return (m.string[m.start():m.start(1)] +
                        p.to +
                        m.string[m.end(1):m.end()])
            else:
                return p.to
        s = p.frpattern.sub(repl, s, count=p.count)
        if verbose:
            verbose_line1 = p.frpattern.sub(
                    red_message, verbose_line1, count=p.count)
            verbose_line2 = p.topattern.sub(
                    green_message, s, count=p.count)
    if verbose and verbose_line1 != s:
        color_writer.write(verbose_line1.rstrip(), fname, lineno)
        color_writer.write(verbose_line2.rstrip(), fname, lineno)
    return s


def replace(f, output, patterns, show_fname, args):
    tmp = tempfile.SpooledTemporaryFile(max_size=1048576)
    replaced = False

    with open(f) as fp:
        fname = os.path.basename(f) if show_fname else None
        lineno = 1
        for line in fp:
            repl_line = replace_line(line, patterns,
                    verbose=args.verbose, fname=fname, lineno=lineno)
            tmp.write(repl_line)
            lineno += 1
            if not replaced and repl_line != line:
                replaced = True

    if args.examine:
        tmp.close()
        return

    tmp.seek(0)

    if output:
        with open(output, 'w') as fp:
            fp.write(tmp.read())
    elif replaced:
        if args.inplace:
            os.rename(f, f + '.old')
            with open(f, 'w') as fp:
                fp.write(tmp.read())
        elif args.clean_inplace:
            with open(f, 'w') as fp:
                fp.write(tmp.read())
        else:
            with open(f + '.new', 'w') as fp:
                fp.write(tmp.read())

    tmp.close()


def description():
    return '''A sed-like replace tool.

python special sequences:
 \\number  the contents of the group of the same number
 \\b       the empty string, but only at the beginning or end of a word
 \\B       the empty string, but only not at the beginning or end of a word
 \\A       the start of the string      \\Z       the end of the string
 \\d       [0-9]                        \\D       [^0-9]
 \\s       [ \\t\\n\\r\\f\\v]                \\S       [^ \\t\\n\\r\\f\\v]
 \\w       [a-zA-Z0-9_]                 \\W       [^a-zA-Z0-9_]'''


def main():
    ap = argparse.ArgumentParser(
            prog=PROG_NAME,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description=textwrap.dedent(description()),
            epilog='Author: Yeolar <yeolar@gmail.com>')
    ap.add_argument('input', nargs='+',
                    help='input file')
    ap.add_argument('-i', '--inplace', action='store_true', dest='inplace',
                    help='save inplace')
    ap.add_argument('-I', '--clean-inplace', action='store_true',
                    dest='clean_inplace', help='save inplace and no backup')
    ap.add_argument('-o', '--output', action='store', dest='output',
                    help='output file')
    ap.add_argument('-p', '--pattern', action='store', dest='pattern',
                    help='specify the pattern') # '/from/to/ig', i&g is optional
    ap.add_argument('-f', '--pattern-file', action='store', dest='pattern_file',
                    type=file, help='specify the pattern file')
    ap.add_argument('-r', '--recursive', action='store_true', dest='recursive',
                    help='operate recursively')
    ap.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                    help='show replace details')
    ap.add_argument('-x', '--examine', action='store_true', dest='examine',
                    help='examine but not really do')
    args = ap.parse_args()

    if args.recursive:
        input_files = extend_directories(args.input)
    else:
        input_files = args.input

    if len(input_files) > 1 and args.output:
        ap.error('Should not set output when multi-input.')
    if not args.pattern and not args.pattern_file:
        ap.error('No pattern specified.')

    patterns = prepare_patterns(args.pattern, args.pattern_file)
    show_fname = len(input_files) > 1

    for input in input_files:
        if os.path.isfile(input):
            replace(input, args.output, patterns, show_fname, args)
        else:
            print "Ignore non-regular file path: '%s'" % input


if __name__ == '__main__':
    main()

