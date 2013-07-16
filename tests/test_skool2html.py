# -*- coding: utf-8 -*-
import re
import os
from os.path import basename, isfile, join
import unittest

from skoolkittest import SkoolKitTestCase
import skoolkit
from skoolkit import skool2html, VERSION, SkoolKitError
from skoolkit.skoolhtml import HtmlWriter
from skoolkit.skoolparser import CASE_UPPER, CASE_LOWER

TEST_WRITER_REF = """[Config]
HtmlWriterClass={0}.TestHtmlWriter
""".format(__name__)

TEST_c_REF = """[Config]
HtmlWriterClass={0}.TestHtmlWriter

[Colours]
RED=197,0,0
""".format(__name__)

TEST_P_REF = """[Page:Page1]
Path=page1.html

[Page:Page2]
Path=page2.html
"""

TEST_w_REF = """[Config]
HtmlWriterClass={0}.TestHtmlWriter

[OtherCode:other]
Source={{0}}
Path=other
Index=other.html
Title=Other code
Header=Other code

[Bug:test:Test]
<p>Hello</p>

[Changelog:20120704]
Intro.

Item 1

[Glossary:Term1]
Definition 1.

[Graphics]
<em>This is the graphics page.</em>

[Page:CustomPage1]
Title=Custom page
Path=page.html

[PageContent:CustomPage1]
<b>This is the content of custom page 1.</b>

[Page:CustomPage2]
Path=page2.html
Link=Custom page 2

[PageContent:CustomPage2]
Lo

[GraphicGlitch:SpriteBug]
There is a bug in this sprite.

[Fact:fact:Fact]
This is a trivia item.

[Poke:poke:POKE]
This is a POKE.
""".format(__name__)

TEST_w_SKOOL = """; Routine
c24576 LD HL,$6003

; Data
b$6003 DEFB 123

; Game status buffer entry
g24580 DEFB 0

; A message
t24581 DEFM "!"

; Unused
u24582 DEFB 0
"""

TEST_w_OTHER_SKOOL = """; Other code routine
c32768 RET
"""

TEST_NO_REF = """; Routine
;
; Description.
;
; A Value
; B Another value
c24576 RET

; Data
;
; Some data.
b24577 DEFB 0

; Message
t24578 DEFM "Hello"
"""

TEST_HTML_WRITER_MODULE = """import sys

from skoolkit.skoolhtml import HtmlWriter

class TestHtmlWriter(HtmlWriter):
    def init(self):
        sys.stdout.write('{0}\\n')
"""

TEST_HTML_WRITER_REF = """[Config]
HtmlWriterClass={0}:{1}.TestHtmlWriter
"""

OUTPUT_NO_REF = """Creating directory {0}
Using skool file: test-html-no-ref.skool
Found no ref file for test-html-no-ref.skool
Parsing test-html-no-ref.skool
Creating directory {0}/test-html-no-ref
Copying {1} to {0}/test-html-no-ref/{1}
  Writing disassembly files in test-html-no-ref/asm
  Writing test-html-no-ref/maps/all.html
  Writing test-html-no-ref/maps/routines.html
  Writing test-html-no-ref/maps/data.html
  Writing test-html-no-ref/maps/messages.html
  Writing test-html-no-ref/index.html"""

html_writer = None

def mock_run(*args):
    global run_args
    run_args = args

def mock_write_disassembly(*args):
    global write_disassembly_args
    write_disassembly_args = args

class TestHtmlWriter(HtmlWriter):
    def init(self):
        global html_writer
        html_writer = self
        self.call_dict = {}

    def add_call(self, method_name, args):
        self.call_dict.setdefault(method_name, []).append(args)

    def write_logo_image(self, *args):
        self.add_call('write_logo_image', args)
        return True

    def write_asm_entries(self, *args):
        self.add_call('write_asm_entries', args)

    def write_map(self, *args):
        self.add_call('write_map', args)

    def write_page(self, *args):
        self.add_call('write_page', args)

    def write_gbuffer(self, *args):
        self.add_call('write_gbuffer', args)

    def write_graphics(self, *args):
        self.add_call('write_graphics', args)

    def write_graphic_glitches(self, *args):
        self.add_call('write_graphic_glitches', args)

    def write_changelog(self, *args):
        self.add_call('write_changelog', args)

    def write_bugs(self, *args):
        self.add_call('write_bugs', args)

    def write_facts(self, *args):
        self.add_call('write_facts', args)

    def write_glossary(self, *args):
        self.add_call('write_glossary', args)

    def write_pokes(self, *args):
        self.add_call('write_pokes', args)

    def write_entries(self, *args):
        self.add_call('write_entries', args)

    def write_index(self, *args):
        self.add_call('write_index', args)

