#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2014 Yeolar
#

import argparse
import os
import urllib2
from HTMLParser import HTMLParser
from xml.etree import ElementTree

from puppytools.util.colors import *


PROG_NAME = os.path.splitext(os.path.basename(__file__))[0]


class SingleParser(HTMLParser):

    def __init__(self, tag, attr, parse_data, *args, **kwargs):
        HTMLParser.__init__(self, *args, **kwargs)
        self._tag = tag
        self._attr = attr
        self._parse_data = parse_data
        self._match = False             # for print data
        self._start = None              # for print all

    def handle_starttag(self, tag, attrs):
        if tag == self._tag:
            if self._attr:
                for attr in attrs:
                    if attr[0] == self._attr:
                        if self._parse_data:
                            self._match = True
                        else:
                            print attr[1]
            else:
                if self._parse_data:
                    self._match = True
                else:
                    self._start = self.getpos()

    def handle_endtag(self, tag):
        if tag == self._tag:
            if self._parse_data:
                self._match = False
            if not self._attr and not self._parse_data:
                if self._start:
                    end = self.getpos()
                    self.print_rawdata(self._start, end)
                    self._start = None

    def handle_data(self, data):
        if self._match:
            print data

    def print_rawdata(self, start, end):    # untest
        lines = self.rawdata.splitlines(True)
        if start[0] == end[0]:
            print lines[start[0]][start[1]:end[1]]
        else:
            print lines[start[0]][start[1]:]
            for i in range(start[0] + 1, end[0]):
                print lines[i]
            print lines[end[0]][:end[1]]


def main():
    ap = argparse.ArgumentParser(
            prog='pp-' + PROG_NAME,
            description='Parse html, '
                        'extract attribute value and data of html element.',
            epilog='Author: Yeolar <yeolar@gmail.com>')
    ap.add_argument('input', nargs='+',
                    help='input file')
    ap.add_argument('-e', '--element', action='store', dest='element',
                    help='element to parse')
    ap.add_argument('-a', '--attr', action='store', dest='attr',
                    help='attribute to parse')
    ap.add_argument('-d', '--data', action='store_true', dest='parse_data',
                    help='parse data')
    ap.add_argument('-x', '--xpath', action='store', dest='xpath',
                    help='xpath to parse')
    args = ap.parse_args()

    input_files = args.input

    if args.xpath:
        for input_file in input_files:
            if input_file.startswith('http://'):
                fp = urllib2.urlopen(input_file)
                root = ElementTree.fromstring(fp.read())
                print root.findall(args.xpath)
                fp.close()
            else:
                with open(input_file) as fp:
                    root = ElementTree.fromstring(fp.read())
        return

    if not args.attr and not args.parse_data:
        ap.error('Should specify --attr or open --data.')
    parser = SingleParser(args.element, args.attr, args.parse_data)

    for input_file in input_files:
        if input_file.startswith('http://'):
            fp = urllib2.urlopen(input_file)
            parser.feed(fp.read())
            parser.reset()
            fp.close()
        else:
            with open(input_file) as fp:
                parser.feed(fp.read())
                parser.reset()

    parser.close()


if __name__ == '__main__':
    main()

