Changelog
=========

6.2rc
-----
* Added the ``--reg`` option to :ref:`bin2sna.py` (for setting the value of a
  register)
* Added the ``--state`` option to :ref:`bin2sna.py` (for setting the value of a
  hardware state attribute)
* :ref:`sna2img.py` can now read a binary (raw memory) file when the
  ``--binary`` option is used, and with a specific origin address when the
  ``--org`` option is used
* Added the ``Includes`` parameter to the :ref:`memoryMap` section (for
  specifying addresses of entries to include on the memory map page in addition
  to those specified by the ``EntryTypes`` parameter)
* The :ref:`SkoolKit command <commands>` options now accept a hexadecimal
  integer prefixed by '0x' wherever an address, byte, length, step, offset or
  range limit value is expected
* Added the ``hex`` parameter to the :ref:`N` macro (for rendering a value in
  hexadecimal format unless the ``--decimal`` option is used with
  :ref:`skool2asm.py` or :ref:`skool2html.py`)
* Added the ``--show-config`` option to :ref:`skool2asm.py`,
  :ref:`skool2html.py` and :ref:`sna2skool.py` (for showing configuration
  parameter values)
* Added support for substituting labels in instruction operands and
  DEFB/DEFM/DEFW statements that contain multiple addresses (e.g.
  ``LD BC,30000+40000%256``), or where the address is the second or later term
  in an expression (e.g. ``DEFW 1+30000``)
* The :ref:`keep` directive can now specify the values to keep, and is applied
  to instructions that have been replaced by an :ref:`isub`, :ref:`ssub` or
  :ref:`rsub` directive
* The :ref:`nolabel` directive is now processed in HTML mode

6.1 (2017-09-03)
----------------
* Added support for converting the base of every numerical term in an
  instruction operand or DEFB/DEFM/DEFS/DEFW statement that contains two or
  more (e.g. ``LD A,32768/256`` to ``LD A,$8000/$100``)
* Added support for assembling instructions and DEFB/DEFM/DEFS/DEFW statements
  whose operands contain arithmetic expressions (e.g. ``DEFM "H","i"+$80``)
* Added support to :ref:`skool2asm.py <skool2asm-conf>`,
  :ref:`skool2html.py <skool2html-conf>` and
  :ref:`sna2skool.py <sna2skool-conf>` for reading configuration from a file
  named `skoolkit.ini`, if present
* Added the ``--ini`` option to :ref:`skool2asm.py`, :ref:`skool2html.py` and
  :ref:`sna2skool.py` (for setting the value of a configuration parameter)
* :ref:`sna2img.py` can now read skool files, in either the default mode, or
  ``@bfix`` mode by using the ``--bfix`` option
* Added the ``--move`` option to :ref:`sna2img.py` (for copying the contents of
  a block of RAM to another location)
* Improved how :ref:`skool2asm.py` formats a comment that covers two or more
  instructions: now the comment is aligned to the widest instruction, and even
  blank lines are prefixed by a semicolon
* Improved how the :ref:`R` macro renders the address of an unavailable
  instruction (an instruction outside the range of the current disassembly, or
  in another disassembly) in ASM mode
* Removed the indent from EQU directives in ASM output (for compatibility with
  SjASMPlus)
* Fixed the bug that prevents the expansion of a macro whose numeric parameters
  contain a '<', '>' or '&' character
* Fixed how labels are substituted for addresses in DEFB/DEFM/DEFW statements
* Fixed :ref:`skool2asm.py` so that it processes ``@ssub`` directives when
  ``--fixes 3`` is specified
* Fixed the styling of entry descriptions for 't' blocks on a memory map page

6.0 (2017-05-06)
----------------
* Dropped support for Python 2.7 and 3.3
* Added the ``--expand`` option to :ref:`sna2img.py` (for expanding a
  :ref:`FONT`, :ref:`SCR`, :ref:`UDG` or :ref:`UDGARRAY` macro)
* Added the ``--basic`` option to :ref:`tapinfo.py` (for listing the BASIC
  program in a tape block)
* Added the ``--find-tile`` option to :ref:`snapinfo.py` (for searching for the
  graphic data of a tile currently on screen)
* Added the ``--word`` option to :ref:`snapinfo.py` (for showing the words at a
  range of addresses)
* Added support to the ``--find`` option of :ref:`snapinfo.py` for specifying a
  range of distances between byte values (e.g. ``--find 1,2,3-1-10``)
* The ``--peek`` option of :ref:`snapinfo.py` now shows UDGs and BASIC tokens
* Added support for replacement fields (such as ``{base}`` and ``{case}``) in
  the ``expr`` parameter of the :ref:`IF` macro and the ``key`` parameter of
  the :ref:`MAP` macro
* Added support for parsing a :ref:`box page <boxpages>` entry section as a
  sequence of multi-line list items prefixed by '-' (with
  ``SectionType=BulletPoints``)
* The following ref file components may now contain skool macros: the
  ``anchor`` and ``title`` of a :ref:`box page <boxpages>` entry section name;
  every parameter in the :ref:`ref-Game`, :ref:`memoryMap`, :ref:`page`,
  :ref:`pageHeaders`, :ref:`paths` and :ref:`titles` sections
* The :ref:`replace` directive now acts on ref file section names as well as
  their contents
* The :ref:`EVAL` macro now renders hexadecimal values in lower case when the
  ``--lower`` option of :ref:`skool2asm.py` or :ref:`skool2html.py` is used
* Added the :ref:`VERSION` macro (which expands to the version of SkoolKit)
* Fixed how an image is cropped when the crop rectangle is very narrow
* Fixed how a masked image with flashing cells is built
* Fixed how :ref:`sna2skool.py` handles a snapshot that contains a dangling
  IX/IY prefix (DD/FD) when generating a control file
* Fixed the bug that prevents the expansion of skool macros in a page's link
  text on the disassembly home page

Older versions
--------------
.. toctree::
   :maxdepth: 1

   changelog5
   changelog4
   changelog3
   changelog2
   changelog1