class MockImageWriter:
    def __init__(self, palette, options):
        global mock_image_writer
        self.palette = palette
        self.options = options
        self.default_format = None
        mock_image_writer = self

class MockSkoolParser:
    def __init__(self, *args, **kwargs):
        global mock_skool_parser
        self.skoolfile = args[0]
        self.base = kwargs.get('base')
        self.create_labels = kwargs.get('create_labels')
        self.asm_labels = kwargs.get('asm_labels')
        self.snapshot = None
        self.entries = None
        self.memory_map = []
        mock_skool_parser = self

class Skool2HtmlTest(SkoolKitTestCase):
    def setUp(self):
        global html_writer
        SkoolKitTestCase.setUp(self)
        self.odir = 'html-{0}'.format(os.getpid())
        self.tempdirs.append(self.odir)
        html_writer = None

    def _css_c(self):
        return '-c Paths/StyleSheet={0}'.format(self.write_text_file(suffix='.css'))

    def test_default_option_values(self):
        self.mock(skool2html, 'run', mock_run)
        infiles = ['game1.ref', 'game2.skool']
        skool2html.main(infiles)
        files, options = run_args
        self.assertEqual(files, infiles)
        self.assertTrue(options.verbose)
        self.assertFalse(options.show_timings)
        self.assertEqual(options.config_specs, [])
        self.assertFalse(options.new_images)
        self.assertEqual(options.case, None)
        self.assertEqual(options.base, None)
        self.assertEqual(options.files, 'BbcdGgimoPpty')
        self.assertEqual(options.pages, [])
        self.assertEqual(options.output_dir, None)

    def test_no_arguments(self):
        output, error = self.run_skool2html(catch_exit=2)
        self.assertEqual(len(output), 0)
        self.assertTrue(error.startswith('usage: skool2html.py'))

    def test_invalid_option(self):
        output, error = self.run_skool2html('-X', catch_exit=2)
        self.assertEqual(len(output), 0)
        self.assertTrue(error.startswith('usage: skool2html.py'))

    def test_no_ref(self):
        skoolfile = self.write_text_file(TEST_NO_REF, 'test-html-no-ref.skool')
        cssfile = self.write_text_file(suffix='.css')
        output, error = self.run_skool2html('-c Paths/StyleSheet={0} -d {1} {2}'.format(cssfile, self.odir, skoolfile))
        self.assertEqual(len(error), 0)
        self.assert_output_equal(output, OUTPUT_NO_REF.format(self.odir, cssfile).split('\n'), True)

    def test_nonexistent_skool_file(self):
        skoolfile = 'xyz.skool'
        try:
            self.run_skool2html('-d {0} {1}'.format(self.odir, skoolfile))
            self.fail()
        except SkoolKitError as e:
            self.assertEqual(e.args[0], '{0}: file not found'.format(skoolfile))

    def test_nonexistent_ref_file(self):
        reffile = 'zyx.ref'
        try:
            self.run_skool2html('-d {0} {1}'.format(self.odir, reffile))
            self.fail()
        except SkoolKitError as e:
            self.assertEqual(e.args[0], '{0}: file not found'.format(reffile))

    def test_nonexistent_css_file(self):
        cssfile = 'abc.css'
        skoolfile = self.write_text_file(suffix='.skool')
        try:
            self.run_skool2html('-c Paths/StyleSheet={0} -w "" -d {1} {2}'.format(cssfile, self.odir, skoolfile))
            self.fail()
        except SkoolKitError as e:
            self.assertEqual(e.args[0], '{0}: file not found'.format(cssfile))

    def test_nonexistent_js_file(self):
        jsfile = 'cba.js'
        skoolfile = self.write_text_file(suffix='.skool')
        ref = '\n'.join((
            '[Page:P1]',
            'Path=p1.html',
            'JavaScript={}'.format(jsfile)
        ))
        self.write_text_file(ref, '{}.ref'.format(skoolfile[:-6]))
        with self.assertRaises(SkoolKitError) as cm:
            self.run_skool2html('{0} -w P -d {1} {2}'.format(self._css_c(), self.odir, skoolfile))
        self.assertEqual(cm.exception.args[0], '{0}: file not found'.format(jsfile))

    def test_invalid_page_id(self):
        page_id = 'NonexistentPage'
        skoolfile = self.write_text_file(suffix='.skool')
        try:
            self.run_skool2html('-d {0} -w P -P {1} {2}'.format(self.odir, page_id, skoolfile))
            self.fail()
        except SkoolKitError as e:
            self.assertEqual(e.args[0], 'Invalid page ID: {0}'.format(page_id))

    def test_default_ref_file(self):
        skoolfile = self.write_text_file("; Routine\nc24576 RET", suffix='.skool')
        game_dir = 'default-ref-file-test-{0}'.format(os.getpid())
        reffile = self.write_text_file("[Config]\nGameDir={0}".format(game_dir), '{0}.ref'.format(skoolfile[:-6]))
        output, error = self.run_skool2html('{0} -d {1} {2}'.format(self._css_c(), self.odir, skoolfile))
        self.assertEqual(len(error), 0)
        self.assertEqual(output[2], 'Using ref file: {0}'.format(reffile))
        self.assertEqual(output[4], 'Creating directory {0}/{1}'.format(self.odir, game_dir))

    def test_multiple_ref_files(self):
        skoolfile = self.write_text_file("; Routine\nc30000 RET", suffix='.skool')
        reffile = self.write_text_file("[Config]\nSkoolFile={0}".format(skoolfile), suffix='.ref')
        prefix = reffile[:-4]
        code_path = "disasm"
        reffile2 = self.write_text_file("[Paths]\nCodePath={0}".format(code_path), '{0}-2.ref'.format(prefix))
        output, error = self.run_skool2html('{0} -d {1} {2}'.format(self._css_c(), self.odir, reffile))
        self.assertEqual(len(error), 0)
        self.assertEqual(output[2], 'Using ref files: {0}, {1}'.format(reffile, reffile2))
        self.assertEqual(output[6], '  Writing disassembly files in {0}/{1}'.format(basename(prefix), code_path))

    def test_skool_from_stdin(self):
        self.write_stdin('; Routine\nc30000 RET')
        game_dir = 'program'
        output, error = self.run_skool2html('{0} -d {1} -'.format(self._css_c(), self.odir))
        self.assertEqual(len(error), 0)
        self.assertEqual(output[1], 'Using skool file: -')
        self.assertEqual(output[2], 'Found no ref file for -')
        self.assertEqual(output[3], 'Parsing standard input')
        self.assertEqual(output[4], 'Creating directory {0}/{1}'.format(self.odir, game_dir))
        self.assertTrue(isfile(join(self.odir, game_dir, 'asm', '30000.html')))

    def test_output_dir_with_trailing_separator(self):
        skoolfile = self.write_text_file("; Routine\nc49152 RET", suffix='.skool')
        output, error = self.run_skool2html('{0} -d {1}/ {2}'.format(self._css_c(), self.odir, skoolfile))
        self.assertEqual(len(error), 0)
        self.assertEqual(output[0], 'Creating directory {0}'.format(self.odir))

    def test_no_output_dir(self):
        skoolfile = self.write_text_file("; Routine\nc49152 RET", suffix='.skool')
        name = basename(skoolfile[:-6])
        self.tempdirs.append(name)
        output, error = self.run_skool2html('{0} {1}'.format(self._css_c(), skoolfile))
        self.assertEqual(len(error), 0)
        self.assertEqual(output[3], 'Creating directory {0}'.format(name))

    def test_html_writer_class(self):
        module_dir = self.make_directory()
        module_path = os.path.join(module_dir, 'testmod.py')
        message = 'Initialising TestHtmlWriter'
        module = self.write_text_file(TEST_HTML_WRITER_MODULE.format(message), path=module_path)
        module_name = basename(module)[:-3]
        reffile = self.write_text_file(TEST_HTML_WRITER_REF.format(module_dir, module_name), suffix='.ref')
        name = reffile[:-4]
        self.write_text_file('', '{0}.skool'.format(name))
        output, error = self.run_skool2html('{0} -d {1} {2}'.format(self._css_c(), self.odir, reffile))
        self.assertEqual(error, '')
        self.assertEqual(output[4], message)

    def test_file_identification(self):
        # Test that a file named *.ref is treated as a ref file
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file(path='{0}.skool'.format(reffile[:-4]))
        output, error = self.run_skool2html('{0} -d {1} {2}'.format(self._css_c(), self.odir, reffile))
        self.assertEqual(error, '')
        self.assertTrue('write_index' in html_writer.call_dict)

        # Test that a file not named *.ref is treated as a skool file
        for suffix in ('.skool', '.sks', '.kit', ''):
            skoolfile = self.write_text_file("; Data\nb40000 DEFB 0", suffix=suffix)
            game_dir = skoolfile[:-len(suffix)] if suffix else skoolfile
            output, error = self.run_skool2html('{0} -d {1} {2}'.format(self._css_c(), self.odir, skoolfile))
            self.assertEqual(error, '')
            self.assertEqual(output[0], 'Using skool file: {0}'.format(skoolfile))
            self.assertTrue(isfile(join(self.odir, game_dir, 'asm', '40000.html')))

    def test_search_dirs(self):
        self.mock(skool2html, 'write_disassembly', mock_write_disassembly)
        subdir = self.make_directory()
        skool = '; Routine\nc30000 RET'
        skoolfile = self.write_text_file(skool, os.path.join(subdir, 'test-{}.skool'.format(os.getpid())))
        game = 'Test{}'.format(os.getpid())
        ref = '[Game]\nGame={}'.format(game)
        reffile = self.write_text_file(ref, '{}.ref'.format(skoolfile[:-6]))

        # Test that a ref file in the same directory as the skool file is found
        output, error = self.run_skool2html(skoolfile)
        self.assertEqual(error, '')
        html_writer = write_disassembly_args[0]
        self.assertEqual(html_writer.game, game)

        # Test that a skool file in the same directory as the ref file is found
        output, error = self.run_skool2html(reffile)
        self.assertEqual(error, '')
        html_writer = write_disassembly_args[0]
        self.assertEqual(len(html_writer.entries), 1)
        self.assertTrue(30000 in html_writer.entries)

    def test_colour_parsing(self):
        self.mock(skool2html, 'write_disassembly', mock_write_disassembly)
        self.mock(skool2html, 'ImageWriter', MockImageWriter)

        # Valid colours
        exp_colours = (
            ('RED', '#C40000', (196, 0, 0)),
            ('WHITE', '#cde', (204, 221, 238)),
            ('YELLOW', '198,197,0', (198, 197, 0))
        )
        colours = ['[Colours]']
        colours.extend(['{}={}'.format(name, spec) for name, spec, rgb in exp_colours])
        reffile = self.write_text_file('\n'.join(colours), suffix='.ref')
        self.write_text_file(path='{0}.skool'.format(reffile[:-4]))
        output, error = self.run_skool2html(reffile)
        self.assertEqual(error, '')
        for name, spec, rgb in exp_colours:
            self.assertEqual(mock_image_writer.palette[name], rgb)

        # Invalid colours
        bad_colours = (
            ('BLACK', ''),
            ('CYAN', '#)0C6C5'),
            ('MAGENTA', '!98,0,198')
        )
        for name, spec in bad_colours:
            colours = ['[Colours]', '{}={}'.format(name, spec)]
            reffile = self.write_text_file('\n'.join(colours), suffix='.ref')
            self.write_text_file(path='{0}.skool'.format(reffile[:-4]))
            with self.assertRaises(SkoolKitError) as cm:
                self.run_skool2html(reffile)
            self.assertEqual(cm.exception.args[0], 'Invalid colour spec: {}={}'.format(name, spec))

    def test_option_a(self):
        self.mock(skool2html, 'write_disassembly', mock_write_disassembly)
        self.mock(skool2html, 'SkoolParser', MockSkoolParser)
        skoolfile = self.write_text_file(suffix='.skool')
        for option in ('-a', '--asm-labels'):
            output, error = self.run_skool2html('{} {}'.format(option, skoolfile))
            self.assertEqual(error, '')
            self.assertIs(mock_skool_parser.create_labels, False)
            self.assertIs(mock_skool_parser.asm_labels, True)

    def test_option_C(self):
        self.mock(skool2html, 'write_disassembly', mock_write_disassembly)
        self.mock(skool2html, 'SkoolParser', MockSkoolParser)
        skoolfile = self.write_text_file(suffix='.skool')
        for option in ('-C', '--create-labels'):
            output, error = self.run_skool2html('{} {}'.format(option, skoolfile))
            self.assertEqual(error, '')
            self.assertIs(mock_skool_parser.create_labels, True)

    def test_option_P(self):
        self.mock(skool2html, 'write_disassembly', mock_write_disassembly)
        reffile = self.write_text_file(TEST_P_REF, suffix='.ref')
        self.write_text_file(path='{}.skool'.format(reffile[:-4]))
        for option in ('-P', '--pages'):
            for pages in ('Page1', 'Page1,Page2'):
                output, error = self.run_skool2html('{} {} {}'.format(option, pages, reffile))
                self.assertEqual(error, '')
                self.assertEqual(write_disassembly_args[4], pages.split(','))
        output, error = self.run_skool2html(reffile)
        self.assertEqual(write_disassembly_args[4], ['Page1', 'Page2'])

    def test_option_w(self):
        options = [
            ('d', 'write_asm_entries', [()]),
            ('m', 'write_map', [({'Name': 'MemoryMap', 'PageByteColumns': '1'},),
                                ({'EntryTypes': 'c', 'Name': 'RoutinesMap'},),
                                ({'EntryTypes': 'bw', 'Name': 'DataMap', 'PageByteColumns': '1'},),
                                ({'EntryTypes': 't', 'Name': 'MessagesMap'},),
                                ({'Name': 'UnusedMap', 'EntryTypes': 'uz', 'PageByteColumns': '1'},)]),
            ('P', 'write_page', [('CustomPage1',), ('CustomPage2',)]),
            ('G', 'write_gbuffer', [()]),
            ('g', 'write_graphics', [()]),
            ('B', 'write_graphic_glitches', [()]),
            ('c', 'write_changelog', [()]),
            ('b', 'write_bugs', [()]),
            ('t', 'write_facts', [()]),
            ('y', 'write_glossary', [()]),
            ('p', 'write_pokes', [()]),
            ('o', 'write_map', [({'Path': 'other.html', 'Title': 'Other code', 'AsmPath': 'other'},)]),
            ('o', 'write_entries', [('other', 'other.html', 'Other code')]),
            ('i', 'write_index', [()])
        ]
        other_skoolfile = self.write_text_file(TEST_w_OTHER_SKOOL, suffix='.skool')
        reffile = self.write_text_file(TEST_w_REF.format(other_skoolfile), suffix='.ref')
        self.write_text_file(TEST_w_SKOOL, '{0}.skool'.format(reffile[:-4]))
        for write_option in ('-w', '--write'):
            for file_ids, method_name, exp_arg_list in options:
                output, error = self.run_skool2html('{0} -d {1} {2} {3} {4}'.format(self._css_c(), self.odir, write_option, file_ids, reffile))
                self.assertEqual(error, '')
                self.assertTrue(method_name in html_writer.call_dict, '{0} was not called'.format(method_name))
                arg_list = html_writer.call_dict[method_name]
                self.assertEqual(arg_list, exp_arg_list, '{0}: {1} != {2}'.format(method_name, arg_list, exp_arg_list))

    def test_option_V(self):
        for option in ('-V', '--version'):
            output, error = self.run_skool2html(option, err_lines=True, catch_exit=0)
            self.assertEqual(len(output), 0)
            self.assertEqual(len(error), 1)
            self.assertEqual(error[0], 'SkoolKit {}'.format(VERSION))

    def test_option_p(self):
        for option in ('-p', '--package-dir'):
            output, error = self.run_skool2html(option, catch_exit=0)
            self.assertEqual(error, '')
            self.assertEqual(len(output), 1)
            self.assertEqual(output[0], os.path.dirname(skoolkit.__file__))

    def test_option_q(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        name = reffile[:-4]
        self.write_text_file('', '{0}.skool'.format(name))
        logo_method = 'write_logo_image'
        for option in ('-q', '--quiet'):
            output, error = self.run_skool2html('{0} {1} -d {2} -w i {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertTrue(logo_method in html_writer.call_dict, '{0} was not called'.format(logo_method))
            self.assertEqual(html_writer.call_dict[logo_method], [('{0}/{1}'.format(self.odir, basename(name)),)])
            self.assertEqual(len(output), 0)

    def test_option_t(self):
        skoolfile = self.write_text_file(suffix='.skool')
        pattern = 'Done \([0-9]+\.[0-9][0-9]s\)'
        for option in ('-t', '--time'):
            output, error = self.run_skool2html('{0} {1} -w i -d {2} {3}'.format(self._css_c(), option, self.odir, skoolfile))
            self.assertEqual(error, '')
            done = output[-1]
            search = re.search(pattern, done)
            self.assertTrue(search is not None, '"{0}" is not of the form "{1}"'.format(done, pattern))

    def test_option_c(self):
        reffile = self.write_text_file(TEST_c_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        sl_spec = 'GARBAGE'
        for option in ('-c', '--config'):
            for section_name, param_name, value in (
                ('Colours', 'RED', '255,0,0'),
                ('Config', 'GameDir', 'test-c'),
                ('ImageWriter', 'DefaultFormat', 'gif')
            ):
                output, error = self.run_skool2html('{0} {1} {2}/{3}={4} -w i -d {5} {6}'.format(self._css_c(), option, section_name, param_name, value, self.odir, reffile))
                self.assertEqual(error, '')
                section = html_writer.ref_parser.get_dictionary(section_name)
                self.assertEqual(section[param_name], value, '{0}/{1}!={2}'.format(section_name, param_name, value))
            try:
                self.run_skool2html('{0} {1} -w i -d {2} {3}'.format(option, sl_spec, self.odir, reffile))
                self.fail()
            except SkoolKitError as e:
                self.assertEqual(e.args[0], 'Malformed SectionName/Line spec: {0}'.format(sl_spec))

    def test_option_T(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        skoolfile = self.write_text_file(path='{0}.skool'.format(reffile[:-4]))
        cssfile1 = self.write_text_file(suffix='.css')
        cssfile2 = self.write_text_file(suffix='.css')
        theme = 'blue'
        cssfile3 = self.write_text_file(path='{0}-{1}.css'.format(cssfile2[:-4], theme))
        stylesheet = 'Paths/StyleSheet={0};{1}'.format(cssfile1, cssfile2)
        for option in ('-T', '--theme'):
            output, error = self.run_skool2html('-d {0} -c {1} {2} {3} {4}'.format(self.odir, stylesheet, option, theme, reffile))
            self.assertEqual(error, '')
            self.assertEqual(html_writer.paths['StyleSheet'], '{0};{1}'.format(cssfile1, cssfile3))

    def test_option_o(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        for option in ('-o', '--rebuild-images'):
            output, error = self.run_skool2html('{0} {1} -w "" -d {2} {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertTrue(html_writer.file_info.replace_images)

    def test_option_l(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        for option in ('-l', '--lower'):
            output, error = self.run_skool2html('{0} {1} -w "" -d {2} {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertEqual(html_writer.case, CASE_LOWER)

    def test_option_u(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        for option in ('-u', '--upper'):
            output, error = self.run_skool2html('{0} {1} -w "" -d {2} {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertEqual(html_writer.case, CASE_UPPER)

    def test_option_D(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        for option in ('-D', '--decimal'):
            output, error = self.run_skool2html('{0} {1} -w "" -d {2} {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertTrue(html_writer.parser.mode.decimal)

    def test_option_H(self):
        reffile = self.write_text_file(TEST_WRITER_REF, suffix='.ref')
        self.write_text_file('', '{0}.skool'.format(reffile[:-4]))
        for option in ('-H', '--hex'):
            output, error = self.run_skool2html('{0} {1} -w "" -d {2} {3}'.format(self._css_c(), option, self.odir, reffile))
            self.assertEqual(error, '')
            self.assertTrue(html_writer.parser.mode.hexadecimal)

if __name__ == '__main__':
    unittest.main()
